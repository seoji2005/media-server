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


def seed_generated_captions(data):
    """Synthetic inference only; exercise normal job publication before restart."""
    sys.path.insert(0, str(ROOT))
    from unittest.mock import patch
    from media_clarity.jobs import Jobs, execute
    from media_clarity.storage import Store
    class Fixture:
        def __init__(self, root): pass
        def identity(self): return 'browser-transcript-fixture-v1'
        def transcribe(self, *args):
            return [{'start':1., 'end':8., 'text':'Original <voice> & text.'}]
        def translate(self, text): return '한국어 자동 번역 확인'
        def close(self): pass
    store = Store(data); store.start(); jobs = Jobs(store)
    try:
        item = store.list_items()[0]
        with patch('media_clarity.models.local_models'):
            jid = jobs.enqueue(item['id'], force=True)
        execute(store, jid, Fixture)
        assert jobs.row(jid)['state'] == 'succeeded'
        track = next(t for t in jobs.status(item['id'])['tracks'] if t['has_transcript'])
        assert '&lt;voice&gt;' in jobs.track(item['id'],track['id'],transcript=True)
    finally:
        jobs.close(); store.close()


def serve(data, port_file):
    """Run the production CLI with a socket held by this test child from bind onward."""
    sys.path.insert(0, str(ROOT))
    import uvicorn
    import webbrowser
    from media_clarity.__main__ import main
    with socket.socket() as sock:
        if os.name == 'nt':
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind(('127.0.0.1', 0))
        sock.listen(128)
        port = sock.getsockname()[1]
        Path(port_file).write_text(str(port), encoding='ascii')
        original_run = uvicorn.Server.run
        def run_with_socket(server, sockets=None):
            return original_run(server, sockets=[sock])
        uvicorn.Server.run = run_with_socket
        def unavailable_browser(url, new=0):
            # An OS handler failure must leave this successfully bound app usable.
            with urllib.request.urlopen(url + '/api/session', timeout=5) as response:
                assert response.status == 200
            Path(port_file + '.opened').write_text(url, encoding='ascii')
            return False
        webbrowser.open = unavailable_browser
        sys.argv = ['media_clarity', '--data-dir', data, '--port', str(port)]
        if Path(port_file).name.startswith('first'):
            sys.argv.append('--open-browser')
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
        pending = work / 'pending.mkv'
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(source), '-c', 'copy', str(pending)],
                       check=True, timeout=30)
        pending_digest = hashlib.sha256(pending.read_bytes()).hexdigest()
        data = work / 'library'
        for phase in ('first', 'restart'):
            if phase == 'restart':
                seed_generated_captions(data)
            log_path = work / f'{phase}.log'
            port_file = work / f'{phase}.port'
            with log_path.open('wb') as log:
                server = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                    '--serve', str(data), str(port_file)], cwd=ROOT, stdout=log, stderr=log,
                    env={**os.environ, 'GEMINI_API_KEY':''})
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
                if phase == 'first':
                    opened = Path(str(port_file) + '.opened')
                    observed = None
                    while time.monotonic() < deadline:
                        try:
                            observed = opened.read_text(encoding='ascii')
                        except FileNotFoundError:
                            pass
                        if observed == base:
                            break
                        time.sleep(.05)
                    assert observed == base, f'browser opener URL mismatch: {observed!r}'
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
            if phase == 'first':
                expected = (f'감상 준비가 끝났습니다: {base}\n종료하려면 이 창에서 Ctrl+C를 누르세요.\n'
                            '브라우저를 열지 못했습니다. 위 주소를 브라우저에 직접 입력해 주세요.\n')
                observed = log_path.read_text(encoding='utf-8')
                # Keep the exact quiet-log gate. Report counts only: raw diagnostics
                # may contain URLs/paths, so they must not reach shared CI output.
                expected_lines, observed_lines = expected.splitlines(), observed.splitlines()
                assert observed == expected, (
                    'unexpected launcher diagnostics: '
                    f'expected_lines={len(expected_lines)}, actual_lines={len(observed_lines)}, '
                    f'missing_lines={sum(line not in observed_lines for line in expected_lines)}, '
                    f'extra_lines={sum(line not in expected_lines for line in observed_lines)}, '
                    f'sanitized_server_errors={observed.count("Local server operation failed; check the in-app diagnostic.")}'
                )
            else:
                observed = log_path.read_text(encoding='utf-8', errors='replace')
                # Fixed categories only; retain the strict gate without publishing
                # paths, URLs or arbitrary exception messages from the server.
                categories = ('ConnectionResetError', 'ClientDisconnect', 'CancelledError',
                              'RuntimeError', 'Exception in callback',
                              'Local server operation failed; check the in-app diagnostic.')
                assert observed == '', (
                    'production server unexpectedly logged data: '
                    f'lines={len(observed.splitlines())}, '
                    f'categories={dict((name, observed.count(name)) for name in categories)}'
                )
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
        originals = list((data / 'files').glob('*/original.mp4'))
        assert len(originals) == 2  # Imported MP4 plus the explicitly requested MKV rendition.
        assert sum(hashlib.sha256(p.read_bytes()).hexdigest() == digest for p in originals) == 1
        pending_copies = list((data / 'files').glob('*/original.mkv'))
        assert len(pending_copies) == 1 and hashlib.sha256(pending_copies[0].read_bytes()).hexdigest() == pending_digest
        assert hashlib.sha256(pending.read_bytes()).hexdigest() == pending_digest
        print('PASS browser source/copy preservation, bound-server launch/fallback, quiet default restart (synthetic20s; OS browser handler mocked; no model/GPU evidence)')


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--serve':
        sys.exit(serve(sys.argv[2], sys.argv[3]))
    run()
