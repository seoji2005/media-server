"""One local worker, durable stage/cue checkpoints, append-only subtitle versions."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import uuid

from .storage import ID, MediaError, Store, no_symlink
from .subtitles import MAX_SUBTITLE_BYTES, parse_srt, validate_cues, webvtt


def document(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


@contextmanager
def worker_guard(root):
    """A kernel-owned worker lease outlives a server crash and Python GIL stalls."""
    path = root / 'worker.lock'
    no_symlink(path)
    stream = path.open('a+b')
    try:
        try:
            if os.name == 'nt':
                import msvcrt
                stream.seek(0)
                if not stream.read(1):
                    stream.write(b'0')
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise MediaError('processing_worker_active', 409) from None
        yield
    finally:
        stream.close()


class Jobs:
    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.thread = None
        self.process = None
        self.active = None
        self.expected_attempt = None
        self.recovery_pending = False

    def init(self, recover=False):
        with self.store.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS subtitle_jobs (
                    id TEXT PRIMARY KEY, item_id TEXT NOT NULL REFERENCES items(id),
                    input_sha TEXT NOT NULL, state TEXT NOT NULL, stage TEXT NOT NULL DEFAULT 'asr',
                    attempt INTEGER NOT NULL DEFAULT 0, completed INTEGER NOT NULL DEFAULT 0,
                    total INTEGER NOT NULL DEFAULT 0, error TEXT,
                    config_sha TEXT, transcript TEXT, transcript_sha TEXT, translation_sha TEXT, translation TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_subtitle_job ON subtitle_jobs(item_id)
                    WHERE state IN ('queued','running','paused');
                CREATE TABLE IF NOT EXISTS subtitle_tracks (
                    id TEXT PRIMARY KEY, item_id TEXT NOT NULL REFERENCES items(id),
                    input_sha TEXT NOT NULL, job_id TEXT UNIQUE REFERENCES subtitle_jobs(id),
                    source TEXT NOT NULL, cues TEXT NOT NULL, sha256 TEXT NOT NULL, source_srt BLOB,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                );
            ''')
            columns = {r['name'] for r in db.execute('PRAGMA table_info(subtitle_tracks)')}
            if 'source_srt' not in columns:
                db.execute('ALTER TABLE subtitle_tracks ADD COLUMN source_srt BLOB')
            db.commit()
        if recover:
            self.recovery_pending = True
            self.recover()

    def recover(self):
        try:
            with worker_guard(self.store.root), self.store.db() as db:
                db.execute("UPDATE subtitle_jobs SET state='paused',error='processing_interrupted' WHERE state='running'")
                db.commit()
            self.recovery_pending = False
        except MediaError as exc:
            if exc.code != 'processing_worker_active':
                raise
            # Keep original watching available while an orphan releases its GPU.
            self.recovery_pending = True

    def start(self):
        self.init(recover=True)
        self.thread = threading.Thread(target=self._supervise, daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        with self.lock:
            self._terminate()
        if self.thread:
            self.thread.join()
        if self.process:
            self.process.stdin.close()

    def _terminate(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

    def _supervise(self):
        while not self.stop.wait(.25):
            try:
                with self.lock:
                    if self.recovery_pending:
                        self.recover()
                        if self.recovery_pending:
                            continue
                    if self.process:
                        code = self.process.poll()
                        if code is None:
                            continue
                        with self.store.db() as db:
                            db.execute("UPDATE subtitle_jobs SET state='failed',error='worker_stopped' WHERE id=? AND state='running'", (self.active,))
                            db.commit()
                        self.process.stdin.close()
                        self.process, self.active = None, None
                    with self.store.db() as db:
                        row = db.execute("SELECT id FROM subtitle_jobs WHERE state='queued' ORDER BY created_at,id LIMIT 1").fetchone()
                    if not row or self.stop.is_set():
                        continue
                    self.active = row['id']
                    # No title, text, diagnostic traceback or model output reaches logs.
                    self.process = subprocess.Popen(
                        [sys.executable, '-m', 'media_clarity.worker', str(self.store.root), self.active],
                        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        env={**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
                             'HF_HUB_DISABLE_TELEMETRY': '1', 'DO_NOT_TRACK': '1'})
            except (OSError, sqlite3.Error):
                # A launch/storage failure is visible and retryable; never hot-loop.
                if self.active:
                    try:
                        self.update(self.active, state='failed', error='worker_unavailable')
                    except (OSError, sqlite3.Error):
                        pass
                self.stop.wait(1)

    def update(self, job_id, **values):
        allowed = {'state','stage','attempt','completed','total','error','config_sha','transcript','translation','transcript_sha','translation_sha'}
        if not values or not set(values) <= allowed:
            raise ValueError('invalid job fields')
        with self.store.db() as db:
            where = 'id=?'
            params = (*values.values(), job_id)
            if self.expected_attempt is not None:
                where += " AND state='running' AND attempt=?"
                params += (self.expected_attempt,)
            changed = db.execute('UPDATE subtitle_jobs SET '+','.join(f'{k}=?' for k in values)+' WHERE '+where, params).rowcount
            if self.expected_attempt is not None and changed != 1:
                raise MediaError('processing_interrupted', 409)
            db.commit()

    def row(self, job_id):
        if not ID.fullmatch(job_id):
            raise MediaError('job_not_found', 404)
        with self.store.db() as db:
            row = db.execute('SELECT * FROM subtitle_jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            raise MediaError('job_not_found', 404)
        return dict(row)

    def status(self, item_id):
        media = self.store._row(item_id)
        with self.store.db() as db:
            jobs = db.execute('SELECT id,state,stage,attempt,completed,total,error FROM subtitle_jobs WHERE item_id=? ORDER BY created_at DESC,id DESC', (item_id,)).fetchall()
            tracks = db.execute('SELECT id,source,input_sha FROM subtitle_tracks WHERE item_id=? ORDER BY created_at DESC,id DESC', (item_id,)).fetchall()
        return {'jobs': [dict(r) for r in jobs], 'tracks': [
            {'id':r['id'], 'source':r['source'], 'language':'ko'} for r in tracks if r['input_sha'] == media['sha256']]}

    def enqueue(self, item_id, force=False):
        from .models import local_models
        row = self.store._row(item_id)
        # Supplied Korean subtitles should avoid needless expensive ASR.
        with self.lock, self.store.db() as db:
            existing = db.execute("SELECT id FROM subtitle_jobs WHERE item_id=? AND state IN ('queued','running','paused')", (item_id,)).fetchone()
            if existing:
                return self.row(existing['id'])['id']
            if not force and db.execute('SELECT 1 FROM subtitle_tracks WHERE item_id=?', (item_id,)).fetchone():
                raise MediaError('subtitles_already_available', 409)
            local_models(self.store.root, check_packages=True)
            self.store.open_verified(row).close()
            job_id = uuid.uuid4().hex
            db.execute('INSERT INTO subtitle_jobs(id,item_id,input_sha,state) VALUES(?,?,?,?)', (job_id,item_id,row['sha256'],'queued'))
            db.commit()
            return job_id

    def action(self, job_id, action):
        with self.lock:
            if self.recovery_pending:
                raise MediaError('processing_worker_active', 409)
            row = self.row(job_id)
            if action == 'restart':
                if row['state'] not in ('failed','paused'):
                    raise MediaError('processing_busy', 409)
                from .models import local_models
                local_models(self.store.root, check_packages=True)
                media = self.store._row(row['item_id'])
                self.store.open_verified(media).close()
                with self.store.db() as db:
                    db.execute('BEGIN IMMEDIATE')
                    other = db.execute("SELECT 1 FROM subtitle_jobs WHERE item_id=? AND id<>? AND state IN ('queued','running','paused')", (row['item_id'],job_id)).fetchone()
                    if other:
                        raise MediaError('processing_busy', 409)
                    db.execute("UPDATE subtitle_jobs SET state='superseded' WHERE id=?", (job_id,))
                    db.execute('INSERT INTO subtitle_jobs(id,item_id,input_sha,state) VALUES(?,?,?,?)',
                               (uuid.uuid4().hex,row['item_id'],media['sha256'],'queued'))
                    db.commit()
                return
            if action == 'pause':
                if row['state'] not in ('running','queued'):
                    return
                if self.active == job_id:
                    self._terminate()
                # A worker may have committed success before termination; retain it.
                with self.store.db() as db:
                    db.execute("UPDATE subtitle_jobs SET state='paused',error=NULL WHERE id=? AND state IN ('running','queued')", (job_id,))
                    db.commit()
            elif action == 'resume':
                if row['state'] not in ('paused','failed'):
                    return
                from .models import local_models
                local_models(self.store.root, check_packages=True)
                with self.store.db() as db:
                    other = db.execute("SELECT 1 FROM subtitle_jobs WHERE item_id=? AND id<>? AND state IN ('queued','running','paused')", (row['item_id'],job_id)).fetchone()
                if other:
                    raise MediaError('processing_busy', 409)
                self.update(job_id, state='queued', error=None)
            else:
                raise MediaError('invalid_request', 422)

    def import_srt(self, item_id, data):
        row = self.store._row(item_id)
        cues = parse_srt(data, row['duration'])
        if not cues:
            raise MediaError('invalid_subtitles', 422)
        self.store.open_verified(row).close()
        return self.publish(row, cues, 'supplied', None, source_srt=data)

    def publish(self, media, cues, source, job_id, source_srt=None):
        encoded = document(validate_cues(cues, media['duration']))
        if len(encoded.encode()) > MAX_SUBTITLE_BYTES * 4:
            raise MediaError('subtitles_too_large', 422)
        track_id = uuid.uuid4().hex
        with self.store.db() as db:
            db.execute('INSERT INTO subtitle_tracks(id,item_id,input_sha,job_id,source,cues,sha256,source_srt) VALUES(?,?,?,?,?,?,?,?)',
                       (track_id,media['id'],media['sha256'],job_id,source,encoded,hashlib.sha256(encoded.encode()).hexdigest(),source_srt))
            if job_id:
                changed = db.execute("UPDATE subtitle_jobs SET state='succeeded',stage='ready',error=NULL WHERE id=? AND state='running' AND attempt=?", (job_id,self.expected_attempt)).rowcount
                if changed != 1:
                    raise MediaError('processing_interrupted', 409)
            db.commit()
        return track_id

    def track(self, item_id, track_id):
        if not ID.fullmatch(track_id):
            raise MediaError('subtitle_not_found', 404)
        media = self.store._row(item_id)
        with self.store.db() as db:
            row = db.execute('SELECT * FROM subtitle_tracks WHERE id=? AND item_id=?', (track_id,item_id)).fetchone()
        if not row:
            raise MediaError('subtitle_not_found', 404)
        if row['input_sha'] != media['sha256'] or hashlib.sha256(row['cues'].encode()).hexdigest() != row['sha256']:
            raise MediaError('subtitle_changed', 409)
        self.store.open_verified(media).close()
        return webvtt(validate_cues(json.loads(row['cues']), media['duration']))


def execute(store, job_id, backend_factory=None):
    """Serialize actual workers, including survivors of a crashed parent."""
    with worker_guard(store.root):
        _execute(store, job_id, backend_factory)


def _execute(store, job_id, backend_factory):
    """The parent keeps the Store lock; this child keeps worker_guard throughout."""
    from .models import LocalModels
    jobs = Jobs(store)
    with store.db() as db:
        claimed = db.execute("UPDATE subtitle_jobs SET state='running',attempt=attempt+1,error=NULL WHERE id=? AND state='queued' RETURNING attempt", (job_id,)).fetchone()
        db.commit()
    if claimed is None:
        return
    jobs.expected_attempt = claimed['attempt']
    backend = path = attempt = None
    try:
        row = jobs.row(job_id)
        if row['attempt'] != jobs.expected_attempt or row['state'] != 'running':
            return
        media = store._row(row['item_id'])
        if media['sha256'] != row['input_sha']:
            raise MediaError('processing_input_changed', 409)
        store.open_verified(media).close()
        backend = (backend_factory or LocalModels)(store.root)
        identity = backend.identity()
        has_checkpoint = row['transcript'] is not None or row['translation'] != '[]' or row['completed'] or row['total']
        if has_checkpoint and not row['config_sha']:
            raise MediaError('processing_checkpoint_invalid', 409)
        if row['config_sha'] and row['config_sha'] != identity:
            raise MediaError('processing_config_changed', 409)
        if row['transcript'] is None and (row['translation'] != '[]' or row['total']):
            raise MediaError('processing_checkpoint_invalid', 409)
        if row['completed'] != len(json.loads(row['translation'])):
            raise MediaError('processing_checkpoint_invalid', 409)
        jobs.update(job_id, config_sha=identity)
        if row['transcript'] is None:
            jobs.update(job_id, stage='asr')
            directory = store.root / 'processing'
            no_symlink(directory)
            directory.mkdir(exist_ok=True, mode=0o700)
            attempt = directory / uuid.uuid4().hex
            attempt.mkdir(mode=0o700)
            path = attempt / ('input.' + media['extension'])
            store.ensure_space(media['size'])
            verified = store.open_verified(media)
            try:
                with path.open('xb') as out:
                    for block in verified.read_range(0, media['size'] - 1):
                        out.write(block)
                    out.flush()
                    os.fsync(out.fileno())
            finally:
                verified.close()
            transcript = validate_cues(backend.transcribe(path, media['duration']), media['duration'])
            if not transcript:
                raise MediaError('no_speech_detected', 422)
            encoded = document(transcript)
            if len(encoded.encode()) > MAX_SUBTITLE_BYTES * 4:
                raise MediaError('subtitles_too_large', 422)
            jobs.update(job_id, transcript=encoded, transcript_sha=hashlib.sha256(encoded.encode()).hexdigest(), total=len(transcript), stage='translation')
        else:
            if hashlib.sha256(row['transcript'].encode()).hexdigest() != row['transcript_sha']:
                raise MediaError('processing_checkpoint_invalid', 409)
            transcript = validate_cues(json.loads(row['transcript']), media['duration'])
        if row['translation'] != '[]' and hashlib.sha256(row['translation'].encode()).hexdigest() != row['translation_sha']:
            raise MediaError('processing_checkpoint_invalid', 409)
        translated = validate_cues(json.loads(row['translation']), media['duration'])
        if len(translated) > len(transcript) or any((c['start'],c['end']) != (transcript[i]['start'],transcript[i]['end']) for i,c in enumerate(translated)):
            raise MediaError('processing_checkpoint_invalid', 409)
        jobs.update(job_id, stage='translation', completed=len(translated), total=len(transcript))
        for cue in transcript[len(translated):]:
            translated.append({**cue, 'text':backend.translate(cue['text'])})
            translated = validate_cues(translated, media['duration'])
            encoded = document(translated)
            if len(encoded.encode()) > MAX_SUBTITLE_BYTES * 4:
                raise MediaError('subtitles_too_large', 422)
            jobs.update(job_id, translation=encoded, translation_sha=hashlib.sha256(encoded.encode()).hexdigest(), completed=len(translated))
        if identity != backend.identity():
            raise MediaError('processing_config_changed', 409)
        store.open_verified(media).close()
        jobs.publish(media, translated, 'generated', job_id)
    except MediaError as exc:
        try:
            jobs.update(job_id, state='failed', error=exc.code)
        except MediaError:
            pass  # A newer attempt owns the row; never overwrite its state.
    except Exception:
        try:
            jobs.update(job_id, state='failed', error='processing_failed')
        except MediaError:
            pass
    finally:
        if backend is not None:
            backend.close()
        # Only this invocation's disposable input; crash leftovers stay preserved.
        if path is not None:
            try:
                no_symlink(path)
                path.unlink(missing_ok=True)
                attempt.rmdir()
            except (OSError, MediaError):
                pass
