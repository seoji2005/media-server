"""App-owned copies and transactional watch history; never mutate source files."""
from __future__ import annotations

from contextlib import contextmanager
from collections import OrderedDict
from dataclasses import dataclass
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import sqlite3
import subprocess
import threading
import uuid


class MediaError(Exception):
    def __init__(self, code: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(code)


ID = re.compile(r"^[0-9a-f]{32}$")
CHUNK = 1024 * 1024
RESERVE = 32 * 1024 * 1024
INTEGRITY_CACHE_BYTES = 8 * 1024 * 1024
INTEGRITY_CACHE_ENTRIES = 16


def file_signature(stream) -> tuple:
    """Windows ctime is creation time; ask the open handle for native ChangeTime."""
    info = os.fstat(stream.fileno())
    if not stat.S_ISREG(info.st_mode):
        raise MediaError("unsafe_storage", 503)
    change_time = info.st_ctime_ns
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        import msvcrt

        class FileBasicInfo(ctypes.Structure):
            _fields_ = [(name, ctypes.c_longlong) for name in
                        ("CreationTime", "LastAccessTime", "LastWriteTime", "ChangeTime")] + [
                            ("FileAttributes", wintypes.DWORD)]

        get_info = ctypes.WinDLL("kernel32", use_last_error=True).GetFileInformationByHandleEx
        get_info.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        get_info.restype = wintypes.BOOL
        native = FileBasicInfo()
        if not get_info(msvcrt.get_osfhandle(stream.fileno()), 0, ctypes.byref(native), ctypes.sizeof(native)):
            raise MediaError("storage_unavailable", 503)
        change_time = native.ChangeTime
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, change_time)


@dataclass(frozen=True)
class VerifiedSnapshot:
    signature: tuple
    sha256: str
    block_size: int
    digests: bytes


class VerifiedContent:
    """One open descriptor, with every emitted block tied to the verified full SHA."""
    def __init__(self, store, row, path, stream, snapshot):
        self.store, self.row, self.path = store, row, path
        self.stream, self.snapshot = stream, snapshot

    def close(self):
        self.stream.close()

    def read_range(self, start: int, end: int):
        block_size = self.snapshot.block_size
        try:
            for index in range(start // block_size, end // block_size + 1):
                self.store._check_signature(self.row, self.path, self.stream, self.snapshot.signature)
                offset = index * block_size
                self.stream.seek(offset)
                expected_size = min(block_size, self.row["size"] - offset)
                block = self.stream.read(expected_size)
                self.store._check_signature(self.row, self.path, self.stream, self.snapshot.signature)
                expected = self.snapshot.digests[index * 32:(index + 1) * 32]
                if len(block) != expected_size or hashlib.sha256(block).digest() != expected:
                    self.store._changed(self.row)
                yield block[max(start - offset, 0):min(end - offset + 1, len(block))]
        finally:
            self.close()


def default_data_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "MediaClarity"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "media-clarity"


def no_symlink(path: Path) -> None:
    """Reject existing symlink/reparse components before opening managed paths."""
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise MediaError("unsafe_storage", 503)


def title_from_name(name: str) -> str:
    # Only the basename is user-visible; never retain a client/server source path.
    clean = name.replace("\\", "/").split("/")[-1]
    clean = "".join(c for c in clean if c.isprintable() and c not in "\u202a\u202b\u202d\u202e\u202c\u2066\u2067\u2068\u2069")
    return (Path(clean).stem.strip() or "제목 없는 영상")[:180]


def safe_io(exc: OSError) -> MediaError:
    return MediaError("insufficient_space" if exc.errno == errno.ENOSPC else "storage_unavailable", 507 if exc.errno == errno.ENOSPC else 503)


def run_media(args: list[str], timeout: int, max_bytes: int) -> bytes:
    """Capture no unbounded/private decoder diagnostics, even on malformed media."""
    try:
        process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        data = bytearray()
        def read_bounded():
            while chunk := process.stdout.read(min(4096, max_bytes + 1 - len(data))):
                data.extend(chunk)
                if len(data) > max_bytes:
                    process.kill()
                    return
        reader = threading.Thread(target=read_bounded, daemon=True)
        reader.start()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            reader.join()
            process.stdout.close()
            raise MediaError("media_timeout", 422) from None
        reader.join()
        process.stdout.close()
        if process.returncode or len(data) > max_bytes:
            raise MediaError("invalid_media", 422)
        return bytes(data)
    except FileNotFoundError:
        raise MediaError("ffmpeg_unavailable", 503) from None


class Store:
    def __init__(self, root: Path):
        self.root = root.absolute()
        self.lock_file = None
        self.recovered = 0
        self.import_lock = threading.Lock()
        self.integrity_lock = threading.RLock()
        self.integrity_cache = OrderedDict()
        self.integrity_failures = set()

    def start(self) -> None:
        self._clear_integrity()
        no_symlink(self.root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        for name in ("staging", "files", "recovery"):
            path = self.root / name
            no_symlink(path)
            path.mkdir(exist_ok=True, mode=0o700)
        lock = self.root / "instance.lock"
        no_symlink(lock)
        self.lock_file = lock.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                self.lock_file.seek(0)
                if not self.lock_file.read(1):
                    self.lock_file.write(b"0")
                    self.lock_file.flush()
                self.lock_file.seek(0)
                msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock_file.close()
            self.lock_file = None
            raise MediaError("already_running", 503) from None
        try:
            self._init_db()
            self._recover()
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        self._clear_integrity()
        if self.lock_file is not None:
            self.lock_file.close()
            self.lock_file = None

    def _clear_integrity(self):
        with self.integrity_lock:
            self.integrity_cache.clear()
            self.integrity_failures.clear()

    def _changed(self, row):
        with self.integrity_lock:
            self.integrity_cache.pop(row["file_id"], None)
            self.integrity_failures.add(row["file_id"])
        raise MediaError("managed_file_changed", 409)

    def _check_signature(self, row, path, stream, expected):
        no_symlink(path)
        try:
            current = file_signature(stream)
            named = path.stat()
        except FileNotFoundError:
            self._changed(row)
        # The response keeps this descriptor: a path replacement must not silently
        # change which file is checked versus which file supplies response bytes.
        if current != expected or (named.st_dev, named.st_ino, named.st_size, named.st_mtime_ns) != expected[:4]:
            self._changed(row)

    def _scan_content(self, row, path, stream, signature):
        # Adaptive blocks bound each file's digest table to 2 MiB, without making
        # a very large video ineligible for Range cache reuse.
        block_size = max(CHUNK, (row["size"] + 65535) // 65536)
        digest, blocks = hashlib.sha256(), bytearray()
        stream.seek(0)
        remaining = row["size"]
        while remaining:
            block = stream.read(min(block_size, remaining))
            if not block:
                self._changed(row)
            digest.update(block)
            blocks.extend(hashlib.sha256(block).digest())
            remaining -= len(block)
        self._check_signature(row, path, stream, signature)
        if digest.hexdigest() != row["sha256"]:
            self._changed(row)
        return VerifiedSnapshot(signature, row["sha256"], block_size, bytes(blocks))

    def open_verified(self, row) -> VerifiedContent:
        """Hash on first use/change/eviction, never eagerly hash the library."""
        path = self.file_path(row)
        stream = path.open("rb")
        try:
            with self.integrity_lock:
                signature = file_signature(stream)
                if signature[2] != row["size"]:
                    self._changed(row)
                self._check_signature(row, path, stream, signature)
                snapshot = self.integrity_cache.get(row["file_id"])
                if snapshot is None or snapshot.signature != signature or snapshot.sha256 != row["sha256"]:
                    self.integrity_cache.pop(row["file_id"], None)
                    snapshot = self._scan_content(row, path, stream, signature)
                    self.integrity_cache[row["file_id"]] = snapshot
                    self.integrity_failures.discard(row["file_id"])
                self.integrity_cache.move_to_end(row["file_id"])
                while len(self.integrity_cache) > INTEGRITY_CACHE_ENTRIES or sum(len(s.digests) for s in self.integrity_cache.values()) > INTEGRITY_CACHE_BYTES:
                    self.integrity_cache.popitem(last=False)
            return VerifiedContent(self, row, path, stream, snapshot)
        except BaseException:
            stream.close()
            raise

    @contextmanager
    def db(self):
        for suffix in ("", "-wal", "-shm", "-journal"):
            no_symlink(self.root / ("library.sqlite3" + suffix))
        connection = sqlite3.connect(self.root / "library.sqlite3", timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA synchronous = FULL")
        try:
            yield connection
        finally:
            connection.close()

    def _init_db(self):
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE,
                    size INTEGER NOT NULL, extension TEXT NOT NULL,
                    mime TEXT NOT NULL, duration REAL NOT NULL,
                    width INTEGER NOT NULL, height INTEGER NOT NULL,
                    thumbnail INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY, file_id TEXT NOT NULL UNIQUE REFERENCES files(id),
                    title TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    position REAL NOT NULL DEFAULT 0,
                    watched_at TEXT
                );
                CREATE TABLE IF NOT EXISTS renditions (
                    id TEXT PRIMARY KEY, item_id TEXT NOT NULL UNIQUE REFERENCES items(id),
                    input_sha TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL,
                    extension TEXT NOT NULL, mime TEXT NOT NULL, kind TEXT NOT NULL, duration REAL
                );
            """)
            columns = {r['name'] for r in db.execute('PRAGMA table_info(files)')}
            if 'preparation' not in columns:
                db.execute("ALTER TABLE files ADD COLUMN preparation TEXT NOT NULL DEFAULT 'unchecked'")
            if 'preparation_error' not in columns:
                db.execute('ALTER TABLE files ADD COLUMN preparation_error TEXT')
            if 'duration' not in {r['name'] for r in db.execute('PRAGMA table_info(renditions)')}:
                db.execute('ALTER TABLE renditions ADD COLUMN duration REAL')
            db.commit()

    def _recover(self):
        # The instance lock excludes another local app process, not another Work.
        # Never discard potentially complete copies after an interrupted transaction.
        with self.db() as db:
            known = {r[0] for r in db.execute("SELECT id FROM files UNION SELECT id FROM renditions")}
        for directory in (self.root / "staging", self.root / "files"):
            for path in directory.iterdir():
                no_symlink(path)
                orphan = (directory.name == "staging" and re.fullmatch(r"[0-9a-f]{32}\.part", path.name)) or (directory.name == "files" and ID.fullmatch(path.name) and path.name not in known)
                if orphan:
                    destination = self.root / "recovery" / uuid.uuid4().hex
                    path.rename(destination)
        self.recovered = len(list((self.root / "recovery").iterdir()))

    def diagnostics(self):
        return {"ffprobe": shutil.which("ffprobe") is not None,
                "ffmpeg": shutil.which("ffmpeg") is not None,
                "recovered_copies": self.recovered}

    def ensure_space(self, amount: int):
        if shutil.disk_usage(self.root).free < amount + RESERVE:
            raise MediaError("insufficient_space", 507)

    def new_stage(self) -> tuple[Path, object]:
        no_symlink(self.root / "staging")
        self.ensure_space(CHUNK)
        path = self.root / "staging" / (uuid.uuid4().hex + ".part")
        return path, path.open("xb")

    def remove_stage(self, path: Path):
        no_symlink(path)
        path.unlink(missing_ok=True)

    def probe(self, path: Path) -> dict:
        with path.open("rb") as stream:
            magic = stream.read(12)
        if not (magic[4:8] == b"ftyp" or magic[:4] == b"\x1aE\xdf\xa3"):
            raise MediaError("unsupported_container", 422)
        raw = run_media([
            "ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
            "-format_whitelist", "mov,matroska,webm", "-show_entries",
            "format=format_name,duration,start_time:stream=codec_type,codec_name,width,height,pix_fmt,start_time,duration:stream_disposition=attached_pic:stream_tags=DURATION",
            "-of", "json", str(path)], 25, 128 * 1024)
        try:
            result = json.loads(raw)
            streams = result["streams"]
            video = [s for s in streams if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")]
            audio = [s for s in streams if s.get("codec_type") == "audio"]
            if len(video) != 1:
                raise ValueError
            track = video[0]
            duration = float(result["format"]["duration"])
            start = float(result['format'].get('start_time',0))
            width, height = int(track["width"]), int(track["height"])
            if not math.isfinite(start) or not math.isfinite(duration) or duration <= 0 or not (0 < width <= 8192 and 0 < height <= 8192):
                raise ValueError
        except (ValueError, KeyError, TypeError, IndexError):
            raise MediaError("invalid_media", 422) from None
        is_mp4 = magic[4:8] == b"ftyp"
        from .renditions import playback_plan, selected_duration
        preparation = playback_plan(track, audio, is_mp4)
        extension = 'mp4' if is_mp4 else 'mkv' if track.get('codec_name') == 'h264' else 'webm'
        return {"duration": duration, "width": width, "height": height,
                "extension": extension, "mime": {'mp4':'video/mp4', 'mkv':'video/x-matroska', 'webm':'video/webm'}[extension],
                "preparation": preparation, 'selected_duration':selected_duration(track,audio,start)}

    def finish_import(self, stage: Path, digest: str, size: int, title: str) -> dict:
        if size <= 0:
            raise MediaError("empty_media", 422)
        no_symlink(stage)
        # Re-read the persisted staged copy; the ingest hash alone does not verify copy integrity.
        with stage.open("rb") as copied:
            if hashlib.file_digest(copied, "sha256").hexdigest() != digest or stage.stat().st_size != size:
                raise MediaError("copy_changed", 409)
        metadata = self.probe(stage)
        file_id, item_id = uuid.uuid4().hex, uuid.uuid4().hex
        destination = self.root / "files" / file_id
        no_symlink(destination)
        with self.db() as db:
            duplicate = db.execute("SELECT items.id FROM files JOIN items ON files.id=items.file_id WHERE sha256=?", (digest,)).fetchone()
            if duplicate:
                self.open_verified(self._row(duplicate["id"])).close()
                existing = self.item(duplicate["id"])
                if not existing["available"] and existing['unavailable_reason'] != 'rendition_required':
                    raise MediaError(existing["unavailable_reason"], 409)
                return {"duplicate": True, "item": existing}
            # Exclusive fresh directory prevents destination collision/overwrite.
            try:
                destination.mkdir(mode=0o700)
            except FileExistsError:
                raise MediaError("destination_collision", 409) from None
            try:
                target = destination / ("original." + metadata["extension"])
                stage.rename(target)
                thumbnail = False
                try:
                    run_media(["ffmpeg", "-v", "error", "-nostdin", "-protocol_whitelist", "file,pipe",
                               "-format_whitelist", "mov,matroska,webm", "-ss", str(min(metadata["duration"] * .15, 15)),
                               "-i", str(target), "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "4",
                               "-n", str(destination / "thumbnail.jpg")], 30, 1024)
                    thumbnail = (destination / "thumbnail.jpg").is_file()
                except MediaError:
                    (destination / "thumbnail.jpg").unlink(missing_ok=True)
                db.execute("INSERT INTO files (id,sha256,size,extension,mime,duration,width,height,thumbnail,preparation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (file_id, digest, size, metadata["extension"], metadata["mime"], metadata["duration"], metadata["width"], metadata["height"], thumbnail, metadata['preparation']))
                db.execute("INSERT INTO items (id,file_id,title) VALUES (?,?,?)", (item_id, file_id, title))
                db.commit()
            except BaseException:
                db.rollback()
                # Only this invocation's exclusive app-owned destination is rolled back.
                shutil.rmtree(destination)
                raise
        return {"duplicate": False, "item": self.item(item_id)}

    def import_path(self, source: Path, after_chunk=None) -> dict:
        """CLI import with before/after source identity/hash checks; source is read-only."""
        if not self.import_lock.acquire(blocking=False):
            raise MediaError("import_busy", 409)
        stage = None
        try:
            if not source.is_file():
                raise MediaError("source_unavailable", 404)
            stage, output = self.new_stage()
            with output, source.open("rb") as input_file:
                before = os.fstat(input_file.fileno())
                self.ensure_space(before.st_size)
                digest, size = hashlib.sha256(), 0
                while chunk := input_file.read(CHUNK):
                    self.ensure_space(len(chunk))
                    output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                    if after_chunk:
                        after_chunk()
                output.flush()
                os.fsync(output.fileno())
                input_file.seek(0)
                checked = hashlib.file_digest(input_file, "sha256").hexdigest()
                after, path_after = os.fstat(input_file.fileno()), source.stat()
                identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
                if identity(before) != identity(after) or identity(after) != identity(path_after) or checked != digest.hexdigest() or size != before.st_size:
                    raise MediaError("source_changed", 409)
            return self.finish_import(stage, digest.hexdigest(), size, title_from_name(source.name))
        except OSError as exc:
            raise safe_io(exc) from None
        finally:
            try:
                if stage is not None:
                    self.remove_stage(stage)
            finally:
                self.import_lock.release()

    def _row(self, item_id: str):
        if not ID.fullmatch(item_id):
            raise MediaError("item_not_found", 404)
        with self.db() as db:
            row = db.execute("SELECT items.*, files.sha256,files.size,files.extension,files.mime,files.duration,files.width,files.height,files.thumbnail,files.preparation,files.preparation_error FROM items JOIN files ON items.file_id=files.id WHERE items.id=?", (item_id,)).fetchone()
        if row is None:
            raise MediaError("item_not_found", 404)
        return dict(row)

    def file_path(self, row: dict, thumbnail=False) -> Path:
        if not ID.fullmatch(row["file_id"]) or row["extension"] not in {"mp4", "webm", "mkv"}:
            raise MediaError("unsafe_storage", 503)
        path = self.root / "files" / row["file_id"] / ("thumbnail.jpg" if thumbnail else "original." + row["extension"])
        no_symlink(path)
        if not path.is_file():
            raise MediaError("managed_file_missing", 410)
        return path

    def item(self, item_id: str) -> dict:
        row = self._row(item_id)
        unavailable_reason = None
        try:
            if self.file_path(row).stat().st_size != row["size"]:
                self._changed(row)
            playback = self.playback_row(item_id)
            if self.file_path(playback).stat().st_size != playback['size']:
                self._changed(playback)
            if row["file_id"] in self.integrity_failures or playback['file_id'] in self.integrity_failures:
                unavailable_reason = "managed_file_changed"
        except MediaError as exc:
            if exc.code not in {"managed_file_missing", "managed_file_changed", "rendition_required"}:
                raise
            unavailable_reason = exc.code
        return {k: row[k] for k in ("id", "file_id", "title", "created_at", "position", "watched_at", "duration", "size", "width", "height", "sha256", "preparation", "preparation_error")} | {"available": unavailable_reason is None, "unavailable_reason": unavailable_reason, "thumbnail": bool(row["thumbnail"]), "mime": playback['mime'] if unavailable_reason is None else row['mime'], 'duration':playback['duration'] if unavailable_reason is None else row['duration']}

    def playback_row(self, item_id):
        source = self._row(item_id)
        if source['preparation'] == 'original':
            return source
        with self.db() as db:
            ready = db.execute('SELECT * FROM renditions WHERE item_id=?', (item_id,)).fetchone()
        if ready is None:
            raise MediaError('rendition_required', 409)
        if ready['input_sha'] != source['sha256'] or ready['kind'] != source['preparation']:
            raise MediaError('managed_file_changed', 409)
        return source | {k:ready[k] for k in ('sha256','size','extension','mime')} | {'file_id':ready['id'], 'duration':ready['duration'] or source['duration']}

    def list_items(self) -> list[dict]:
        with self.db() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM items ORDER BY created_at DESC, id DESC")]
        return [self.item(item_id) for item_id in ids]

    def save_position(self, item_id: str, position) -> dict:
        row = self._row(item_id)
        try:
            duration = self.playback_row(item_id)['duration']
        except MediaError as exc:
            if exc.code != 'rendition_required':
                raise
            duration = row['duration']  # Existing history can survive pending preparation.
        if type(position) not in (int, float) or not math.isfinite(position) or not 0 <= position <= duration:
            raise MediaError("invalid_position", 422)
        with self.db() as db:
            db.execute("UPDATE items SET position=?, watched_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?", (position, item_id))
            db.commit()
        return {"position": position}
