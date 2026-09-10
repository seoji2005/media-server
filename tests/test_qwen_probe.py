"""The offline probe refuses overwrite and never places text/paths in its summary."""
from contextlib import ExitStack
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from scripts import probe_qwen_speech as probe
from media_clarity import qwen


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.input = self.root / 'private-video.mp4'
        self.input.write_bytes(b'original media')
        self.args = types.SimpleNamespace(input=self.input, output=self.root / 'result',
            data_dir=self.root, duration=1., audio_index=0, threads=4, resume_from=None, reuse_spans=None)
        self.part = {'clip': [0, 1],
            'cues': [{'start': .1, 'end': .5, 'text': 'private dialogue.'}],
            'evidence': {'profile': qwen.PROFILE, 'language': 'English',
                'text': 'private dialogue.', 'audio_sha256': 'a' * 64,
                'units': [{'text': 'private dialogue', 'start': .1, 'end': .5, 'raw_start': .1, 'raw_end': .5}],
                'boundary': 'end', 'recognition_end': 1}, 'error': None}
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
        self.part['evidence']['units'][0].update(start=0., end=0., raw_start=0., raw_end=0.)
        self.part['cues'] = []
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
        raw = (prior / 'checkpoint.json').read_text()
        for key, value in [('runtime_identity', 'other'), ('profile', 'other'),
                           ('input_sha256', 'other'), ('duration', 2), ('audio_index', 1)]:
            value_record = json.loads(raw)
            value_record['summary'][key] = value
            (prior / 'checkpoint.json').write_text(json.dumps(value_record))
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
        (prior / 'checkpoint.json').write_text(raw)
        self.args.resume_from = prior
        self.args.output = self.root / 'valid-resume'
        self.speech.transcribe_parts.return_value = iter([])
        self.assertEqual(probe.run(self.args), 0)
        self.assertEqual(self.summary()['saved_spans'], 1)
        value_record = json.loads(raw)
        value_record['parts'] = []
        (prior / 'checkpoint.json').write_text(json.dumps(value_record))
        self.args.output = self.root / 'tampered'
        with self.assertRaisesRegex(ValueError, 'invalid_saved_parts'):
            probe.run(self.args)

    def test_legacy_final_exports_remain_readable_but_never_override_new_checkpoint(self):
        self.assertEqual(probe.run(self.args), 0)
        checkpoint = self.args.output / 'checkpoint.json'
        raw = checkpoint.read_bytes()
        checkpoint.unlink()
        saved, prior = probe.load_saved(self.args.output)
        self.assertEqual(saved, [self.part])
        self.assertTrue(prior['complete'])
        checkpoint.write_bytes(raw)
        (self.args.output / 'parts.json').write_text('broken final export')
        self.assertEqual(probe.load_saved(self.args.output)[0], [self.part])
        checkpoint.write_text('{')
        with self.assertRaises(ValueError):
            probe.load_saved(self.args.output)

    def test_rejected_production_evidence_is_not_republished_for_resume(self):
        self.assertEqual(probe.run(self.args), 0)
        self.args.resume_from, self.args.output = self.args.output, self.root / 'rejected'
        self.speech.transcribe_parts.side_effect = probe.MediaError('processing_checkpoint_invalid', 409)
        self.assertEqual(probe.run(self.args), 1)
        self.assertFalse(self.summary()['resumable'])
        self.assertEqual(self.summary()['retained_spans'], 0)

    def test_malformed_hashed_parts_never_become_resumable(self):
        self.assertEqual(probe.run(self.args), 0)
        prior = self.args.output
        raw = (prior / 'checkpoint.json').read_bytes()
        changes = [('clip', None), ('clip', []), ('evidence', []), ('cues', None)]
        for index, (key, value) in enumerate(changes):
            checkpoint = json.loads(raw)
            if value is None:
                del checkpoint['parts'][0][key]
            else:
                checkpoint['parts'][0][key] = value
            checkpoint['summary']['parts_sha256'] = hashlib.sha256(probe.canonical(checkpoint['parts'])).hexdigest()
            (prior / 'checkpoint.json').write_bytes(probe.canonical(checkpoint))
            self.args.resume_from, self.args.output = prior, self.root / ('malformed-' + str(index))
            self.speech.transcribe_parts.reset_mock()
            self.assertEqual(probe.run(self.args), 1)
            self.speech.transcribe_parts.assert_not_called()
            self.assertEqual(self.summary()['error'], 'processing_checkpoint_invalid')
            self.assertFalse(self.summary()['resumable'])
            self.assertEqual(self.summary()['retained_spans'], 0)

    def test_valid_saved_prefix_survives_later_model_failure(self):
        self.assertEqual(probe.run(self.args), 0)
        self.args.resume_from, self.args.output = self.args.output, self.root / 'model-failed'
        self.speech.transcribe_parts.side_effect = RuntimeError('private model failure')
        self.assertEqual(probe.run(self.args), 1)
        self.assertEqual(self.summary()['error'], 'RuntimeError')
        self.assertTrue(self.summary()['resumable'])
        self.assertEqual(self.summary()['retained_spans'], 1)

    def test_failed_atomic_replacement_leaves_previous_checkpoint_readable(self):
        self.assertEqual(probe.run(self.args), 0)
        path = self.args.output / 'checkpoint.json'
        before = path.read_bytes()
        with patch.object(probe.os, 'replace', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                probe.atomic_write(path, b'new snapshot')
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(probe.load_saved(self.args.output)[0], [self.part])
        self.assertEqual({p.name for p in self.args.output.iterdir()},
                         {'parts.json', 'summary.json', 'checkpoint.json'})

    def test_killed_process_recovers_published_prefix_without_final_exports(self):
        # Real process termination skips run()'s finally and kills a replacement
        # after its new bytes have been written but before they become visible.
        script = '''
import json, sys, threading, types
from pathlib import Path
from unittest.mock import Mock
from scripts import probe_qwen_speech as probe
root = Path(sys.argv[1])
part = json.loads(sys.argv[2])
speech = Mock(asr_profile='profile', device='cpu')
speech.identity.return_value = 'a' * 64
def parts(*args):
    yield part
    yield part
speech.transcribe_parts.side_effect = parts
probe.QwenSpeech = Mock(return_value=speech)
probe.private_runtime = lambda: None
probe.importlib.metadata.version = lambda name: 'version'
sys.modules['torch'] = Mock()
original_replace = probe.os.replace
calls = 0
def replace(source, destination):
    global calls
    calls += 1
    if calls == 2:
        (root / 'ready').write_text('ready')
        threading.Event().wait(30)
    original_replace(source, destination)
probe.os.replace = replace
probe.run(types.SimpleNamespace(input=root / 'private-video.mp4', output=root / 'result',
    data_dir=root, duration=1., audio_index=0, threads=4, resume_from=None, reuse_spans=None))
'''
        process = subprocess.Popen([sys.executable, '-c', script, str(self.root), json.dumps(self.part)],
            cwd=probe.ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            import time
            deadline = time.monotonic() + 10
            while not (self.root / 'ready').exists() and time.monotonic() < deadline and process.poll() is None:
                time.sleep(.02)
            self.assertTrue((self.root / 'ready').exists())
        finally:
            process.kill()
            process.wait(timeout=5)
        self.assertFalse((self.args.output / 'summary.json').exists())
        self.assertFalse((self.args.output / 'parts.json').exists())
        saved, prior = probe.load_saved(self.args.output)
        self.assertEqual(saved, [self.part])
        self.assertFalse(prior['complete'])
        self.assertTrue(prior['resumable'])
        self.args.resume_from, self.args.output = self.args.output, self.root / 'resume'
        self.speech.transcribe_parts.return_value = iter([])
        self.assertEqual(probe.run(self.args), 0)
        self.assertEqual(self.summary()['saved_spans'], 1)
        self.assertEqual(self.summary()['new_spans'], 0)

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
