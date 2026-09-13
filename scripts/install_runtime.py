"""Prepare a full or viewing-only runtime, preserving existing environments and model data."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
from time import monotonic, sleep

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_clarity.storage import MediaError, default_data_dir, no_symlink, open_lock, run_media
from media_clarity.models import device_configuration
from scripts.check_setup import run_setup, worker_output

TOTAL_SECONDS = 1800
VIEWING_SECONDS = 600
IDLE_SECONDS = 120
TORCH = {'cpu':'2.8.0+cpu', 'cuda':'2.8.0+cu126'}
INDEX = {'cpu':'https://download.pytorch.org/whl/cpu', 'cuda':'https://download.pytorch.org/whl/cu126'}
STAGES = ('preflight', 'environment', 'pip', 'torch', 'packages', 'dependencies', 'runtime')
VIEWING_STAGES = tuple(name for name in STAGES if name != 'torch')
ERRORS = {'unsafe_storage', 'already_running', 'processing_worker_active', 'setup_active',
          'install_platform_unsupported', 'install_device_conflict', 'model_settings_invalid',
          'install_existing_environment_invalid', 'install_pip_unsupported', 'install_failed',
          'install_command_failed', 'install_progress_timeout', 'install_output_limit',
          'install_prerequisites_missing', 'install_requirements_invalid', 'insufficient_space'}


def requirements_snapshot(viewing_only=False):
    result = {}
    for name in (('requirements.txt',) if viewing_only else ('requirements.txt','requirements-qwen.txt')):
        path = ROOT/name
        no_symlink(path)
        if not path.is_file() or path.stat().st_size > 65536:
            raise MediaError('install_requirements_invalid',503)
        content = path.read_text(encoding='utf-8')
        lines = [line.split('#',1)[0].strip() for line in content.splitlines()]
        if any(line and not re.fullmatch(r'[A-Za-z0-9_.-]+(?:(?:==|>=|<=|>|<)\d+(?:\.\d+)*)(?:,(?:==|>=|<=|>|<)\d+(?:\.\d+)*)*',line) for line in lines):
            raise MediaError('install_requirements_invalid',503)
        if viewing_only and any(line and not re.fullmatch(r'[A-Za-z0-9_.-]+==\d+(?:\.\d+)*',line) for line in lines):
            raise MediaError('install_requirements_invalid',503)
        result[name] = content
    if not viewing_only and 'torch==2.8.0' not in [line.split('#',1)[0].strip() for line in result['requirements-qwen.txt'].splitlines()]:
        raise MediaError('install_requirements_invalid',503)
    return result


def environment():
    # Keep the platform's existing TLS/proxy route, but never inherit pip indexes,
    # credentials, config, Python path injection or a user-selected install target.
    env = {k:v for k,v in os.environ.items() if not k.upper().startswith('PIP_')
           and k.upper() not in ('PYTHONPATH', 'PYTHONHOME', 'GEMINI_API_KEY',
                                'GOOGLE_API_KEY', 'HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN')}
    env.update(PIP_CONFIG_FILE=os.devnull, PYTHONUTF8='1', PYTHONUNBUFFERED='1')
    return env


def byte_count(paths):
    total = count = 0
    for root in paths:
        for directory, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if not (Path(directory)/d).is_symlink()]
            for name in files:
                count += 1
                if count > 150000:
                    raise MediaError('install_output_limit', 503)
                try:
                    path = Path(directory)/name
                    if not path.is_symlink():
                        total += path.stat().st_size
                except FileNotFoundError:
                    pass
    return total


def command(argv, env, emit, paths=(), *, timeout=TOTAL_SECONDS):
    """All descendants stay inside the install worker's owned group/Windows Job."""
    process = subprocess.Popen(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = bytearray()
    overflow = threading.Event()
    def drain():
        while block := process.stdout.read(8192):
            if len(output) + len(block) > 4 * 1024 * 1024:
                overflow.set()
            else:
                output.extend(block)
    reader = threading.Thread(target=drain, daemon=True); reader.start()
    started = last = tick = monotonic()
    previous = byte_count(paths)
    try:
        while process.poll() is None:
            now = monotonic()
            if overflow.is_set():
                raise MediaError('install_output_limit', 503)
            if now - started >= timeout or now - last >= IDLE_SECONDS:
                raise MediaError('install_progress_timeout', 503)
            if now - tick >= 2:
                current = byte_count(paths)
                if current != previous:
                    last = now
                    emit({'progress':'install'})
                previous, tick = current, now
            sleep(.2)
        reader.join(timeout=2)
        if reader.is_alive() or overflow.is_set():
            raise MediaError('install_output_limit', 503)
        if process.returncode:
            reason = next((code for pattern,code in (
                (b'ProxyError','proxy_error'), (b'ConnectTimeout','connect_timeout'),
                (b'ReadTimeout','read_timeout'), (b'CERTIFICATE_VERIFY_FAILED','tls_error'),
                (b'No matching distribution','no_matching_wheel'),
                (b'ResolutionImpossible','dependency_conflict')) if pattern in output),'command_failed')
            emit({'check':{'name':'install','state':'blocked','exit_code':process.returncode,'reason':reason}})
            raise MediaError('install_command_failed', 503)
        return bytes(output)
    finally:
        if process.poll() is None:
            process.kill(); process.wait(timeout=5)
        process.stdout.close()


def pip_flags(help_text):
    # Bundled Python 3.12 pip25.0.1 has no resume loop. Newer versions must expose
    # the explicit resume limit. Unknown older implementations stop before traffic.
    text = help_text.decode('utf-8', errors='replace')
    if '--resume-retries' in text:
        return ['--resume-retries', '0']
    raise MediaError('install_pip_unsupported', 503)


def pip_command(python, action, extra, flags):
    launch = [str(python), '-I', '-m', 'pip']
    if action == 'install':
        # --no-index alone does not prohibit a direct URL in wheel dependencies.
        # Enforce the offline boundary in the actual pip child before imports.
        launch = [str(python), '-I', '-c', """import sys,runpy
def offline(event, values):
 if event in ('socket.connect','socket.getaddrinfo','socket.sendto'):
  raise OSError('offline_install_network_blocked')
sys.addaudithook(offline)
runpy.run_module('pip',run_name='__main__',alter_sys=True)
"""]
    return [*launch, '--disable-pip-version-check', action,
            '--retries', '0', '--timeout', '20', '--no-input', '--no-cache-dir',
            '--keyring-provider', 'disabled', '--progress-bar', 'off',
            *flags, *extra]


def native_check(python, root, device, env, emit):
    code = """import json,struct,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from scripts.check_setup import package_checks
from media_clarity.model_check import diagnose
import importlib.metadata
packages=package_checks()
valid=(sys.version_info[:2]==(3,12) and struct.calcsize('P')==8 and
       Path(sys.prefix)==Path(sys.argv[2]) and sys.prefix!=sys.base_prefix and
       all(p['state']=='ready' for p in packages) and
       importlib.metadata.version('torch')==sys.argv[4])
result=diagnose(Path(sys.argv[3]),runtime_only=True) if valid else {'state':'blocked','error':'install_existing_environment_invalid'}
print(json.dumps(result))
"""
    # -I ignores Python environment flags: use -B for this interpreter and pass
    # the environment flag to diagnose's separate, non-isolated probe as well.
    native_env = {**env, 'PYTHONDONTWRITEBYTECODE':'1'}
    value = json.loads(command([str(python), '-I', '-B', '-c', code, str(ROOT),
                               str(ROOT/'.venv'), str(root), TORCH[device]], native_env, emit, timeout=75))
    if value.get('state') != 'ready' or value.get('device') != device:
        raise MediaError('install_existing_environment_invalid', 503)
    return value


def viewing_check(python, venv, requirements, env, emit):
    # Check the frozen requirements in the selected interpreter. No DB, model
    # configuration, weights, GPU probe, provider request or environment mutation.
    code = """import importlib.metadata,json,struct,sys
from pathlib import Path
expected=json.loads(sys.argv[2])
valid=(sys.version_info[:2]==(3,12) and struct.calcsize('P')==8 and
       Path(sys.prefix)==Path(sys.argv[1]) and sys.prefix!=sys.base_prefix and
       all(importlib.metadata.version(name)==version for name,version in expected))
if not valid: raise SystemExit(1)
import fastapi,uvicorn
print(json.dumps({'state':'ready','mode':'viewing_only'}))
"""
    pins = []
    for line in requirements['requirements.txt'].splitlines():
        line = line.split('#', 1)[0].strip()
        if line:
            if not re.fullmatch(r'[A-Za-z0-9_.-]+==\d+(?:\.\d+)*', line):
                raise MediaError('install_requirements_invalid',503)
            pins.append(line.split('=='))
    try:
        result = json.loads(command([str(python),'-I','-B','-c',code,str(venv),json.dumps(pins)],
                                    env,emit,timeout=30))
        if result != {'state':'ready','mode':'viewing_only'}:
            raise ValueError()
    except (MediaError, ValueError, OSError):
        raise MediaError('install_existing_environment_invalid',503) from None
    return result


def install(args, emit):
    def record(name, **values):
        emit({'check':{'name':name, 'state':'ready', **values}})
    if (sys.version_info[:2] != (3, 12) or struct.calcsize('P') != 8 or
            sys.platform not in ('win32', 'linux') or platform.machine().lower() not in ('amd64','x86_64')):
        raise MediaError('install_platform_unsupported', 503)
    viewing = getattr(args, 'viewing_only', False)
    stages = VIEWING_STAGES if viewing else STAGES
    root = args.data_dir.absolute()
    venv = ROOT/('.venv-viewing' if viewing else '.venv')
    cache = ROOT/'.setup-cache'
    for path in (ROOT, root, venv, cache):
        no_symlink(path)
    requirements = requirements_snapshot(viewing)
    for tool in ('ffmpeg','ffprobe'):
        if not run_media([tool,'-version'],10,16384).startswith((tool+' version ').encode()):
            raise MediaError('install_prerequisites_missing', 503)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    cache.mkdir(exist_ok=True, mode=0o700)
    with ExitStack() as locks:
        locks.enter_context(open_lock(cache/'install.lock','setup_active',409))
        locks.enter_context(open_lock(root/'instance.lock','already_running',503))
        lease = locks.enter_context(open_lock(root/'worker.lock','processing_worker_active',409))
        selection = None if viewing else device_configuration(root)
        device = None if viewing else args.device or selection['device']
        if not viewing and args.device and selection['selection'] == 'configured' and device != selection['device']:
            raise MediaError('install_device_conflict',409)
        if not viewing and device != selection['device']:
            # Explicit first device selection only; never replace an existing setting.
            target = root/'models/settings.json'
            no_symlink(target)
            target.parent.mkdir(exist_ok=True, mode=0o700)
            fd, partial = tempfile.mkstemp(prefix='.device-', suffix='.partial', dir=target.parent)
            with os.fdopen(fd,'w') as stream:
                json.dump({'device':device}, stream); stream.flush(); os.fsync(stream.fileno())
            os.link(partial,target); Path(partial).unlink()
        record('preflight', **({'mode':'viewing_only'} if viewing else {'device':device}))
        env = environment()
        python = venv/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        def check_runtime():
            if viewing:
                return viewing_check(python,venv,requirements,env,emit)
            lease.close()
            return native_check(python,root,device,env,emit)
        if venv.exists():
            # No pip or package mutations in an existing environment, even if broken.
            native = check_runtime()
            for name in stages[1:-1]:
                record(name, status='reused')
        else:
            if shutil.disk_usage(ROOT).free < (1 if viewing else 12 if device == 'cuda' else 4) * 1024**3:
                raise MediaError('insufficient_space',507)
            run = Path(tempfile.mkdtemp(prefix='install-', dir=cache))
            wheels = run/'wheels'; wheels.mkdir()
            temporary = run/'tmp'; temporary.mkdir()
            env.update(TMPDIR=str(temporary), TEMP=str(temporary), TMP=str(temporary))
            paths = (venv, run)
            # Final location from the start: moving a venv breaks its launchers.
            command([sys.executable,'-I','-m','venv','--copies',str(venv)],env,emit,paths,timeout=90)
            record('environment', status='created')
            version = command([str(python),'-I','-m','pip','--version'],env,emit,timeout=15)
            help_text = command([str(python),'-I','-m','pip','download','--help'],env,emit,timeout=15)
            flags = [] if version.startswith(b'pip 25.0.1 ') else pip_flags(help_text)
            record('pip', resume_retries=0, connection_retries=0)
            constraints = []
            if not viewing:
                command(pip_command(python,'download', ['torch=='+TORCH[device], '--no-deps',
                    '--only-binary=:all:', '--index-url',INDEX[device], '--dest',str(wheels)],flags),env,emit,paths)
                record('torch', version=TORCH[device])
                constraint = run/'torch-constraint.txt'
                constraint.write_text('torch=='+TORCH[device]+'\n',encoding='ascii')
                constraints = ['-c', str(constraint)]
            for name, content in requirements.items():
                (run/name).write_text(content,encoding='utf-8')
            required_args = [arg for name in requirements for arg in ('-r', str(run/name))]
            command(pip_command(python,'download', [*required_args,*constraints,
                '--only-binary=:all:', '--index-url','https://pypi.org/simple',
                '--find-links',str(wheels),'--dest',str(wheels)],flags),env,emit,paths)
            record('packages', status='downloaded')
            command(pip_command(python,'install', [*required_args,*constraints,
                '--only-binary=:all:', '--no-index','--find-links',str(wheels)],flags),env,emit,paths)
            command([str(python),'-I','-m','pip','--disable-pip-version-check','check'],env,emit,paths,timeout=30)
            record('dependencies', status='installed')
            native = check_runtime()
        record('runtime', **{k:v for k,v in native.items() if k != 'state'})
        emit({'state':'ready'})


def worker(args):
    output = worker_output()
    def emit(value):
        os.write(output,(json.dumps(value,ensure_ascii=True)+'\n').encode('ascii'))
    try:
        if args.restore_worker:
            from scripts.restore_qwen_cache import restore
            from scripts.check_setup import collect
            def offline(event, values):
                if event in ('socket.connect','socket.getaddrinfo','socket.sendto'):
                    raise MediaError('install_failed',503)
            sys.addaudithook(offline)
            args.verify_only = False
            restore(args,emit)
            collect(args.data_dir.absolute(),emit)
        else:
            install(args,emit)
        return 0
    except Exception as exc:
        code = exc.code if isinstance(exc,MediaError) and exc.code in ERRORS else 'install_failed'
        emit({'state':'blocked','error':code})
        return 1
    finally:
        os.close(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=default_data_dir())
    parser.add_argument('--device',choices=('cpu','cuda'),help='Existing selection is preserved; explicit first selection is saved')
    parser.add_argument('--viewing-only',action='store_true',help='Prepare .venv-viewing with requirements.txt only; no models or device selection')
    parser.add_argument('--asr-bundle',type=Path)
    parser.add_argument('--aligner-bundle',type=Path)
    parser.add_argument('--parts-dir',type=Path)
    parser.add_argument('--json',action='store_true')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--restore-worker',action='store_true',help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.viewing_only and (args.device or args.asr_bundle or args.aligner_bundle or args.parts_dir or args.restore_worker):
        parser.error('--viewing-only cannot select a device or restore models')
    if bool(args.asr_bundle) != bool(args.aligner_bundle) or (args.parts_dir and not args.asr_bundle):
        parser.error('Both cache bundles are required for restoration')
    if args.worker or args.restore_worker:
        return worker(args)
    def show(check):
        labels = dict(zip(STAGES,('사전 조건','Python 환경','설치 도구','PyTorch','의존 패키지 다운로드','패키지 설치','감상 실행 환경' if args.viewing_only else '네이티브 실행 환경')))
        if check['name'] in labels:
            print(labels[check['name']]+': 확인',flush=True)
        elif check['name'] == 'install':
            print('설치 명령 중단' if check['state']=='blocked' else '설치 파일 준비 중',flush=True)
        else:
            print('모델 복원·진단: '+check['name'],flush=True)
    command_args = [str(Path(__file__).resolve()),*sys.argv[1:]]
    result = run_setup([sys.executable,*command_args,'--worker'],total_seconds=VIEWING_SECONDS if args.viewing_only else TOTAL_SECONDS,
        idle_seconds=IDLE_SECONDS,expected_checks=len(VIEWING_STAGES if args.viewing_only else STAGES),progress=None if args.json else show)
    if result['state'] == 'ready' and args.asr_bundle:
        python = ROOT/'.venv'/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        restored = run_setup([str(python),*command_args,'--restore-worker'],total_seconds=1320,
            idle_seconds=90,expected_checks=27,progress=None if args.json else show)
        result['checks'].extend(restored.pop('checks'))
        result.update(restored)
    result.update(api_connection='not_checked',actual_inference='not_checked',
                  models='checked' if args.asr_bundle and result['state']=='ready' else 'not_checked')
    if args.json:
        print(json.dumps(result,ensure_ascii=False))
    else:
        print('실행 환경 준비 완료.' if result['state']=='ready' else
              '설치 중단. 기존 환경과 완료 파일은 보존됩니다. 진단 코드: '+result.get('error','install_failed'))
        if args.viewing_only:
            print('감상은 start-media-clarity.cmd로 시작하세요. 영상과 제공 자막의 재생·검색·시간 보정을 사용할 수 있습니다.')
            print('새 자막 생성이 필요할 때 install-media-clarity.cmd로 별도 전체 환경을 준비하세요. 모델·API 연결은 별도입니다.')
        else:
            print('모델 캐시를 지정하지 않았다면 restore-qwen-models.cmd로 복원하세요.')
            print('Gemini 실행은 start-media-clarity-gemini.cmd를 사용하세요. API 연결·실제 추론·감상 품질은 별도 검사입니다.')
    return 0 if result['state']=='ready' else 1


if __name__ == '__main__':
    raise SystemExit(main())
