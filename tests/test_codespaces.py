"""Real synthetic files, product import/DB/API; Codespaces edge/CLI is simulated."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from media_clarity import codespaces
from media_clarity.app import create_app
from media_clarity.storage import MediaError

ENV = {'CODESPACES':'true', 'CODESPACE_NAME':'test-garden-123',
       'GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN':'app.github.dev'}
ORIGIN = 'https://test-garden-123-8765.app.github.dev'


class CodespacesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cloud-감상 공간-')
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, ENV)
        self.paths = patch.object(codespaces, 'ROOT', self.root)
        self.env.start(); self.paths.start()

    def tearDown(self):
        self.paths.stop(); self.env.stop(); self.temp.cleanup()

    def test_explicit_exact_environment_and_separate_data(self):
        self.assertEqual(codespaces.origin(), ORIGIN)
        for key, values in {
            'CODESPACES':['false', ''],
            'CODESPACE_NAME':['', '*.app', 'good.evil', 'x/y', 'x@evil', '-x', 'x\n'],
            'GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN':['evil.test', 'app.github.dev.evil',
                                                        '*.app.github.dev', 'APP.GITHUB.DEV'],
        }.items():
            for value in values:
                with self.subTest(key=key, value=value), patch.dict(os.environ, {key:value}):
                    with self.assertRaises(MediaError):
                        codespaces.origin()
        with self.assertRaises(MediaError):
            create_app(self.root / 'personal-library', codespaces_demo=True)
        self.assertFalse((self.root / 'personal-library').exists())
        cloud = self.root / '.codespaces-data'
        cloud.mkdir()
        sentinel = cloud / 'library.sqlite3'
        sentinel.write_bytes(b'existing data must remain')
        with self.assertRaises(MediaError):
            create_app(codespaces_demo=True)
        self.assertEqual(sentinel.read_bytes(), b'existing data must remain')

    def test_default_local_boundary_ignores_codespaces_environment(self):
        with TestClient(create_app(self.root / 'local'), base_url='http://127.0.0.1:8765') as client:
            self.assertNotIn(codespaces.NOTICE, client.get('/').text)
            self.assertEqual(client.get('/api/session').status_code, 200)
            self.assertEqual(client.get('/api/session', headers={'Host':ORIGIN[8:]}).status_code, 403)
            self.assertEqual(client.get('/api/session', headers={'Origin':ORIGIN}).status_code, 403)

    def test_private_port_is_fail_closed_and_has_no_create_or_billing_command(self):
        listing = [{'sourcePort':8765, 'visibility':'private', 'browseUrl':ORIGIN}]
        with patch('media_clarity.codespaces.subprocess.run') as run:
            run.return_value = subprocess.CompletedProcess([], 0, json.dumps(listing).encode())
            codespaces.private_port(ORIGIN)
            self.assertEqual(run.call_args_list[0].args[0],
                ['gh','codespace','ports','visibility','8765:private','-c','test-garden-123'])
            self.assertEqual(len(run.call_args_list), 2)
            for bad in ([], [dict(listing[0], visibility='public')],
                        [dict(listing[0], browseUrl='https://other-8765.app.github.dev')]):
                run.return_value.stdout = json.dumps(bad).encode()
                with self.assertRaises(MediaError) as error:
                    codespaces.private_port(ORIGIN)
                self.assertEqual(error.exception.code, 'codespaces_private_port_unverified')
            run.reset_mock()
            run.side_effect = subprocess.TimeoutExpired('gh', 30)
            with self.assertRaises(MediaError):
                codespaces.private_port(ORIGIN)
            self.assertEqual(run.call_count, 1, 'no automatic retry')

    def test_interrupted_seed_reuses_committed_subtitle_receipt(self):
        from media_clarity.jobs import Jobs
        original = Jobs.import_provided
        calls = []
        def interrupted(jobs, *args, **kwargs):
            if calls:
                raise MediaError('injected_seed_interruption', 503)
            result = original(jobs, *args, **kwargs)
            calls.append(result['id'])
            return result
        with patch.object(Jobs, 'import_provided', interrupted):
            with self.assertRaises(MediaError):
                with TestClient(create_app(codespaces_demo=True), base_url=ORIGIN):
                    pass
        with TestClient(create_app(codespaces_demo=True), base_url=ORIGIN) as client:
            tracks = [track for item in client.get('/api/library').json()['items']
                      for track in client.get(f'/api/library/{item["id"]}/subtitles').json()['tracks']]
            self.assertEqual(len(tracks), 4)
            self.assertIn(calls[0], {track['id'] for track in tracks})

    def test_launcher_never_starts_after_private_check_failure(self):
        with patch('sys.argv', ['codespaces', '--start']), \
             patch('media_clarity.codespaces.shutil.which', return_value='/tool'), \
             patch.object(codespaces, 'private_port', side_effect=MediaError('codespaces_private_port_unverified')), \
             patch('media_clarity.app.create_app') as app, \
             patch('builtins.print'):
            self.assertEqual(codespaces.main(), 1)
            app.assert_not_called()
        with patch('sys.argv', ['codespaces', '--start']), \
             patch('media_clarity.codespaces.shutil.which', return_value='/tool'), \
             patch.object(codespaces, 'private_port'), \
             patch('media_clarity.app.create_app') as app, \
             patch('uvicorn.run') as run, patch('builtins.print'), \
             patch.dict(os.environ, {'GEMINI_API_KEY':'synthetic-placeholder', 'GOOGLE_API_KEY':'synthetic-placeholder'}):
            self.assertEqual(codespaces.main(), 0)
            app.assert_called_once_with(codespaces_demo=True)
            self.assertNotIn('GEMINI_API_KEY', os.environ)
            self.assertNotIn('GOOGLE_API_KEY', os.environ)
            self.assertEqual(run.call_args.kwargs['host'], '127.0.0.1')
            self.assertFalse(run.call_args.kwargs['proxy_headers'])

    def test_seed_playback_security_and_restart_preserve_user_results(self):
        # A provider accidentally present in the environment still cannot start.
        with patch('media_clarity.jobs.Jobs.start') as workers, \
             patch('media_clarity.gemini.Gemini') as provider:
            with TestClient(create_app(codespaces_demo=True), base_url=ORIGIN) as client:
                self.assertEqual(client.get('/').text.count(codespaces.NOTICE), 2)
                token = client.get('/api/session').json()['token']
                headers = {'X-Media-Token':token, 'Origin':ORIGIN}
                items = client.get('/api/library').json()['items']
                self.assertEqual(len(items), 2)
                item = items[0]; item_id = item['id']
                url = f'/api/library/{item_id}'
                self.assertEqual(item['duration'], 32)
                media = client.get(f'/api/media/{item_id}/content')
                self.assertEqual(hashlib.sha256(media.content).hexdigest(), item['sha256'])
                part = client.get(f'/api/media/{item_id}/content', headers={'Range':'bytes=100-199'})
                self.assertEqual((part.status_code, part.content), (206, media.content[100:200]))
                tracks = client.get(url + '/subtitles').json()
                self.assertEqual({t['language'] for t in tracks['tracks']}, {'ko','en'})
                ko = next(t['id'] for t in tracks['tracks'] if t['language'] == 'ko')
                raw_caption = client.get(url + f'/subtitles/{ko}.vtt').content
                self.assertIn('하늘 아래'.encode(), raw_caption)
                self.assertIn('천천히'.encode(), raw_caption)
                # UI writes use the unchanged real product handlers.
                self.assertEqual(client.put(url+'/position', headers=headers, json={'position':18.25}).status_code, 200)
                self.assertEqual(client.put(url+'/caption-view', headers=headers, json={
                    'audio_index':0, 'selection':ko, 'offset_ms':500, 'revision':0}).status_code, 200)
                self.assertEqual(client.put(url+'/title', headers=headers,
                    json={'title':'사용자 체험 제목', 'expected_title':item['title']}).status_code, 200)
                user = client.post(url+'/subtitles', headers=headers,
                    content='1\n00:00:01,000 --> 00:00:03,000\n사용자 자막 보존'.encode()).json()['id']
                # Session token remains necessary even at the exact HTTPS origin.
                self.assertEqual(client.put(url+'/position', json={'position':0},
                    headers={'Origin':ORIGIN}).json()['error'], 'session_required')
                denied = [{'Host':'evil.test'}, {'Host':'127.0.0.1:8765'},
                    {'Host':'other-8765.app.github.dev'}, {'Origin':'null'},
                    {'Origin':'http://'+ORIGIN[8:]}, {'Origin':ORIGIN+'.evil'},
                    {'Origin':'https://other-8765.app.github.dev'}, {'Sec-Fetch-Site':'cross-site'},
                    {'Host':'evil.test', 'X-Forwarded-Host':ORIGIN[8:], 'X-Forwarded-Proto':'https'}]
                for attack in denied:
                    self.assertEqual(client.get('/api/session', headers=attack).status_code, 403, attack)
                for endpoint in ('/api/models/diagnostics', url+'/subtitle-jobs',
                                 url+'/subtitle-jobs/regenerate', url+f'/subtitles/{ko}/retranslate',
                                 '/api/subtitle-jobs/fake/resume', url+'/scenes/prepare',
                                 url+'/scenes/search', '/api/companion/library/lookup'):
                    self.assertEqual(client.post(endpoint, headers=headers).json()['error'], 'codespaces_viewing_only')
                saved_view = client.get(url+'/subtitles').json()['view']
                all_tracks = {t['id'] for t in client.get(url+'/subtitles').json()['tracks']}
                # Repeat seeding does not publish newer sample tracks over user work.
                codespaces.seed_samples(client.app.state.store, client.app.state.jobs)
                self.assertEqual({t['id'] for t in client.get(url+'/subtitles').json()['tracks']}, all_tracks)
            with TestClient(create_app(codespaces_demo=True), base_url=ORIGIN) as restarted:
                after = restarted.get(url).json()
                self.assertEqual((after['position'], after['title']), (18.25, '사용자 체험 제목'))
                self.assertEqual(after['sha256'], item['sha256'])
                state = restarted.get(url+'/subtitles').json()
                self.assertEqual(state['view'], saved_view)
                self.assertEqual({t['id'] for t in state['tracks']}, all_tracks)
                self.assertIn(user, all_tracks)
                self.assertEqual(restarted.get(url+f'/subtitles/{ko}.vtt').content, raw_caption)
                shifted = restarted.get(url+f'/subtitles/{ko}.vtt?offset_ms=500').text
                self.assertIn('00:00:04.500 --> 00:00:06.500', shifted)
                self.assertNotEqual(restarted.get('/api/session').json()['token'], token)
                self.assertEqual(restarted.put(url+'/position', headers=headers,
                    json={'position':0}).json()['error'], 'session_required')
            workers.assert_not_called(); provider.assert_not_called()
        # Changed sample originals are preserved and rejected, never regenerated.
        source = self.root / '.codespaces-data/samples-v1/보랏빛 산책.mp4'
        source.write_bytes(b'changed synthetic source')
        with self.assertRaises(MediaError) as error:
            with TestClient(create_app(codespaces_demo=True), base_url=ORIGIN):
                pass
        self.assertEqual(error.exception.code, 'codespaces_sample_changed')
        self.assertEqual(source.read_bytes(), b'changed synthetic source')


if __name__ == '__main__':
    unittest.main()
