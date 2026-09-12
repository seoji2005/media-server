"""No package/apt requests: prerequisite planning and real owned timeout cleanup."""
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts import setup_codespaces as setup


@unittest.skipUnless(sys.platform == 'linux', 'Linux Codespaces installer')
class CodespacesSetupTests(unittest.TestCase):
    def test_runtime_plan_excludes_models_and_preserves_other_environments(self):
        with tempfile.TemporaryDirectory(prefix='설치 공간 ') as temporary:
            root = Path(temporary)
            existing = root / '.venv'; existing.mkdir()
            marker = existing / 'original'; marker.write_bytes(b'keep')
            with patch.object(setup, 'ROOT', root), patch.dict(os.environ, {
                'CODESPACES':'true', 'GEMINI_API_KEY':'synthetic-placeholder',
                'PIP_EXTRA_INDEX_URL':'https://invalid.test/simple'}), \
                 patch('scripts.setup_codespaces.shutil.which', return_value=None), \
                 patch.object(setup, 'command') as command, patch('builtins.print'):
                setup.main()
            argv = [c.args[0] for c in command.call_args_list]
            self.assertEqual(argv[0][-2:], ['update','-qq'])
            self.assertIn('Acquire::Retries=0', argv[0])
            pip = next(a for a in argv if 'install' in a and 'pip' in a)
            self.assertEqual(pip[pip.index('--retries')+1], '0')
            self.assertEqual(pip[-1], str(root / 'requirements.txt'))
            self.assertFalse(any('qwen' in v or 'torch' in v for a in argv for v in a))
            for call in command.call_args_list:
                self.assertNotIn('GEMINI_API_KEY', call.args[1])
                self.assertNotIn('PIP_EXTRA_INDEX_URL', call.args[1])
            self.assertEqual(marker.read_bytes(), b'keep')

    def test_no_progress_kills_owned_parent_and_child_without_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            late = Path(temporary) / 'child-survived'
            child = f'import time; from pathlib import Path; time.sleep(1); Path({str(late)!r}).write_text("bad")'
            parent = f'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",{child!r}]); time.sleep(30)'
            with patch.object(setup, 'IDLE_SECONDS', .15):
                with self.assertRaisesRegex(RuntimeError, '^setup_progress_timeout$'):
                    setup.command([sys.executable, '-c', parent], os.environ.copy(), time.monotonic()+5)
            time.sleep(1.1)
            self.assertFalse(late.exists())

    def test_total_limit_applies_even_when_output_progresses(self):
        argv = [sys.executable, '-u', '-c', 'import time\nwhile True:\n print("progress"); time.sleep(.02)']
        with self.assertRaisesRegex(RuntimeError, '^setup_progress_timeout$'):
            setup.command(argv, os.environ.copy(), time.monotonic()+.15)


if __name__ == '__main__':
    unittest.main()
