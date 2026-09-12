"""Viewing dependencies only. No model installer, secrets file or inference."""
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
TOTAL_SECONDS = 600
IDLE_SECONDS = 120


def command(argv, env, deadline):
    """Linux Codespaces: bounded progress, no output/credentials in diagnostics."""
    process = subprocess.Popen(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               start_new_session=True)
    last = time.monotonic()
    try:
        with selectors.DefaultSelector() as events:
            events.register(process.stdout, selectors.EVENT_READ)
            while process.poll() is None:
                now = time.monotonic()
                if now >= deadline or now - last >= IDLE_SECONDS:
                    raise RuntimeError('setup_progress_timeout')
                for key, _ in events.select(timeout=.2):
                    block = os.read(key.fileobj.fileno(), 8192)
                    if block:
                        last = time.monotonic()
                    else:
                        events.unregister(key.fileobj)
        if process.returncode:
            raise RuntimeError('setup_command_failed')
    finally:
        # This process group belongs only to this command, including sudo/apt/pip.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)
        process.stdout.close()


def main():
    if sys.platform != 'linux' or sys.version_info[:2] != (3, 12) or os.environ.get('CODESPACES') != 'true':
        raise RuntimeError('codespaces_python312_required')
    sys.path.insert(0, str(ROOT))
    from media_clarity.storage import no_symlink, open_lock
    target = ROOT / '.codespaces-venv'
    no_symlink(target)
    # Do not inherit a configured alternate index, install target or provider key.
    env = {k:v for k,v in os.environ.items() if not k.upper().startswith('PIP_')
           and k.upper() not in {'PYTHONPATH', 'PYTHONHOME', 'GEMINI_API_KEY',
                                'GOOGLE_API_KEY', 'HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN'}}
    env.update(PIP_CONFIG_FILE=os.devnull, PYTHONUNBUFFERED='1', PYTHONUTF8='1',
               DEBIAN_FRONTEND='noninteractive')
    deadline = time.monotonic() + TOTAL_SECONDS
    with open_lock(ROOT / '.codespaces-setup.lock', 'setup_active', 409):
        if not all(shutil.which(tool) for tool in ('ffmpeg', 'ffprobe', 'gh')):
            print('FFmpeg · GitHub CLI 준비 중 (전체 10분 / 무진행 2분 / 재시도 0)', flush=True)
            apt = ['sudo', '-n', 'apt-get', '-o', 'Acquire::Retries=0',
                   '-o', 'Acquire::http::Timeout=30', '-o', 'Acquire::https::Timeout=30']
            command(apt + ['update', '-qq'], env, deadline)
            command(apt + ['install', '-y', '--no-install-recommends', 'ffmpeg', 'gh'], env, deadline)
        if not target.exists():
            command([sys.executable, '-m', 'venv', str(target)], env, deadline)
        python = str(target / 'bin/python')
        print('감상용 Python 의존성 확인·준비 중', flush=True)
        command([python, '-m', 'pip', '--isolated', '--disable-pip-version-check',
                 'install', '--index-url', 'https://pypi.org/simple', '--retries', '0',
                 '--timeout', '30', '--no-input', '--no-cache-dir', '--progress-bar', 'off',
                 '-r', str(ROOT / 'requirements.txt')], env, deadline)
        command([python, '-m', 'pip', 'check'], env, deadline)
        command([python, '-c', 'import fastapi, uvicorn; assert __import__("sys").version_info[:2] == (3, 12)'], env, deadline)
    print('준비 완료. bash scripts/start_codespaces.sh 로 체험을 시작하세요.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        code = str(exc) if type(exc) is RuntimeError else 'setup_failed'
        print('ERROR: ' + code + ' · 자동 재시도하지 않았습니다. docs/codespaces.ko.md 를 확인하세요.', file=sys.stderr)
        sys.exit(1)
