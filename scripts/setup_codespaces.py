"""Viewing dependencies only. No model installer, secrets file or inference."""
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
TOTAL_SECONDS = 300
IDLE_SECONDS = 120


def command(argv, env, deadline, *, capture=False):
    """Linux Codespaces: bounded progress, no output/credentials in diagnostics."""
    process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--child', *argv],
                               cwd=ROOT, env=env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               start_new_session=True)
    last = time.monotonic()
    output = bytearray()
    try:
        with selectors.DefaultSelector() as events:
            events.register(process.stdout, selectors.EVENT_READ)
            while process.poll() is None or events.get_map():
                now = time.monotonic()
                if now >= deadline or now - last >= IDLE_SECONDS:
                    raise RuntimeError('setup_progress_timeout')
                for key, _ in events.select(timeout=.2):
                    block = os.read(key.fileobj.fileno(), 8192)
                    if block:
                        last = time.monotonic()
                        if capture:
                            if len(output) + len(block) > 65536:
                                raise RuntimeError('setup_output_limit')
                            output.extend(block)
                    else:
                        events.unregister(key.fileobj)
        if process.returncode:
            raise RuntimeError('setup_command_failed')
        return bytes(output)
    finally:
        # This group belongs only to this worker and its same-UID apt/pip children.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)
        process.stdin.close()
        process.stdout.close()


def child(argv):
    # A parent SIGTERM/SIGKILL closes the retained pipe. The independent watcher
    # then kills this owned session, including the actual install descendants.
    if os.getpid() != os.getpgrp() or not argv:
        return 1
    def parent_gone():
        # No buffered Python I/O lock held by a daemon at interpreter shutdown.
        os.read(sys.stdin.fileno(), 1)
        os.killpg(os.getpid(), signal.SIGKILL)
    threading.Thread(target=parent_gone, daemon=True).start()
    return subprocess.run(argv, stdin=subprocess.DEVNULL).returncode


def environment():
    # Do not inherit a configured alternate index, install target or provider key.
    env = {k:v for k,v in os.environ.items() if not k.upper().startswith('PIP_')
           and k.upper() not in {'PYTHONPATH', 'PYTHONHOME', 'GEMINI_API_KEY',
                                'GOOGLE_API_KEY', 'HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN',
                                'GITHUB_TOKEN', 'GH_TOKEN'}}
    env.update(PIP_CONFIG_FILE=os.devnull, PYTHONUNBUFFERED='1', PYTHONUTF8='1',
               DEBIAN_FRONTEND='noninteractive')
    return env


def system_tools():
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise RuntimeError('codespaces_image_build_required')
    env = environment()
    deadline = time.monotonic() + TOTAL_SECONDS
    print('이미지 FFmpeg · GitHub CLI 준비 (전체 5분 / 무진행 2분 / 재시도 0)', flush=True)
    apt = ['apt-get', '-o', 'Acquire::Retries=0', '-o', 'Acquire::http::Timeout=30',
           '-o', 'Acquire::https::Timeout=30']
    command(apt + ['update', '-qq'], env, deadline)
    command(apt + ['install', '-y', '--no-install-recommends', 'ffmpeg', 'gh'], env, deadline)


def main():
    if sys.platform != 'linux' or sys.version_info[:2] != (3, 12) or os.environ.get('CODESPACES') != 'true':
        raise RuntimeError('codespaces_python312_required')
    sys.path.insert(0, str(ROOT))
    from media_clarity.storage import no_symlink, open_lock
    from scripts.install_runtime import pip_flags
    target = ROOT / '.codespaces-venv'
    no_symlink(target)
    env = environment()
    deadline = time.monotonic() + TOTAL_SECONDS
    with open_lock(ROOT / '.codespaces-setup.lock', 'setup_active', 409):
        if not all(shutil.which(tool) for tool in ('ffmpeg', 'ffprobe', 'gh')):
            raise RuntimeError('codespaces_image_rebuild_required')
        if not target.exists():
            command([sys.executable, '-I', '-m', 'venv', str(target)], env, deadline)
        python = str(target / 'bin/python')
        version = command([python, '-I', '-m', 'pip', '--version'], env, deadline, capture=True)
        help_text = command([python, '-I', '-m', 'pip', 'install', '--help'], env, deadline, capture=True)
        flags = [] if version.startswith(b'pip 25.0.1 ') else pip_flags(help_text)
        print('감상용 Python 의존성 준비 (전체 5분 / 무진행 2분 / 재시도 0)', flush=True)
        command([python, '-I', '-m', 'pip', '--isolated', '--disable-pip-version-check',
                 'install', '--index-url', 'https://pypi.org/simple', '--retries', '0',
                 '--timeout', '30', '--no-input', '--no-cache-dir', '--progress-bar', 'off',
                 '--only-binary=:all:', *flags,
                 '-r', str(ROOT / 'requirements.txt')], env, deadline)
        command([python, '-I', '-m', 'pip', 'check'], env, deadline)
        command([python, '-I', '-c', 'import fastapi, uvicorn; assert __import__("sys").version_info[:2] == (3, 12)'], env, deadline)
    print('준비 완료. bash scripts/start_codespaces.sh 로 체험을 시작하세요.')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--child':
        sys.exit(child(sys.argv[2:]))
    try:
        if sys.argv[1:] == ['--system-tools']:
            system_tools()
        elif not sys.argv[1:]:
            main()
        else:
            raise RuntimeError('setup_arguments_invalid')
    except Exception as exc:
        code = str(exc) if type(exc) is RuntimeError else 'setup_failed'
        print('ERROR: ' + code + ' · 자동 재시도하지 않았습니다. docs/codespaces.ko.md 를 확인하세요.', file=sys.stderr)
        sys.exit(1)
