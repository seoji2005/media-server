"""Identity-bound entry with real imported media, SQLite and the HTTP boundary."""
import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from media_clarity.app import create_app
from media_clarity.caption_view import CaptionView
from media_clarity.item_entry import validate
from media_clarity.jobs import Jobs
from media_clarity.migrations import companion_identity
from media_clarity.storage import MediaError
from tests import test_subtitles as fixtures


class ItemEntryTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.SubtitleTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.SubtitleTests.tearDownClass.__func__)
    setUp = fixtures.SubtitleTests.setUp
    tearDown = fixtures.SubtitleTests.tearDown

    def entry(self):
        with self.store.db() as db:
            identity = companion_identity(db)
        return {key: identity[key] for key in ('version', 'server_id', 'library_id')} | {
            'item_id': self.item['id'], 'file_id': self.item['file_id'], 'sha256': self.item['sha256']}

    def snapshot(self, store):
        with store.db() as db:
            tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            return {t: [tuple(r) for r in db.execute(f'SELECT * FROM {t}')] for t in tables}

    def test_http_retry_restart_and_viewing_state_are_read_only(self):
        track = self.jobs.import_srt(self.item['id'], fixtures.SRT.encode())
        self.store.save_position(self.item['id'], 1.25)
        CaptionView(self.store).save(self.item['id'], 0, track, 500, 0)
        value = self.entry()
        before = self.snapshot(self.store)
        original = self.store.file_path(self.store._row(self.item['id'])).read_bytes()
        vtt = self.jobs.track(self.item['id'], track)
        self.store.close()
        for restart in range(2):
            with patch.object(Jobs, 'start', lambda jobs: jobs.init()), TestClient(
                    create_app(self.root), base_url='http://127.0.0.1:8765') as client:
                headers = {'X-Media-Token': client.get('/api/session').json()['token']}
                path = f"/api/library/{self.item['id']}/item-entry"
                self.assertEqual(client.post(path, json=value).status_code, 403)
                for extra in ({'Origin': 'https://example.com'}, {'Sec-Fetch-Site': 'cross-site'}):
                    self.assertEqual(client.post(path, json=value, headers=headers | extra).status_code, 403)
                for retry in range(2):
                    response = client.post(path, json=value, headers=headers)
                    self.assertEqual(response.status_code, 200, response.text)
                    data = response.json()
                    self.assertEqual(set(data), {'version', 'server_id', 'library_id', 'item'})
                    self.assertEqual(data['item']['id'], self.item['id'])
                    self.assertEqual(data['item']['position'], 1.25)
                    self.assertTrue(data['item']['available'])
                for key in ('item_id', 'file_id', 'sha256', 'server_id', 'library_id'):
                    bad = value | {key: 'f' * len(value[key])}
                    self.assertEqual(client.post(path, json=bad, headers=headers).status_code, 409)
                for bad in (value | {'version': True}, value | {'version': 2}, value | {'sha256': []},
                            value | {'position': 0}, value | {'file_id': '../private'}, [], None):
                    self.assertEqual(client.post(path, content=json.dumps(bad), headers=headers).status_code, 422)
                for raw in (b'{', b'\xff', b'x' * 1025):
                    self.assertEqual(client.post(path, content=raw, headers=headers).status_code, 422)
                store = client.app.state.store
                self.assertEqual(self.snapshot(store), before)
                self.assertEqual(CaptionView(store).read(self.item['id']),
                                 {'selection': track, 'offset_ms': 500, 'revision': 1})
                self.assertEqual(store.file_path(store._row(self.item['id'])).read_bytes(), original)
                self.assertEqual(client.app.state.jobs.track(self.item['id'], track), vtt)

    def test_preparation_required_and_selected_rendition_do_not_change_identity(self):
        value = self.entry()
        # The genuine imported bytes can represent an already verified alternate
        # audio rendition for this contract test; no audio transformation is claimed.
        import uuid
        fid = uuid.uuid4().hex
        folder = self.root / 'files' / fid
        folder.mkdir()
        (folder / 'original.mp4').write_bytes(self.source.read_bytes())
        with self.store.db() as db:
            db.execute('UPDATE items SET audio_index=1 WHERE id=?', (self.item['id'],))
            db.execute('UPDATE files SET audio_tracks=? WHERE id=?',
                       (json.dumps([{'index': 0}, {'index': 1}]), self.item['file_id']))
            db.execute('INSERT INTO renditions(id,item_id,input_sha,sha256,size,extension,mime,kind,duration,audio_index) VALUES(?,?,?,?,?,?,?,?,?,1)',
                       (fid, self.item['id'], self.item['sha256'], self.item['sha256'],
                        self.item['size'], 'mp4', 'video/mp4', 'audio_mp4', 3.9))
            db.commit()
        before = self.snapshot(self.store)
        item = validate(self.store, self.item['id'], value)['item']
        self.assertEqual(item['audio_index'], 1)
        self.assertEqual(item['duration'], 3.9)
        self.assertEqual(item['file_id'], value['file_id'])
        self.assertTrue(item['available'])
        self.assertEqual(self.snapshot(self.store), before)
        with self.store.db() as db:
            db.execute('DELETE FROM renditions'); db.commit()
        before = self.snapshot(self.store)
        item = validate(self.store, self.item['id'], value)['item']
        self.assertFalse(item['available'])
        self.assertEqual(item['unavailable_reason'], 'rendition_required')
        self.assertEqual(self.snapshot(self.store), before)

    def test_same_size_changed_original_and_missing_original_are_rejected(self):
        value = self.entry()
        path = self.store.file_path(self.store._row(self.item['id']))
        raw = path.read_bytes()
        validate(self.store, self.item['id'], value)
        path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        with self.assertRaisesRegex(MediaError, 'managed_file_changed'):
            validate(self.store, self.item['id'], value)
        path.rename(path.with_suffix('.preserved'))
        with self.assertRaisesRegex(MediaError, 'managed_file_missing'):
            validate(self.store, self.item['id'], value)
