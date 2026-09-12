"""Bounded, offline setup checks. No installation, API call or media scan."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import re
import signal
import struct
import subprocess
import sys
import tempfile
import threading
from time import monotonic, sleep

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_clarity.storage import MediaError, default_data_dir, no_symlink, run_media

TOTAL_SECONDS = 120
IDLE_SECONDS = 75
MAX_OUTPUT = 65536


def release(value):
    # Current requirements use release numbers; local Torch CPU/CUDA tags are OK.
    if not re.fullmatch(r'\d+(?:\.\d+){0,3}(?:\+[A-Za-z0-9._-]+)?', value):
        raise ValueError('unrecognized version')
    parts = tuple(map(int, value.split('+')[0].split('.')))
    return parts + (0,) * (4 - len(parts))


def package_checks():
    packages = []
    for filename in ('requirements.txt', 'requirements-qwen.txt'):
        path = ROOT / filename
        if path.is_symlink() or path.stat().st_size > 65536:
            raise ValueError('invalid requirements')
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.split('#', 1)[0].strip()
            if not line:
                continue
            match = re.fullmatch(r'([A-Za-z0-9_.-]+)((?:(?:==|>=|<=|>|<)\d+(?:\.\d+)*)(?:,(?:==|>=|<=|>|<)\d+(?:\.\d+)*)*)', line)
            if not match:
                raise ValueError('invalid requirements')
            name, expected = match.groups()
            try:
                installed = importlib.metadata.version(name)
                actual = release(installed)
            except importlib.metadata.PackageNotFoundError:
                installed, actual = None, None
            except ValueError:
                installed, actual = 'unrecognized', None
            ready = actual is not None
            for operator, version in re.findall(r'(==|>=|<=|>|<)(\d+(?:\.\d+)*)', expected):
                target = release(version)
                if actual is not None:
                    ready &= {'==':actual == target, '>=':actual >= target,
                              '<=':actual <= target, '>':actual > target, '<':actual < target}[operator]
            packages.append({'name':name, 'expected':expected, 'installed':installed,
                             'state':'ready' if ready else 'blocked'})
    return packages


def collect(root, emit):
    checks = []
    def record(value):
        checks.append(value)
        emit({'check':value})
    record({'name':'python', 'state':'ready' if sys.version_info[:2] == (3, 12)
            and struct.calcsize('P') == 8 else 'blocked',
            'version':'.'.join(map(str, sys.version_info[:3])), 'bits':struct.calcsize('P') * 8})
    try:
        packages = package_checks()
        record({'name':'packages', 'state':'ready' if all(p['state'] == 'ready' for p in packages)
                else 'blocked', 'packages':packages})
    except Exception:
        record({'name':'packages', 'state':'blocked', 'error':'requirements_check_failed'})
    for tool in ('ffmpeg', 'ffprobe'):
        try:
            output = run_media([tool, '-version'], 10, 16384)
            if not output.startswith((tool + ' version ').encode('ascii')):
                raise MediaError('invalid_media', 422)
            record({'name':tool, 'state':'ready'})
        except Exception as exc:
            code = exc.code if isinstance(exc, MediaError) and exc.code in (
                'ffmpeg_unavailable', 'media_timeout', 'invalid_media') else 'tool_check_failed'
            record({'name':tool, 'state':'blocked', 'error':code})
    if any(check['state'] != 'ready' for check in checks):
        record({'name':'models', 'state':'not_checked', 'error':'prerequisites_missing'})
    else:
        emit({'progress':'models'})
        try:
            no_symlink(root)
            if not root.is_dir():
                raise MediaError('local_models_missing', 503)
            from media_clarity.model_check import diagnose
            result = diagnose(root)
            record({'name':'models', **result})
        except Exception as exc:
            code = exc.code if isinstance(exc, MediaError) and exc.code in (
                'unsafe_storage', 'local_models_missing') else 'model_check_failed'
            record({'name':'models', 'state':'blocked', 'error':code})
    emit({'state':'ready' if all(c['state'] == 'ready' for c in checks) else 'blocked'})


def worker(root):
    # Wait until the parent owns our POSIX group or Windows kill-on-close Job.
    if os.name != 'nt' and os.getpgrp() != os.getpid():
        return 1
    if os.read(sys.stdin.fileno(), 1) != b'1':
        return 1
    from media_clarity.worker_lifecycle import parent_gone
    threading.Thread(target=parent_gone, daemon=True).start()
    output = os.dup(1)
    with open(os.devnull, 'wb') as quiet:
        os.dup2(quiet.fileno(), 1)
        os.dup2(quiet.fileno(), 2)
    def emit(value):
        os.write(output, (json.dumps(value, ensure_ascii=True) + '\n').encode('ascii'))
    try:
        collect(root, emit)
        return 0
    except Exception:
        emit({'state':'blocked', 'error':'setup_check_failed'})
        return 1
    finally:
        os.close(output)


def check_setup(root, progress=None):
    from media_clarity.gemini import configured
    from media_clarity.worker_lifecycle import WindowsJob
    result = {'state':'blocked', 'checks':[], 'gemini_configured':configured(),
              'api_connection':'not_checked', 'model_full_hashes':'not_checked',
              'actual_inference':'not_checked', 'automatic_retries':0}
    # The diagnostic does not need an API credential in any child environment.
    env = {k:v for k,v in os.environ.items() if k not in ('GEMINI_API_KEY', 'GOOGLE_API_KEY')}
    env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
    started = last = monotonic()
    seen = size = 0
    process = job = None
    with tempfile.TemporaryDirectory(prefix='media-setup-') as temp:
        path = Path(temp) / 'progress.jsonl'
        def drain():
            nonlocal seen, size, last
            current = path.stat().st_size
            if current > MAX_OUTPUT:
                raise ValueError('output limit')
            if current <= size:
                return
            size, last = current, monotonic()
            with path.open('rb') as reader:
                raw = reader.read(MAX_OUTPUT + 1)
            if len(raw) > MAX_OUTPUT:
                raise ValueError('output limit')
            lines = raw.split(b'\n')[:-1]
            for line in lines[seen:]:
                event = json.loads(line)
                if 'check' in event:
                    result['checks'].append(event['check'])
                    if progress:
                        progress(event['check'])
                elif event.get('progress') == 'models' and progress:
                    progress({'name':'models', 'state':'checking'})
                elif event.get('state') in ('ready', 'blocked'):
                    result['state'] = event['state']
                    if event.get('error'):
                        result.setdefault('error', event['error'])
            seen = len(lines)
        try:
            if os.name != 'nt' and not all(hasattr(os, name) for name in ('waitid','WNOWAIT')):
                raise OSError('safe process observation unavailable')
            with path.open('wb') as output:
                process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                    '--worker', '--data-dir', str(root)], stdin=subprocess.PIPE,
                    stdout=output, stderr=subprocess.DEVNULL, env=env,
                    start_new_session=os.name != 'nt')
                if os.name == 'nt':
                    job = WindowsJob(process)
                process.stdin.write(b'1'); process.stdin.flush()
                while True:
                    # Keep a POSIX leader waitable until group cleanup, so its
                    # PID/group identity cannot be recycled before killpg.
                    finished = (process.poll() is not None if os.name == 'nt' else
                        os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None)
                    drain()
                    now = monotonic()
                    if now - started >= TOTAL_SECONDS or now - last >= IDLE_SECONDS:
                        result['error'] = 'setup_check_timeout'
                        break
                    if finished:
                        break
                    sleep(.2)
        except (Exception, KeyboardInterrupt):
            result.update(state='blocked', error='setup_check_failed')
        finally:
            try:
                if process:
                    # Always clean descendants, including when their leader
                    # already exited normally or with an error.
                    if os.name == 'nt':
                        if job:
                            job.close()
                        if process.poll() is None:
                            process.kill()
                    else:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    process.wait(timeout=5)
                    process.stdin.close()
                if job:
                    job.close()
            except Exception:
                result['cleanup_error'] = 'setup_check_cleanup_failed'
                result.setdefault('error', 'setup_check_cleanup_failed')
            try:
                if path.exists():
                    drain()  # Preserve completed rows even at a deadline boundary.
            except Exception:
                result.setdefault('error', 'setup_check_failed')
    if not result.get('error') and (not process or process.returncode or len(result['checks']) != 5):
        result['error'] = 'setup_check_failed'
    if result.get('error'):
        result['state'] = 'blocked'
    return result


def show(check):
    labels = {'python':'Python 3.12 · 64비트', 'packages':'지정 패키지 버전',
              'ffmpeg':'FFmpeg 실행', 'ffprobe':'ffprobe 실행', 'models':'자막 모델 실행 환경'}
    states = {'ready':'확인', 'blocked':'설정 필요', 'not_checked':'앞 단계 설정 후 확인', 'checking':'확인 중'}
    print(f"{labels[check['name']]}: {states[check['state']]}", flush=True)
    for package in check.get('packages', []):
        if package['state'] != 'ready':
            print(f"  {package['name']}{package['expected']} 필요 (현재: {package['installed'] or '미설치'})", flush=True)
    if check.get('error'):
        print('  진단 코드: ' + check['error'], flush=True)
    if check.get('device') in ('cpu', 'cuda'):
        print('  선택 장치: ' + check['device'].upper(), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=default_data_dir())
    parser.add_argument('--json', action='store_true', help='Print a shareable diagnostic without private paths or keys')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        return worker(args.data_dir)
    result = check_setup(args.data_dir, None if args.json else show)
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print('Gemini 키: 형식 확인 (연결 미검증)' if result['gemini_configured'] else
              'Gemini 키: 미설정 (Gemini 실행 도우미에서 입력)')
        print('기본 실행 환경 확인 완료.' if result['state'] == 'ready' else
              '설정을 완료한 뒤 다시 확인하세요. README.md와 docs/qwen-subtitles.md를 참고하세요.')
        print('모델 전체 해시·실제 추론·영상 재생·Gemini 연결은 별도 확인이 필요합니다.')
    return 0 if result['state'] == 'ready' else 1


if __name__ == '__main__':
    raise SystemExit(main())
