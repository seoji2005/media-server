"""Manual foreign captions join the saved-text path without ASR or implicit egress."""
import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from media_clarity import gemini
from media_clarity.app import create_app
from media_clarity.caption_view import CaptionView
from media_clarity.jobs import Jobs, execute
from tests import test_gemini as fixtures


SRT = b'1\n00:00:00,100 --> 00:00:01,000\nLet us leave at noon.\n'
VTT = 'WEBVTT\n\n00:00.100 --> 00:01.000\nお昼に出よう。\n'.encode()


class ManualCaptionTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.GeminiJobTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.GeminiJobTests.tearDownClass.__func__)
    setUp = fixtures.GeminiJobTests.setUp
    tearDown = fixtures.GeminiJobTests.tearDown

    def test_foreign_http_import_restart_and_explicit_38_translation_preserve_views(self):
        old = self.jobs.import_srt(self.item['id'], SRT)
        original_vtt = self.jobs.track(self.item['id'], old)
        self.store.save_position(self.item['id'], 1.25)
        view = CaptionView(self.store).save(self.item['id'], 0, old, 500, 0)
        original_bytes = self.store.file_path(self.store._row(self.item['id'])).read_bytes()
        self.store.close()
        imports = []
        with patch.object(Jobs, 'start', lambda jobs: jobs.init()), patch('media_clarity.gemini.request') as transport:
            for restart in range(2):
                with TestClient(create_app(self.root), base_url='http://127.0.0.1:8765') as client:
                    store, jobs = client.app.state.store, client.app.state.jobs
                    headers = {'X-Media-Token': client.get('/api/session').json()['token']}
                    url = f"/api/library/{self.item['id']}/subtitles"
                    if restart == 0:
                        for raw, language, format in ((SRT, 'en', 'srt'), (VTT, 'ja', 'webvtt')):
                            response = client.post(url, params={'language': language, 'format': format, 'audio_index': 0}, content=raw, headers=headers)
                            self.assertEqual(response.status_code, 201, response.text)
                            imports.append((response.json()['id'], raw, language))
                    for track_id, raw, language in imports:
                        track = next(t for t in jobs.status(self.item['id'])['tracks'] if t['id'] == track_id)
                        self.assertEqual(track['language'], language)
                        self.assertTrue(track['can_retranslate'])
                        with store.db() as db:
                            self.assertEqual(db.execute('SELECT source_srt FROM subtitle_tracks WHERE id=?', (track_id,)).fetchone()[0], raw)
                    self.assertEqual(CaptionView(store).read(self.item['id']), view)
                    self.assertEqual(store.item(self.item['id'])['position'], 1.25)
                    self.assertEqual(jobs.track(self.item['id'], old), original_vtt)
                    transport.assert_not_called()
                    if restart:
                        track_id = imports[0][0]
                        result = client.post(url + f'/{track_id}/retranslate', headers=headers)
                        self.assertEqual(result.status_code, 202, result.text)
                        jid = result.json()['id']
                        self.assertEqual(gemini.model_for(jobs.row(jid)['translation_config']), 'gemini-3.8-flash')
                        with patch('media_clarity.qwen.QwenSpeech', side_effect=AssertionError('ASR forbidden')), patch('media_clarity.models.LocalModels', side_effect=AssertionError('Local models forbidden')), patch('media_clarity.gemini.request', side_effect=fixtures.reply) as translated:
                            execute(store, jid)
                        self.assertEqual(jobs.row(jid)['state'], 'succeeded')
                        self.assertEqual(translated.call_count, 1)
                        self.assertEqual(translated.call_args.args[2], 'gemini-3.8-flash')
                        payload = json.loads(translated.call_args.args[0]['contents'][0]['parts'][0]['text'])
                        self.assertEqual(payload['targets'][0]['text'], 'Let us leave at noon.')
                        self.assertEqual(len(jobs.status(self.item['id'])['tracks']), 4)
                        self.assertEqual(CaptionView(store).read(self.item['id']), view)
                        self.assertEqual(jobs.track(self.item['id'], old), original_vtt)
                        self.assertEqual(store.file_path(store._row(self.item['id'])).read_bytes(), original_bytes)

    def test_http_import_defaults_validation_and_no_failed_publish(self):
        self.store.close()
        with patch.object(Jobs, 'start', lambda jobs: jobs.init()), TestClient(create_app(self.root), base_url='http://127.0.0.1:8765') as client:
            headers = {'X-Media-Token': client.get('/api/session').json()['token']}
            url = f"/api/library/{self.item['id']}/subtitles"
            self.assertEqual(client.post(url, content=SRT).status_code, 403)
            good = client.post(url, content=SRT, headers=headers)
            self.assertEqual(good.status_code, 201)
            before = client.get(url).json()['tracks']
            self.assertEqual(before[0]['language'], 'ko')
            self.assertFalse(before[0]['can_retranslate'])
            for params, raw in (({'language': ''}, SRT), ({'language': 'en<script>'}, SRT),
                                ({'format': 'ass'}, SRT), ({'format': 'webvtt'}, SRT),
                                ({'audio_index': 128}, SRT), ({}, b'x' * (2 * 1024 * 1024 + 1))):
                with self.subTest(params=params):
                    self.assertIn(client.post(url, params=params, content=raw, headers=headers).status_code, (413, 422))
                    self.assertEqual(client.get(url).json()['tracks'], before)

