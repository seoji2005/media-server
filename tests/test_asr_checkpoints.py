"""Real persistence/kill recovery; model words are synthetic unless stated otherwise."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

from media_clarity import asr_checkpoints as checkpoints
from media_clarity.jobs import Jobs, execute
from media_clarity.models import LocalModels, local_models
from media_clarity.storage import MediaError, Store

PARTS = [{'clip':[0.,1.5],'cues':[{'start':.1,'end':1.4,'text':'First sentence.'}]},
         {'clip':[2.,4.],'cues':[{'start':2.1,'end':3.9,'text':'Second sentence.'}]}]


class SpanModel:
    asr_profile = 'synthetic-spans-v1'
    def __init__(self, root): self.root = root
    def identity(self): return 'synthetic-model-v1'
    def transcribe_parts(self, path, duration, audio_index, saved):
        for index in range(len(saved), len(PARTS)):
            with (self.root/'asr-calls').open('a') as f: f.write(str(index)+'\n')
            if index == 1 and (self.root/'block').exists():
                (self.root/'entered').touch(); time.sleep(30)
            yield PARTS[index]
    def translate(self, text): return '첫 문장입니다.' if text.startswith('First') else '두 번째 문장입니다.'
    def close(self): pass


class ASRCheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory(); cls.source = Path(cls.fixture.name)/'source.mp4'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x96:rate=10',
            '-f','lavfi','-i','sine=frequency=300','-t','4','-c:v','libx264','-threads','1',
            '-c:a','aac',str(cls.source)], check=True, capture_output=True)
    @classmethod
    def tearDownClass(cls): cls.fixture.cleanup()
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)/'store'
        self.store = Store(self.root); self.store.start()
        self.item = self.store.import_path(self.source)['item']; self.jobs = Jobs(self.store)
        with patch('media_clarity.models.local_models'): self.jid = self.jobs.enqueue(self.item['id'])
    def tearDown(self): self.jobs.close(); self.store.close(); self.temp.cleanup()

    def test_actual_kill_reuses_asr_span_and_preserves_existing_track(self):
        old = self.jobs.import_srt(self.item['id'], b'1\n00:00:00,100 --> 00:00:01,000\nExisting\n')
        original = hashlib.sha256(self.source.read_bytes()).hexdigest()
        (self.root/'block').touch()
        code = 'from pathlib import Path;from test_asr_checkpoints import SpanModel;from media_clarity.jobs import execute;from media_clarity.storage import Store;import sys;execute(Store(Path(sys.argv[1])),sys.argv[2],SpanModel)'
        child = subprocess.Popen([sys.executable,'-c',code,str(self.root),self.jid],
            env={**os.environ,'PYTHONPATH':str(Path('tests').absolute())}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic()+10
            while not (self.root/'entered').exists() and time.monotonic()<deadline:
                self.assertIsNone(child.poll()); time.sleep(.02)
            self.assertTrue((self.root/'entered').exists())
            self.assertEqual(self.jobs.row(self.jid)['asr_completed'],1)
            child.kill(); child.wait(timeout=5)
        finally:
            if child.poll() is None: child.kill(); child.wait(timeout=5)
        self.store.close(); self.store.start(); self.jobs.init(recover=True)
        self.assertEqual(self.jobs.row(self.jid)['state'],'paused')
        (self.root/'block').unlink()
        with patch('media_clarity.models.local_models'): self.jobs.action(self.jid,'resume')
        execute(self.store,self.jid,SpanModel)
        row = self.jobs.row(self.jid)
        self.assertEqual(row['state'],'succeeded',row['error'])
        self.assertEqual((self.root/'asr-calls').read_text().splitlines(),['0','1','1'])
        self.assertEqual(json.loads(row['transcript']),[c for p in PARTS for c in p['cues']])
        self.assertIn('Existing',self.jobs.track(self.item['id'],old))
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),original)

    def test_stale_writer_and_lost_or_corrupt_spans_are_rejected(self):
        self.jobs.update(self.jid,state='running',attempt=2,config_sha='fixture')
        with self.assertRaisesRegex(MediaError,'processing_interrupted'):
            checkpoints.save(self.store,self.jid,1,0,PARTS[0],0,4)
        checkpoints.save(self.store,self.jid,2,0,PARTS[0],0,4)
        with self.store.db() as db:
            before = db.execute('SELECT * FROM asr_spans').fetchone()
            db.execute("UPDATE asr_spans SET payload='{}'"); db.commit()
        with self.assertRaisesRegex(MediaError,'processing_checkpoint_invalid'):
            checkpoints.load(self.store,self.jobs.row(self.jid),4)
        with self.store.db() as db:
            db.execute('UPDATE asr_spans SET payload=?',(before['payload'],)); db.commit()
        self.assertEqual(len(checkpoints.load(self.store,self.jobs.row(self.jid),4)),1)
        with self.store.db() as db: db.execute('DELETE FROM asr_spans'); db.commit()
        with self.assertRaisesRegex(MediaError,'processing_checkpoint_invalid'):
            checkpoints.load(self.store,self.jobs.row(self.jid),4)

    def test_adapter_restores_prompt_and_offsets_and_does_not_repeat_saved_audio(self):
        calls = []
        def encode(text, *, add_special_tokens):
            self.assertFalse(add_special_tokens)
            return types.SimpleNamespace(ids=list(text.encode()))
        class Whisper:
            def __init__(self,*args,**kwargs):
                self.hf_tokenizer = types.SimpleNamespace(encode=encode)
            def transcribe(self,audio,**kwargs):
                calls.append((len(audio),kwargs['initial_prompt']))
                return iter([types.SimpleNamespace(start=.1,end=1.2,text=' English text. ')]),None
        backend = object.__new__(LocalModels); backend.paths={'asr':self.root/'unused'}; backend.device='cpu'
        np = types.SimpleNamespace(frombuffer=lambda data,dtype:memoryview(data).cast('f'))
        with patch.dict(sys.modules,{'numpy':np,'onnxruntime':None,'faster_whisper':types.SimpleNamespace(WhisperModel=Whisper)}), patch.object(backend,'speech_clips',return_value=[.5,1.5,2.5,3.5]):
            full = list(backend.transcribe_parts(self.source,4,0,[])); full_calls = calls[:]; calls.clear()
            resumed = list(backend.transcribe_parts(self.source,4,0,full[:1]))
            self.assertEqual(resumed,full[1:]); self.assertEqual(calls,full_calls[1:])
            self.assertEqual(full[1]['cues'][0]['start'],2.6)
            self.assertEqual(full[1]['cues'][0]['end'],3.5)
            self.assertEqual(full_calls[1][1],list(b' English text.'))
            # Normalization applies to fresh output only, never trusted storage.
            with self.assertRaisesRegex(MediaError,'processing_checkpoint_invalid'):
                checkpoints.validate_part({'clip':[2.5,3.5], 'cues':[{'start':2.6,'end':3.7,'text':'English text.'}]},4)
            calls.clear(); self.assertEqual(list(backend.transcribe_parts(self.source,4,0,full)),[]); self.assertEqual(calls,[])
            with self.assertRaisesRegex(MediaError,'processing_checkpoint_invalid'):
                list(backend.transcribe_parts(self.source,4,0,[PARTS[0]]))

    def test_completed_legacy_transcript_keeps_translation_resume_identity(self):
        class Legacy(SpanModel):
            def transcribe_parts(self,*args): raise AssertionError('Legacy transcript must not run ASR')
        text = json.dumps([c for p in PARTS for c in p['cues']],ensure_ascii=False)
        self.jobs.update(self.jid,config_sha='synthetic-model-v1',transcript=text,
                         transcript_sha=hashlib.sha256(text.encode()).hexdigest(),stage='translation',total=2)
        execute(self.store,self.jid,Legacy)
        self.assertEqual(self.jobs.row(self.jid)['state'],'succeeded')

    def test_large_v3_setup_requires_feature_configuration(self):
        asr = self.root/'models'/'asr'; mt = self.root/'models'/'translation'
        asr.mkdir(parents=True); mt.mkdir()
        for name in ('model.bin','config.json','tokenizer.json'): (asr/name).write_bytes(b'fixture')
        for name in ('config.json','tokenizer_config.json','model.safetensors'): (mt/name).write_bytes(b'fixture')
        with self.assertRaisesRegex(MediaError,'local_models_missing'): local_models(self.root)
        (asr/'preprocessor_config.json').write_text('{"feature_size":128}')
        self.assertEqual(local_models(self.root)['asr'],asr)
