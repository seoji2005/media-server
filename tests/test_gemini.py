"""Synthetic Gemini transport; no credential, network or model quality claims."""
from contextlib import closing
import copy
import hashlib
import io
import json
import os
import sqlite3
import subprocess
import sys
import unittest
import urllib.error
from unittest.mock import patch

from fastapi.testclient import TestClient
from media_clarity import gemini
from media_clarity.app import create_app
from media_clarity.jobs import Jobs, document, execute
from media_clarity.storage import MediaError
from tests import test_retranslation as fixtures


def response(rows):
    return {'candidates':[{'finishReason':'STOP', 'content':{'parts':[{'text':json.dumps({'translations':rows})}]}}]}


def reply(body, key, model=None):
    targets = json.loads(body['contents'][0]['parts'][0]['text'])
    return response([{'id':t['id'], 'text':'번역 '+t['text']} for t in targets])


class GeminiTransportTests(unittest.TestCase):
    def test_system_https_opt_in_does_not_shadow_os_proxy_discovery(self):
        # A *_PROXY flag would become a fake proxy and suppress OS fallback on
        # Windows/macOS even when no ordinary proxy environment is configured.
        with patch.dict(os.environ, {'MEDIA_GEMINI_USE_SYSTEM_HTTPS':'1'}, clear=True):
            self.assertEqual(urllib.request.getproxies_environment(), {})

    def test_system_proxy_requires_explicit_opt_in_and_keeps_destination_guards(self):
        configured = {'https':'http://127.0.0.1:12345'}
        for option in ('', '0', 'true', '1'):
            with (self.subTest(option=option),
                  patch.dict(os.environ, {'MEDIA_GEMINI_USE_SYSTEM_HTTPS':option}),
                  patch('urllib.request.getproxies', return_value=configured),
                  patch('media_clarity.gemini.urllib.request.build_opener') as build):
                body = io.BytesIO(b'private-provider-body synthetic-key')
                build.return_value.open.side_effect = urllib.error.HTTPError(
                    gemini.ENDPOINT, 403, 'private', {}, body)
                with self.assertRaisesRegex(MediaError, '^gemini_auth_failed$'):
                    gemini.request({'synthetic':'dialogue'}, 'synthetic-key')
                proxy, redirect = build.call_args.args
                self.assertEqual(proxy.proxies, configured if option == '1' else {})
                self.assertIsNone(redirect.redirect_request(None,None,302,'',{},'https://example.com'))
                req = build.return_value.open.call_args.args[0]
                self.assertEqual(req.full_url, gemini.ENDPOINT)
                self.assertEqual(req.get_header('X-goog-api-key'), 'synthetic-key')
                self.assertEqual(build.return_value.open.call_count, 1)
                self.assertTrue(body.closed)

    def test_prompt_profiles_are_exact_and_reject_unknown_identity(self):
        self.assertNotEqual(gemini.CONFIG, gemini.CONFIGS[gemini.MODEL])
        for config, prompt in gemini.PROFILES.items():
            with self.subTest(config=config):
                saved = json.loads(config)
                self.assertEqual(saved['prompt_sha256'], hashlib.sha256(prompt.encode()).hexdigest())
                with patch.dict(os.environ, {'GEMINI_API_KEY':'synthetic-key'}):
                    backend = gemini.Gemini(config)
                self.assertEqual(backend.prompt, prompt)
                self.assertEqual(backend.model, saved['model'])
                backend.close()
        changed = json.loads(gemini.CONFIG);changed['prompt_sha256'] = '0'*64
        for config in (None, {}, json.dumps(changed), '{}'):
            with self.assertRaisesRegex(MediaError, 'processing_config_changed'):
                gemini.model_for(config)

    def test_authorization_key_format_without_header_injection(self):
        for key in ('synthetic-key','AQ.synthetic_auth-key.123'):
            with patch.dict(os.environ,{'GEMINI_API_KEY':key}):
                self.assertEqual(gemini.api_key(),key)
                self.assertTrue(gemini.configured())
        for key in ('','x\r\ny: z','x y','x\t','x'*513,'한글'):
            with patch.dict(os.environ,{'GEMINI_API_KEY':key}):
                self.assertFalse(gemini.configured())
                with self.assertRaisesRegex(MediaError,'gemini_key_missing'):
                    gemini.api_key()

    def test_request_fixed_destination_no_proxy_redirect_or_retry(self):
        data = json.dumps(response([{'id':'0', 'text':'안녕'}])).encode()
        with (patch.dict(os.environ, {'MEDIA_GEMINI_USE_SYSTEM_HTTPS':''}),
              patch('media_clarity.gemini.urllib.request.build_opener') as build):
            build.return_value.open.return_value = io.BytesIO(data)
            result = gemini.request({'synthetic':'dialogue'}, 'synthetic-key')
            args = build.call_args.args
            self.assertEqual(args[0].proxies, {})
            self.assertIsNone(args[1].redirect_request(None,None,302,'',{},'https://example.com'))
            req = build.return_value.open.call_args.args[0]
            self.assertEqual(req.full_url, gemini.ENDPOINT)
            self.assertEqual(req.get_header('X-goog-api-key'), 'synthetic-key')
            self.assertNotIn('synthetic-key', req.full_url)
            self.assertEqual(build.return_value.open.call_args.kwargs, {'timeout':60})
            self.assertEqual(result, json.loads(data))
        for status, expected in ((401,'gemini_auth_failed'),(403,'gemini_auth_failed'),
                                 (429,'gemini_quota'),(503,'gemini_unavailable'),(302,'gemini_unavailable')):
            with self.subTest(status=status), patch('media_clarity.gemini.urllib.request.build_opener') as build:
                body = io.BytesIO(b'private-provider-body synthetic-key')
                build.return_value.open.side_effect = urllib.error.HTTPError(gemini.ENDPOINT,status,'private',{},body)
                with self.assertRaises(MediaError) as caught:
                    gemini.request({}, 'synthetic-key')
                self.assertEqual(caught.exception.code, expected)
                self.assertEqual(str(caught.exception), expected)
                self.assertTrue(body.closed)
                self.assertEqual(build.return_value.open.call_count, 1)

    def test_malformed_and_oversized_transport_response(self):
        for raw in (b'not-json', b'\xff', b'x'*(1024*1024+1)):
            with self.subTest(size=len(raw)), patch('media_clarity.gemini.urllib.request.build_opener') as build:
                build.return_value.open.return_value = io.BytesIO(raw)
                with self.assertRaisesRegex(MediaError, 'gemini_response_invalid'):
                    gemini.request({}, 'synthetic-key')

    def test_strict_output_validation_and_refusal(self):
        good = response([{'id':'0', 'text':'안녕 &amp; <대사>'}])
        self.assertEqual(gemini.translations(good, ['0']), ['안녕 &amp; <대사>'])
        invalid = [None, {}, {'candidates':[]}, response([]), response([{'id':'1','text':'안녕'}]),
                   response([{'id':'0','text':''}]), response([{'id':'0','text':'x'*4001}]),
                   response([{'id':'0','text':'a\x00'}]), response([{'id':'0','text':23}]),
                   response([{'id':'0','text':'a','extra':'x'}]),
                   response([{'id':'0','text':'a'},{'id':'0','text':'b'}])]
        truncated = copy.deepcopy(good);truncated['candidates'][0]['finishReason']='MAX_TOKENS';invalid.append(truncated)
        extra = copy.deepcopy(good);extra['candidates'].append(good['candidates'][0]);invalid.append(extra)
        for value in invalid:
            with self.subTest(value=value), self.assertRaisesRegex(MediaError, 'gemini_response_invalid'):
                gemini.translations(value, ['0'])
        for value in ({'promptFeedback':{'blockReason':'SAFETY'}}, {'candidates':[{'finishReason':'SAFETY'}]}):
            with self.assertRaisesRegex(MediaError, 'gemini_blocked'):
                gemini.translations(value, ['0'])


class GeminiJobTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.RetranslationTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.RetranslationTests.tearDownClass.__func__)
    tearDown = fixtures.RetranslationTests.tearDown
    make_source = fixtures.RetranslationTests.make_source

    def setUp(self):
        fixtures.RetranslationTests.setUp(self)
        key = patch.dict(os.environ, {'GEMINI_API_KEY':'synthetic-key'})
        key.start();self.addCleanup(key.stop)

    def seed_source(self, texts=None):
        old, track = self.make_source()
        if texts:
            value = document([{'start':i*.3, 'end':i*.3+.2, 'text':t} for i,t in enumerate(texts)])
            self.jobs.update(old, transcript=value, transcript_sha=hashlib.sha256(value.encode()).hexdigest())
        return old, track

    def queue(self, track):
        return self.jobs.retranslate(self.item['id'], track, 'gemini')

    def test_saved_source_text_only_append_only_and_no_local_runtime(self):
        old, track = self.seed_source(['Before.', '한국어.', 'After.'])
        original = self.jobs.row(old);vtt=self.jobs.track(self.item['id'],track)
        media = self.store.file_path(self.store._row(self.item['id'])).read_bytes()
        calls = []
        def capture(body, key, model):
            calls.append(body)
            self.assertEqual(key, 'synthetic-key')
            self.assertEqual(model, 'gemini-3.1-flash-lite')
            return reply(body,key)
        with (patch('media_clarity.models.LocalModels',side_effect=AssertionError('local runtime loaded')),
              patch('media_clarity.gemini.request',side_effect=capture)):
            jid = self.queue(track);execute(self.store,jid)
        row = self.jobs.row(jid)
        self.assertEqual(row['state'],'succeeded');self.assertEqual(row['fallback_count'],0)
        targets=json.loads(calls[0]['contents'][0]['parts'][0]['text'])
        self.assertEqual(targets,[{'id':'0','text':'Before.','before':'','after':'한국어.'},
                                  {'id':'1','text':'After.','before':'한국어.','after':''}])
        self.assertEqual(set(calls[0]),{'systemInstruction','contents','generationConfig'})
        self.assertEqual(calls[0]['systemInstruction']['parts'][0]['text'],gemini.PROMPT)
        self.assertEqual(row['transcript'],original['transcript'])
        self.assertEqual(row['translation_config'],gemini.CONFIG)
        status=self.jobs.status(self.item['id'])
        self.assertTrue(status['gemini_configured'])
        self.assertEqual(next(t for t in status['tracks'] if t['id']!=track)['provider'],'gemini')
        self.assertNotIn('synthetic-key',document(status))
        self.assertNotIn('translation_config',document(status))
        self.store.close();self.store.start();self.jobs=Jobs(self.store)
        self.assertEqual(self.jobs.row(old),original)
        self.assertEqual(self.jobs.track(self.item['id'],track),vtt)
        self.assertEqual(self.store.file_path(self.store._row(self.item['id'])).read_bytes(),media)
        self.assertEqual((self.root/'calls').read_text().count('asr'),1)

    def test_checkpoint_survives_process_exit_resume_only_remaining_and_key_rotation(self):
        _,track=self.seed_source([f'Line {i}.' for i in range(10)])
        jid=self.queue(track)
        script = '''import sys
from pathlib import Path
from unittest.mock import patch
from media_clarity.storage import Store, MediaError
from media_clarity.jobs import execute
from tests.test_gemini import reply
root=Path(sys.argv[1]); calls=0
def transport(body,key,model):
    global calls
    calls+=1
    if calls==2: raise MediaError('gemini_quota',503)
    return reply(body,key)
with patch('media_clarity.gemini.request',side_effect=transport):
    execute(Store(root),sys.argv[2])
'''
        subprocess.run([sys.executable,'-c',script,str(self.root),jid],check=True,capture_output=True,timeout=30)
        row=self.jobs.row(jid)
        self.assertEqual((row['state'],row['error'],row['completed']),('failed','gemini_quota',8))
        self.assertEqual(len(self.jobs.status(self.item['id'])['tracks']),1)
        self.store.close();self.store.start();self.jobs=Jobs(self.store)
        with patch.dict(os.environ,{'GEMINI_API_KEY':'rotated-synthetic-key'}),patch('media_clarity.gemini.request',side_effect=reply) as transport:
            self.jobs.action(jid,'resume');execute(self.store,jid)
        self.assertEqual(self.jobs.row(jid)['state'],'succeeded')
        self.assertEqual(transport.call_count,1)
        targets=json.loads(transport.call_args.args[0]['contents'][0]['parts'][0]['text'])
        self.assertEqual([t['text'] for t in targets],['Line 8.','Line 9.'])
        self.assertEqual(targets[0]['before'],'Line 7.')
        self.assertEqual(self.jobs.row(jid)['config_sha'],row['config_sha'])

    def test_restart_keeps_provider_source_and_failed_preflight_rolls_back(self):
        old,track=self.seed_source();jid=self.queue(track);self.jobs.action(jid,'pause')
        before=self.jobs.row(jid)
        with patch.dict(os.environ,{'GEMINI_API_KEY':''}),self.assertRaisesRegex(MediaError,'gemini_key_missing'):
            self.jobs.action(jid,'restart')
        self.assertEqual(self.jobs.row(jid),before)
        self.jobs.action(jid,'restart')
        with self.store.db() as db:
            successor=dict(db.execute("SELECT * FROM subtitle_jobs WHERE state='queued'").fetchone())
        self.assertEqual(successor['translation_config'],gemini.CONFIG)
        self.assertEqual(successor['source_track_id'],track)
        self.assertEqual(successor['transcript'],self.jobs.row(old)['transcript'])

    def test_legacy_31_job_resumes_and_restarts_with_original_prompt(self):
        self.check_legacy_recovery('gemini-3.1-flash-lite')

    def test_legacy_38_job_resumes_and_restarts_with_original_prompt(self):
        self.check_legacy_recovery('gemini-3.8-flash')

    def check_legacy_recovery(self, model):
        from media_clarity.jobs import saved_transcript
        _,track=self.seed_source()
        legacy=gemini.CONFIGS[model]
        self.assertEqual(gemini.model_for(gemini.CONFIG),'gemini-3.1-flash-lite')
        media=self.store._row(self.item['id'])
        with self.store.db() as db:
            seed=saved_transcript(db,media,track)
            jid=self.jobs._queue_translation(db,media,seed,legacy);db.commit()
        before=self.jobs.row(jid)
        self.store.close();self.store.start();self.jobs=Jobs(self.store)
        self.jobs.action(jid,'pause');self.jobs.action(jid,'resume')
        with patch('media_clarity.gemini.request',side_effect=reply) as transport:
            execute(self.store,jid)
        self.assertEqual(self.jobs.row(jid)['state'],'succeeded')
        self.assertEqual(transport.call_args.args[2],model)
        self.assertEqual(transport.call_args.args[0]['systemInstruction']['parts'][0]['text'],gemini.LEGACY_PROMPT)
        self.assertEqual(self.jobs.row(jid)['config_sha'],before['config_sha'])
        # A paused historical job restarts with its saved model, not today's choice.
        with self.store.db() as db:
            old=self.jobs._queue_translation(db,media,seed,legacy);db.commit()
        self.jobs.action(old,'pause');self.jobs.action(old,'restart')
        with self.store.db() as db:
            successor=dict(db.execute("SELECT * FROM subtitle_jobs WHERE state='queued'").fetchone())
        self.assertEqual(successor['translation_config'],legacy)
        self.assertEqual(successor['config_sha'],before['config_sha'])
        with patch('media_clarity.gemini.request',side_effect=reply) as transport:
            execute(self.store,successor['id'])
        self.assertEqual(transport.call_args.args[2],model)
        self.assertEqual(transport.call_args.args[0]['systemInstruction']['parts'][0]['text'],gemini.LEGACY_PROMPT)


    def test_tampering_and_refusal_never_send_or_publish(self):
        _,track=self.seed_source()
        changes=({'config_sha':None},{'translation_config':'{}'},{'transcript_sha':'0'*64},
                 {'source_track_id':None},{'completed':1})
        for change in changes:
            with self.subTest(change=change):
                jid=self.queue(track)
                with self.store.db() as db:
                    db.execute('UPDATE subtitle_jobs SET '+','.join(k+'=?' for k in change)+' WHERE id=?',(*change.values(),jid));db.commit()
                with patch('media_clarity.gemini.request') as transport:
                    execute(self.store,jid)
                transport.assert_not_called();self.assertEqual(self.jobs.row(jid)['state'],'failed')
        jid=self.queue(track)
        with patch('media_clarity.gemini.request',return_value={'promptFeedback':{'blockReason':'SAFETY'}}):
            execute(self.store,jid)
        self.assertEqual(self.jobs.row(jid)['error'],'gemini_blocked')
        self.assertEqual(self.jobs.row(jid)['completed'],0)
        self.assertEqual(len(self.jobs.status(self.item['id'])['tracks']),1)

    def test_korean_passthrough_sends_nothing(self):
        _,track=self.seed_source(['안녕하세요.', '다음 장면입니다.']);jid=self.queue(track)
        with patch('media_clarity.gemini.request') as transport:
            execute(self.store,jid)
        transport.assert_not_called();self.assertEqual(self.jobs.row(jid)['state'],'succeeded')

    def test_http_explicit_provider_validation_missing_key_and_active_conflict(self):
        _,track=self.seed_source();self.store.close()
        with patch.object(Jobs,'start',lambda jobs:jobs.init()),patch('media_clarity.gemini.request') as transport,TestClient(create_app(self.root),base_url='http://127.0.0.1:8765') as client:
            url=f"/api/library/{self.item['id']}/subtitles/{track}/retranslate"
            headers={'X-Media-Token':client.get('/api/session').json()['token']}
            self.assertEqual(client.post(url,json={'provider':'gemini'}).status_code,403)
            for body in ({'provider':'other'},{'provider':{}},{'provider':'gemini','key':'synthetic'},[],None):
                self.assertEqual(client.post(url,content=json.dumps(body),headers=headers).status_code,422)
            self.assertEqual(client.post(url,content='x'*2049,headers=headers).status_code,422)
            with patch.dict(os.environ,{'GEMINI_API_KEY':''}):
                result=client.post(url,json={'provider':'gemini'},headers=headers)
                self.assertEqual((result.status_code,result.json()['error']),(503,'gemini_key_missing'))
                self.assertEqual(len(client.app.state.jobs.status(self.item['id'])['jobs']),1)
            result=client.post(url,json={'provider':'gemini'},headers=headers)
            self.assertEqual(result.status_code,202);jid=result.json()['id']
            self.assertEqual(client.post(url,json={'provider':'gemini'},headers=headers).json()['id'],jid)
            self.assertEqual(client.post(url,headers=headers).json()['id'],jid)
            transport.assert_not_called()

    def test_v7_upgrade_preserves_rows_and_identity_without_cloud_selection(self):
        self.seed_source()
        with self.store.db() as db:
            before={t:[dict(r) for r in db.execute(f'SELECT * FROM {t}')]
                    for t in ('subtitle_jobs','subtitle_tracks','companion_identity')}
        self.store.close()
        with closing(sqlite3.connect(self.root/'library.sqlite3')) as db,db:
            db.execute('ALTER TABLE subtitle_jobs DROP COLUMN translation_config')
            db.execute('PRAGMA user_version=7')
        self.store.start()
        with self.store.db() as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],9)
            for table,rows in before.items():
                self.assertEqual([dict(r) for r in db.execute(f'SELECT * FROM {table}')],rows)
