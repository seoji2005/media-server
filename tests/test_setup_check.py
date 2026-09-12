"""Setup evidence, early failure, partial results and owned-process deadlines."""
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from media_clarity.storage import MediaError
from scripts import check_setup as setup


class SetupCheckTests(unittest.TestCase):
    def test_exact_pins_local_torch_tag_range_and_missing_package(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'requirements.txt').write_text('fastapi==0.141.1\n')
            (root/'requirements-qwen.txt').write_text('torch==2.8.0\nnumpy>=2.0,<3\n')
            versions = {'fastapi':'0.141.1', 'torch':'2.8.0+cu128', 'numpy':'2.5.3'}
            with patch.object(setup, 'ROOT', root), patch('importlib.metadata.version', side_effect=versions.__getitem__):
                self.assertTrue(all(p['state'] == 'ready' for p in setup.package_checks()))
                versions.update(torch='2.14.0+cpu', numpy='3.0.0')
                self.assertEqual([p['state'] for p in setup.package_checks()], ['ready','blocked','blocked'])
                versions['torch'] = 'private/path?secret=value'
                self.assertEqual(setup.package_checks()[1]['installed'], 'unrecognized')
            with patch.object(setup, 'ROOT', root), patch('importlib.metadata.version', side_effect=importlib.metadata.PackageNotFoundError):
                self.assertTrue(all(p['installed'] is None for p in setup.package_checks()))

    def test_unsupported_requirement_never_echoes_its_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'requirements.txt').write_text('private/path?secret=value\n')
            events = []
            with patch.object(setup, 'ROOT', root), patch.object(setup, 'run_media', side_effect=MediaError('ffmpeg_unavailable')):
                setup.collect(root, events.append)
            self.assertNotIn('private/path', json.dumps(events))
            self.assertIn('requirements_check_failed', json.dumps(events))

    def test_missing_dependencies_or_failed_binary_skip_native_models(self):
        for packages, binary in (([{'state':'blocked'}], b'ffmpeg version test'),
                                 ([{'state':'ready'}], OSError('private/path'))):
            events = []
            with patch.object(setup, 'package_checks', return_value=packages), \
                    patch.object(setup, 'run_media', **({'side_effect':binary} if isinstance(binary, Exception)
                                                       else {'return_value':binary})), \
                    patch('media_clarity.model_check.diagnose') as probe:
                setup.collect(Path('unused'), events.append)
            probe.assert_not_called()
            self.assertEqual(events[-1], {'state':'blocked'})
            self.assertEqual(events[-2]['check']['error'], 'prerequisites_missing')
            self.assertNotIn('private/path', json.dumps(events))

    def test_ready_means_prerequisites_only_and_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); original = root/'original'; original.write_bytes(b'preserve')
            events = []
            with patch.object(setup, 'package_checks', return_value=[{'state':'ready'}]), \
                    patch.object(setup, 'run_media', side_effect=lambda args,*a:(args[0]+' version fixture').encode()), \
                    patch('media_clarity.model_check.diagnose', return_value={'state':'ready','device':'cpu','selection':'default','error':None}):
                setup.collect(root, events.append)
            self.assertEqual(events[-1], {'state':'ready'})
            self.assertEqual(original.read_bytes(), b'preserve')
            self.assertEqual(list(root.iterdir()), [original])

    def test_actual_diagnostic_keeps_credentials_and_missing_library_out_of_child(self):
        real_popen = subprocess.Popen
        observed = []
        def launch(*args, **kwargs):
            observed.append(kwargs['env'])
            return real_popen(*args, **kwargs)
        with tempfile.TemporaryDirectory() as temp, \
                patch.dict(os.environ, {'GEMINI_API_KEY':'Synthetic-setup-canary.19'}), \
                patch.object(setup.subprocess, 'Popen', side_effect=launch):
            root = Path(temp)/'private-library'
            result = setup.check_setup(root)
            self.assertEqual(result['state'], 'blocked')
            self.assertTrue(result['gemini_configured'])
            self.assertEqual(result['api_connection'], 'not_checked')
            self.assertFalse(root.exists())
            self.assertNotIn(str(root), json.dumps(result))
            self.assertNotIn('Synthetic-setup-canary', json.dumps(result))
        self.assertEqual(len(observed), 1)
        self.assertNotIn('GEMINI_API_KEY', observed[0])
        self.assertNotIn('GOOGLE_API_KEY', observed[0])

    def test_total_and_idle_caps_keep_partial_results_and_stop_only_owned_child(self):
        real_popen = subprocess.Popen
        code = '''import sys,time,json
sys.stdin.buffer.read(1)
print(json.dumps({'check':{'name':'python','state':'ready'}}),flush=True)
time.sleep(30)
'''
        for total, idle in ((3, 75), (10, 2)):
            owned = []
            def launch(args, **kwargs):
                process = real_popen([sys.executable, '-c', code], **kwargs)
                owned.append(process)
                return process
            unrelated = real_popen([sys.executable, '-c', 'import time;time.sleep(30)'])
            try:
                with self.subTest(total=total, idle=idle), patch.object(setup, 'TOTAL_SECONDS', total), \
                        patch.object(setup, 'IDLE_SECONDS', idle), \
                        patch.object(setup.subprocess, 'Popen', side_effect=launch):
                    result = setup.check_setup(Path('unused'))
                self.assertEqual(result['error'], 'setup_check_timeout')
                self.assertEqual(result['state'], 'blocked')
                self.assertEqual(result['checks'], [{'name':'python','state':'ready'}])
                self.assertIsNotNone(owned[0].poll())
                self.assertIsNone(unrelated.poll())
            finally:
                unrelated.terminate(); unrelated.wait(timeout=5)

