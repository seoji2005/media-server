"""Local ASR → explicit cloud translation; synthetic inference and real recovery."""
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from media_clarity import gemini
from media_clarity.app import create_app
from media_clarity.jobs import Jobs, execute
from media_clarity.storage import MediaError
from tests import test_gemini as fixtures


class FreshSpeech:
    asr_profile = 'fresh-synthetic-spans-v1'
    audio_timing = 'source-timestamps-v1'

    def __init__(self, root): self.root = root
    def identity(self): return 'fresh-synthetic-asr-v1'
    def transcribe_parts(self, path, duration, audio_index, saved):
        for index in range(len(saved), 2):
            with (self.root/'fresh-asr-calls').open('a') as log: log.write(str(index)+'\n')
            if index == 1 and (self.root/'interrupt-asr').exists():
                raise MediaError('processing_interrupted', 409)
            start = index*2.
            yield {'clip':[start,start+1.5], 'cues':[
                {'start':start+.05+i*.25,'end':start+.25+i*.25,'text':f'Line {index*5+i}.'}
                for i in range(5)]}
    def translate(self, text): raise AssertionError('Local translation must not run')
    def close(self): pass


class FreshGeminiTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.GeminiJobTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.GeminiJobTests.tearDownClass.__func__)
    setUp = fixtures.GeminiJobTests.setUp
    tearDown = fixtures.GeminiJobTests.tearDown

    def queue(self):
        with patch('media_clarity.models.local_models') as setup:
            jid = self.jobs.enqueue(self.item['id'], force=True, provider='gemini')
        setup.assert_called_once_with(self.root, check_packages=True, asr_only=True)
        return jid

    def test_fresh_worker_checkpoint_restart_text_only_and_original_preservation(self):
        old = self.jobs.import_srt(self.item['id'], b'1\n00:00:00,100 --> 00:00:01,000\nExisting\n')
        old_vtt = self.jobs.track(self.item['id'],old)
        media = self.store.file_path(self.store._row(self.item['id'])).read_bytes()
        jid = self.queue()
        script = '''import json,sys
from pathlib import Path
from unittest.mock import patch
from media_clarity.storage import Store,MediaError
from media_clarity.jobs import execute
from tests.test_fresh_gemini import FreshSpeech
from tests.test_gemini import reply
root=Path(sys.argv[1]);calls=[]
def transport(body,key,model):
    calls.append(body)
    (root/'fresh-api-calls').write_text(json.dumps(calls))
    if len(calls)==2:raise MediaError('gemini_quota',503)
    return reply(body,key,model)
with patch('media_clarity.gemini.request',side_effect=transport):
    execute(Store(root),sys.argv[2],FreshSpeech)
'''
        child = subprocess.run([sys.executable,'-c',script,str(self.root),jid],capture_output=True,timeout=30)
        self.assertEqual(child.returncode,0);self.assertEqual(child.stdout,b'')
        # Importing the test fixture can emit the dependency's deprecation warning.
        self.assertNotIn(b'synthetic-key',child.stderr)
        row = self.jobs.row(jid)
        self.assertEqual((row['state'],row['error'],row['asr_completed'],row['completed']),('failed','gemini_quota',2,8))
        self.assertIsNone(row['source_track_id']);self.assertEqual(row['translation_config'],gemini.CONFIG)
        calls = json.loads((self.root/'fresh-api-calls').read_text())
        targets = json.loads(calls[0]['contents'][0]['parts'][0]['text'])
        self.assertEqual(len(targets),8)
        self.assertTrue(all(set(t)=={'id','text','before','after'} for t in targets))
        self.assertEqual([t['id'] for t in targets],[str(i) for i in range(8)])
        for secret in (str(self.root),self.item['id'],jid,'synthetic-key'):
            self.assertNotIn(secret,json.dumps(calls))
        self.assertEqual(len(self.jobs.status(self.item['id'])['tracks']),1)
        asr_calls = (self.root/'fresh-asr-calls').read_bytes()
        self.store.close();self.store.start();self.jobs=Jobs(self.store)
        with patch('media_clarity.models.local_models'),patch.dict(os.environ,{'GEMINI_API_KEY':'rotated-key'}),patch('media_clarity.gemini.request',side_effect=fixtures.reply) as transport:
            self.jobs.action(jid,'resume');execute(self.store,jid,FreshSpeech)
        self.assertEqual(self.jobs.row(jid)['state'],'succeeded')
        transport.assert_called_once()
        pending = json.loads(transport.call_args.args[0]['contents'][0]['parts'][0]['text'])
        self.assertEqual([t['text'] for t in pending],['Line 8.','Line 9.'])
        self.assertEqual(pending[0]['before'],'Line 7.')
        self.assertEqual((self.root/'fresh-asr-calls').read_bytes(),asr_calls)
        self.assertEqual(self.jobs.row(jid)['config_sha'],row['config_sha'])
        self.assertEqual(self.jobs.track(self.item['id'],old),old_vtt)
        self.assertEqual(self.store.file_path(self.store._row(self.item['id'])).read_bytes(),media)

    def test_asr_interruption_sends_nothing_then_reuses_saved_span(self):
        jid = self.queue();(self.root/'interrupt-asr').touch()
        with patch('media_clarity.gemini.request') as transport:
            execute(self.store,jid,FreshSpeech)
        transport.assert_not_called()
        self.assertEqual(self.jobs.row(jid)['asr_completed'],1)
        (self.root/'interrupt-asr').unlink()
        with patch('media_clarity.models.local_models'),patch('media_clarity.gemini.request',side_effect=fixtures.reply):
            self.jobs.action(jid,'resume');execute(self.store,jid,FreshSpeech)
        self.assertEqual(self.jobs.row(jid)['state'],'succeeded')
        self.assertEqual((self.root/'fresh-asr-calls').read_text().splitlines(),['0','1','1'])

    def test_changed_asr_identity_and_corrupt_span_fail_before_cloud_call(self):
        class Changed(FreshSpeech):
            def identity(self): return 'changed-asr'
        for change in ('model','span'):
            jid = self.queue();(self.root/'interrupt-asr').touch()
            execute(self.store,jid,FreshSpeech)
            (self.root/'interrupt-asr').unlink()
            if change == 'span':
                with self.store.db() as db:
                    db.execute("UPDATE asr_spans SET payload='{}' WHERE job_id=?",(jid,));db.commit()
            with patch('media_clarity.models.local_models'),patch('media_clarity.gemini.request') as transport:
                self.jobs.action(jid,'resume');execute(self.store,jid,Changed if change=='model' else FreshSpeech)
            transport.assert_not_called()
            self.assertEqual(self.jobs.row(jid)['error'],'processing_config_changed' if change=='model' else 'processing_checkpoint_invalid')

    def test_restart_freezes_model_and_failed_setup_preserves_job(self):
        legacy = gemini.CONFIGS['gemini-3.8-flash']
        with patch('media_clarity.gemini.CONFIG',legacy): jid = self.queue()
        self.jobs.action(jid,'pause');before=self.jobs.row(jid)
        with patch.dict(os.environ,{'GEMINI_API_KEY':''}),self.assertRaisesRegex(MediaError,'gemini_key_missing'):
            self.jobs.action(jid,'restart')
        self.assertEqual(self.jobs.row(jid),before)
        with patch('media_clarity.models.local_models',side_effect=MediaError('local_models_missing',503)),self.assertRaisesRegex(MediaError,'local_models_missing'):
            self.jobs.action(jid,'restart')
        self.assertEqual(self.jobs.row(jid),before)
        with patch('media_clarity.models.local_models'):
            self.jobs.action(jid,'restart')
        with self.store.db() as db:
            successor = dict(db.execute("SELECT * FROM subtitle_jobs WHERE state='queued'").fetchone())
        self.assertEqual(successor['translation_config'],legacy)
        self.assertIsNone(successor['source_track_id'])
        self.assertEqual(successor['audio_index'],before['audio_index'])
        with patch('media_clarity.gemini.request',side_effect=fixtures.reply) as transport:
            execute(self.store,successor['id'],FreshSpeech)
        self.assertEqual(self.jobs.row(successor['id'])['state'],'succeeded')
        self.assertTrue(all(c.args[2]=='gemini-3.8-flash' for c in transport.call_args_list))

    def test_http_default_local_explicit_cloud_validation_and_conflicts(self):
        self.store.close()
        with patch.object(Jobs,'start',lambda jobs:jobs.init()),patch('media_clarity.models.local_models') as setup,patch('media_clarity.gemini.request') as transport,TestClient(create_app(self.root),base_url='http://127.0.0.1:8765') as client:
            root = f"/api/library/{self.item['id']}/subtitle-jobs"
            headers = {'X-Media-Token':client.get('/api/session').json()['token']}
            for url in (root,root+'/regenerate'):
                self.assertEqual(client.post(url,json={'provider':'gemini'}).status_code,403)
                for value in ({'provider':'other'},{'provider':{}},{'provider':'gemini','key':'x'},[],None):
                    self.assertEqual(client.post(url,content=json.dumps(value),headers=headers).status_code,422)
                self.assertEqual(client.post(url,content='x'*2049,headers=headers).status_code,422)
                with patch.dict(os.environ,{'GEMINI_API_KEY':''}):
                    result = client.post(url,json={'provider':'gemini'},headers=headers)
                    self.assertEqual((result.status_code,result.json()['error']),(503,'gemini_key_missing'))
            self.assertEqual(client.app.state.jobs.status(self.item['id'])['jobs'],[])
            local = client.post(root,headers=headers).json()['id']
            self.assertIsNone(client.app.state.jobs.row(local)['translation_config'])
            self.assertEqual(client.post(root,json={'provider':'gemini'},headers=headers).status_code,409)
            client.app.state.jobs.update(local,state='failed')
            cloud = client.post(root,json={'provider':'gemini'},headers=headers).json()['id']
            self.assertEqual(client.app.state.jobs.row(cloud)['translation_config'],gemini.CONFIG)
            self.assertEqual(client.post(root,json={'provider':'gemini'},headers=headers).json()['id'],cloud)
            self.assertEqual(client.post(root,headers=headers).status_code,409)
            setup.assert_called_with(self.root,check_packages=True,asr_only=True)
            transport.assert_not_called()
