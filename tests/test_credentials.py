"""Session credentials stay out of storage, command arguments and diagnostics."""
import contextlib
import getpass
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings

from media_clarity.__main__ import main
from media_clarity.credentials import prompt_gemini_key
from media_clarity.storage import MediaError

CANARY = 'Synthetic-session-key_19.test'


class CredentialTests(unittest.TestCase):
    def test_optional_input_skips_disabled_or_valid_inherited_key(self):
        for enabled, existing in ((False, ''), (True, CANARY)):
            with self.subTest(enabled=enabled), patch.dict(os.environ, {'GEMINI_API_KEY':existing}), \
                    patch('getpass.getpass') as prompt:
                with prompt_gemini_key(enabled):
                    self.assertEqual(os.environ['GEMINI_API_KEY'], existing)
                prompt.assert_not_called()

    def test_session_key_reaches_child_environment_without_command_line_or_output(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY':'invalid old key'}), \
                patch('getpass.getpass', return_value=CANARY), tempfile.TemporaryDirectory() as temp:
            args = [sys.executable, '-c',
                    'import os; print(bool(os.environ.get("GEMINI_API_KEY")))']
            with self.assertRaisesRegex(RuntimeError, 'server stopped'):
                with prompt_gemini_key(True):
                    self.assertEqual(os.environ['GEMINI_API_KEY'], CANARY)
                    result = subprocess.run(args, cwd=temp, capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(result.stdout.strip(), b'True')
                    self.assertNotIn(CANARY.encode(), result.stdout + result.stderr)
                    self.assertNotIn(CANARY, ' '.join(args))
                    self.assertEqual(list(Path(temp).iterdir()), [])
                    raise RuntimeError('server stopped')
            self.assertEqual(os.environ['GEMINI_API_KEY'], 'invalid old key')

    def test_blank_input_removes_invalid_key_only_for_session(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY':'invalid old key'}), \
                patch('getpass.getpass', return_value=''):
            with prompt_gemini_key(True):
                self.assertNotIn('GEMINI_API_KEY', os.environ)
            self.assertEqual(os.environ['GEMINI_API_KEY'], 'invalid old key')

    def test_prompt_failures_stop_before_serve_or_storage_without_private_error(self):
        def no_hidden_input(*args):
            warnings.warn('private tty detail', getpass.GetPassWarning)
            self.fail('must not continue to echoed input')
        failures = [EOFError('private tty detail'), KeyboardInterrupt(),
                    OSError('private tty detail'), no_hidden_input]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__), tempfile.TemporaryDirectory() as temp, \
                    patch.dict(os.environ, {'GEMINI_API_KEY':''}), \
                    patch('sys.argv', ['media_clarity', '--prompt-gemini-key', '--data-dir', temp]), \
                    patch('getpass.getpass', side_effect=failure), \
                    patch('media_clarity.__main__.serve') as serve, \
                    contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(main(), 1)
                self.assertEqual(errors.getvalue(), 'ERROR: gemini_key_input_unavailable\n')
                serve.assert_not_called()
                self.assertEqual(list(Path(temp).iterdir()), [])

    def test_invalid_key_stops_before_serve_and_restores_environment(self):
        for invalid in (CANARY+'\r\n', CANARY+'\0', '한글', 'a'*513):
            with self.subTest(kind=repr(invalid[-2:])), patch.dict(os.environ, {'GEMINI_API_KEY':''}), \
                patch('sys.argv', ['media_clarity', '--prompt-gemini-key']), \
                patch('getpass.getpass', return_value=invalid), \
                patch('media_clarity.__main__.serve') as serve, \
                contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(main(), 1)
                self.assertEqual(errors.getvalue(), 'ERROR: gemini_key_invalid\n')
                self.assertEqual(os.environ['GEMINI_API_KEY'], '')
                serve.assert_not_called()

    def test_successful_main_scopes_prompt_to_serve(self):
        with patch.dict(os.environ), \
                patch('sys.argv', ['media_clarity', '--prompt-gemini-key']), \
                patch('getpass.getpass', return_value=CANARY), \
                patch('media_clarity.__main__.serve') as serve:
            # Remove only the credential. Windows Path.home needs its normal
            # user environment even before argument parsing creates the app.
            os.environ.pop('GEMINI_API_KEY', None)
            def run(args):
                self.assertEqual(os.environ['GEMINI_API_KEY'], CANARY)
                return 0
            serve.side_effect = run
            self.assertEqual(main(), 0)
            self.assertNotIn('GEMINI_API_KEY', os.environ)

    def test_prompt_is_serve_only_and_doctor_reports_format_without_key(self):
        with patch('sys.argv', ['media_clarity', 'doctor', '--prompt-gemini-key']), \
                contextlib.redirect_stderr(io.StringIO()), patch('getpass.getpass') as prompt:
            with self.assertRaises(SystemExit) as error:
                main()
            self.assertEqual(error.exception.code, 2)
            prompt.assert_not_called()
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'GEMINI_API_KEY':CANARY}), \
                patch('sys.argv', ['media_clarity', 'doctor', '--data-dir', temp]), \
                patch('socket.socket.connect', side_effect=AssertionError('no network allowed')), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(), 0)
            self.assertTrue(json.loads(output.getvalue())['gemini_configured'])
            self.assertNotIn(CANARY, output.getvalue())
            for path in Path(temp).rglob('*'):
                if path.is_file():
                    self.assertNotIn(CANARY.encode(), path.read_bytes())
