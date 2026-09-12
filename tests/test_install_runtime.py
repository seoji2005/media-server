"""Bounded first installation, non-overwrite, and real offline pip boundaries."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts import install_runtime as install
from scripts.check_setup import run_setup
from media_clarity.storage import MediaError, open_lock

ROOT = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def fixture(self, base):
        repo = base/'repo'; repo.mkdir()
        data = base/'library'; data.mkdir()
        for name in ('requirements.txt','requirements-qwen.txt'):
            shutil.copyfile(ROOT/name,repo/name)
        args = type('Args',(),{'data_dir':data,'device':None})()
        return repo, data, args

    def test_reuse_never_installs_or_changes_existing_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            repo,data,args = self.fixture(Path(temp))
            (repo/'.venv').mkdir(); sentinel = repo/'.venv/user-file'; sentinel.write_bytes(b'keep')
            (data/'models').mkdir(); settings=data/'models/settings.json'
            settings.write_bytes(b'{"device":"cpu"}\n')
            with patch.object(install,'ROOT',repo), patch.object(install,'run_media',side_effect=lambda c,*a:(c[0]+' version test').encode()), \
                    patch.object(install,'native_check',return_value={'state':'ready','device':'cpu'}), patch.object(install,'command') as cmd:
                events=[]; install.install(args,events.append)
                cmd.assert_not_called()
            self.assertEqual(sentinel.read_bytes(),b'keep')
            self.assertEqual(settings.read_bytes(),b'{"device":"cpu"}\n')
            self.assertEqual(events[-1],{'state':'ready'})

    def test_broken_existing_environment_is_preserved_without_pip(self):
        with tempfile.TemporaryDirectory() as temp:
            repo,data,args = self.fixture(Path(temp))
            (repo/'.venv').mkdir(); (repo/'.venv/partial').write_bytes(b'completed')
            with patch.object(install,'ROOT',repo), patch.object(install,'run_media',side_effect=lambda c,*a:(c[0]+' version test').encode()), \
                    patch.object(install,'native_check',side_effect=MediaError('install_existing_environment_invalid')), patch.object(install,'command') as cmd:
                with self.assertRaises(MediaError): install.install(args,lambda e:None)
                cmd.assert_not_called()
            self.assertEqual((repo/'.venv/partial').read_bytes(),b'completed')

    def test_busy_worker_blocks_first_device_setting_and_all_package_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            repo,data,args = self.fixture(Path(temp)); args.device='cuda'
            with open_lock(data/'worker.lock','busy',409), patch.object(install,'ROOT',repo), \
                    patch.object(install,'run_media',side_effect=lambda c,*a:(c[0]+' version test').encode()), patch.object(install,'command') as cmd:
                with self.assertRaises(MediaError) as caught: install.install(args,lambda e:None)
                self.assertEqual(caught.exception.code,'processing_worker_active'); cmd.assert_not_called()
            self.assertFalse((data/'models/settings.json').exists())
            self.assertFalse((repo/'.venv').exists())

    def test_conflicting_setting_and_untrusted_requirements_stop_before_commands(self):
        with tempfile.TemporaryDirectory() as temp:
            repo,data,args = self.fixture(Path(temp)); args.device='cuda'
            (data/'models').mkdir(); settings=data/'models/settings.json'; settings.write_text('{"device":"cpu"}')
            with patch.object(install,'ROOT',repo), patch.object(install,'run_media',side_effect=lambda c,*a:(c[0]+' version test').encode()), patch.object(install,'command') as cmd:
                with self.assertRaises(MediaError) as caught: install.install(args,lambda e:None)
                self.assertEqual(caught.exception.code,'install_device_conflict')
                (repo/'requirements.txt').write_text('--extra-index-url https://example.invalid\n')
                with self.assertRaises(MediaError) as caught: install.install(args,lambda e:None)
                self.assertEqual(caught.exception.code,'install_requirements_invalid'); cmd.assert_not_called()
            self.assertEqual(settings.read_text(),'{"device":"cpu"}')

    def test_child_environment_removes_keys_and_pip_targets_preserves_tls_route(self):
        values={'GEMINI_API_KEY':'synthetic-private','GOOGLE_API_KEY':'synthetic-private',
                'PIP_INDEX_URL':'https://example.invalid','PIP_TARGET':'elsewhere',
                'PIP_TRUSTED_HOST':'example.invalid','PYTHONPATH':'elsewhere',
                'HTTPS_PROXY':'http://configured.invalid','SSL_CERT_FILE':'existing-ca'}
        with patch.dict(os.environ,values): env=install.environment()
        for key in values:
            if key not in ('HTTPS_PROXY','SSL_CERT_FILE'): self.assertNotIn(key,env)
        self.assertEqual(env['PIP_CONFIG_FILE'],os.devnull)
        self.assertEqual(env['HTTPS_PROXY'],values['HTTPS_PROXY'])
        self.assertEqual(env['SSL_CERT_FILE'],'existing-ca')

    def test_real_command_failure_keeps_exit_code_without_raw_output(self):
        events=[]
        with self.assertRaises(MediaError):
            install.command([sys.executable,'-c',"print('private/path token-value ProxyError');raise SystemExit(7)"],install.environment(),events.append)
        self.assertEqual(events,[{'check':{'name':'install','state':'blocked','exit_code':7,'reason':'proxy_error'}}])

    def test_offline_pip_guard_runs_in_actual_child_before_pip_entry(self):
        argv=install.pip_command(sys.executable,'install',[],[])
        guard=argv[3]
        injected="""import sys,runpy
def probe(*a,**kw):
 for event in ('socket.connect','socket.getaddrinfo','socket.sendto'):
  try: sys.audit(event,None,None)
  except OSError: continue
  raise AssertionError('network audit event was allowed')
 print('blocked')
runpy.run_module=probe
"""
        result=install.command([sys.executable,'-I','-c',injected+guard],install.environment(),lambda e:None,timeout=10)
        self.assertEqual(result.strip(),b'blocked')

    def test_stalled_owned_install_keeps_completed_file_and_releases_locks(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp); completed=base/'completed.whl'
            code = '''import os,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from scripts.check_setup import worker_output
from media_clarity.storage import open_lock
out=worker_output()
with open_lock(Path(sys.argv[2])/'worker.lock','busy',409):
 Path(sys.argv[2]+'/completed.whl').write_bytes(b'preserved')
 os.write(out,b'{"check":{"name":"torch","state":"ready"}}\\n')
 time.sleep(10)
'''
            result=run_setup([sys.executable,'-c',code,str(ROOT),str(base)],total_seconds=1,idle_seconds=.4,expected_checks=7)
            self.assertEqual(result['state'],'blocked')
            self.assertEqual(result['error'],'setup_check_timeout')
            self.assertEqual(result['checks'],[{'name':'torch','state':'ready'}])
            self.assertEqual(completed.read_bytes(),b'preserved')
            with open_lock(base/'worker.lock','busy',409): pass

    def test_real_pip_download_and_install_from_local_wheel_only(self):
        # No registry or network. Exercise the actual pip CLI flags and .venv target.
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp); wheels=base/'wheels'; wheels.mkdir(); downloaded=base/'downloaded'; downloaded.mkdir()
            dist='media_install_fixture-1.0.dist-info'
            with zipfile.ZipFile(wheels/'media_install_fixture-1.0-py3-none-any.whl','w') as z:
                z.writestr('media_install_fixture.py','VALUE = 42\n')
                z.writestr(dist+'/METADATA','Metadata-Version: 2.1\nName: media-install-fixture\nVersion: 1.0\n')
                z.writestr(dist+'/WHEEL','Wheel-Version: 1.0\nGenerator: tests\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
                z.writestr(dist+'/RECORD','')
            env=install.environment(); venv=base/'venv'
            install.command([sys.executable,'-I','-m','venv','--copies',str(venv)],env,lambda e:None,(venv,),timeout=45)
            python=venv/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
            help_text=install.command([str(python),'-I','-m','pip','download','--help'],env,lambda e:None,timeout=15)
            version=install.command([str(python),'-I','-m','pip','--version'],env,lambda e:None,timeout=15)
            flags=[] if version.startswith(b'pip 25.0.1 ') else install.pip_flags(help_text)
            install.command(install.pip_command(python,'download',['media-install-fixture==1.0','--no-index','--find-links',str(wheels),'--dest',str(downloaded),'--only-binary=:all:'],flags),env,lambda e:None,(downloaded,),timeout=30)
            install.command(install.pip_command(python,'install',['media-install-fixture==1.0','--no-index','--find-links',str(downloaded),'--only-binary=:all:'],flags),env,lambda e:None,(venv,),timeout=30)
            value=install.command([str(python),'-I','-c','import media_install_fixture;print(media_install_fixture.VALUE)'],env,lambda e:None,timeout=10)
            self.assertEqual(value.strip(),b'42')


if __name__=='__main__': unittest.main()
