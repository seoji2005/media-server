"""Synthetic model results exercise real DB, subprocess interruption and HTTP paths."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import time
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from media_clarity.app import create_app
from media_clarity.jobs import Jobs, execute, document, translate_chunk
from media_clarity.storage import Store, MediaError
from media_clarity.subtitles import parse_srt, validate_cues, webvtt, translation_units

SRT = '1\n00:00:00,100 --> 00:00:01,900\n안녕하세요 <b>여러분</b>\n\n2\n00:00:02,000 --> 00:00:03,500\n다음 장면입니다.\n'

class FixtureModel:
    def __init__(self, root):
        self.root = root
    def identity(self):
        return 'fixture-v1'
    def transcribe(self, path, duration, audio_index=0):
        with (self.root/'calls').open('a') as f:
            f.write('asr\n')
        return [{'start':.1,'end':1.9,'text':'hello.'}, {'start':2.,'end':3.5,'text':'next.'}]
    def translate(self, text):
        text = text.removesuffix('.')
        with (self.root/'calls').open('a') as f:
            f.write('translate-'+text+'\n')
        if text == 'next' and (self.root/'fail').exists():
            raise RuntimeError('private-content-must-not-be-recorded')
        if text == 'next' and (self.root/'block').exists():
            (self.root/'entered').touch()
            time.sleep(30)
        return '안녕하세요' if text == 'hello' else '다음 장면입니다.'
    def close(self):
        pass

class SubtitleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = tempfile.TemporaryDirectory()
        cls.source = Path(cls.fixtures.name)/'fixture.mp4'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=10','-f','lavfi','-i','sine=frequency=300','-t','4','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(cls.source)], check=True, capture_output=True)
    @classmethod
    def tearDownClass(cls):
        cls.fixtures.cleanup()
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)/'store'
        self.store = Store(self.root); self.store.start()
        self.item = self.store.import_path(self.source)['item']
        self.jobs = Jobs(self.store); self.jobs.init()
    def tearDown(self):
        self.jobs.close(); self.store.close(); self.temp.cleanup()
    def enqueue(self):
        with patch('media_clarity.models.local_models'):
            return self.jobs.enqueue(self.item['id'])
    def run_job(self, job_id):
        execute(self.store,job_id,FixtureModel)
    def test_srt_timing_text_and_append_only_versions(self):
        first = self.jobs.import_srt(self.item['id'],SRT.encode())
        second = self.jobs.import_srt(self.item['id'],SRT.replace('여러분','친구들').encode())
        self.assertNotEqual(first,second)
        self.assertIn('여러분',self.jobs.track(self.item['id'],first))
        self.assertIn('친구들',self.jobs.track(self.item['id'],second))
        with self.assertRaisesRegex(MediaError,'subtitles_already_available'):
            self.jobs.enqueue(self.item['id'])
        literal=webvtt([{'start':0,'end':1,'text':'<script> & -->'}])
        self.assertNotIn('<script>',literal); self.assertIn('&lt;script&gt;',literal)
        clipped, notes = parse_srt(SRT.replace('03,500','09,500').encode(),4,report=True)
        self.assertEqual(clipped[-1]['end'],4);self.assertEqual(notes['clipped'],1)
        for bad in [SRT.replace('01,900','00,050'),'abc',SRT.replace('00:00:02','00:67:02')]:
            with self.subTest(bad=bad), self.assertRaises(MediaError): parse_srt(bad.encode(),4)
        for value in [True,float('nan'),float('inf')]:
            with self.assertRaises(MediaError):validate_cues([{'start':value,'end':3,'text':'x'}],4)
    def test_literal_angles_and_original_upload_bytes_survive(self):
        raw = SRT.replace('안녕하세요 <b>여러분</b>', '<Enter> 키를 누르세요. 0 < 값 > 10').encode()
        track = self.jobs.import_srt(self.item['id'], raw)
        vtt = self.jobs.track(self.item['id'], track)
        self.assertIn('&lt;Enter&gt; 키를 누르세요. 0 &lt; 값 &gt; 10', vtt)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT source_srt FROM subtitle_tracks WHERE id=?',(track,)).fetchone()[0],raw)

    def test_transcript_captions_follow_selected_version_and_survive_restart(self):
        jid = self.enqueue(); self.run_job(jid)
        track = self.jobs.status(self.item['id'])['tracks'][0]
        korean = self.jobs.track(self.item['id'], track['id'])
        original = self.jobs.track(self.item['id'], track['id'], transcript=True)
        self.assertTrue(track['has_transcript'])
        self.assertEqual(original, webvtt(json.loads(self.jobs.row(jid)['transcript'])))
        self.assertIn('00:00:00.100 --> 00:00:01.900\nhello.', original)
        class Other(FixtureModel):
            def transcribe(self, *args):
                return [{'start':.2,'end':3.2,'text':'日本語 <voice> & English.'}]
        with patch('media_clarity.models.local_models'):
            newer = self.jobs.enqueue(self.item['id'], force=True)
        execute(self.store, newer, Other)
        supplied = self.jobs.import_srt(self.item['id'], SRT.encode())
        self.assertFalse(next(t for t in self.jobs.status(self.item['id'])['tracks'] if t['id']==supplied)['has_transcript'])
        self.jobs.close(); self.store.close(); self.store.start(); self.jobs = Jobs(self.store)
        self.assertEqual(self.jobs.track(self.item['id'], track['id']), korean)
        self.assertEqual(self.jobs.track(self.item['id'], track['id'], transcript=True), original)
        with self.store.db() as db:
            new_track = db.execute('SELECT id FROM subtitle_tracks WHERE job_id=?', (newer,)).fetchone()[0]
        shown = self.jobs.track(self.item['id'], new_track, transcript=True)
        self.assertIn('日本語 &lt;voice&gt; &amp; English.', shown)
        self.assertNotIn('<voice>', shown)

    def test_transcript_rejects_corruption_or_wrong_audio_input_without_breaking_korean(self):
        jid = self.enqueue(); self.run_job(jid)
        track = self.jobs.status(self.item['id'])['tracks'][0]['id']
        korean = self.jobs.track(self.item['id'], track)
        before = self.jobs.row(jid)
        changes = [({'transcript_sha':'0'*64}, 'subtitle_changed'),
                   ({'transcript':'{','transcript_sha':hashlib.sha256(b'{').hexdigest()}, 'subtitle_changed'),
                   ({'transcript':'{}','transcript_sha':hashlib.sha256(b'{}').hexdigest()}, 'subtitle_changed'),
                   ({'input_sha':'wrong-input'}, 'subtitle_not_found'),
                   ({'audio_index':1}, 'subtitle_not_found'),
                   ({'transcript':None}, 'subtitle_not_found')]
        for change, code in changes:
            with self.subTest(change=tuple(change)):
                with self.store.db() as db:
                    db.execute('UPDATE subtitle_jobs SET '+','.join(f'{key}=?' for key in change)+' WHERE id=?', (*change.values(),jid)); db.commit()
                try:
                    with self.assertRaisesRegex(MediaError, code):
                        self.jobs.track(self.item['id'], track, transcript=True)
                    self.assertEqual(self.jobs.track(self.item['id'], track), korean)
                    if code == 'subtitle_not_found':
                        self.assertFalse(self.jobs.status(self.item['id'])['tracks'][0]['has_transcript'])
                finally:
                    with self.store.db() as db:
                        db.execute('UPDATE subtitle_jobs SET '+','.join(f'{key}=?' for key in change)+' WHERE id=?', (*(before[key] for key in change),jid)); db.commit()

    def test_transcript_http_is_read_only_and_supplied_tracks_have_no_asr(self):
        jid = self.enqueue(); self.run_job(jid)
        track = self.jobs.status(self.item['id'])['tracks'][0]['id']
        source_vtt = self.jobs.track(self.item['id'],track,transcript=True)
        supplied = self.jobs.import_srt(self.item['id'],SRT.encode())
        before = self.jobs.row(jid)
        self.jobs.close(); self.store.close()
        with TestClient(create_app(self.root), base_url='http://127.0.0.1:8765') as client:
            url = f'/api/library/{self.item["id"]}/subtitles/'
            result = client.get(url+track+'.vtt?transcript=true')
            self.assertEqual(result.status_code,200)
            self.assertEqual(result.text,source_vtt)
            self.assertTrue(result.headers['content-type'].startswith('text/vtt'))
            self.assertEqual(client.get(url+supplied+'.vtt?transcript=true').status_code,404)
            self.assertEqual(client.get(url+'f'*32+'.vtt?transcript=true').status_code,404)
        self.store.start(); self.jobs = Jobs(self.store)
        self.assertEqual(self.jobs.row(jid),before)

    def test_missing_identity_and_erased_checkpoint_fail_closed(self):
        for mutation in ({'config_sha':None},{'transcript':None},{}):
            with self.subTest(mutation=mutation):
                job_id=self.enqueue(); (self.root/'fail').touch(); self.run_job(job_id)
                if not mutation:
                    with self.store.db() as db:
                        db.execute('DELETE FROM subtitle_batches WHERE job_id=?',(job_id,));db.commit()
                self.jobs.update(job_id,**mutation,state='queued');self.run_job(job_id)
                row=self.jobs.row(job_id)
                self.assertEqual(row['state'],'failed');self.assertEqual(row['error'],'processing_checkpoint_invalid')
                self.assertEqual(self.jobs.status(self.item['id'])['tracks'],[])

    def test_worker_lease_blocks_restart_until_old_child_exits(self):
        job_id=self.enqueue()
        self.jobs.update(job_id,state='running',attempt=1)
        code="from pathlib import Path;from media_clarity.jobs import worker_guard;import sys,ctypes,os;root=Path(sys.argv[1]);guard=worker_guard(root);guard.__enter__();(root/'lease-ready').touch();(ctypes.PyDLL('kernel32').Sleep(30000) if os.name=='nt' else ctypes.PyDLL(None).sleep(30))"
        child=subprocess.Popen([sys.executable,'-c',code,str(self.root)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            deadline=time.monotonic()+5
            while not (self.root/'lease-ready').exists() and time.monotonic()<deadline:time.sleep(.02)
            self.assertTrue((self.root/'lease-ready').exists())
            self.jobs.init(recover=True)
            self.assertTrue(self.jobs.recovery_pending)
            self.assertEqual(self.jobs.row(job_id)['state'],'running')
            with self.assertRaisesRegex(MediaError,'processing_worker_active'):self.jobs.action(job_id,'resume')
            with self.assertRaisesRegex(MediaError,'processing_worker_active'):self.run_job(job_id)
            child.kill();child.wait(timeout=5)
            self.jobs.recover();self.assertFalse(self.jobs.recovery_pending)
            self.assertEqual(self.jobs.row(job_id)['state'],'paused')
        finally:
            if child.poll() is None:child.kill();child.wait()

    def test_real_local_audio_decode_passes_samples_to_asr(self):
        import builtins
        from media_clarity.models import LocalModels
        observed = {}
        original_import = builtins.__import__
        def checked_import(name, *args, **kwargs):
            if name == 'onnxruntime':
                raise AssertionError('ORT must not be loaded')
            if name == 'faster_whisper':
                self.assertIsNone(sys.modules['onnxruntime'])
            return original_import(name, *args, **kwargs)
        class WhisperStub:
            def __init__(inner, model, **options):
                observed['options'] = options
            def transcribe(inner, samples, **options):
                observed['samples'] = len(samples)
                observed['transcribe'] = options
                def segments():
                    observed['materialized'] = True
                    yield types.SimpleNamespace(start=.1, end=1.9, text=' synthetic ASR ')
                return segments(), None
        backend=object.__new__(LocalModels)
        backend.paths={'asr':self.root/'unused-model'};backend.device='cpu'
        np=types.SimpleNamespace(frombuffer=lambda data,dtype:memoryview(data).cast('f'))
        with patch.dict(sys.modules,{'onnxruntime':None,'numpy':np,'faster_whisper':types.SimpleNamespace(WhisperModel=WhisperStub)}), patch('builtins.__import__',side_effect=checked_import), patch.object(backend,'speech_clips',return_value=[.1,1.9,2.,3.5]):
            cues=backend.transcribe(self.source,4)
        self.assertFalse(observed['transcribe']['vad_filter'])
        self.assertEqual(observed['transcribe']['clip_timestamps'],[.1,1.9,2.,3.5])
        self.assertTrue(observed['options']['local_files_only'])
        self.assertTrue(observed['transcribe']['multilingual'])
        self.assertGreater(observed['samples'],60000)
        self.assertLess(observed['samples'],70000)
        self.assertTrue(observed['materialized']);self.assertEqual(cues[0]['text'],'synthetic ASR')

    def test_loaded_ort_is_rejected_before_model_import_or_job_creation(self):
        from media_clarity.models import LocalModels
        with patch.dict(sys.modules,{'onnxruntime':object()}), patch('builtins.__import__',side_effect=AssertionError('unexpected runtime import')):
            with self.assertRaisesRegex(MediaError,'model_privacy_setup_required'):
                LocalModels(self.root)
            with self.assertRaisesRegex(MediaError,'model_privacy_setup_required'):
                object.__new__(LocalModels).transcribe(self.source,4)
        with patch.dict(sys.modules,{'onnxruntime':object()}):
            with self.assertRaisesRegex(MediaError,'model_privacy_setup_required'):
                self.jobs.enqueue(self.item['id'])
        self.assertEqual(self.jobs.status(self.item['id'])['jobs'],[])

    def test_clean_windows_process_can_check_setup_but_cannot_import_ort(self):
        import importlib
        from media_clarity.models import require_private_runtime
        with patch.dict(sys.modules,{'onnxruntime':None}), patch('media_clarity.models.sys.platform','win32'):
            require_private_runtime()
            with self.assertRaises(ModuleNotFoundError):importlib.import_module('onnxruntime')
            # Missing weights are now the setup diagnostic, not a blanket OS veto.
            with self.assertRaisesRegex(MediaError,'local_models_missing'):self.jobs.enqueue(self.item['id'])

    def test_no_detected_speech_does_not_load_asr(self):
        from media_clarity.models import LocalModels
        backend=object.__new__(LocalModels);backend.device='cpu'
        whisper=types.SimpleNamespace(WhisperModel=lambda *a,**kw:self.fail('ASR loaded for silence'))
        np=types.SimpleNamespace(frombuffer=lambda data,dtype:memoryview(data).cast('f'))
        with patch.dict(sys.modules,{'onnxruntime':None,'numpy':np,'faster_whisper':whisper}),patch.object(backend,'speech_clips',return_value=[]):
            self.assertEqual(backend.transcribe(self.source,4),[])

    def test_restart_preserves_failed_checkpoint_and_existing_subtitles(self):
        job_id=self.enqueue(); (self.root/'fail').touch(); self.run_job(job_id)
        old=self.jobs.row(job_id)
        track=self.jobs.import_srt(self.item['id'],SRT.encode())
        with patch('media_clarity.models.local_models'):self.jobs.action(job_id,'restart')
        preserved=self.jobs.row(job_id)
        self.assertEqual(preserved['state'],'superseded')
        self.assertEqual(preserved['transcript'],old['transcript'])
        self.assertEqual(preserved['translation'],old['translation'])
        current=next(j for j in self.jobs.status(self.item['id'])['jobs'] if j['state']=='queued')
        self.assertNotEqual(current['id'],job_id)
        self.assertIsNone(self.jobs.row(current['id'])['transcript'])
        self.assertIn('안녕하세요',self.jobs.track(self.item['id'],track))

    def test_stale_attempt_cannot_checkpoint_or_publish(self):
        job_id=self.enqueue();self.jobs.update(job_id,state='running',attempt=2)
        stale=Jobs(self.store);stale.expected_attempt=1
        with self.assertRaisesRegex(MediaError,'processing_interrupted'):
            stale.update(job_id,state='failed',error='stale')
        with self.assertRaisesRegex(MediaError,'processing_interrupted'):
            stale.publish(self.store._row(self.item['id']),parse_srt(SRT.encode(),4),'generated',job_id)
        self.assertEqual(self.jobs.status(self.item['id'])['tracks'],[])
        self.assertEqual(self.jobs.row(job_id)['state'],'running')

    def test_failure_resume_reuses_transcript_and_translated_cue(self):
        job_id = self.enqueue(); (self.root/'fail').touch(); self.run_job(job_id)
        failed=self.jobs.row(job_id)
        self.assertEqual((failed['state'],failed['completed']),('failed',1))
        self.assertEqual(failed['error'],'processing_failed')
        self.assertEqual(self.jobs.status(self.item['id'])['tracks'],[])
        (self.root/'fail').unlink()
        with patch('media_clarity.models.local_models'): self.jobs.action(job_id,'resume')
        self.run_job(job_id)
        self.assertEqual(self.jobs.row(job_id)['state'],'succeeded')
        calls=(self.root/'calls').read_text().splitlines()
        self.assertEqual(calls.count('asr'),1);self.assertEqual(calls.count('translate-hello'),1)
        self.assertEqual(calls.count('translate-next'),2)
        self.assertEqual(len(self.jobs.status(self.item['id'])['tracks']),1)
        self.assertIn('다음 장면',self.jobs.track(self.item['id'],self.jobs.status(self.item['id'])['tracks'][0]['id']))
    def test_actual_child_kill_and_restart_recovery(self):
        job_id=self.enqueue();(self.root/'block').touch()
        code="from pathlib import Path;from test_subtitles import FixtureModel;from media_clarity.jobs import execute;from media_clarity.storage import Store;import sys;execute(Store(Path(sys.argv[1])),sys.argv[2],FixtureModel)"
        child=subprocess.Popen([sys.executable,'-c',code,str(self.root),job_id],env={**os.environ,'PYTHONPATH':str(Path('tests').absolute())},stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+10
            while not (self.root/'entered').exists() and time.monotonic()<deadline:
                if child.poll() is not None: self.fail(child.communicate()[1].decode())
                time.sleep(.03)
            self.assertTrue((self.root/'entered').exists())
            child.kill();child.wait(timeout=5)
        finally:
            if child.poll() is None: child.kill();child.wait()
            child.stdout.close();child.stderr.close()
        self.store.close();self.store.start();self.jobs.init(recover=True)
        row=self.jobs.row(job_id);self.assertEqual(row['state'],'paused');self.assertEqual(row['completed'],1)
        (self.root/'block').unlink()
        with patch('media_clarity.models.local_models'):self.jobs.action(job_id,'resume')
        self.run_job(job_id);self.assertEqual(self.jobs.row(job_id)['state'],'succeeded')
        self.assertEqual((self.root/'calls').read_text().count('asr'),1)
    def test_changed_config_checkpoint_or_media_cannot_publish(self):
        for mutation in ['config','transcript','media']:
            with self.subTest(mutation=mutation):
                job_id=self.enqueue();(self.root/'fail').touch();self.run_job(job_id)
                if mutation=='config':self.jobs.update(job_id,config_sha='changed')
                elif mutation=='transcript':self.jobs.update(job_id,transcript=self.jobs.row(job_id)['transcript'].replace('hello','other'))
                else:
                    path=self.store.file_path(self.store._row(self.item['id']))
                    data=bytearray(path.read_bytes());data[-1]^=1;path.write_bytes(data)
                self.jobs.update(job_id,state='queued');self.run_job(job_id)
                self.assertEqual(self.jobs.row(job_id)['state'],'failed')
                self.assertEqual(self.jobs.status(self.item['id'])['tracks'],[])
                if mutation=='media': break
    def test_missing_model_diagnostic_and_private_http_boundary(self):
        self.store.close()
        app=create_app(self.root)
        with TestClient(app,base_url='http://127.0.0.1:8765') as client:
            headers={'X-Media-Token':client.get('/api/session').json()['token']}
            url=f"/api/library/{self.item['id']}/subtitle-jobs"
            self.assertEqual(client.post(url).status_code,403)
            r=client.post(url,headers=headers);self.assertEqual(r.status_code,503);self.assertEqual(r.json()['error'],'gemini_key_missing')
            url=f"/api/library/{self.item['id']}/subtitles"
            self.assertEqual(client.post(url,headers=headers,content=b'x'*(2*1024*1024+1)).status_code,413)
            r=client.post(url,headers=headers,content=SRT.encode());self.assertEqual(r.status_code,201)
            vtt=client.get(url+'/'+r.json()['id']+'.vtt');self.assertEqual(vtt.status_code,200)
            self.assertIn('WEBVTT',vtt.text);self.assertIn('안녕하세요 여러분',vtt.text)
            self.assertEqual(vtt.headers['cache-control'],'no-store')
            self.assertEqual(client.get(url,headers={'Origin':'https://foreign.example'}).status_code,403)
            self.assertEqual(client.get(f"/api/media/{self.item['id']}/content",headers={'Range':'bytes=0-99'}).status_code,206)
    def test_track_tampering_is_rejected_and_original_preserved(self):
        track=self.jobs.import_srt(self.item['id'],SRT.encode())
        with self.store.db() as db:
            db.execute("UPDATE subtitle_tracks SET cues=replace(cues,'안녕하세요','변경됐어요') WHERE id=?",(track,));db.commit()
        with self.assertRaisesRegex(MediaError,'subtitle_changed'):self.jobs.track(self.item['id'],track)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),self.item['sha256'])

    def test_cp949_and_euc_kr_preserve_upload_bytes(self):
        for encoding, text in [('cp949',SRT.replace('여러분','똠방각하')),('euc-kr',SRT)]:
            raw=text.encode(encoding);track=self.jobs.import_srt(self.item['id'],raw)
            self.assertIn('똠방각하' if encoding=='cp949' else '여러분',self.jobs.track(self.item['id'],track))
            with self.store.db() as db:
                self.assertEqual(db.execute('SELECT source_srt FROM subtitle_tracks WHERE id=?',(track,)).fetchone()[0],raw)
        with self.assertRaisesRegex(MediaError,'subtitle_encoding_unsupported'):
            parse_srt(b'\xff',4)

    def test_regenerate_http_preserves_supplied_track_and_deduplicates(self):
        track=self.jobs.import_srt(self.item['id'],SRT.encode());before=self.jobs.track(self.item['id'],track)
        self.store.close()
        with patch('media_clarity.gemini.api_key',return_value='synthetic-key'),patch.object(Jobs,'start',lambda jobs:jobs.init(recover=True)), patch('media_clarity.qwen.local_models'), TestClient(create_app(self.root),base_url='http://127.0.0.1:8765') as client:
            headers={'X-Media-Token':client.get('/api/session').json()['token']}
            url=f"/api/library/{self.item['id']}/subtitle-jobs"
            self.assertEqual(client.post(url,headers=headers).json()['error'],'subtitles_already_available')
            self.assertEqual(client.post(url+'/regenerate').status_code,403)
            first=client.post(url+'/regenerate',headers=headers)
            self.assertEqual(first.status_code,202)
            self.assertEqual(client.post(url+'/regenerate',headers=headers).json(),first.json())
            self.assertEqual(client.get(f"/api/library/{self.item['id']}/subtitles/{track}.vtt").text,before)

    def test_failed_translation_units_publish_marked_source_and_resume(self):
        class Batched(FixtureModel):
            batch_size=2;checkpoint_size=20
            def transcribe(inner,path,duration,audio_index=0):
                self.assertEqual(path,self.store.file_path(self.store._row(self.item['id'])))
                return [{'start':i*.5,'end':i*.5+.4,'text':text} for i,text in enumerate(['Hello.','Too long.','Empty.','Truncated.','안녕하세요.','Finish.'])]
            def translate_many(inner,texts):
                if texts==['Finish.']:
                    raise RuntimeError('private diagnostic')
                values={'Hello.':'안녕.','Too long.':MediaError('translation_input_too_long',422),'Empty.':None,'Truncated.':MediaError('translation_truncated',422)}
                return [values[text] for text in texts]
        job=self.enqueue();execute(self.store,job,Batched)
        row=self.jobs.row(job);self.assertEqual((row['state'],row['completed'],row['fallback_count']),('failed',4,3))
        with self.store.db() as db:
            before=[tuple(r) for r in db.execute('SELECT * FROM subtitle_batches WHERE job_id=?',(job,))]
        class Resumed(Batched):
            def transcribe(inner,*args):raise AssertionError('ASR repeated')
            def translate_many(inner,texts):
                self.assertEqual(texts,['Finish.']);return ['끝.']
        with patch('media_clarity.models.local_models'):self.jobs.action(job,'resume')
        execute(self.store,job,Resumed)
        row=self.jobs.row(job);self.assertEqual((row['state'],row['completed'],row['fallback_count']),('succeeded',6,3))
        track=self.jobs.status(self.item['id'])['tracks'][0];self.assertEqual(track['fallback_count'],3)
        vtt=self.jobs.track(self.item['id'],track['id']);self.assertEqual(vtt.count('[원문]'),3)
        self.assertIn('[원문] Too long.',vtt);self.assertIn('안녕하세요.',vtt);self.assertIn('끝.',vtt)
        self.assertFalse((self.root/'processing').exists())
        with self.store.db() as db:
            after=[tuple(r) for r in db.execute('SELECT * FROM subtitle_batches WHERE job_id=? ORDER BY first_index',(job,))]
            self.assertEqual(after[:len(before)],before)
            # Warning deletion must not silently turn source fallbacks into translated cues.
            db.execute('UPDATE subtitle_tracks SET warnings=NULL WHERE id=?',(track['id'],));db.commit()
        with self.assertRaisesRegex(MediaError,'subtitle_changed'):self.jobs.track(self.item['id'],track['id'])

    def test_generated_plaintext_and_korean_units_survive_resume_as_saved(self):
        supplied=self.jobs.import_srt(self.item['id'],SRT.encode())
        original=self.jobs.track(self.item['id'],supplied)
        class Content(FixtureModel):
            batch_size=2;checkpoint_size=20
            def transcribe(inner,path,duration,audio_index=0):
                return [{'start':i,'end':i+.8,'text':text} for i,text in enumerate(
                    ['Hello.','한국어 15m입니다.','Keep &quot;.','Finish.'])]
            def translate_many(inner,texts):
                if texts==['Hello.']:return ['&quot;안녕&quot; &lt;b&gt;']
                raise RuntimeError('interrupted')
        with patch('media_clarity.models.local_models'):
            job=self.jobs.enqueue(self.item['id'],force=True)
        execute(self.store,job,Content)
        self.assertEqual(self.jobs.row(job)['completed'],2)
        with self.store.db() as db:
            saved=[tuple(r) for r in db.execute('SELECT * FROM subtitle_batches WHERE job_id=?',(job,))]
        class Resumed(Content):
            def transcribe(inner,*args):raise AssertionError('ASR repeated')
            def translate_many(inner,texts):
                self.assertEqual(texts,['Keep &quot;.','Finish.'])
                return [MediaError('translation_empty',422),'&amp;lt;끝&amp;gt;']
        with patch('media_clarity.models.local_models'):self.jobs.action(job,'resume')
        execute(self.store,job,Resumed)
        self.assertEqual(self.jobs.row(job)['state'],'succeeded')
        with self.store.db() as db:
            after=[tuple(r) for r in db.execute('SELECT * FROM subtitle_batches WHERE job_id=? ORDER BY first_index',(job,))]
            track=db.execute('SELECT id FROM subtitle_tracks WHERE job_id=?',(job,)).fetchone()[0]
        self.assertEqual(after[:len(saved)],saved)
        vtt=self.jobs.track(self.item['id'],track)
        self.assertIn('"안녕" &lt;b&gt;',vtt);self.assertIn('한국어 15m입니다.',vtt)
        self.assertIn('[원문] Keep &amp;quot;.',vtt);self.assertIn('&amp;lt;끝&amp;gt;',vtt)
        self.assertEqual(self.jobs.track(self.item['id'],supplied),original)

    def test_append_checkpoints_and_legacy_track_compatibility(self):
        class Many(FixtureModel):
            batch_size=2;checkpoint_size=20
            def transcribe(inner,path,duration,audio_index=0):
                return [{'start':i*.03,'end':i*.03+.02,'text':'A.'} for i in range(100)]
            def translate_many(inner,texts):return ['가.']*len(texts)
        job=self.enqueue();execute(self.store,job,Many)
        self.assertEqual(self.jobs.row(job)['state'],'succeeded')
        with self.store.db() as db:
            rows=db.execute('SELECT first_index,payload FROM subtitle_batches WHERE job_id=? ORDER BY first_index',(job,)).fetchall()
        self.assertEqual([r['first_index'] for r in rows],[0,20,40,60,80])
        self.assertTrue(all(len(json.loads(r['payload'])['cues'])==20 for r in rows))
        self.assertEqual(self.jobs.row(job)['translation'],'[]','never rewrite the growing prefix')
        # A database from the previous representation still renders old ready tracks.
        legacy=document(parse_srt(SRT.encode(),4));track='a'*32
        with self.store.db() as db:
            db.execute('INSERT INTO subtitle_tracks(id,item_id,input_sha,source,cues,sha256) VALUES(?,?,?,?,?,?)',
                       (track,self.item['id'],self.item['sha256'],'supplied',legacy,hashlib.sha256(legacy.encode()).hexdigest()));db.commit()
        self.assertIn('여러분',self.jobs.track(self.item['id'],track))

    def test_legacy_translation_prefix_can_resume_without_rewrite(self):
        job=self.enqueue();(self.root/'fail').touch();self.run_job(job)
        with self.store.db() as db:
            payload=json.loads(db.execute('SELECT payload FROM subtitle_batches WHERE job_id=?',(job,)).fetchone()[0])
            prefix=document(payload['cues'])
            db.execute('UPDATE subtitle_jobs SET translation=?,translation_sha=? WHERE id=?',(prefix,hashlib.sha256(prefix.encode()).hexdigest(),job))
            db.execute('DELETE FROM subtitle_batches WHERE job_id=?',(job,));db.commit()
        (self.root/'fail').unlink()
        with patch('media_clarity.models.local_models'):self.jobs.action(job,'resume')
        self.run_job(job)
        self.assertEqual(self.jobs.row(job)['state'],'succeeded');self.assertEqual(self.jobs.row(job)['translation'],prefix)
        self.assertEqual((self.root/'calls').read_text().count('translate-hello'),1)

    def test_source_change_during_decode_prevents_checkpoint_and_publish(self):
        class Changed(FixtureModel):
            def transcribe(inner,path,duration,audio_index=0):
                data=bytearray(path.read_bytes());data[-1]^=1;path.write_bytes(data)
                return super().transcribe(path,duration)
        job=self.enqueue();execute(self.store,job,Changed)
        self.assertEqual(self.jobs.row(job)['state'],'failed')
        self.assertIsNone(self.jobs.row(job)['transcript'])
        self.assertEqual(self.jobs.status(self.item['id'])['tracks'],[])
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),self.item['sha256'])

    def test_layout_is_published_after_resume_without_rewriting_units_or_old_tracks(self):
        old=self.jobs.import_srt(self.item['id'],SRT.encode())
        old_vtt=self.jobs.track(self.item['id'],old)
        long_text='중요한 이름과 날짜를 잊지 않으려고 친구에게 다시 물었습니다. 다음 약속은 2026년 10월 11일입니다.'
        class Content(FixtureModel):
            def transcribe(inner,*args):
                return [{'start':.1,'end':2.9,'text':'Long.'}, {'start':3,'end':3.9,'text':'Finish.'}]
            def translate(inner,text):
                if text=='Finish.':raise RuntimeError('private details')
                return long_text
        with patch('media_clarity.models.local_models'):
            job=self.jobs.enqueue(self.item['id'],force=True)
        execute(self.store,job,Content)
        self.assertEqual(self.jobs.row(job)['completed'],1)
        with self.store.db() as db:
            before=[tuple(r) for r in db.execute('SELECT * FROM subtitle_batches WHERE job_id=?',(job,))]
        class Resumed(Content):
            def transcribe(inner,*args):raise AssertionError('ASR repeated')
            def translate(inner,text):
                self.assertEqual(text,'Finish.');return '끝.'
        with patch('media_clarity.models.local_models'):self.jobs.action(job,'resume')
        execute(self.store,job,Resumed)
        self.assertEqual(self.jobs.row(job)['state'],'succeeded')
        with self.store.db() as db:
            after=[tuple(r) for r in db.execute('SELECT * FROM subtitle_batches WHERE job_id=? ORDER BY first_index',(job,))]
            row=dict(db.execute('SELECT * FROM subtitle_tracks WHERE job_id=?',(job,)).fetchone())
        self.assertEqual(after[:len(before)],before)
        units=json.loads(row['cues']);layout=json.loads(row['presentation'])
        self.assertEqual(units[0]['text'],long_text)
        self.assertGreater(len(layout['cues']),len(units))
        for cue,index in zip(layout['cues'],layout['units']):
            self.assertGreaterEqual(cue['start'],units[index]['start'])
            self.assertLessEqual(cue['end'],units[index]['end'])
        rendered=self.jobs.track(self.item['id'],row['id'])
        self.store.close();self.store.start();self.jobs.init(recover=True)
        with patch('media_clarity.jobs.generated_layout',side_effect=AssertionError('old presentation regenerated')):
            self.assertEqual(self.jobs.track(self.item['id'],row['id']),rendered)
        self.assertEqual(self.jobs.track(self.item['id'],old),old_vtt)
        info=next(t for t in self.jobs.status(self.item['id'])['tracks'] if t['id']==row['id'])
        self.assertEqual(info['layout'],'ko-readable-v1')
        self.assertGreater(info['fast_count'],0)
        # Removing the new column must not silently revert a ready track to old layout.
        with self.store.db() as db:
            db.execute('UPDATE subtitle_tracks SET presentation=NULL WHERE id=?',(row['id'],));db.commit()
        with self.assertRaisesRegex(MediaError,'subtitle_changed'):self.jobs.track(self.item['id'],row['id'])

    def test_import_adjustments_are_persisted_with_original_bytes_and_reported_over_http(self):
        raw=('2\n0:00:02,000 --> 0:00:09,000 X1:0 X2:100\n마지막\n\n'
             '1\n0:00:00,100 --> 0:00:01,000\n처음\n\n'
             '3\n0:00:03,000 --> 0:00:03,500\n\n'
             '4\n0:00:05,000 --> 0:00:06,000\n영상 밖').encode('cp949')
        self.store.close()
        with TestClient(create_app(self.root),base_url='http://127.0.0.1:8765') as client:
            headers={'X-Media-Token':client.get('/api/session').json()['token']}
            url=f"/api/library/{self.item['id']}/subtitles"
            r=client.post(url,headers=headers,content=raw)
            self.assertEqual(r.status_code,201)
            track=r.json()['id'];status=client.get(url).json()['tracks'][0]
            self.assertEqual(status['import_notes'],dict(empty=1,outside=1,clipped=1,settings=1,reordered=True))
            vtt=client.get(url+'/'+track+'.vtt').text
            self.assertLess(vtt.index('처음'),vtt.index('마지막'))
            self.assertNotIn('영상 밖',vtt);self.assertNotIn('X1',vtt)
        self.store.start();self.jobs.init()
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT source_srt FROM subtitle_tracks WHERE id=?',(track,)).fetchone()[0],raw)

    def test_overlapping_units_publish_after_resume_with_correct_fallback_children(self):
        text='첫 번째 문장입니다. 두 번째 문장입니다. 세 번째 문장입니다.'
        class Overlap(FixtureModel):
            def transcribe(inner,*args):
                return [{'start':0,'end':3.5,'text':text}, {'start':.5,'end':1.5,'text':'Overlap.'}]
            def translate(inner,source):raise RuntimeError('interrupted translation')
        job=self.enqueue();execute(self.store,job,Overlap)
        self.assertEqual(self.jobs.row(job)['completed'],1)
        class Resume(Overlap):
            def transcribe(inner,*args):raise AssertionError('ASR repeated')
            def translate(inner,source):raise MediaError('translation_empty')
        with patch('media_clarity.models.local_models'):self.jobs.action(job,'resume')
        execute(self.store,job,Resume)
        self.assertEqual(self.jobs.row(job)['state'],'succeeded')
        with self.store.db() as db:
            row=dict(db.execute('SELECT * FROM subtitle_tracks WHERE job_id=?',(job,)).fetchone())
        layout=json.loads(row['presentation'])
        self.assertEqual(layout['units'][:3],[0,1,0])
        vtt=self.jobs.track(self.item['id'],row['id'])
        self.assertEqual(vtt.count('[원문]'),1)
        self.assertIn('[원문] Overlap.',vtt)
        self.assertNotIn('[원문] 두',vtt)


class TranslationUnitTests(unittest.TestCase):
    def test_torch_vad_preserves_original_clips_and_thread_setting_on_error(self):
        from media_clarity.models import LocalModels
        observed={};changes=[]
        model=types.SimpleNamespace(eval=lambda:object())
        torch=types.SimpleNamespace(get_num_threads=lambda:4,set_num_threads=changes.append,
            from_numpy=lambda a:a,jit=types.SimpleNamespace(load=lambda path,**kw:model))
        def speech(audio,model,**options):
            observed.update(options);return [{'start':64000,'end':176000},{'start':240000,'end':336000}]
        backend=object.__new__(LocalModels);backend.paths={'vad':Path('fixture')}
        audio=types.SimpleNamespace(copy=lambda:object())
        with patch.dict(sys.modules,{'onnxruntime':None,'torch':torch,'silero_vad':types.SimpleNamespace(get_speech_timestamps=speech)}):
            self.assertEqual(backend.speech_clips(audio),[4.,11.,15.,21.])
        self.assertEqual(changes,[1,4]);self.assertEqual(observed['min_speech_duration_ms'],0)
        self.assertEqual(observed['min_silence_duration_ms'],2000);self.assertEqual(observed['speech_pad_ms'],400)
        changes.clear()
        with patch.dict(sys.modules,{'onnxruntime':None,'torch':torch,'silero_vad':types.SimpleNamespace(get_speech_timestamps=lambda *a,**kw:(_ for _ in ()).throw(RuntimeError('private detail')))}):
            with self.assertRaises(RuntimeError):backend.speech_clips(audio)
        self.assertEqual(changes,[1,4])

    def test_model_identity_uses_metadata_without_reading_weights(self):
        from media_clarity.models import LocalModels
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);weight=root/'model.safetensors';weight.write_bytes(b'weights')
            backend=object.__new__(LocalModels);backend.paths={'translation':root};backend.device='cpu'
            opened=Path.open
            class MetadataOnly:
                def __init__(self,path,*args,**kwargs):self.stream=opened(path,*args,**kwargs)
                def __enter__(self):return self
                def __exit__(self,*args):self.stream.close()
                def fileno(self):return self.stream.fileno()
                def read(self,*args):raise AssertionError('weight bytes read')
            with patch('media_clarity.models.importlib.metadata.version',return_value='fixture'),patch.object(Path,'open',lambda path,*a,**kw:MetadataOnly(path,*a,**kw)):
                before=backend.identity();self.assertEqual(backend.identity(),before)
            weight.write_bytes(b'changed and longer')
            with patch('media_clarity.models.importlib.metadata.version',return_value='fixture'):
                self.assertNotEqual(backend.identity(),before)

    def test_sentence_join_has_bounded_timing_and_keeps_source(self):
        cues=[{'start':0,'end':1,'text':'When I got home,'},{'start':1.1,'end':3,'text':'I called my mother.'},{'start':3.1,'end':4,'text':'Next.'}]
        before=document(cues);units=translation_units(cues)
        self.assertEqual(units,[{'start':0,'end':3,'text':'When I got home, I called my mother.'},cues[2]])
        self.assertEqual(document(cues),before)
        for first,second in [({'text':'Done。'},{}),({}, {'start':2}),({}, {'end':13}),({'text':'a'*400},{})]:
            pair=[{**cues[0],**first},{**cues[1],**second}]
            self.assertEqual(len(translation_units(pair)),2)

    def test_korean_passthrough_is_per_unit_and_content_failures_are_bounded(self):
        observed=[]
        class Model:
            def translate_many(self,texts):observed.extend(texts);return ['혼합 언어.', 'x'*4001]
        units=[{'start':i,'end':i+.8,'text':t} for i,t in enumerate(['안녕 2026!','Hello 한국어.','Long.'])]
        cues,codes=translate_chunk(Model(),units)
        self.assertEqual(observed,['Hello 한국어.','Long.'])
        self.assertEqual(cues[0]['text'],'안녕 2026!');self.assertEqual(cues[2]['text'],'Long.')
        self.assertEqual(codes,[None,None,'translation_truncated'])

    def test_korean_measurements_pass_through_without_skipping_foreign_words(self):
        preserved=['다리 밑 수직 간격은 15m이며 공사는 2011년 8월에 마무리되었다.',
                   '거리는 1.5 km, 질량은 20kg, 기온은 25°C입니다.', '길이는 20cm & 30mm입니다.']
        foreign=['15minutes 기다리세요.', '25miles 거리입니다.', '15m away입니다.',
                 '높이 15mですが。', '15m', '50GB Download 완료.']
        observed=[]
        class Model:
            def translate_many(self,texts):observed.extend(texts);return ['번역됨.']*len(texts)
        units=[{'start':i,'end':i+.8,'text':t} for i,t in enumerate(preserved+foreign)]
        before=document(units);cues,codes=translate_chunk(Model(),units)
        self.assertEqual([c['text'] for c in cues[:len(preserved)]],preserved)
        self.assertEqual(observed,foreign);self.assertEqual(codes,[None]*len(units))
        self.assertEqual(document(units),before)

    def test_generated_entities_decode_once_and_markup_stays_literal(self):
        class Model:
            def translate_many(self,texts):
                return ['&quot;안녕&#33;&quot; &amp; &lt;script&gt;alert(1)&lt;/script&gt;',
                        '&amp;lt;b&amp;gt;', MediaError('translation_empty',422), '&nbsp;']
        units=[{'start':i,'end':i+.8,'text':t} for i,t in enumerate(
            ['Hello.', 'Nested.', 'Keep &quot; source.', 'Empty.', '한국어 & 15m.'])]
        before=document(units);cues,codes=translate_chunk(Model(),units)
        self.assertEqual(cues[0]['text'],'"안녕!" & <script>alert(1)</script>')
        self.assertEqual(cues[1]['text'],'&lt;b&gt;')
        self.assertEqual(cues[2:],units[2:])
        self.assertEqual(codes,[None,None,'translation_empty','translation_empty',None])
        vtt=webvtt(validate_cues(cues,5),{2,3})
        self.assertIn('"안녕!" &amp; &lt;script&gt;alert(1)&lt;/script&gt;',vtt)
        self.assertNotIn('<script>',vtt);self.assertIn('&amp;lt;b&amp;gt;',vtt)
        self.assertIn('[원문] Keep &amp;quot; source.',vtt)
        self.assertEqual(document(units),before)

if __name__=='__main__':unittest.main()
