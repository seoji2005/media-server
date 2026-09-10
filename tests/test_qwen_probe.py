"""The offline probe refuses overwrite and never places text/paths in its summary."""
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from scripts import probe_qwen_speech as probe


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.input = self.root / 'private-video.mp4'
        self.input.write_bytes(b'original media')
        self.args = types.SimpleNamespace(input=self.input, output=self.root / 'result',
            data_dir=self.root, duration=1., audio_index=0, threads=4, resume_from=None, reuse_spans=None)
        self.part = {'clip': [0, 1], 'cues': [], 'evidence': {'text': 'private dialogue'}, 'error': None}
        self.speech = Mock(asr_profile='profile', device='cpu')
        self.speech.identity.return_value = 'a' * 64
        self.speech.transcribe_parts.return_value = iter([self.part])
        stack = self.enterContext(ExitStack())
        self.factory = stack.enter_context(patch.object(probe, 'QwenSpeech', return_value=self.speech))
        stack.enter_context(patch.object(probe, 'private_runtime'))
        stack.enter_context(patch.object(probe.sys, 'addaudithook'))
        stack.enter_context(patch.dict('sys.modules', torch=Mock()))
        stack.enter_context(patch.object(probe.importlib.metadata, 'version', return_value='version'))
        stack.enter_context(patch.object(probe.subprocess, 'check_output', return_value='b' * 40))

    def summary(self):
        text = (self.args.output / 'summary.json').read_text()
        self.assertNotIn(str(self.root), text)
        self.assertNotIn('private', text)
        return json.loads(text)

    def test_outputs_are_exclusive_and_summary_excludes_content(self):
        self.assertEqual(probe.run(self.args), 0)
        summary = self.summary()
        self.assertTrue(summary['complete'])
        self.assertEqual(summary['new_spans'], 1)
        original = (self.args.output / 'parts.json').read_bytes()
        self.factory.reset_mock()
        with self.assertRaises(FileExistsError):
            probe.run(self.args)
        self.factory.assert_not_called()
        self.assertEqual((self.args.output / 'parts.json').read_bytes(), original)

    def test_model_failure_is_redacted_and_preserves_incomplete_status(self):
        self.speech.transcribe_parts.side_effect = RuntimeError(str(self.input) + ' private dialogue')
        self.assertEqual(probe.run(self.args), 1)
        summary = self.summary()
        self.assertFalse(summary['complete'])
        self.assertEqual(summary['error'], 'RuntimeError')
        self.assertIn('parts_sha256', summary)

    def test_input_change_does_not_become_a_successful_cost_sample(self):
        def changed(*args):
            yield self.part
            self.input.write_bytes(b'changed')
        self.speech.transcribe_parts.side_effect = changed
        self.assertEqual(probe.run(self.args), 1)
        summary = self.summary()
        self.assertFalse(summary['complete'])
        self.assertIn('parts_sha256', summary)
        self.assertFalse(summary['resumable'])
        self.assertEqual(summary['retained_spans'], 0)

    def test_unresolved_saved_evidence_never_becomes_complete(self):
        self.part['error'] = 'alignment_unresolved'
        self.assertEqual(probe.run(self.args), 1)
        self.args.resume_from = self.args.output
        self.args.output = self.root / 'retry'
        self.speech.transcribe_parts.return_value = iter([])
        self.assertEqual(probe.run(self.args), 1)
        self.assertEqual(self.summary()['error'], 'alignment_unresolved')

    def test_resume_checks_runtime_input_selection_and_saved_parts_integrity(self):
        self.assertEqual(probe.run(self.args), 0)
        prior = self.args.output
        raw = (prior / 'summary.json').read_text()
        for key, value in [('runtime_identity', 'other'), ('profile', 'other'),
                           ('input_sha256', 'other'), ('duration', 2), ('audio_index', 1)]:
            summary = json.loads(raw)
            summary[key] = value
            (prior / 'summary.json').write_text(json.dumps(summary))
            self.args.resume_from = prior
            self.args.output = self.root / key
            self.speech.transcribe_parts.reset_mock()
            self.assertEqual(probe.run(self.args), 1)
            self.speech.transcribe_parts.assert_not_called()
            self.assertEqual(self.summary()['error'], 'processing_config_changed')
            self.assertFalse(self.summary()['resumable'])
            self.assertEqual(self.summary()['saved_spans'], 0)
            self.assertEqual(json.loads((self.args.output / 'parts.json').read_text()), [])
            failed = self.args.output
            self.args.resume_from = failed
            self.args.output = self.root / (key + '-retry')
            with self.assertRaisesRegex(ValueError, 'invalid_saved_parts'):
                probe.run(self.args)
        (prior / 'summary.json').write_text(raw)
        self.args.resume_from = prior
        self.args.output = self.root / 'valid-resume'
        self.speech.transcribe_parts.return_value = iter([])
        self.assertEqual(probe.run(self.args), 0)
        self.assertEqual(self.summary()['saved_spans'], 1)
        (prior / 'parts.json').write_text('[]')
        self.args.output = self.root / 'tampered'
        with self.assertRaisesRegex(ValueError, 'invalid_saved_parts'):
            probe.run(self.args)

    def test_runtime_change_during_processing_cannot_create_resumable_parts(self):
        self.speech.identity.side_effect = ['a' * 64, 'c' * 64]
        self.assertEqual(probe.run(self.args), 1)
        summary = self.summary()
        self.assertFalse(summary['complete'])
        self.assertFalse(summary['resumable'])
        self.assertEqual(summary['retained_spans'], 0)

    def test_interruption_preserves_only_identity_verified_prefix(self):
        def interrupted(*args):
            yield self.part
            raise KeyboardInterrupt()
        self.speech.transcribe_parts.side_effect = interrupted
        self.assertEqual(probe.run(self.args), 1)
        summary = self.summary()
        self.assertFalse(summary['complete'])
        self.assertTrue(summary['resumable'])
        self.assertEqual(summary['retained_spans'], 1)


if __name__ == '__main__':
    unittest.main()
