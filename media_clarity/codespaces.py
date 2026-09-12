"""Explicit, isolated Codespaces viewing entry point for the actual product."""
import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from .storage import MediaError, no_symlink, open_lock, run_media

ROOT = Path(__file__).resolve().parents[1]
PORT = 8765
NOTICE = '클라우드 체험용, 민감 자료 업로드 금지'
MARKER = 'media-clarity-codespaces-experience-v1\n'


def origin():
    name = os.environ.get('CODESPACE_NAME', '')
    domain = os.environ.get('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN', '')
    # This configuration supports GitHub.com only. No suffix/wildcard match or
    # arbitrary URL override, even when a forwarded header claims another host.
    if (os.environ.get('CODESPACES') != 'true'
            or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,48}[a-z0-9])?', name)
            or domain != 'app.github.dev'):
        raise MediaError('codespaces_environment_required', 503)
    return f'https://{name}-{PORT}.{domain}'


def data_directory():
    return ROOT / '.codespaces-data' / 'library'


def prepare_directory():
    root = data_directory().parent
    no_symlink(root)
    root.mkdir(mode=0o700, exist_ok=True)
    with open_lock(root / 'seed.lock', 'already_running', 409):
        marker = root / 'experience.txt'
        no_symlink(marker)
        if not marker.exists():
            if any(p.name != 'seed.lock' for p in root.iterdir()):
                raise MediaError('codespaces_existing_data', 409)
            with marker.open('x', encoding='ascii') as stream:
                stream.write(MARKER)
                stream.flush()
                os.fsync(stream.fileno())
        if marker.read_text(encoding='ascii') != MARKER:
            raise MediaError('codespaces_existing_data', 409)
    return data_directory()


def viewing_mutation(path):
    # Fail closed for future inference endpoints too; workers never start here.
    return path == '/api/import' or bool(re.fullmatch(
        r'/api/library/[0-9a-f]{32}/(?:position|caption-view|title|preference|'
        r'playback|audio/[0-9]+|subtitles|previews(?:/[0-9]+/retry)?)', path))


def viewing_html(html):
    notice = f'<p class="cloud-notice" role="note">{NOTICE}</p>'
    return (html.replace('<body>', '<body data-codespaces-experience>' + notice)
            .replace('<header class="player-header">', notice + '<header class="player-header">')
            .replace('이 기기에만 보관', 'Codespace에 보관')
            .replace('로컬 보관 · 원본 보존', '클라우드 체험 보관함')
            .replace('내 기기의 영상을 한곳에.', '합성 샘플로 감상을 체험하세요.'))


def sample_subtitles(language):
    lines = {
        'en': ['Welcome to the viewing library.', 'Under the violet sky,',
               'we walk slowly.', 'Find this moment through the captions.',
               'Choose captions and adjust their timing.', 'Pause here and return later.'],
        'ko': ['감상 체험 보관함에 오신 것을 환영합니다.', '보랏빛 하늘 아래',
               '천천히 걸어갑니다.', '자막으로 이 장면을 찾아보세요.',
               '자막을 고르고 시간을 조절해 보세요.', '여기서 멈추고 나중에 이어 보세요.'],
    }[language]
    times = [('01,000', '03,800'), ('04,000', '06,000'), ('06,200', '09,500'),
             ('11,000', '15,000'), ('17,000', '22,000'), ('24,000', '29,000')]
    return '\n\n'.join(f'{i}\n00:00:{a} --> 00:00:{b}\n{text}'
                       for i, ((a,b),text) in enumerate(zip(times,lines),1)).encode('utf-8')


def seed_samples(store, jobs):
    """Called under the Store instance lease. No direct DB inserts or reset writes."""
    source = store.root.parent / 'samples-v1'
    no_symlink(source)
    names = ('보랏빛 산책.mp4', '초록빛 산책.mp4')
    if not source.exists():
        # A failed encode leaves the managed library and earlier results intact.
        with tempfile.TemporaryDirectory(prefix='sample-build-', dir=source.parent) as temporary:
            staging = Path(temporary)
            hashes = {}
            for index, name in enumerate(names):
                target = staging / name
                run_media(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=size=640x360:rate=24', '-f', 'lavfi', '-i',
                    'sine=frequency=330:sample_rate=44100', '-t', '32',
                    '-vf', f'hue=h={index*90}', '-af', 'volume=0.03',
                    '-c:v', 'libx264', '-threads', '2', '-preset', 'veryfast',
                    '-crf', '28', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                    '-movflags', '+faststart', str(target)], 90, 1024)
                hashes[name] = hashlib.sha256(target.read_bytes()).hexdigest()
            (staging / 'manifest.json').write_text(json.dumps(hashes, ensure_ascii=False), encoding='utf-8')
            # Publish the complete source set once; never overwrite existing samples.
            staging.rename(source)
    manifest = source / 'manifest.json'
    no_symlink(manifest)
    hashes = json.loads(manifest.read_text(encoding='utf-8'))
    if set(hashes) != set(names):
        raise MediaError('codespaces_sample_changed', 409)
    # Check all originals before importing any of them.
    for name in names:
        target = source / name
        no_symlink(target)
        if hashlib.sha256(target.read_bytes()).hexdigest() != hashes[name]:
            raise MediaError('codespaces_sample_changed', 409)
    for name in names:
        item = store.import_path(source / name)['item']  # Same CLI/UI storage pipeline.
        for language in ('en', 'ko'):
            data = sample_subtitles(language)
            # Existing provided-caption import receipts make a crash between
            # subtitle publication and setup completion safe to run again.
            jobs.import_provided(item['id'], data, item['file_id'], item['sha256'],
                                 hashlib.sha256(data).hexdigest(), 'srt', language, 'original-file')


def private_port(expected_origin):
    """Only restrict this existing port; never create a Codespace or change billing."""
    env = os.environ.copy()
    for key in ('GH_DEBUG', 'GH_HOST', 'GH_TOKEN', 'GH_ENTERPRISE_TOKEN', 'GITHUB_ENTERPRISE_TOKEN'):
        env.pop(key, None)
    env.update(GH_PROMPT_DISABLED='1', GH_HOST='github.com', GH_NO_UPDATE_NOTIFIER='1')
    name = os.environ['CODESPACE_NAME']
    try:
        for args in (['visibility', f'{PORT}:private'], ['--json', 'sourcePort,visibility,browseUrl']):
            result = subprocess.run(['gh', 'codespace', 'ports', *args, '-c', name],
                env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, timeout=30, check=True)
        ports = json.loads(result.stdout)
        matching = [p for p in ports if p['sourcePort'] == PORT]
        if (len(matching) != 1 or matching[0]['visibility'] != 'private'
                or matching[0]['browseUrl'].rstrip('/') != expected_origin):
            raise ValueError('port mismatch')
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        raise MediaError('codespaces_private_port_unverified', 503) from None


def main():
    parser = argparse.ArgumentParser(description=NOTICE)
    parser.add_argument('--start', action='store_true', required=True,
                        help='명시적으로 Private Codespaces 체험을 시작합니다')
    parser.parse_args()
    try:
        expected = origin()
        if not all(shutil.which(tool) for tool in ('ffmpeg', 'ffprobe', 'gh')):
            raise MediaError('codespaces_setup_required', 503)
        private_port(expected)
        # No credential files are read. Provider secrets cannot reach app workers.
        for key in ('GEMINI_API_KEY', 'GOOGLE_API_KEY', 'HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN',
                    'GITHUB_TOKEN', 'GH_TOKEN'):
            os.environ.pop(key, None)
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        import uvicorn
        from .app import create_app
        from .__main__ import SafeServerLog
        for name in ('uvicorn', 'uvicorn.error', 'uvicorn.asgi', 'asyncio'):
            logging.getLogger(name).addFilter(SafeServerLog())
        app = create_app(codespaces_demo=True)
        print(NOTICE + '\nPrivate 포트 주소: ' + expected, flush=True)
        uvicorn.run(app, host='127.0.0.1', port=PORT, access_log=False,
                    log_level='warning', proxy_headers=False, timeout_keep_alive=5,
                    limit_concurrency=32, h11_max_incomplete_event_size=16384)
        return 0
    except MediaError as exc:
        print('ERROR: ' + exc.code + ' · docs/codespaces.ko.md 를 확인하세요.', file=sys.stderr)
        return 1
    except Exception:
        print('ERROR: codespaces_start_failed', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
