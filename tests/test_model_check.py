"""Device preflight failures, isolated diagnostics and unchanged job boundaries."""
import builtins
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from media_clarity.app import create_app
from media_clarity.jobs import Jobs, worker_guard
from media_clarity.model_check import configuration, diagnose, run_probe
from media_clarity.models import LocalModels, check_runtime, device_configuration, local_models, model_identity, translation_identity
from media_clarity.storage import MediaError


class ModelCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def modules(self, *, available=True, bf16=True, devices=1, compute=('int8','int8_float16')):
        self.events=[]
        cuda=types.SimpleNamespace(is_available=lambda:available,
            is_bf16_supported=lambda **kw:self.events.append(('bf16',kw)) or bf16)
        torch=types.SimpleNamespace(cuda=cuda,get_num_threads=lambda:4,
            set_num_threads=lambda n:self.events.append(('threads',n)))
        ct=types.SimpleNamespace(get_cuda_device_count=lambda:devices,
            get_supported_compute_types=lambda device,**kw:set(compute))
        return {'torch':torch,'ctranslate2':ct,'onnxruntime':None,
                **{k:types.ModuleType(k) for k in ('torchaudio','faster_whisper','silero_vad','transformers','sentencepiece','google','google.protobuf')}}

    def test_windows_default_and_explicit_cpu_configuration_are_read_only(self):
        with patch('media_clarity.models.sys.platform','win32'):
            self.assertEqual(device_configuration(self.root),{'device':'cuda','selection':'default'})
            self.assertFalse((self.root/'models').exists())
            (self.root/'models').mkdir();p=self.root/'models/settings.json'
            p.write_bytes(b'{"device":"cpu"}\n');before=p.read_bytes()
            self.assertEqual(configuration(self.root)['device'],'cpu')
            self.assertEqual(p.read_bytes(),before)
            for raw in (b'{"device":"auto"}',b'{"device":[]}',b'x'*513,b'not json'):
                p.write_bytes(raw)
                self.assertEqual(configuration(self.root)['error'],'model_settings_invalid')

    def test_cuda_cpu_wheel_is_diagnosed_before_asr_or_translation_load(self):
        with patch.dict(sys.modules,self.modules(available=False)),patch('media_clarity.models.local_models',return_value={}),patch('media_clarity.models.sys.platform','win32'):
            with self.assertRaisesRegex(MediaError,'model_cuda_unavailable'):LocalModels(self.root)
        self.assertEqual(self.events,[])

    def test_cuda_capability_failures_and_native_bf16_are_distinct(self):
        for options,code in (({'bf16':False},'model_bf16_unavailable'),
                             ({'devices':0},'model_asr_cuda_unavailable'),
                             ({'compute':('float32',)},'model_asr_precision_unavailable')):
            with self.subTest(code=code),patch.dict(sys.modules,self.modules(**options)):
                with self.assertRaisesRegex(MediaError,code):check_runtime('cuda')
        with patch.dict(sys.modules,self.modules()):check_runtime('cuda')
        self.assertIn(('bf16',{'including_emulation':False}),self.events)
        self.assertIn(('threads',4),self.events)
        with patch.dict(sys.modules,self.modules(available=False)):
            check_runtime('cpu')
        self.assertNotIn('bf16',[e[0] for e in self.events])

    def test_import_failures_are_opaque_and_silero_thread_change_is_restored(self):
        original=builtins.__import__
        for failed,code in (('torch','model_torch_unavailable'),
                            ('ctranslate2','model_asr_runtime_unavailable'),
                            ('torchaudio','model_audio_runtime_unavailable'),
                            ('silero_vad','model_runtime_incompatible'),
                            ('google.protobuf','model_runtime_incompatible')):
            def importing(name,*args,**kwargs):
                if name==failed:raise OSError('secret media path and native diagnostic')
                return original(name,*args,**kwargs)
            with self.subTest(failed=failed),patch.dict(sys.modules,self.modules()),patch('builtins.__import__',side_effect=importing):
                with self.assertRaises(MediaError) as caught:check_runtime('cpu')
                self.assertEqual(str(caught.exception),code)
            if failed in ('silero_vad','google.protobuf'):self.assertIn(('threads',4),self.events)
        with patch.dict(sys.modules,{'onnxruntime':object()}):
            with self.assertRaisesRegex(MediaError,'model_privacy_setup_required'):check_runtime('cpu')

    def test_actual_isolated_missing_model_and_bounded_error_results(self):
        result=diagnose(self.root)
        self.assertEqual(result['state'],'blocked');self.assertEqual(result['error'],'local_models_missing')
        self.assertNotIn(str(self.root),json.dumps(result))
        for raw in (b'not json',b'{"device":"secret-path"}',
                    b'{"device":"cpu","selection":"default","state":"blocked","error":"secret"}'):
            with patch('media_clarity.model_check.run_probe',return_value=raw):
                self.assertEqual(diagnose(self.root)['error'],'model_check_failed')
        with patch('media_clarity.model_check.run_probe',side_effect=MediaError('model_check_timeout')):
            self.assertEqual(diagnose(self.root)['error'],'model_check_timeout')

    def test_translation_only_preflight_never_imports_asr_and_keeps_cuda_checks(self):
        original=builtins.__import__
        def importing(name,*args,**kwargs):
            if name in ('ctranslate2','torchaudio','faster_whisper','silero_vad'):
                raise AssertionError('ASR import during retranslation')
            return original(name,*args,**kwargs)
        with patch.dict(sys.modules,self.modules()),patch('builtins.__import__',side_effect=importing):
            check_runtime('cpu',translation_only=True)
            check_runtime('cuda',translation_only=True)
        with patch.dict(sys.modules,self.modules(available=False)):
            with self.assertRaisesRegex(MediaError,'model_cuda_unavailable'):
                check_runtime('cuda',translation_only=True)

    def test_translation_identity_needs_only_mt_files_and_ignores_asr_media_runtime(self):
        mt=self.root/'models/translation';mt.mkdir(parents=True)
        for name in ('config.json','tokenizer_config.json','spiece.model','model.safetensors'):
            (mt/name).write_bytes(b'fixture')
        with patch('media_clarity.models.importlib.util.find_spec',return_value=object()),patch('media_clarity.models.importlib.metadata.version',return_value='fixture') as versions,patch('media_clarity.models.run_media',side_effect=AssertionError('media runtime inspected')):
            paths=local_models(self.root,check_packages=True,translation_only=True)
            self.assertEqual(set(paths),{'translation'})
            before=translation_identity(self.root)
            asr=self.root/'models/asr';asr.mkdir();(asr/'model.bin').write_bytes(b'changed')
            self.assertEqual(translation_identity(self.root),before)
            with patch('media_clarity.models.PIPELINE','changed-ASR-only-profile'):
                self.assertEqual(translation_identity(self.root),before)
            with patch('media_clarity.models.TRANSLATION_PROFILE','changed-translation-profile'):
                self.assertNotEqual(translation_identity(self.root),before)
            self.assertNotIn('faster-whisper',[c.args[0] for c in versions.call_args_list])
            (mt/'spiece.model').write_bytes(b'changed vocabulary')
            self.assertNotEqual(translation_identity(self.root),before)
        with self.assertRaisesRegex(MediaError,'local_models_missing'):local_models(self.root)

    def test_asr_only_preflight_excludes_translation_imports_and_bf16(self):
        original = builtins.__import__
        def importing(name,*args,**kwargs):
            if name in ('transformers','sentencepiece','google.protobuf'):
                raise AssertionError('Translation dependency imported')
            return original(name,*args,**kwargs)
        with patch.dict(sys.modules,self.modules(bf16=False)),patch('builtins.__import__',side_effect=importing):
            check_runtime('cuda',asr_only=True)
        self.assertNotIn('bf16',[e[0] for e in self.events])
        self.assertIn(('threads',4),self.events)
        with patch.dict(sys.modules,self.modules(compute=('float32',))):
            with self.assertRaisesRegex(MediaError,'model_asr_precision_unavailable'):
                check_runtime('cuda',asr_only=True)
        with patch.dict(sys.modules,{'onnxruntime':object()}):
            with self.assertRaisesRegex(MediaError,'model_privacy_setup_required'):
                check_runtime('cpu',asr_only=True)
        backend=object.__new__(LocalModels);backend.asr_only=True
        with self.assertRaisesRegex(MediaError,'processing_config_changed'):
            backend.translate_many(['No local translation.'])

    def test_asr_only_files_and_identity_ignore_madlad_but_pin_asr_vad_tokenizer(self):
        asr=self.root/'models/asr';asr.mkdir(parents=True)
        vad=self.root/'vad';vad.mkdir();(vad/'silero_vad.jit').write_bytes(b'fixture')
        for name in ('model.bin','config.json','tokenizer.json','preprocessor_config.json'):
            (asr/name).write_bytes(b'fixture')
        distribution=types.SimpleNamespace(locate_file=lambda path:vad)
        with patch('media_clarity.models.importlib.util.find_spec',return_value=object()) as specs,patch('media_clarity.models.importlib.metadata.distribution',return_value=distribution),patch('media_clarity.models.importlib.metadata.version',return_value='fixture') as versions,patch('media_clarity.models.run_media',return_value=b'fixture-ffmpeg'):
            paths=local_models(self.root,check_packages=True,asr_only=True)
            self.assertEqual(set(paths),{'asr','vad'})
            before=model_identity(paths,'cpu',asr_only=True)
            mt=self.root/'models/translation';mt.mkdir();(mt/'model.safetensors').write_bytes(b'unrelated')
            self.assertEqual(model_identity(paths,'cpu',asr_only=True),before)
            self.assertTrue({'transformers','sentencepiece','google.protobuf'}.isdisjoint(c.args[0] for c in specs.call_args_list))
            self.assertTrue({'transformers','sentencepiece','protobuf'}.isdisjoint(c.args[0] for c in versions.call_args_list))
            self.assertIn('tokenizers',[c.args[0] for c in versions.call_args_list])
            (asr/'tokenizer.json').write_bytes(b'changed ASR tokenizer')
            self.assertNotEqual(model_identity(paths,'cpu',asr_only=True),before)
            (vad/'silero_vad.jit').unlink()
            with self.assertRaisesRegex(MediaError,'model_runtime_missing'):
                local_models(self.root,check_packages=True,asr_only=True)

    def test_native_output_is_suppressed_and_parent_eof_stops_diagnostic(self):
        code='''import atexit,os,sys,time
from unittest.mock import patch
from media_clarity import model_check as m
def noisy(root):
    os.write(1,b"PRIVATE STDOUT");os.write(2,b"PRIVATE STDERR")
    if sys.argv[2]=="wait":
        (root/'entered').touch();time.sleep(30)
    if sys.argv[2]=="teardown":atexit.register(time.sleep,30)
    raise RuntimeError("PRIVATE ERROR")
with patch("media_clarity.models.LocalModels",side_effect=noisy):m.main()
'''
        # Keep the parent pipe open through normal completion, matching production.
        for mode in ('finish','wait','teardown'):
            child=subprocess.Popen([sys.executable,'-c',code,str(self.root),mode],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                if mode=='wait':
                    deadline=time.monotonic()+5
                    while not (self.root/'entered').exists() and time.monotonic()<deadline:time.sleep(.01)
                    self.assertTrue((self.root/'entered').exists())
                    with self.assertRaisesRegex(MediaError,'processing_worker_active'):
                        with worker_guard(self.root):pass
                    child.stdin.close();child.wait(timeout=5)
                    self.assertNotEqual(child.returncode,0)
                    with worker_guard(self.root):pass
                else:
                    child.wait(timeout=5)
                    self.assertEqual(child.returncode,0)
                    self.assertEqual(json.loads(child.stdout.read())['error'],'model_check_failed')
                self.assertEqual(child.stderr.read(),b'')
            finally:
                if child.poll() is None:child.kill();child.wait()
                if not child.stdin.closed:child.stdin.close()
                child.stdout.close();child.stderr.close()

    def test_actual_timeout_kills_and_reaps_probe_child(self):
        popen=subprocess.Popen;children=[]
        def sleeping(*args,**kw):
            child=popen([sys.executable,'-c','import time;time.sleep(30)'],**kw);children.append(child);return child
        with patch('media_clarity.model_check.subprocess.Popen',side_effect=sleeping):
            with self.assertRaisesRegex(MediaError,'model_check_timeout'):run_probe(self.root,timeout=.05)
        self.assertIsNotNone(children[0].poll())
        self.assertTrue(children[0].stdin.closed and children[0].stdout.closed)

    def test_normal_worker_exit_does_not_abort_with_open_parent_pipe(self):
        code='''import time
from unittest.mock import patch
from media_clarity.worker import main
with patch("media_clarity.jobs.execute",side_effect=lambda *args:time.sleep(.05)):main()
'''
        child=subprocess.Popen([sys.executable,'-c',code,str(self.root),'unused'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            child.wait(timeout=5)
            self.assertEqual(child.returncode,0)
            self.assertEqual(child.stdout.read(),b'');self.assertEqual(child.stderr.read(),b'')
        finally:
            if child.poll() is None:child.kill();child.wait()
            child.stdin.close();child.stdout.close();child.stderr.close()

    def test_http_token_gate_and_active_or_orphan_worker_exclusion(self):
        with patch.object(Jobs,'start',lambda jobs:jobs.init()),TestClient(create_app(self.root),base_url='http://127.0.0.1:8765') as client:
            session=client.get('/api/session').json()
            self.assertEqual(session['diagnostics']['models']['state'],'unchecked')
            headers={'X-Media-Token':session['token']}
            self.assertEqual(client.post('/api/models/diagnostics').status_code,403)
            jobs=client.app.state.jobs
            jobs.process=types.SimpleNamespace(poll=lambda:None)
            try:
                with patch('media_clarity.app.diagnose_models',side_effect=AssertionError('probe during inference')):
                    self.assertEqual(client.post('/api/models/diagnostics',headers=headers).status_code,409)
            finally:jobs.process=None
            with worker_guard(self.root):
                result=client.post('/api/models/diagnostics',headers=headers).json()
                self.assertEqual(result['error'],'processing_worker_active')
            self.assertEqual(client.post('/api/models/diagnostics',headers=headers).json()['error'],'local_models_missing')
            with client.app.state.store.db() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM subtitle_jobs').fetchone()[0],0)

    def test_doctor_base_still_succeeds_without_optional_models(self):
        cmd=[sys.executable,'-m','media_clarity','doctor','--data-dir',str(self.root)]
        base=subprocess.run(cmd,capture_output=True,timeout=10)
        self.assertEqual(base.returncode,0);self.assertEqual(base.stderr,b'')
        self.assertEqual(json.loads(base.stdout)['models']['state'],'unchecked')
        full=subprocess.run(cmd+['--models'],capture_output=True,timeout=10)
        self.assertEqual(full.returncode,1);self.assertEqual(full.stderr,b'')
        self.assertEqual(json.loads(full.stdout)['models']['error'],'local_models_missing')

    def test_probe_keeps_library_responsive_and_serializes_with_supervisor(self):
        from concurrent.futures import ThreadPoolExecutor
        entered,release=threading.Event(),threading.Event()
        def checking(root):
            entered.set();release.wait(5)
            return {'device':'cpu','selection':'default','state':'ready','error':None}
        with patch.object(Jobs,'start',lambda jobs:jobs.init()),TestClient(create_app(self.root),base_url='http://127.0.0.1:8765') as client:
            headers={'X-Media-Token':client.get('/api/session').json()['token']}
            with patch('media_clarity.app.diagnose_models',side_effect=checking),ThreadPoolExecutor() as pool:
                pending=pool.submit(client.post,'/api/models/diagnostics',headers=headers)
                try:
                    self.assertTrue(entered.wait(5))
                    self.assertEqual(client.get('/api/library').status_code,200)
                    self.assertEqual(client.post('/api/models/diagnostics',headers=headers).status_code,409)
                    self.assertFalse(client.app.state.jobs.lock.acquire(blocking=False))
                finally:release.set()
                self.assertEqual(pending.result(timeout=5).json()['state'],'ready')


if __name__=='__main__':unittest.main()
