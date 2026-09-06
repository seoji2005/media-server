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
from media_clarity.jobs import Jobs, execute
from media_clarity.storage import Store, MediaError
from media_clarity.subtitles import parse_srt, validate_cues, webvtt

SRT = '1\n00:00:00,100 --> 00:00:01,900\n안녕하세요 <b>여러분</b>\n\n2\n00:00:02,000 --> 00:00:03,500\n다음 장면입니다.\n'

class FixtureModel:
    def __init__(self, root):
        self.root = root
    def identity(self):
        return 'fixture-v1'
    def transcribe(self, path, duration):
        with (self.root/'calls').open('a') as f:
            f.write('asr\n')
        return [{'start':.1,'end':1.9,'text':'hello'}, {'start':2.,'end':3.5,'text':'next'}]
    def translate(self, text):
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
        for bad in [SRT.replace('03,500','09,500'),SRT.replace('01,900','00,050'),'abc',SRT.replace('00:00:02','00:67:02')]:
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

    def test_missing_identity_and_erased_checkpoint_fail_closed(self):
        for mutation in ({'config_sha':None},{'transcript':None},{'translation':'[]'}):
            with self.subTest(mutation=mutation):
                job_id=self.enqueue(); (self.root/'fail').touch(); self.run_job(job_id)
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
                self.assertEqual(os.environ['ORT_DISABLE_TELEMETRY'], '1')
                observed['guarded_import'] = True
            if name == 'faster_whisper':
                self.assertTrue(observed['telemetry_disabled'])
            return original_import(name, *args, **kwargs)
        ort=types.SimpleNamespace(disable_telemetry_events=lambda:observed.update(telemetry_disabled=True))
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
        with patch('media_clarity.models.require_private_runtime'), patch.dict(os.environ,{'ORT_DISABLE_TELEMETRY':'0'}), patch.dict(sys.modules,{'onnxruntime':ort,'numpy':np,'faster_whisper':types.SimpleNamespace(WhisperModel=WhisperStub)}), patch('builtins.__import__',side_effect=checked_import):
            cues=backend.transcribe(self.source,4)
        self.assertTrue(observed['guarded_import'])
        self.assertTrue(observed['options']['local_files_only'])
        self.assertTrue(observed['transcribe']['multilingual'])
        self.assertGreater(observed['samples'],60000)
        self.assertLess(observed['samples'],70000)
        self.assertTrue(observed['materialized']);self.assertEqual(cues[0]['text'],'synthetic ASR')

    def test_windows_runtime_is_rejected_before_model_import_or_job_creation(self):
        from media_clarity.models import LocalModels
        with patch('media_clarity.models.sys.platform','win32'), patch('builtins.__import__',side_effect=AssertionError('unexpected runtime import')):
            with self.assertRaisesRegex(MediaError,'model_privacy_setup_required'):
                LocalModels(self.root)
            with self.assertRaisesRegex(MediaError,'model_privacy_setup_required'):
                object.__new__(LocalModels).transcribe(self.source,4)
        with patch('media_clarity.models.sys.platform','win32'):
            with self.assertRaisesRegex(MediaError,'model_privacy_setup_required'):
                self.jobs.enqueue(self.item['id'])
        self.assertEqual(self.jobs.status(self.item['id'])['jobs'],[])

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
            r=client.post(url,headers=headers);self.assertEqual(r.status_code,503);self.assertEqual(r.json()['error'],'local_models_missing')
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

if __name__=='__main__':unittest.main()
