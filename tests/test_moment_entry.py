"""Companion entry on real SQLite/media, including the preceding retranslation schema."""
import hashlib
from unittest.mock import patch
import unittest

from fastapi.testclient import TestClient
from media_clarity.app import create_app
from media_clarity.jobs import Jobs, execute
from media_clarity.recommendations import Recommendations
from tests import test_subtitles as fixtures


class MomentEntryTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.SubtitleTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.SubtitleTests.tearDownClass.__func__)
    setUp = fixtures.SubtitleTests.setUp
    tearDown = fixtures.SubtitleTests.tearDown

    def test_v6_upgrade_preserves_retranslation_source_and_every_existing_row(self):
        with patch('media_clarity.models.local_models'):
            source_job = self.jobs.enqueue(self.item['id'])
        execute(self.store, source_job, fixtures.FixtureModel)
        with self.store.db() as db:
            track = db.execute('SELECT id FROM subtitle_tracks').fetchone()[0]
        with patch('media_clarity.models.translation_identity', return_value='fixture-mt'):
            new_job = self.jobs.retranslate(self.item['id'], track)
        vtt = self.jobs.track(self.item['id'], track)
        original = self.store.file_path(self.store._row(self.item['id'])).read_bytes()
        with self.store.db() as db:
            db.execute('DROP TABLE companion_identity')
            db.execute('PRAGMA user_version=6')
            db.commit()
            tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            before = {t: [tuple(r) for r in db.execute(f'SELECT * FROM {t}')] for t in tables}
        self.jobs.close(); self.store.close(); self.store.start()
        with self.store.db() as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 8)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
            for t, rows in before.items():
                self.assertEqual([tuple(r) for r in db.execute(f'SELECT * FROM {t}')], rows)
        self.assertEqual(self.jobs.row(new_job)['source_track_id'], track)
        self.assertEqual(self.jobs.track(self.item['id'], track), vtt)
        self.assertEqual(self.store.file_path(self.store._row(self.item['id'])).read_bytes(), original)

    def test_http_identity_and_entry_are_protected_exact_and_read_only(self):
        item_id = self.item['id']; path = f'/api/library/{item_id}'
        self.store.save_position(item_id, 1.25)
        media = self.store.file_path(self.store._row(item_id))
        original_sha = hashlib.sha256(media.read_bytes()).hexdigest()
        self.store.close()
        with patch.object(Jobs, 'start', lambda jobs: jobs.init()), TestClient(create_app(self.root), base_url='http://127.0.0.1:8765') as client:
            token = client.get('/api/session').json()['token']
            headers = {'X-Media-Token': token}
            for route in ('/api/companion/identity', path+'/moment-reference'):
                self.assertEqual(client.get(route).status_code, 403)
                self.assertEqual(client.get(route, headers={**headers, 'Origin':'https://example.com'}).status_code, 403)
            self.assertEqual(client.post(path+'/moment-entry', json={}).status_code, 403)
            self.assertEqual(client.get(path+'/moment-reference', headers=headers).status_code, 404)
            store = client.app.state.store
            preferences = Recommendations(store)
            saved = preferences.save(item_id, True, 'neutral', 0)
            identity = client.get('/api/companion/identity', headers=headers).json()
            reference = client.get(path+'/moment-reference', headers=headers).json()
            self.assertEqual(reference['library_id'], identity['library_id'])
            valid = {**reference, 'start_ms': 2000, 'end_ms': 3000}
            result = client.post(path+'/moment-entry', json=valid, headers=headers)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json(), {'start_ms':2000, 'end_ms':3000})
            self.assertEqual(client.post(path+'/moment-entry', json=valid, headers={**headers, 'Sec-Fetch-Site':'cross-site'}).status_code, 403)
            for change in ({'server_id':'f'*32}, {'library_id':'f'*32}, {'item_id':'f'*32}, {'duration_ms':1},
                           {'timeline':{**reference['timeline'], 'sha256':'0'*64}}):
                with self.subTest(change=change):
                    self.assertEqual(client.post(path+'/moment-entry', json={**valid, **change}, headers=headers).status_code, 409)
            for change in ({'version':True}, {'start_ms':True}, {'start_ms':-1}, {'start_ms':reference['duration_ms']},
                           {'end_ms':2000}, {'end_ms':reference['duration_ms']+1}, {'extra':0}):
                with self.subTest(change=change):
                    self.assertEqual(client.post(path+'/moment-entry', json={**valid, **change}, headers=headers).status_code, 422)
            for value in ('{', 'x'*2049, 'null', '[]'):
                self.assertEqual(client.post(path+'/moment-entry', content=value, headers=headers).status_code, 422)
            self.assertEqual(client.post(path.replace(item_id,'f'*32)+'/moment-entry', json=valid, headers=headers).status_code, 404)
            with store.db() as db:
                row = dict(db.execute('SELECT * FROM files').fetchone())
                for column, value in (('audio_tracks',None), ('preparation','unchecked'), ('preparation','remux_mp4')):
                    db.execute(f'UPDATE files SET {column}=?', (value,)); db.commit()
                    self.assertEqual(client.post(path+'/moment-entry', json=valid, headers=headers).status_code, 409)
                    db.execute(f'UPDATE files SET {column}=?', (row[column],)); db.commit()
                self.assertEqual(db.execute('SELECT count(*) FROM renditions').fetchone()[0], 0)
                self.assertEqual(db.execute('SELECT count(*) FROM subtitle_jobs').fetchone()[0], 0)
            self.assertEqual(preferences.preference(item_id), saved)
            preferences.save(item_id, False, 'neutral', saved['revision'])
            self.assertEqual(client.post(path+'/moment-entry', json=valid, headers=headers).status_code, 404)
            self.assertEqual(store.item(item_id)['position'], 1.25)
            self.assertEqual(hashlib.sha256(media.read_bytes()).hexdigest(), original_sha)
