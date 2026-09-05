"""Real generated media and focused failure boundaries; no private fixtures."""
from contextlib import contextmanager
import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from media_clarity.app import byte_range, create_app
from media_clarity.storage import MediaError, Store, run_media, title_from_name


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise RuntimeError("FFmpeg and ffprobe are required for real media tests")
        cls.fixtures = tempfile.TemporaryDirectory()
        cls.source = Path(cls.fixtures.name) / "private-fixture.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=12", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "4", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", str(cls.source)], check=True, capture_output=True)
        cls.video_bytes = cls.source.read_bytes()
        cls.digest = hashlib.sha256(cls.video_bytes).hexdigest()

    @classmethod
    def tearDownClass(cls):
        cls.fixtures.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "app"
        self.app = create_app(self.root)
        self.client = TestClient(self.app, base_url="http://127.0.0.1:8765")
        self.client.__enter__()
        self.store = self.app.state.store
        self.token = self.client.get("/api/session").json()["token"]
        self.headers = {"X-Media-Token": self.token, "Content-Type": "application/octet-stream", "X-Media-Filename": "private-fixture.mp4"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def imported(self):
        response = self.client.post("/api/import", headers=self.headers, content=self.video_bytes)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["item"]

    def assert_code(self, code, function, *args, **kwargs):
        with self.assertRaises(MediaError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_supported_import_preserves_source_and_copy_identity(self):
        item = self.imported()
        self.assertEqual(item["sha256"], self.digest)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.digest)
        managed = self.store.file_path(self.store._row(item["id"]))
        self.assertEqual(hashlib.sha256(managed.read_bytes()).hexdigest(), self.digest)
        self.assertNotEqual(os.stat(self.source).st_ino, os.stat(managed).st_ino)
        self.assertNotEqual(item["id"], item["file_id"])
        self.assertEqual(len(self.client.get("/api/library").json()["items"]), 1)
        self.assertTrue(item["thumbnail"])
        self.assertEqual(self.client.get(f'/api/media/{item["id"]}/thumbnail').headers["content-type"], "image/jpeg")

    def test_cli_copy_and_duplicate_keep_item_and_history(self):
        item = self.store.import_path(self.source)["item"]
        self.store.save_position(item["id"], 2.5)
        duplicate = self.store.import_path(self.source)
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(duplicate["item"]["id"], item["id"])
        self.assertEqual(duplicate["item"]["position"], 2.5)
        self.assertEqual(list((self.root / "staging").iterdir()), [])
        self.assertEqual(len(list((self.root / "files").iterdir())), 1)

    def test_ranges_are_exact_and_bounded(self):
        item = self.imported()
        url = f'/api/media/{item["id"]}/content'
        self.assertEqual(self.client.get(url).content, self.video_bytes)
        for value, expected in [("bytes=0-99",self.video_bytes[:100]),("bytes=100-",self.video_bytes[100:]),("bytes=-83",self.video_bytes[-83:])]:
            with self.subTest(value=value):
                result = self.client.get(url, headers={"Range": value})
                self.assertEqual(result.status_code, 206)
                self.assertEqual(result.content, expected)
                self.assertEqual(int(result.headers["content-length"]), len(expected))
        for value in ["bytes=0-1,2-3", "bytes=-0", "bytes=-", "bytes=8-2", "bytes=999999999-", "bytes=" + "1"*200 + "-", "BYTES=1-2"]:
            self.assertEqual(self.client.get(url, headers={"Range": value}).status_code, 416)
        self.assertEqual(self.client.head(url).content, b"")
        self.assertEqual(self.client.get(url, headers={"Range":"bytes=0-99","If-Range":"old-etag"}).status_code, 200)

    def test_positions_strict_and_persisted(self):
        item = self.imported()
        url = f'/api/library/{item["id"]}/position'
        for value in (True, False, "1", None, -1, 4.5, float("nan"), float("inf"), -float("inf"), [], {}):
            with self.subTest(value=value):
                result = self.client.put(url, headers={"X-Media-Token":self.token}, content=json.dumps({"position":value}))
                self.assertEqual(result.status_code, 422)
        for value in (0, 1, 2.25, item["duration"]):
            result = self.client.put(url, headers={"X-Media-Token":self.token}, json={"position":value})
            self.assertEqual(result.status_code, 200)
        with self.store.db() as db:
            self.assertEqual(db.execute("SELECT position FROM items").fetchone()[0], item["duration"])
        for payload in (b"a"*257, b'{"position":1,"extra":2}', b'null'):
            self.assertEqual(self.client.put(url, headers={"X-Media-Token":self.token}, content=payload).status_code,422)

    def test_uncommitted_save_process_crash_keeps_previous_position(self):
        item = self.imported()
        self.store.save_position(item["id"], 1.25)
        # The child runs the actual save method and dies at the transaction commit boundary.
        code = """
from contextlib import contextmanager
import os,sys
from pathlib import Path
from media_clarity.storage import Store
s=Store(Path(sys.argv[1]))
original=s.db
class Interrupt:
 def __init__(self,c): self.c=c
 def execute(self,*a): return self.c.execute(*a)
 def commit(self): os._exit(23)
@contextmanager
def crash_db():
 with original() as c: yield Interrupt(c)
s.db=crash_db
s.save_position(sys.argv[2],3.25)
"""
        child = subprocess.run([sys.executable, "-c", code, str(self.root), item["id"]], capture_output=True)
        self.assertEqual(child.returncode, 23)
        self.assertEqual(self.store.item(item["id"])["position"], 1.25)

    def test_origin_host_and_token_fail_closed(self):
        for headers in ({"Host":"attacker.example"},{"Origin":"https://attacker.example"},{"Origin":"null"},{"Origin":"http://127.0.0.1:9999"},{"Sec-Fetch-Site":"cross-site"}):
            with self.subTest(headers=headers):
                self.assertEqual(self.client.get("/api/library",headers=headers).status_code,403)
        self.assertEqual(self.client.post("/api/import",content=self.video_bytes).status_code,403)
        self.assertEqual(self.client.get("/api/session",headers={"Origin":"http://127.0.0.1:8765"}).status_code,200)
        page=self.client.get("/")
        self.assertIn("frame-ancestors 'none'",page.headers["content-security-policy"])
        self.assertEqual(page.headers["cache-control"],"no-store")
        self.assertEqual(self.client.get("/assets/app.js").status_code,200)
        self.assertEqual(self.client.get("/assets/%5C%5Cserver%5Cprivate").status_code,404)
        self.assertEqual(self.client.get("/api/media/../../library.sqlite3/content").status_code,404)

    def test_malformed_playlist_and_unsupported_codec_are_rejected(self):
        for payload in (b"", b"not media", b"#EXTM3U\nhttp://example.invalid/private.mp4", b"\x00\x00\x00\x20ftypisominvalid"):
            result=self.client.post("/api/import",headers=self.headers,content=payload)
            self.assertEqual(result.status_code,422)
        invalid=Path(self.temp.name)/"mpeg4.mp4"
        subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i","testsrc2=size=64x64:rate=5","-t","1","-c:v","mpeg4",str(invalid)],capture_output=True,check=True)
        self.assert_code("unsupported_codec", self.store.import_path, invalid)
        self.assertEqual(self.store.list_items(),[])
        self.assertEqual(list((self.root/"staging").iterdir()),[])

    def test_source_change_and_partial_copy_do_not_publish(self):
        source=Path(self.temp.name)/"changing.mp4"
        source.write_bytes(self.video_bytes)
        def mutate():
            with source.open("r+b") as data:
                data.seek(10);data.write(b"changed")
        self.assert_code("source_changed",self.store.import_path,source,after_chunk=mutate)
        source.write_bytes(self.video_bytes)
        def interrupted():
            raise OSError(errno.EIO,"private source path must not escape")
        self.assert_code("storage_unavailable",self.store.import_path,source,after_chunk=interrupted)
        self.assertEqual(source.read_bytes(),self.video_bytes)
        self.assertEqual(self.store.list_items(),[])
        self.assertEqual(list((self.root/"staging").iterdir()),[])

    def test_destination_collision_never_overwrites(self):
        collision="a"*32
        destination=self.root/"files"/collision
        destination.mkdir();(destination/"original.mp4").write_bytes(b"preserve")
        class Fixed:
            hex=collision
        with patch("media_clarity.storage.uuid.uuid4",return_value=Fixed()):
            self.assert_code("destination_collision",self.store.import_path,self.source)
        self.assertEqual((destination/"original.mp4").read_bytes(),b"preserve")
        self.assertEqual(self.store.list_items(),[])

    def test_space_exhaustion_keeps_source_and_database_untouched(self):
        usage=shutil._ntuple_diskusage(100,99,1)
        with patch("media_clarity.storage.shutil.disk_usage",return_value=usage):
            response=self.client.post("/api/import",headers=self.headers,content=self.video_bytes)
            self.assertEqual(response.status_code,507)
            self.assertEqual(response.json(),{"error":"insufficient_space"})
        self.assertEqual(self.source.read_bytes(),self.video_bytes)
        self.assertEqual(self.store.list_items(),[])

    def test_database_commit_failure_rolls_back_managed_publication(self):
        original=self.store.db
        class CommitFailure:
            def __init__(self,connection): self.connection=connection
            def execute(self,*args): return self.connection.execute(*args)
            def commit(self): raise sqlite3.OperationalError("private path")
            def rollback(self): return self.connection.rollback()
        @contextmanager
        def failing_db():
            with original() as db:
                yield CommitFailure(db)
        with patch.object(self.store,"db",failing_db):
            response=self.client.post("/api/import",headers=self.headers,content=self.video_bytes)
            self.assertEqual(response.status_code,503)
            self.assertNotIn("private path",response.text)
        self.assertEqual(self.store.list_items(),[])
        self.assertEqual(list((self.root/"files").iterdir()),[])

    def test_cleanup_failure_releases_http_and_cli_import_ownership(self):
        with patch.object(self.store,"remove_stage",side_effect=PermissionError("temporary file locked")):
            response=self.client.post("/api/import",headers=self.headers,content=b"invalid")
            self.assertEqual(response.status_code,503)
            self.assertFalse(self.store.import_lock.locked())
            with self.assertRaises(PermissionError):
                self.store.import_path(self.source)
            self.assertFalse(self.store.import_lock.locked())
        # The CLI copy committed before cleanup failed; retry must find the same item.
        response=self.client.post("/api/import",headers=self.headers,content=self.video_bytes)
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()["duplicate"])

    def test_missing_managed_file_is_explicit_in_library_play_and_duplicate(self):
        item=self.imported()
        self.store.file_path(self.store._row(item["id"])).unlink()
        self.assertFalse(self.client.get("/api/library").json()["items"][0]["available"])
        self.assertEqual(self.client.get(f'/api/media/{item["id"]}/content').status_code,410)
        response=self.client.post("/api/import",headers=self.headers,content=self.video_bytes)
        self.assertEqual(response.status_code,410)
        self.assertEqual(response.json()["error"],"managed_file_missing")

    def test_changed_managed_size_and_symlinks_fail_closed(self):
        item=self.imported()
        path=self.store.file_path(self.store._row(item["id"]))
        path.write_bytes(b"changed")
        self.assertEqual(self.client.get(f'/api/media/{item["id"]}/content').status_code,409)
        path.unlink()
        try: path.symlink_to(self.source)
        except (OSError,NotImplementedError): self.skipTest("symlink privilege unavailable")
        self.assertEqual(self.client.get(f'/api/media/{item["id"]}/content').status_code,503)
        self.assertEqual(self.source.read_bytes(),self.video_bytes)

    def test_single_instance_and_non_destructive_recovery(self):
        second=Store(self.root)
        self.assert_code("already_running",second.start)
        stage=self.root/"staging"/("b"*32+".part")
        stage.write_bytes(b"partial")
        orphan=self.root/"files"/("c"*32)
        orphan.mkdir();(orphan/"original.mp4").write_bytes(self.video_bytes)
        self.store.close()
        second.start()
        try:
            self.assertEqual(second.recovered,2)
            self.assertEqual(second.list_items(),[])
            recovered=list((self.root/"recovery").iterdir())
            self.assertTrue(any(p.is_file() and p.read_bytes()==b"partial" for p in recovered))
            self.assertTrue(any(p.is_dir() and (p/"original.mp4").read_bytes()==self.video_bytes for p in recovered))
        finally: second.close()

    def test_private_title_rendering_and_safe_errors(self):
        headers=self.headers|{"X-Media-Filename":"%2Fprivate%2F%3Cscript%3Ealert%281%29%3C%2Fscript%3E.mp4"}
        response=self.client.post("/api/import",headers=headers,content=self.video_bytes)
        self.assertEqual(response.status_code,201)
        self.assertNotIn("/private/",response.json()["item"]["title"])
        self.assertNotIn(str(self.root),response.text)
        self.assertEqual(title_from_name(r"C:\secret\hello.mp4"),"hello")
        script=self.client.get("/assets/app.js").text
        self.assertNotIn("innerHTML",script)
        self.assertNotIn("http://",script)
        self.assertNotIn("https://",script)
        with patch.object(self.store,"list_items",side_effect=ValueError("sensitive transcript and source path")):
            response=self.client.get("/api/library?private-query=hidden")
            self.assertEqual(response.json(),{"error":"internal_error"})


class DecoderBoundaryTests(unittest.TestCase):
    def test_decoder_output_is_bounded(self):
        with self.assertRaises(MediaError) as error:
            run_media([sys.executable,"-c","import sys;sys.stdout.write('x'*10000000)"],3,200)
        self.assertEqual(error.exception.code,"invalid_media")

    def test_decoder_timeout_and_stderr_are_safe(self):
        with self.assertRaises(MediaError) as error:
            run_media([sys.executable,"-c","import time,sys;sys.stderr.write('PRIVATE');time.sleep(5)"],1,200)
        self.assertEqual(str(error.exception),"media_timeout")


if __name__ == "__main__":
    unittest.main()
