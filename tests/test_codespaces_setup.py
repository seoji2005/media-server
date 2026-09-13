"""No package/apt requests: prerequisite planning and real owned timeout cleanup."""
import os
from pathlib import Path
import sys
import signal
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts import setup_codespaces as setup


@unittest.skipUnless(sys.platform == 'linux', 'Linux Codespaces installer')
class CodespacesSetupTests(unittest.TestCase):
    def test_normal_command_exits_and_returns_complete_bounded_capture(self):
        output = setup.command([sys.executable, '-c', 'print("bounded-ok")'],
                               setup.environment(), time.monotonic()+5, capture=True)
        self.assertEqual(output, b'bounded-ok\n')

    def test_runtime_plan_excludes_models_and_preserves_other_environments(self):
        with tempfile.TemporaryDirectory(prefix='설치 공간 ') as temporary:
            root = Path(temporary)
            existing = root / '.venv'; existing.mkdir()
            marker = existing / 'original'; marker.write_bytes(b'keep')
            with patch.object(setup, 'ROOT', root), patch.dict(os.environ, {
                'CODESPACES':'true', 'GEMINI_API_KEY':'synthetic-placeholder',
                'PIP_EXTRA_INDEX_URL':'https://invalid.test/simple'}), \
                 patch('scripts.setup_codespaces.shutil.which', return_value='/tool'), \
                 patch.object(setup, 'command', side_effect=lambda argv,*a,**k:
                     b'pip 26.0 ' if '--version' in argv else b'--resume-retries') as command, patch('builtins.print'):
                setup.main()
            argv = [c.args[0] for c in command.call_args_list]
            self.assertFalse(any('sudo' in a or 'apt-get' in a for a in argv))
            pip = next(a for a in argv if 'install' in a and 'pip' in a and '--help' not in a)
            self.assertEqual(pip[pip.index('--retries')+1], '0')
            self.assertEqual(pip[pip.index('--resume-retries')+1], '0')
            self.assertEqual(pip[-1], str(root / 'requirements.txt'))
            self.assertFalse(any('qwen' in v or 'torch' in v for a in argv for v in a))
            for call in command.call_args_list:
                self.assertNotIn('GEMINI_API_KEY', call.args[1])
                self.assertNotIn('PIP_EXTRA_INDEX_URL', call.args[1])
            self.assertEqual(marker.read_bytes(), b'keep')

    def test_apt_runs_in_root_image_stage_and_nonroot_setup_requires_image(self):
        with patch('os.geteuid', return_value=0), patch.object(setup, 'command') as command, patch('builtins.print'):
            setup.system_tools()
        args = [c.args[0] for c in command.call_args_list]
        self.assertEqual(len(args), 2)
        self.assertTrue(all(a[0] == 'apt-get' and 'Acquire::Retries=0' in a for a in args))
        with patch('os.geteuid', return_value=1000), patch.object(setup, 'command') as command:
            with self.assertRaisesRegex(RuntimeError, 'codespaces_image_build_required'):
                setup.system_tools()
            command.assert_not_called()

    def test_unknown_pip_without_resume_control_stops_before_download(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(setup, 'ROOT', Path(temporary)), \
             patch.dict(os.environ, {'CODESPACES':'true'}), \
             patch('scripts.setup_codespaces.shutil.which', return_value='/tool'), \
             patch.object(setup, 'command', return_value=b'unknown pip') as command:
            with self.assertRaisesRegex(Exception, 'install_pip_unsupported'):
                setup.main()
            self.assertFalse(any('install' in c.args[0] and '--help' not in c.args[0]
                                 for c in command.call_args_list))

    def test_parent_sigterm_and_sigkill_close_liveness_pipe(self):
        for sig in (signal.SIGTERM, signal.SIGKILL):
            with self.subTest(signal=sig), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); ready = root/'ready'; late = root/'survived'
                child = (f'from pathlib import Path; import time; Path({str(ready)!r}).touch(); '
                         f'time.sleep(.8); Path({str(late)!r}).touch()')
                argv = [sys.executable, '-c', child]
                parent = ('from scripts.setup_codespaces import command; import os,time; '
                          f'command({argv!r},os.environ.copy(),time.monotonic()+5)')
                process = subprocess.Popen([sys.executable, '-c', parent], cwd=setup.ROOT,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    deadline = time.monotonic()+5
                    while not ready.exists() and process.poll() is None and time.monotonic()<deadline:
                        time.sleep(.02)
                    self.assertTrue(ready.exists(), 'actual descendant started before parent termination')
                    process.send_signal(sig); process.wait(timeout=5)
                    time.sleep(1)
                    self.assertFalse(late.exists(), 'descendant survived its parent')
                finally:
                    if process.poll() is None:
                        process.kill(); process.wait(timeout=5)

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
