"""Real H.264/AAC browser playback and process restart; synthetic media only."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def serve(data, port_file):
    """Run the production CLI with a socket held by this test child from bind onward."""
    sys.path.insert(0, str(ROOT))
    import uvicorn
    from media_clarity.__main__ import main
    with socket.socket() as sock:
        if os.name == 'nt':
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind(('127.0.0.1', 0))
        sock.listen(128)
        Path(port_file).write_text(str(sock.getsockname()[1]), encoding='ascii')
        def run_with_socket(app, **options):
            options.pop('host')
            options.pop('port')
            uvicorn.Server(uvicorn.Config(app, **options)).run(sockets=[sock])
        uvicorn.run = run_with_socket
        sys.argv = ['media_clarity', '--data-dir', data]
        return main()


def run():
    with tempfile.TemporaryDirectory(prefix='media-browser-') as directory:
        work = Path(directory)
        source = work / '브라우저 영상.mp4'
        subtitle = work / '한국어.srt'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
            'testsrc2=size=320x180:rate=12', '-f', 'lavfi', '-i',
            'sine=frequency=440:sample_rate=44100', '-t', '20', '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart', str(source)],
            check=True, timeout=30)
        subtitle.write_text('1\n00:00:01,000 --> 00:00:18,000\n한국어 자막 재생 확인\n', encoding='utf-8')
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        data = work / 'library'
        for phase in ('first', 'restart'):
            log_path = work / f'{phase}.log'
            port_file = work / f'{phase}.port'
            with log_path.open('wb') as log:
                server = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                    '--serve', str(data), str(port_file)], cwd=ROOT, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 15
                while True:
                    if server.poll() is not None:
                        raise RuntimeError('test server exited before readiness')
                    try:
                        port = int(port_file.read_text(encoding='ascii'))
                        base = f'http://127.0.0.1:{port}'
                        with urllib.request.urlopen(base + '/api/session', timeout=1) as response:
                            session = json.load(response)
                        assert session['diagnostics']['ffmpeg'] and session['diagnostics']['ffprobe']
                        break
                    except (FileNotFoundError, ValueError, urllib.error.URLError, TimeoutError):
                        if time.monotonic() >= deadline:
                            raise RuntimeError('test server readiness timed out') from None
                        time.sleep(.1)
                subprocess.run(['node', 'tests/ui/browser.mjs', base, str(source), str(subtitle), phase],
                    cwd=ROOT, check=True, timeout=75)
                assert server.poll() is None, 'browser must use the newly launched server'
            finally:
                if server.poll() is None:
                    server.terminate()
                    try:
                        server.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=5)
            assert log_path.read_bytes() == b'', 'production server unexpectedly logged data'
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
        originals = list((data / 'files').glob('*/original.mp4'))
        assert len(originals) == 1 and hashlib.sha256(originals[0].read_bytes()).hexdigest() == digest
        print('PASS browser source/copy preservation, quiet server, persisted restart (synthetic20s; no model/GPU evidence)')


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--serve':
        sys.exit(serve(sys.argv[2], sys.argv[3]))
    run()
