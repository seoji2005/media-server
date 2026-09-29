"""Real guardians and durable captions; synthetic inference, no model/API calls."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from media_clarity.app import create_app
from media_clarity.jobs import Jobs, execute, worker_guard
from media_clarity.storage import MediaError, Store
from tests.test_subtitles import FixtureModel, SRT


def fixture_child(mode, root, job_id):
    if mode == 'guardian':
        from media_clarity.worker_lifecycle import supervise
        return supervise([sys.executable, '-m', 'tests.test_job_resume', 'compute', root, job_id])
    if mode == 'compute':
        if os.read(sys.stdin.fileno(), 1) != b'1':
            return 1
        execute(Store(Path(root)), job_id, FixtureModel)
        return 0
    if mode == 'hold':
        # Extend the observed Windows handle-release interval deterministically.
        # This separate fixture is not an escaping production worker descendant.
        deadline = time.monotonic() + 5
        while True:
            try:
                with worker_guard(Path(root)):
                    Path(job_id).write_text('ready', encoding='ascii')
                    os.read(sys.stdin.fileno(), 1)
                return 0
            except MediaError as error:
                if error.code != 'processing_worker_active' or time.monotonic() >= deadline:
                    raise
                time.sleep(.02)
    raise ValueError('invalid fixture mode')


class JobResumeTests(unittest.TestCase):
    def test_http_resume_waits_for_lease_without_losing_completed_captions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'library'
            source = Path(directory) / 'sample.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                'testsrc2=size=160x90:rate=10', '-f', 'lavfi', '-i',
                'sine=frequency=300', '-t', '4', '-c:v', 'libx264', '-pix_fmt',
                'yuv420p', '-c:a', 'aac', str(source)],
                check=True, capture_output=True, timeout=15)
            original = hashlib.sha256(source.read_bytes()).hexdigest()
            store = Store(root); store.start()
            try:
                item = store.import_path(source)['item']
                jobs = Jobs(store)
                with patch('media_clarity.models.local_models'):
                    job_id = jobs.enqueue(item['id'])
                old_track = jobs.import_srt(item['id'], SRT.encode())
                old_vtt = jobs.track(item['id'], old_track)
                (root / 'block').touch()
            finally:
                store.close()

            popen = subprocess.Popen
            launched = []
            def start_fixture(args, **kwargs):
                if args[1:3] == ['-m', 'media_clarity.worker']:
                    child = popen([sys.executable, '-m', 'tests.test_job_resume',
                                   'guardian', *args[3:]], **kwargs)
                    launched.append(child)
                    return child
                return popen(args, **kwargs)

            app = create_app(root)
            held = None
            with patch('media_clarity.jobs.subprocess.Popen', side_effect=start_fixture), \
                    TestClient(app, base_url='http://127.0.0.1:8765') as client:
                jobs = app.state.jobs
                headers = {'X-Media-Token':client.get('/api/session').json()['token']}
                url = f'/api/subtitle-jobs/{job_id}'
                try:
                    deadline = time.monotonic() + 10
                    while not (root / 'entered').exists() and time.monotonic() < deadline:
                        time.sleep(.02)
                    self.assertTrue((root / 'entered').exists(), 'fixture did not reach second translation')
                    before = jobs.row(job_id)
                    self.assertEqual((before['state'], before['completed'], before['attempt']), ('running', 1, 1))
                    with app.state.store.db() as db:
                        saved = tuple(db.execute('SELECT * FROM subtitle_batches WHERE job_id=?', (job_id,)).fetchone())
                    self.assertEqual(client.post(url + '/pause', headers=headers).status_code, 200)
                    self.assertEqual(jobs.row(job_id)['state'], 'paused')
                    self.assertIsNone(jobs.process)

                    ready = Path(directory) / 'lease-ready'
                    held = popen([sys.executable, '-m', 'tests.test_job_resume',
                                  'hold', str(root), str(ready)], stdin=subprocess.PIPE,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    deadline = time.monotonic() + 6
                    while not ready.exists() and time.monotonic() < deadline:
                        self.assertIsNone(held.poll(), 'lease fixture stopped')
                        time.sleep(.02)
                    self.assertTrue(ready.exists(), 'lease fixture did not become ready')
                    (root / 'block').unlink()
                    with patch('media_clarity.models.local_models'):
                        self.assertEqual(client.post(url + '/resume', headers=headers).status_code, 200)
                    # Multiple real supervisor ticks must preserve this one request.
                    deadline = time.monotonic() + 3
                    while jobs.row(job_id)['state'] == 'queued' and time.monotonic() < deadline:
                        time.sleep(.02)
                    row = jobs.row(job_id)
                    self.assertEqual((row['state'], row['attempt'], row['completed']), ('queued', 1, 1))
                    self.assertEqual(len(launched), 1, 'lease contention must not launch a doomed attempt')
                    self.assertEqual(client.get(f"/api/media/{item['id']}/content",
                        headers={'Range':'bytes=0-99'}).status_code, 206)
                    self.assertEqual(jobs.track(item['id'], old_track), old_vtt)

                    self.assertEqual(client.post(url + '/pause', headers=headers).status_code, 200)
                    self.assertEqual(jobs.row(job_id)['state'], 'paused')
                    with patch('media_clarity.models.local_models'):
                        self.assertEqual(client.post(url + '/resume', headers=headers).status_code, 200)
                    held.stdin.close(); held.wait(timeout=5)
                    self.assertEqual(held.returncode, 0)
                    deadline = time.monotonic() + 10
                    while jobs.row(job_id)['state'] == 'queued' or jobs.row(job_id)['state'] == 'running':
                        self.assertLess(time.monotonic(), deadline, 'resumed job did not finish')
                        time.sleep(.02)
                    after = jobs.row(job_id)
                    self.assertEqual((after['state'], after['completed'], after['attempt']), ('succeeded', 2, 2))
                    self.assertEqual(after['transcript'], before['transcript'])
                    self.assertEqual(after['transcript_sha'], before['transcript_sha'])
                    with app.state.store.db() as db:
                        rows = db.execute('SELECT * FROM subtitle_batches WHERE job_id=? ORDER BY first_index', (job_id,)).fetchall()
                    self.assertEqual(tuple(rows[0]), saved)
                    self.assertEqual(len(rows), 2)
                    self.assertEqual(len(launched), 2)
                    calls = (root / 'calls').read_text().splitlines()
                    self.assertEqual(calls.count('asr'), 1)
                    self.assertEqual(calls.count('translate-hello'), 1)
                    self.assertEqual(calls.count('translate-next'), 2)  # Interrupted, then explicitly resumed.
                    self.assertEqual(jobs.track(item['id'], old_track), old_vtt)
                    tracks = jobs.status(item['id'])['tracks']
                    self.assertEqual(len([track for track in tracks if track['source'] == 'generated']), 1)
                finally:
                    if held:
                        if held.stdin and not held.stdin.closed: held.stdin.close()
                        try: held.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            held.kill(); held.wait(timeout=5)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original)
            with TestClient(create_app(root), base_url='http://127.0.0.1:8765') as client:
                self.assertEqual(client.app.state.jobs.row(job_id)['state'], 'succeeded')
                self.assertEqual(client.app.state.jobs.track(item['id'], old_track), old_vtt)
                self.assertEqual(len(client.app.state.jobs.status(item['id'])['tracks']), 2)
                content = client.get(f"/api/media/{item['id']}/content")
                self.assertEqual(content.status_code, 200)
                self.assertEqual(hashlib.sha256(content.content).hexdigest(), original)


if __name__ == '__main__':
    raise SystemExit(fixture_child(*sys.argv[1:]))
