"""Execute real speech methods with tiny deterministic model substitutes."""
from contextlib import nullcontext
import copy
import hashlib
import io
import json
from pathlib import Path
import types
import unittest
from unittest.mock import Mock, patch

import numpy as np

from media_clarity import qwen


class Tensor(np.ndarray):
    def cpu(self):
        return self


class Inputs(dict):
    def to(self, *args):
        return self


class Model:
    config = types.SimpleNamespace(eos_token_id=10, timestamp_token_id=0)

    def to(self, *args):
        return self

    def eval(self):
        return self

    def generate(self, **kwargs):
        return np.array([[0, 0, 9, 10]])

    def __call__(self, **kwargs):
        return types.SimpleNamespace(logits=np.array([[[0, 1, 0], [0, 0, 1]]]).view(Tensor))


class Processor:
    timestamp_segment_time = 80

    def apply_transcription_request(self, **kwargs):
        return Inputs(input_ids=np.array([[0, 0]]))

    def decode(self, *args, **kwargs):
        return [{'transcription': 'Hello.', 'language': 'English'}]

    def prepare_forced_aligner_inputs(self, **kwargs):
        return Inputs(input_ids=np.array([[0, 0]])), ['Hello']

    def decode_forced_alignment(self, **kwargs):
        return [[{'text': 'Hello', 'start_time': .08, 'end_time': .16}]]


class SpeechTimingTests(unittest.TestCase):
    def setUp(self):
        self.sync = Mock()
        self.torch = types.SimpleNamespace(float32='float32', float16='float16',
            inference_mode=nullcontext, cuda=types.SimpleNamespace(
                synchronize=self.sync, empty_cache=Mock()))
        self.model = Model()
        self.processor = Processor()
        transformers = types.SimpleNamespace(
            AutoProcessor=types.SimpleNamespace(from_pretrained=Mock(return_value=self.processor)),
            AutoModelForMultimodalLM=types.SimpleNamespace(from_pretrained=Mock(return_value=self.model)),
            AutoModelForTokenClassification=types.SimpleNamespace(from_pretrained=Mock(return_value=self.model)))
        self.modules = patch.dict('sys.modules', torch=self.torch, transformers=transformers)
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.speech = object.__new__(qwen.QwenSpeech)
        self.speech.device = 'cpu'
        self.speech.paths = {'asr': Path('asr'), 'aligner': Path('aligner')}
        self.speech.close = Mock()
        self.audio = np.ones(35 * 16000, dtype=np.float32) * .1

    def parts(self, saved=()):
        with io.BytesIO(self.audio.tobytes()) as stream:
            return list(self.speech._transcribe_audio(stream, len(self.audio), saved))

    def test_enabled_and_disabled_produce_identical_parts_and_identity(self):
        for profile in qwen.PROFILES:
            self.speech.asr_profile = profile
            self.speech.timings = None
            with patch('media_clarity.qwen.time.perf_counter', side_effect=AssertionError('disabled clock')):
                before = self.parts()
            self.speech.timings = timings = qwen.SpeechTimings()
            after = self.parts()
            encode = lambda parts: hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()
            self.assertEqual(encode(before), encode(after))
            for row in timings.phases.values():
                self.assertEqual(row['calls'], 2)
                self.assertEqual(row['failures'], 0)
                self.assertGreaterEqual(row['seconds'], 0)
            with patch('media_clarity.qwen.run_media', return_value=b'ffmpeg'), \
                    patch('media_clarity.qwen.importlib.metadata.version', return_value='1'):
                first = self.speech.identity()
                self.speech.timings = None
                self.assertEqual(self.speech.identity(), first)
        self.sync.assert_not_called()

    def test_saved_prefix_and_complete_resume_do_not_reload_saved_spans(self):
        saved = self.parts()
        self.speech.timings = timings = qwen.SpeechTimings()
        self.assertEqual(self.parts(saved[:1]), saved[1:])
        self.assertTrue(all(row['calls'] == 1 for row in timings.phases.values()))
        snapshot = copy.deepcopy(timings.phases)
        self.assertEqual(self.parts(saved), [])
        self.assertEqual(timings.phases, snapshot)

    def test_original_errors_survive_and_cleanup_is_measured(self):
        self.speech.device = 'cuda'
        self.speech.timings = timings = qwen.SpeechTimings()
        original = RuntimeError('private detail must not be recorded')
        with patch.object(self.model, 'generate', side_effect=original):
            with self.assertRaises(RuntimeError) as caught:
                self.speech.recognize(self.audio)
        self.assertIs(caught.exception, original)
        self.assertEqual(timings.phases['asr_infer']['failures'], 1)
        self.assertEqual(timings.phases['asr_cleanup']['calls'], 1)
        self.assertEqual(timings.phases['asr_decode']['calls'], 0)
        # load/prepare each have two syncs; failed inference only its pre-sync.
        self.assertEqual(self.sync.call_count, 5)
        self.speech.close.assert_called_once()
        self.assertNotIn('private', json.dumps(timings.phases))
        self.speech.timings = timings = qwen.SpeechTimings()
        with patch.object(self.processor, 'decode_forced_alignment', return_value=[[]]):
            with self.assertRaisesRegex(qwen.MediaError, 'alignment_unresolved'):
                self.speech.align(self.audio, 'Hello.', 'English')
        self.assertEqual(timings.phases['align_decode']['failures'], 1)
        self.assertEqual(timings.phases['align_cleanup']['calls'], 1)

    def test_cuda_only_synchronizes_when_enabled_and_preserves_sync_failure(self):
        self.speech.device = 'cuda'
        self.speech.recognize(self.audio)
        self.sync.assert_not_called()
        self.speech.timings = timings = qwen.SpeechTimings()
        self.speech.recognize(self.audio)
        self.assertEqual(self.sync.call_count, 8)
        original = RuntimeError('sync failed')
        self.sync.side_effect = original
        with self.assertRaises(RuntimeError) as caught:
            self.speech.recognize(self.audio)
        self.assertIs(caught.exception, original)
        self.assertEqual(timings.phases['asr_load']['failures'], 1)
        self.assertEqual(timings.phases['asr_cleanup']['calls'], 2)

    def test_cleanup_does_not_add_a_failing_ninth_cuda_sync(self):
        self.speech.device = 'cuda'
        self.speech.timings = qwen.SpeechTimings()
        self.sync.side_effect = [None] * 8 + [RuntimeError('cleanup observer failure')]
        self.speech.recognize(self.audio)
        self.assertEqual(self.sync.call_count, 8)
        self.speech.close.assert_called_once()

    def test_empty_and_unsupported_speech_never_load_alignment(self):
        for text, language in [('', ''), ('Hello.', 'Unsupported')]:
            self.speech.timings = timings = qwen.SpeechTimings()
            with patch.object(self.processor, 'decode', return_value=[{
                    'transcription': text, 'language': language}]):
                self.parts()
            self.assertEqual(timings.phases['asr_load']['calls'], 2)
            self.assertTrue(all(row['calls'] == 0 for name, row in timings.phases.items()
                                if name.startswith('align_')))


if __name__ == '__main__':
    unittest.main()
