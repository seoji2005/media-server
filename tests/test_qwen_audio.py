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
