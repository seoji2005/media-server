"""Viewing-only install planning, isolated interpreter checks, and preservation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from media_clarity.storage import MediaError, open_lock
from scripts import install_runtime as install

ROOT = Path(__file__).resolve().parents[1]


class ViewingInstallTests(unittest.TestCase):
    def fixture(self, base):
        repo=base/'감상 시작';repo.mkdir()
        data=base/'보관함';data.mkdir()
        shutil.copyfile(ROOT/'requirements.txt',repo/'requirements.txt')
        # No Qwen requirements file: viewing must not read it at all.
        args=type('Args',(),{'data_dir':data,'device':None,'viewing_only':True})()
        return repo,data,args

    def test_viewing_uses_only_pypi_pins_and_preserves_full_environment_and_model_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            repo,data,args=self.fixture(Path(temp))
            (repo/'.venv').mkdir();original=repo/'.venv/owner-file';original.write_bytes(b'keep full runtime')
            (data/'models').mkdir();settings=data/'models/settings.json';settings.write_bytes(b'owner settings even if invalid')
            database=data/'library.sqlite3';database.write_bytes(b'untouched database')
            commands=[]
            def command(argv,env,*a,**kw):
                commands.append(argv)
                self.assertNotIn('GEMINI_API_KEY',env)
                if 'venv' in argv:(repo/'.venv-viewing').mkdir()
                return b'pip 25.0.1 fixture' if '--version' in argv else b''
            with patch.object(install,'ROOT',repo), patch.object(install,'command',side_effect=command), \
                    patch.object(install,'viewing_check',return_value={'state':'ready','mode':'viewing_only'}), \
                    patch.object(install,'device_configuration',side_effect=AssertionError('model settings read')), \
                    patch.object(install,'native_check',side_effect=AssertionError('model probe')), \
                    patch.dict(os.environ,{'GEMINI_API_KEY':'synthetic-private'}):
                events=[];install.install(args,events.append)
            self.assertEqual([e['check']['name'] for e in events if 'check' in e],list(install.VIEWING_STAGES))
            self.assertEqual(events[-1],{'state':'ready'})
            downloads=[c for c in commands if 'download' in c and '--help' not in c]
            self.assertEqual(len(downloads),1)
            self.assertIn('https://pypi.org/simple',downloads[0])
            self.assertEqual(downloads[0][downloads[0].index('--retries')+1],'0')
            self.assertFalse(any('torch' in word.lower() or 'requirements-qwen' in word for c in commands for word in c))
            self.assertEqual(original.read_bytes(),b'keep full runtime')
            self.assertEqual(settings.read_bytes(),b'owner settings even if invalid')
            self.assertEqual(database.read_bytes(),b'untouched database')

    def test_existing_viewing_environment_never_installs_even_when_invalid(self):
        with tempfile.TemporaryDirectory() as temp:
            repo,data,args=self.fixture(Path(temp))
            target=repo/'.venv-viewing';target.mkdir();kept=target/'partial';kept.write_bytes(b'preserved')
            for valid in (True,False):
                with patch.object(install,'ROOT',repo), patch.object(install,'command') as command, \
                        patch.object(install,'viewing_check',return_value={'state':'ready','mode':'viewing_only'},
                                     side_effect=None if valid else MediaError('install_existing_environment_invalid')):
                    if valid:install.install(args,lambda e:None)
                    else:
                        with self.assertRaisesRegex(MediaError,'install_existing_environment_invalid'):
                            install.install(args,lambda e:None)
                    command.assert_not_called()
            self.assertEqual(kept.read_bytes(),b'preserved')
            self.assertFalse((repo/'.venv').exists())

    def test_actual_viewing_probe_is_read_only_and_rejects_wrong_versions(self):
        # Tiny package fixtures exercise isolation/version/import behavior without
        # registry traffic. Actual app imports/startup are a separate HTTP check.
        with tempfile.TemporaryDirectory() as temp:
            repo,data,args=self.fixture(Path(temp));target=repo/'.venv-viewing'
            subprocess.run([sys.executable,'-I','-m','venv','--copies','--without-pip',str(target)],check=True,capture_output=True,timeout=30)
            python=target/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
            # -I ignores PYTHONUTF8; Windows pipes may use an ANSI code page.
            # ASCII JSON preserves the Korean path without relying on that page.
            site=Path(json.loads(subprocess.check_output([str(python),'-I','-c',
                "import json,sysconfig;print(json.dumps(sysconfig.get_path('purelib')))"],
                encoding='ascii',timeout=10)))
            for name in ('fastapi','uvicorn'):
                (site/(name+'.py')).write_text('# synthetic import\n')
                dist=site/(name+'-1.0.dist-info');dist.mkdir()
                (dist/'METADATA').write_text('Metadata-Version: 2.1\nName: '+name+'\nVersion: 1.0\n')
            def snapshot():return {str(p.relative_to(target)):(p.stat().st_size,p.stat().st_mtime_ns) for p in target.rglob('*') if p.is_file()}
            before=snapshot();env=install.environment()
            value=install.viewing_check(python,target,{'requirements.txt':'fastapi==1.0\nuvicorn==1.0\n'},env,lambda e:None)
            self.assertEqual(value,{'state':'ready','mode':'viewing_only'})
            with self.assertRaisesRegex(MediaError,'install_existing_environment_invalid'):
                install.viewing_check(python,target,{'requirements.txt':'fastapi==2.0\n'},env,lambda e:None)
            self.assertEqual(snapshot(),before)

    def test_worker_lock_and_bad_requirements_block_before_environment_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            repo,data,args=self.fixture(Path(temp))
            with patch.object(install,'ROOT',repo), patch.object(install,'command') as command:
                with open_lock(data/'worker.lock','busy',409), self.assertRaisesRegex(MediaError,'processing_worker_active'):
                    install.install(args,lambda e:None)
                (repo/'requirements.txt').write_text('fastapi>=1.0\n')
                with self.assertRaisesRegex(MediaError,'install_requirements_invalid'):
                    install.install(args,lambda e:None)
                command.assert_not_called()
            self.assertFalse((repo/'.venv-viewing').exists())

    def test_cli_viewing_budget_and_conflicting_options(self):
        with patch.object(sys,'argv',['install_runtime.py','--viewing-only','--json']), \
                patch.object(install,'run_setup',return_value={'state':'ready','checks':[]}) as run, \
                patch('builtins.print'):
            self.assertEqual(install.main(),0)
            self.assertEqual(run.call_args.kwargs['total_seconds'],600)
            self.assertEqual(run.call_args.kwargs['idle_seconds'],120)
            self.assertEqual(run.call_args.kwargs['expected_checks'],6)
        for option in (['--device','cpu'],['--asr-bundle','cache'],['--restore-worker']):
            result=subprocess.run([sys.executable,str(ROOT/'scripts/install_runtime.py'),'--viewing-only',*option],capture_output=True,timeout=10)
            self.assertEqual(result.returncode,2)
            self.assertIn(b'cannot select a device or restore models',result.stderr)
