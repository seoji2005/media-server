"""Real FFmpeg PCM equivalence and temporary-file lifecycle; no model downloads."""
import hashlib
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from media_clarity import qwen
from media_clarity.models import LocalModels
from media_clarity.storage import MediaError


class QwenAudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.source = Path(cls.temp.name) / 'sample.mkv'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=size=32x32:rate=1',
            '-f','lavfi','-i','sine=frequency=440:sample_rate=44100',
            '-itsoffset','1.25','-f','lavfi','-i','sine=frequency=880:sample_rate=48000',
            '-map','0:v','-map','1:a','-map','2:a','-t','67','-c:v','libx264',
            '-c:a:0','aac','-c:a:1','ac3',str(cls.source)],check=True,capture_output=True)
        cls.source_sha = hashlib.sha256(cls.source.read_bytes()).hexdigest()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def tearDown(self):
        self.assertEqual(list(self.source.parent.iterdir()), [self.source])
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.source_sha)

    def legacy_audio(self, index=0):
        audio = LocalModels.decode_audio(None, self.source, 67, index)
        return audio[:math.floor(67*16000)] if len(audio) > math.ceil(67*16000) else audio

    def test_pcm_matches_historical_decode_on_both_tracks_and_delayed_timeline(self):
        import numpy as np
        for index in (0,1):
            expected = self.legacy_audio(index)
            with qwen.decoded_audio(self.source, 67, index) as (stream, count):
                self.assertEqual(count, len(expected))
                stream.seek(0)
                self.assertEqual(stream.read(count*4), expected.tobytes())
            if index == 1:
                first = np.flatnonzero(abs(expected) > .01)[0]/16000
                self.assertGreater(first, 1.15)
                self.assertLess(first, 1.4)

    def speech(self):
        speech = object.__new__(qwen.QwenSpeech)
        speech.recognize = lambda samples: ('Hello.', 'English')
        speech.align = lambda *args: [{'text':'Hello','start':.1,'end':.5,'raw_start':.1,'raw_end':.5}]
        return speech

    def test_real_decode_keeps_legacy_windows_hashes_and_resume_without_model_work(self):
        expected = self.legacy_audio()
        plan = list(qwen.windows(expected))
        for profile in qwen.PROFILES:
            speech = self.speech();speech.asr_profile = profile
            parts = list(speech.transcribe_parts(self.source,67,0,[]))
            self.assertEqual([p['clip'] for p in parts], [[a/16000,b/16000] for a,b,_ in plan])
            self.assertEqual([p['evidence']['audio_sha256'] for p in parts],
                [hashlib.sha256(expected[a:b].tobytes()).hexdigest() for a,b,_ in plan])
            with patch.object(speech,'recognize',wraps=speech.recognize) as call:
                self.assertEqual(list(speech.transcribe_parts(self.source,67,0,parts[:1])), parts[1:])
                self.assertEqual(call.call_count,len(parts)-1)
                call.reset_mock()
                self.assertEqual(list(speech.transcribe_parts(self.source,67,0,parts)), [])
                call.assert_not_called()

    def test_generator_close_and_inference_failure_release_temporary_audio(self):
        create = tempfile.TemporaryFile
        opened = []
        def track(*args, **kwargs):
            result = create(*args, **kwargs);opened.append(result);return result
        for fail in (False,True):
            speech = self.speech()
            if fail:
                speech.recognize = lambda samples: (_ for _ in ()).throw(MediaError('processing_interrupted',409))
            with patch('media_clarity.qwen.tempfile.TemporaryFile',side_effect=track):
                gen = speech.transcribe_parts(self.source,67,0,[])
                if fail:
                    with self.assertRaisesRegex(MediaError,'processing_interrupted'):next(gen)
                else:
                    next(gen);self.assertFalse(opened[-1].closed);gen.close()
            self.assertTrue(opened[-1].closed)

    def test_abrupt_worker_exit_removes_decoded_audio(self):
        code = '''
import os,sys
from pathlib import Path
from media_clarity.qwen import decoded_audio
with decoded_audio(Path(sys.argv[1]),67,0) as (stream,count):
 assert count > 0
 os._exit(23)
'''
        result = subprocess.run([sys.executable,'-c',code,str(self.source)],capture_output=True,timeout=30)
        self.assertEqual(result.returncode,23)
        self.assertEqual(result.stdout,b'');self.assertEqual(result.stderr,b'')

    def test_decode_limit_missing_track_and_timeout_never_yield_partial_audio(self):
        for duration,index in ((.1,0),(67,127)):
            with self.subTest(duration=duration,index=index),self.assertRaisesRegex(MediaError,'invalid_media'):
                with qwen.decoded_audio(self.source,duration,index):self.fail('partial decode yielded')
        run = subprocess.run
        def expire(*args, **kwargs):
            kwargs['timeout'] = .001
            return run(*args, **kwargs)
        with patch('media_clarity.qwen.subprocess.run',side_effect=expire), \
                self.assertRaisesRegex(MediaError,'media_timeout'):
            with qwen.decoded_audio(self.source,67,0):self.fail('timeout yielded')
        with patch('media_clarity.qwen.subprocess.run',side_effect=FileNotFoundError('private-path')), \
                self.assertRaisesRegex(MediaError,'^ffmpeg_unavailable$'):
            with qwen.decoded_audio(self.source,67,0):self.fail('missing decoder yielded')

    def test_disk_space_failure_keeps_source_and_starts_no_decoder(self):
        full = shutil._ntuple_diskusage(100,99,1)
        with patch('media_clarity.qwen.shutil.disk_usage',return_value=full), \
                patch('media_clarity.qwen.subprocess.run') as run, \
                self.assertRaisesRegex(MediaError,'insufficient_space'):
            with qwen.decoded_audio(self.source,67,0):self.fail('full disk yielded')
        run.assert_not_called()
        enough = shutil._ntuple_diskusage(1000000000,0,1000000000)
        with patch('media_clarity.qwen.shutil.disk_usage',side_effect=[enough,full]), \
                patch('media_clarity.qwen.subprocess.run',return_value=subprocess.CompletedProcess([],1)), \
                self.assertRaisesRegex(MediaError,'insufficient_space'):
            with qwen.decoded_audio(self.source,67,0):self.fail('decoder disk failure yielded')

    def test_bad_input_parameters_fail_before_temporary_file_or_decoder(self):
        for duration,index in ((0,0),(float('nan'),0),(float('inf'),0),(67,True),(67,-1)):
            with patch('media_clarity.qwen.tempfile.TemporaryFile') as create, \
                    self.assertRaises(MediaError):
                with qwen.decoded_audio(self.source,duration,index):self.fail('bad input yielded')
            create.assert_not_called()

    def test_error_output_is_drained_even_when_decoder_exits_successfully(self):
        # A noisy decoder must neither deadlock a full pipe nor retain diagnostics.
        def noisy(args, **kwargs):
            return subprocess.Popen([sys.executable, '-c',
                "import os; os.write(1,b'\\0'*64000); os.write(2,b'private diagnostic'*65536)"],
                stdin=kwargs['stdin'], stdout=kwargs['stdout'], stderr=kwargs['stderr']).wait(timeout=10)
        def run(*args, **kwargs):
            return subprocess.CompletedProcess([], noisy(*args, **kwargs))
        with patch('media_clarity.qwen.subprocess.run', side_effect=run), \
                self.assertRaisesRegex(MediaError, '^invalid_media$'):
            with qwen.decoded_audio(self.source, 67, 0):
                self.fail('error-level diagnostics were ignored')


class IncompleteAudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='audio integrity ')
        cls.root = Path(cls.temp.name)
        cls.full = cls.root / '정상 영상.mp4'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=12',
            '-f','lavfi','-i','sine=frequency=440:sample_rate=48000',
            '-t','12','-c:v','libx264','-c:a','aac','-movflags','+faststart',str(cls.full)],
            check=True,capture_output=True,timeout=30)
        cls.partial = cls.root / '중단 영상.mp4'
        raw = cls.full.read_bytes()
        cls.partial.write_bytes(raw[:len(raw)//2])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_actual_partial_mp4_never_yields_pcm_or_starts_recognition(self):
        digest = hashlib.sha256(self.partial.read_bytes()).hexdigest()
        with qwen.decoded_audio(self.full, 12, 0) as (_, count):
            self.assertGreater(count / 16000, 11.9)
        speech = object.__new__(qwen.QwenSpeech)
        with patch.object(speech, 'recognize') as recognize, \
                self.assertRaisesRegex(MediaError, '^invalid_media$'):
            list(speech.transcribe_parts(self.partial, 12, 0, []))
        recognize.assert_not_called()
        self.assertEqual(hashlib.sha256(self.partial.read_bytes()).hexdigest(), digest)

    def test_valid_shorter_and_delayed_audio_are_not_rejected_as_incomplete(self):
        for extension in ('mp4', 'mkv'):
            source = self.root / ('짧은 음성.' + extension)
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=size=32x32:rate=1:duration=12',
                '-itsoffset','1.25','-f','lavfi','-i','sine=duration=4:sample_rate=48000',
                '-c:v','libx264','-c:a','aac',str(source)],check=True,capture_output=True,timeout=30)
            with qwen.decoded_audio(source, 12, 0) as (_, count):
                self.assertGreater(count / 16000, 5)
                self.assertLess(count / 16000, 5.5)

    def test_http_job_failure_preserves_imported_captions_and_position_after_restart(self):
        from fastapi.testclient import TestClient
        from media_clarity.app import create_app
        from media_clarity.jobs import Jobs, execute
        from tests.test_gemini import reply
        from urllib.parse import quote

        class Speech(qwen.QwenSpeech):
            def __init__(self, root): pass
            def identity(self): return 'synthetic-words-real-decoder'
            def recognize(self, samples): return 'Hello.', 'English'
            def align(self, *args):
                return [{'text':'Hello','start':.1,'end':1.,'raw_start':.1,'raw_end':1.}]
            def close(self): pass

        with tempfile.TemporaryDirectory() as data:
            app = create_app(Path(data) / '체험 보관함')
            with TestClient(app, base_url='http://127.0.0.1:8765') as client, \
                    patch.dict(os.environ, {'GEMINI_API_KEY':'synthetic-key'}), \
                    patch('media_clarity.jobs.speech_preflight'), \
                    patch('media_clarity.gemini.request', side_effect=reply) as provider:
                token = {'X-Media-Token':client.get('/api/session').json()['token']}
                for path in (self.full, self.partial):
                    raw = path.read_bytes()
                    response = client.post('/api/import', content=raw, headers=token | {
                        'X-Media-Filename':quote(path.name),'Content-Type':'application/octet-stream'})
                    self.assertEqual(response.status_code, 201, response.text)
                    item_id = response.json()['item']['id']
                    caption = b'1\n00:00:01,000 --> 00:00:02,000\nUser caption.\n'
                    track = client.post(f'/api/library/{item_id}/subtitles', content=caption,
                        headers=token | {'Content-Type':'application/octet-stream','X-Media-Filename':'user.srt'})
                    self.assertEqual(track.status_code, 201, track.text)
                    self.assertEqual(client.put(f'/api/library/{item_id}/position',json={'position':2.25},headers=token).status_code,200)
                    jobs = Jobs(app.state.store)
                    queued = client.post(f'/api/library/{item_id}/subtitle-jobs/regenerate', headers=token)
                    self.assertEqual(queued.status_code, 202, queued.text)
                    jid = queued.json()['id']
                    provider.reset_mock()
                    execute(app.state.store, jid, Speech)
                    status = client.get(f'/api/library/{item_id}/subtitles').json()
                    row = jobs.row(jid)
                    if path == self.full:
                        self.assertEqual(row['state'], 'succeeded')
                        self.assertEqual(len(status['tracks']), 2)
                        self.assertTrue(provider.called)
                    else:
                        self.assertEqual((row['state'],row['error'],row['asr_until']), ('failed','invalid_media',0))
                        self.assertEqual(len(status['tracks']), 1)
                        self.assertEqual(row['transcript'], None)
                        provider.assert_not_called()
                    managed = app.state.store.file_path(app.state.store._row(item_id))
                    self.assertEqual(managed.read_bytes(), raw)
            with TestClient(create_app(Path(data) / '체험 보관함'), base_url='http://127.0.0.1:8765') as client:
                self.assertEqual(client.get(f'/api/library/{item_id}').json()['position'], 2.25)
                status = client.get(f'/api/library/{item_id}/subtitles').json()
                self.assertEqual(len(status['tracks']), 1)
                self.assertEqual(status['jobs'][0]['state'], 'failed')
