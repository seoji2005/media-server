"""Browser failure isolation and real Windows shell dispatch; no model inference."""
import asyncio
import contextlib
import io
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import uvicorn
from media_clarity.launch import BrowserServer, open_page
from media_clarity.storage import Store

ROOT = Path(__file__).resolve().parents[1]


class LaunchTests(unittest.TestCase):
    def test_browser_failure_has_fixed_fallback_without_exception_text(self):
        for result in (False, OSError('private/browser/configuration')):
            output = io.StringIO()
            kwargs = {'side_effect':result} if isinstance(result, Exception) else {'return_value':result}
            with patch('webbrowser.open', **kwargs), contextlib.redirect_stdout(output):
                open_page('http://127.0.0.1:8765')
            self.assertIn('직접 입력',output.getvalue())
            self.assertNotIn('private',output.getvalue())

    def test_failed_startup_never_opens_page(self):
        server = BrowserServer(uvicorn.Config(None))
        with patch.object(uvicorn.Server,'startup',new=AsyncMock(side_effect=SystemExit(3))), patch('media_clarity.launch.threading.Thread') as thread:
            with self.assertRaises(SystemExit): asyncio.run(server.startup())
            thread.assert_not_called()

    def test_real_port_conflict_never_opens_another_service_and_releases_store(self):
        try:
            sock = socket.socket(); sock.bind(('127.0.0.1',0)); sock.listen(1)
        except PermissionError:
            if os.environ.get('CI'): raise
            self.skipTest('Local socket permission unavailable; mandatory in CI')
        with sock, tempfile.TemporaryDirectory() as temp:
            data = Path(temp)/'private-library'; marker = Path(temp)/'opened'
            code = '''import sys,webbrowser
from pathlib import Path
from media_clarity.__main__ import main
data,port,marker=sys.argv[1:]
webbrowser.open=lambda *a,**k:Path(marker).write_text('unexpected')
sys.argv=['media_clarity','--data-dir',data,'--port',port,'--open-browser']
raise SystemExit(main())'''
            result = subprocess.run([sys.executable,'-c',code,str(data),str(sock.getsockname()[1]),str(marker)],
                                    cwd=ROOT,capture_output=True,timeout=15)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(marker.exists())
            self.assertNotIn(str(data).encode(),result.stdout+result.stderr)
            store=Store(data); store.start(); store.close()

    @unittest.skipUnless(os.name == 'nt','Windows cmd dispatch runs in Windows CI')
    def test_windows_launcher_handles_spaces_unicode_and_missing_setup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'Media Clarity & 공간 !'; root.mkdir()
            script = root/'start-media-clarity.cmd'
            shutil.copyfile(ROOT/script.name,script)
            gemini_script = root/'start-media-clarity-gemini.cmd'
            shutil.copyfile(ROOT/gemini_script.name,gemini_script)
            check_script = root/'check-media-clarity.cmd'
            shutil.copyfile(ROOT/check_script.name,check_script)
            restore_script = root/'restore-qwen-models.cmd'
            shutil.copyfile(ROOT/restore_script.name,restore_script)
            install_script = root/'install-media-clarity.cmd'
            shutil.copyfile(ROOT/install_script.name,install_script)
            def run(launcher=script):
                return subprocess.run(['cmd.exe','/d','/c','call',str(launcher),'--help'],cwd=temp,
                    stdin=subprocess.DEVNULL,capture_output=True,timeout=20)
            missing = run()
            self.assertEqual(missing.returncode,1)
            self.assertIn('처음 실행 설정',missing.stdout.decode('utf-8'))
            missing_gemini = run(gemini_script)
            self.assertEqual(missing_gemini.returncode,1)
            self.assertIn('처음 실행 설정',missing_gemini.stdout.decode('utf-8'))
            self.assertEqual(run(check_script).returncode,1)
            self.assertEqual(run(restore_script).returncode,1)
            shutil.copytree(ROOT/'media_clarity',root/'media_clarity',ignore=shutil.ignore_patterns('__pycache__'))
            (root/'scripts').mkdir()
            shutil.copyfile(ROOT/'scripts/check_setup.py',root/'scripts/check_setup.py')
            shutil.copyfile(ROOT/'scripts/restore_qwen_cache.py',root/'scripts/restore_qwen_cache.py')
            shutil.copyfile(ROOT/'scripts/install_runtime.py',root/'scripts/install_runtime.py')
            ready_install = run(install_script)
            self.assertEqual(ready_install.returncode,0,ready_install.stderr.decode('utf-8',errors='replace'))
            self.assertIn(b'--device',ready_install.stdout)
            subprocess.run([sys.executable,'-m','venv','--without-pip','--system-site-packages',str(root/'.venv')],
                           check=True,capture_output=True,timeout=30)
            ready = run()
            self.assertEqual(ready.returncode,0,ready.stderr.decode('utf-8',errors='replace'))
            self.assertIn(b'--open-browser',ready.stdout)
            ready_gemini = run(gemini_script)
            self.assertEqual(ready_gemini.returncode,0,ready_gemini.stderr.decode('utf-8',errors='replace'))
            self.assertIn(b'--prompt-gemini-key',ready_gemini.stdout)
            ready_check = run(check_script)
            self.assertEqual(ready_check.returncode,0,ready_check.stderr.decode('utf-8',errors='replace'))
            self.assertIn(b'--json',ready_check.stdout)
            ready_restore = run(restore_script)
            self.assertEqual(ready_restore.returncode,0,ready_restore.stderr.decode('utf-8',errors='replace'))
            self.assertIn(b'--verify-only',ready_restore.stdout)
