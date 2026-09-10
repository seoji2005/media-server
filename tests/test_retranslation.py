"""Saved-transcript translation: exact source selection, recovery and preservation."""
import hashlib
import json
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import tests.test_subtitles as fixtures
from media_clarity.app import create_app
from media_clarity.jobs import Jobs, execute
from media_clarity.storage import MediaError


class TranslationModel(fixtures.FixtureModel):
    def identity(self): return 'translation-v2'
    def transcribe(self, *args): raise AssertionError('ASR repeated for saved text')


class RetranslationTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.SubtitleTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.SubtitleTests.tearDownClass.__func__)
    setUp = fixtures.SubtitleTests.setUp
    tearDown = fixtures.SubtitleTests.tearDown

    def make_source(self):
        with patch('media_clarity.models.local_models'):
            jid = self.jobs.enqueue(self.item['id'], force=True)
        execute(self.store, jid, fixtures.FixtureModel)
        with self.store.db() as db:
            track = db.execute('SELECT id FROM subtitle_tracks WHERE job_id=?',(jid,)).fetchone()[0]
        return jid, track

    def queue(self, track):
        with patch('media_clarity.models.translation_identity', return_value='translation-v2'):
            return self.jobs.retranslate(self.item['id'], track)

    def test_new_version_copies_exact_source_without_asr_or_old_track_mutation(self):
        old, track = self.make_source()
        # Retain valid legacy serialization exactly, including whitespace.
        text = json.dumps(json.loads(self.jobs.row(old)['transcript']), indent=2)
        self.jobs.update(old, transcript=text, transcript_sha=hashlib.sha256(text.encode()).hexdigest())
        before = self.jobs.row(old); vtt = self.jobs.track(self.item['id'], track)
        source_vtt = self.jobs.track(self.item['id'], track, transcript=True)
        media_before = self.store.file_path(self.store._row(self.item['id'])).read_bytes()
        new = self.queue(track); seeded = self.jobs.row(new)
        self.assertEqual(seeded['transcript'], text); self.assertNotEqual(seeded['config_sha'],before['config_sha'])
        self.assertEqual(self.queue(track),new)
        with patch('media_clarity.models.local_models'):
            with self.assertRaisesRegex(MediaError,'processing_busy'):self.jobs.enqueue(self.item['id'],force=True)
        execute(self.store,new,TranslationModel)
        self.assertEqual(self.jobs.row(new)['state'],'succeeded')
        self.assertEqual((self.root/'calls').read_text().count('asr'),1)
        self.jobs.close(); self.store.close(); self.store.start(); self.jobs=Jobs(self.store)
        self.assertEqual(self.jobs.row(old),before)
        self.assertEqual(self.jobs.track(self.item['id'],track),vtt)
        self.assertEqual(self.jobs.track(self.item['id'],track,transcript=True),source_vtt)
        self.assertEqual(self.store.file_path(self.store._row(self.item['id'])).read_bytes(),media_before)
        self.assertEqual(len(self.jobs.status(self.item['id'])['tracks']),2)

    def test_resume_reuses_translation_and_changed_model_requires_same_source_restart(self):
        old, track = self.make_source(); before=self.jobs.row(old)
        (self.root/'fail').touch(); new=self.queue(track);execute(self.store,new,TranslationModel)
        self.assertEqual(self.jobs.row(new)['state'],'failed');self.assertEqual(self.jobs.row(new)['completed'],1)
        calls=(self.root/'calls').read_text();(self.root/'fail').unlink()
        with patch('media_clarity.models.local_models'):self.jobs.action(new,'resume')
        execute(self.store,new,TranslationModel)
        self.assertEqual(self.jobs.row(new)['state'],'succeeded')
        self.assertEqual((self.root/'calls').read_text()[len(calls):],'translate-next\n')
        next_job=self.queue(track)
        class Changed(TranslationModel):
            def identity(self):return 'translation-v3'
        execute(self.store,next_job,Changed)
        self.assertEqual(self.jobs.row(next_job)['error'],'processing_config_changed')
        failed=self.jobs.row(next_job)
        # A failed preflight must roll back superseding the previous job.
        with patch('media_clarity.models.translation_identity',side_effect=MediaError('local_models_missing',503)):
            with self.assertRaises(MediaError):self.jobs.action(next_job,'restart')
        self.assertEqual(self.jobs.row(next_job),failed)
        with patch('media_clarity.models.translation_identity',return_value='translation-v3'):
            self.jobs.action(next_job,'restart')
        with self.store.db() as db:
            successor=dict(db.execute("SELECT * FROM subtitle_jobs WHERE state='queued'").fetchone())
        self.assertEqual(successor['source_track_id'],track);self.assertEqual(successor['transcript'],before['transcript'])
        execute(self.store,successor['id'],Changed)
        self.assertEqual(self.jobs.row(successor['id'])['state'],'succeeded')
        self.assertEqual(self.jobs.row(old),before)
        self.assertEqual((self.root/'calls').read_text().count('asr'),1)

    def test_invalid_source_or_seed_cannot_publish_or_fall_back_to_asr(self):
        old, track=self.make_source(); before=self.jobs.row(old)
        supplied=self.jobs.import_srt(self.item['id'],fixtures.SRT.encode())
        with self.assertRaisesRegex(MediaError,'subtitle_not_found'):self.queue(supplied)
        for change in ({'transcript_sha':'0'*64},{'audio_index':1},{'input_sha':'wrong'},
                       {'transcript':'[]','transcript_sha':hashlib.sha256(b'[]').hexdigest()}):
            with self.subTest(source=change):
                with self.store.db() as db:
                    db.execute('UPDATE subtitle_jobs SET '+','.join(k+'=?' for k in change)+' WHERE id=?',(*change.values(),old));db.commit()
                with self.assertRaises(MediaError):self.queue(track)
                with self.store.db() as db:
                    db.execute('UPDATE subtitle_jobs SET '+','.join(k+'=?' for k in change)+' WHERE id=?',(*(before[k] for k in change),old));db.commit()
        for change in ({'config_sha':None},{'transcript':None},{'transcript_sha':'0'*64},{'audio_index':1}):
            with self.subTest(seed=change):
                new=self.queue(track)
                with self.store.db() as db:
                    db.execute('UPDATE subtitle_jobs SET '+','.join(k+'=?' for k in change)+' WHERE id=?',(*change.values(),new));db.commit()
                execute(self.store,new,TranslationModel)
                self.assertEqual(self.jobs.row(new)['state'],'failed')
                self.assertEqual(self.jobs.row(new)['completed'],0)
        self.assertEqual(len(self.jobs.status(self.item['id'])['tracks']),2)
        self.assertEqual((self.root/'calls').read_text().count('asr'),1)

    def test_http_source_selection_csrf_and_distinct_active_job_are_enforced(self):
        old, track=self.make_source(); other,other_track=self.make_source()
        self.assertNotEqual(track,other_track)
        # The chosen historical version supplies the audio, not playback selection.
        with self.store.db() as db:
            audio=json.loads(db.execute('SELECT audio_tracks FROM files').fetchone()[0])
            db.execute('UPDATE files SET audio_tracks=?',(json.dumps(audio+audio),))
            db.execute('UPDATE items SET audio_index=1');db.commit()
        self.store.close()
        with patch('media_clarity.gemini.api_key',return_value='synthetic-key'),patch.object(Jobs,'start',lambda jobs:jobs.init()),patch('media_clarity.models.translation_identity',return_value='translation-v2'),TestClient(create_app(self.root),base_url='http://127.0.0.1:8765') as client:
            url=f"/api/library/{self.item['id']}/subtitles/{track}/retranslate"
            token=client.get('/api/session').json()['token']; headers={'X-Media-Token':token}
            self.assertEqual(client.post(url).status_code,403)
            self.assertEqual(client.post(url,headers={**headers,'Origin':'https://example.com'}).status_code,403)
            result=client.post(url,headers=headers);self.assertEqual(result.status_code,202)
            jid=result.json()['id'];row=client.app.state.jobs.row(jid)
            self.assertEqual(row['source_track_id'],track);self.assertEqual(row['audio_index'],0)
            self.assertEqual(client.post(url,headers=headers).json()['id'],jid)
            self.assertEqual(client.post(url.replace(track,other_track),headers=headers).status_code,409)
            self.assertEqual(client.post(url.replace(self.item['id'],'f'*32),headers=headers).status_code,404)
