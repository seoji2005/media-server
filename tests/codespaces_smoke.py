"""Real HTTP/DB/media/restart. Optional CI Chrome; simulated GitHub forwarding."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_clarity import codespaces
from media_clarity.app import create_app
from test_codespaces import ENV, ORIGIN


@contextmanager
def server():
    import uvicorn
    app = create_app(codespaces_demo=True)
    # Isolated test boundary only: browser stays on localhost while the app sees
    # the exact Codespaces Host/HTTPS Origin. No mock API, media, DB or JS fetch.
    async def edge(scope, receive, send):
        if scope['type'] == 'http':
            scope = dict(scope)
            scope['headers'] = [(k, ORIGIN[8:].encode() if k == b'host' else
                                  ORIGIN.encode() if k == b'origin' else v)
                                 for k,v in scope['headers']]
        await app(scope, receive, send)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); sock.listen(128)
        port = sock.getsockname()[1]
        service = uvicorn.Server(uvicorn.Config(edge, access_log=False, log_level='warning', proxy_headers=False))
        thread = threading.Thread(target=service.run, kwargs={'sockets':[sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 30
            while not service.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(.05)
            assert service.started, 'real HTTP startup failed'
            yield f'http://127.0.0.1:{port}'
        finally:
            service.should_exit = True
            thread.join(timeout=15)
            assert not thread.is_alive(), 'server did not release its lease'


def request(base, path, *, method='GET', body=None, token=None):
    headers = {} if token is None else {'X-Media-Token':token}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(base + path, method=method, headers=headers,
        data=None if body is None else json.dumps(body).encode())
    with urllib.request.urlopen(req, timeout=10) as response:
        data = response.read()
        return json.loads(data) if 'application/json' in response.headers.get('Content-Type','') else data


def main(browser=False):
    with tempfile.TemporaryDirectory(prefix='codespaces-http-체험 ') as temporary, \
         patch.object(codespaces, 'ROOT', Path(temporary)), patch.dict(os.environ, ENV):
        identity = None
        for phase in ('first', 'restart'):
            with server() as base:
                items = request(base, '/api/library')['items']
                assert len(items) == 2
                item = next(i for i in items if i['title'] == '보랏빛 산책')
                if identity is None:
                    identity = item['id']
                assert item['id'] == identity
                url = f'/api/library/{identity}'
                body = request(base, f'/api/media/{identity}/content')
                assert hashlib.sha256(body).hexdigest() == item['sha256']
                token = request(base, '/api/session')['token']
                state = request(base, url+'/subtitles')
                track = next(t['id'] for t in state['tracks'] if t['language'] == 'ko')
                if browser:
                    subprocess.run([shutil.which('node'), 'tests/ui/codespaces-browser.mjs',
                                    base, phase, identity, track], cwd=ROOT, check=True, timeout=90)
                elif phase == 'first':
                    request(base, url+'/position', method='PUT', token=token, body={'position':18.25})
                    request(base, url+'/caption-view', method='PUT', token=token,
                            body={'audio_index':0,'selection':track,'offset_ms':500,'revision':0})
                assert request(base, url)['position'] == 18.25
                assert request(base, url+'/subtitles')['view']['offset_ms'] == 500
                assert request(base, url+'/subtitles')['view']['selection'] == track
                print(json.dumps({'phase':phase, 'realHTTP':True, 'sourceHashVerified':True,
                                  'position':18.25, 'offsetMs':500, 'browser':browser,
                                  'codespacesEdge':'simulated'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', action='store_true')
    main(parser.parse_args().browser)
