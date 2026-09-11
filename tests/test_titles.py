"""Display metadata changes through actual SQLite/ASGI, with original safety."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from media_clarity.app import create_app
from media_clarity.storage import MediaError


class TitleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory()
        cls.source = Path(cls.fixture.name) / 'original.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-f', 'lavfi', '-i',
                        'testsrc2=size=160x90:rate=10', '-t', '4', '-c:v', 'libx264',
                        '-threads', '1', '-pix_fmt', 'yuv420p', str(cls.source)],
                       check=True, capture_output=True, timeout=20)
        cls.content = cls.source.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'library'
        self.start()
        self.item = self.store.import_path(self.source)['item']
        self.url = f'/api/library/{self.item["id"]}'

    def start(self):
        self.client = TestClient(create_app(self.root), base_url='http://127.0.0.1:8765')
        self.client.__enter__()
        self.store = self.client.app.state.store
        self.headers = {'X-Media-Token': self.client.get('/api/session').json()['token']}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def rename(self, title, expected='original'):
        return self.client.put(self.url+'/title', headers=self.headers,
                               json={'title': title, 'expected_title': expected})

    def test_rename_restart_duplicate_and_existing_fetch_entry_preserve_media_and_view(self):
        self.client.put(self.url+'/position', headers=self.headers, json={'position': 1.25})
        caption = self.client.post(self.url+'/subtitles', headers=self.headers,
                                  content=b'1\n00:00:00,000 --> 00:00:03,000\nSaved caption\n').json()
        self.client.put(self.url+'/caption-view', headers=self.headers,
                        json={'audio_index': 0, 'selection': caption['id'], 'offset_ms': 500, 'revision': 0})
        self.client.put(self.url+'/preference', headers=self.headers,
                        json={'included': False, 'preference': 'like', 'revision': 0})
        before = self.client.get(self.url).json()
        tracks = self.client.get(self.url+'/subtitles').json()
        vtt = self.client.get(self.url+f'/subtitles/{caption["id"]}.vtt').content
        preference = self.client.get(self.url+'/preference').json()
        identity = self.client.get('/api/companion/identity', headers=self.headers).json()
        entry = {key: identity[key] for key in ('server_id', 'library_id')}
        entry.update(version=1, item_id=before['id'], file_id=before['file_id'], sha256=before['sha256'])
        expected = '교토 여행 / Part 1.mp4'
        response = self.rename('  '+expected+'  ')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {'id': before['id'], 'title': expected})
        self.client.__exit__(None, None, None); self.start()
        self.assertEqual(self.client.get(self.url).json(), before | {'title': expected})
        self.assertEqual(self.client.get(self.url+'/subtitles').json(), tracks)
        self.assertEqual(self.client.get(self.url+f'/subtitles/{caption["id"]}.vtt').content, vtt)
        self.assertEqual(self.client.get(self.url+'/preference').json(), preference)
        opened = self.client.post(self.url+'/item-entry', headers=self.headers, json=entry)
        self.assertEqual(opened.status_code, 200, opened.text)
        self.assertEqual(opened.json()['item']['title'], expected)
        duplicate = self.store.import_path(self.source)
        self.assertTrue(duplicate['duplicate']); self.assertEqual(duplicate['item']['title'], expected)
        managed = self.store.file_path(self.store._row(before['id']))
        self.assertEqual(self.source.read_bytes(), self.content)
        self.assertEqual(hashlib.sha256(managed.read_bytes()).hexdigest(), before['sha256'])
        self.assertEqual(self.client.get('/api/recommendations').json(), {'items': [], 'included_count': 0})

    def test_atomic_conflict_and_two_simultaneous_edits(self):
        def change(title):
            try:
                return self.store.rename_item(self.item['id'], title, 'original')
            except MediaError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(change, ['First title', 'Second title']))
        self.assertEqual(results.count('title_changed'), 1)
        winner = next(result['title'] for result in results if isinstance(result, dict))
        self.assertEqual(self.client.get(self.url).json()['title'], winner)
        stale = self.rename('Overwrite')
        self.assertEqual(stale.status_code, 409); self.assertEqual(stale.json(), {'error': 'title_changed'})
        self.assertEqual(self.rename('Updated after reread', winner).status_code, 200)

    def test_invalid_input_and_session_gate_do_not_change_title(self):
        for title in ['', '   ', 'a'*181, 'line\nbreak', '\u202ehidden', '\ud800', None, 4, True]:
            with self.subTest(title=repr(title)):
                # Ensure surrogate input reaches the application's JSON validator.
                response = self.client.put(self.url+'/title', headers=self.headers,
                                          content=json.dumps({'title': title, 'expected_title': 'original'}))
                self.assertEqual(response.status_code, 422)
        for body in [[], {}, {'title': 'new'}, {'title': 'new', 'expected_title': None},
                     {'title': 'new', 'expected_title': 'original', 'file_id': 'x'}]:
            self.assertEqual(self.client.put(self.url+'/title', headers=self.headers, json=body).status_code, 422)
        self.assertEqual(self.client.put(self.url+'/title', headers=self.headers, content=b'x'*4097).status_code, 422)
        self.assertEqual(self.client.put(self.url+'/title', json={'title': 'new', 'expected_title': 'original'}).status_code, 403)
        self.assertEqual(self.client.get(self.url).json()['title'], 'original')

    def test_commit_failure_rolls_back_without_file_work(self):
        db_factory = self.store.db
        @contextmanager
        def failing():
            with db_factory() as connection:
                class Proxy:
                    def execute(self, *args, **kwargs):
                        return connection.execute(*args, **kwargs)
                    def commit(self):
                        raise sqlite3.OperationalError('private native failure')
                yield Proxy()
        with patch.object(self.store, 'db', failing), patch.object(self.store, 'open_verified', side_effect=AssertionError('file read')):
            with self.assertRaises(sqlite3.OperationalError):
                self.store.rename_item(self.item['id'], 'new', 'original')
        self.assertEqual(self.client.get(self.url).json()['title'], 'original')

    def test_new_title_updates_existing_opt_in_ranking_without_adding_participation(self):
        candidate_file = Path(self.temp.name)/'candidate.mp4'
        candidate_file.write_bytes(self.content+struct.pack('>I4sI', 12, b'free', 1))
        candidate = self.store.import_path(candidate_file)['item']
        self.store.rename_item(candidate['id'], '교토 여행', 'candidate')
        for iid, preference in [(self.item['id'], 'like'), (candidate['id'], 'neutral')]:
            self.client.put(f'/api/library/{iid}/preference', headers=self.headers,
                            json={'included': True, 'preference': preference, 'revision': 0})
        self.assertEqual(self.client.get('/api/recommendations').json()['items'][0]['recommendation_reason'], 'explore')
        self.assertEqual(self.rename('교토 산책').status_code, 200)
        result = self.client.get('/api/recommendations').json()
        self.assertEqual(result['items'][0]['recommendation_reason'], 'liked_title')
        self.assertEqual(result['included_count'], 2)
        self.assertEqual(self.client.get(self.url+'/preference').json(), {'included': True, 'preference': 'like', 'revision': 1})


if __name__ == '__main__':
    unittest.main()
