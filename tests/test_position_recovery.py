"""Real HTTP handlers and SQLite ordering/restart, with isolated delayed writes."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
import hashlib
from pathlib import Path
import sqlite3
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from media_clarity.app import create_app
from media_clarity.storage import MediaError


@contextmanager
def live_server(root):
    import httpx
    import uvicorn
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        port=sock.getsockname()[1]
        server=uvicorn.Server(uvicorn.Config(create_app(root),log_config=None,log_level='error',access_log=False))
        worker=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True)
        worker.start()
        try:
            until=time.monotonic()+5
            while not server.started and worker.is_alive() and time.monotonic()<until:
                time.sleep(.01)
            if not server.started: raise AssertionError('HTTP startup exceeded five seconds')
            with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=5,trust_env=False) as client:
                yield client
        finally:
            server.should_exit=True
            worker.join(5)
            if worker.is_alive(): raise AssertionError('HTTP server did not stop')


class PositionRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        source = cls.root / 'sample.mp4'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=size=32x32:rate=1',
            '-t','12','-c:v','libx264',str(source)],check=True,capture_output=True,timeout=30)
        cls.raw = source.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_live_http_restart_restores_exact_bytes_captions_and_revision(self):
        with tempfile.TemporaryDirectory() as data:
            root=Path(data)/'HTTP 보관함'
            with live_server(root) as client:
                token={'X-Media-Token':client.get('/api/session').json()['token']}
                result=client.post('/api/import',content=self.raw,headers=token | {
                    'X-Media-Filename':'sample.mp4','Content-Type':'application/octet-stream'})
                self.assertEqual(result.status_code,201,result.text)
                item_id=result.json()['item']['id']
                prefix=f'/api/library/{item_id}'
                caption=b'1\n00:00:01,000 --> 00:00:02,000\nUser caption.\n'
                track=client.post(prefix+'/subtitles',content=caption,headers=token).json()['id']
                view={'audio_index':0,'selection':track,'offset_ms':500,'revision':0}
                saved=client.put(prefix+'/caption-view',json=view,headers=token)
                self.assertEqual(saved.status_code,200,saved.text)
                self.assertEqual(client.put(prefix+'/position',json={'position':7.25,'expected_revision':0},headers=token).status_code,200)
                vtt=client.get(prefix+f'/subtitles/{track}.vtt').content
            with live_server(root) as client:
                item=client.get(prefix).json()
                self.assertEqual((item['position'],item['position_revision']),(7.25,1))
                view=client.get(prefix+'/subtitles').json()['view']
                self.assertEqual((view['selection'],view['offset_ms']),(track,500))
                self.assertEqual(client.get(prefix+f'/subtitles/{track}.vtt').content,vtt)
                self.assertEqual(client.get(f'/api/media/{item_id}/content',headers={'Range':'bytes=10-99'}).content,self.raw[10:100])
                self.assertEqual(client.put(prefix+'/position',json={'position':1,'expected_revision':1},headers=token).status_code,403)

    def test_failed_caption_read_can_reload_without_mutating_view_or_content(self):
        with tempfile.TemporaryDirectory() as data:
            root = Path(data) / '자막 재읽기 보관함'
            def snapshot():
                with closing(sqlite3.connect(root/'library.sqlite3')) as db, closing(sqlite3.connect(':memory:')) as backup:
                    db.backup(backup)
                    return '\n'.join(backup.iterdump())
            with live_server(root) as client:
                token = {'X-Media-Token':client.get('/api/session').json()['token']}
                imported = client.post('/api/import', content=self.raw, headers=token | {
                    'X-Media-Filename':'sample.mp4','Content-Type':'application/octet-stream'})
                self.assertEqual(imported.status_code,201,imported.text)
                item_id = imported.json()['item']['id']
                prefix = f'/api/library/{item_id}'
                caption = '1\n00:00:01,000 --> 00:00:02,000\n문장 경계\n\n2\n00:00:02,000 --> 00:00:03,000\n너머 대사\n'
                supplied = client.post(prefix+'/subtitles',content=caption.encode(),headers=token)
                self.assertEqual(supplied.status_code,201,supplied.text)
                track = supplied.json()['id']
                view = {'audio_index':0,'selection':track,'offset_ms':1500,'revision':0}
                self.assertEqual(client.put(prefix+'/caption-view',json=view,headers=token).status_code,200)
                self.assertEqual(client.put(prefix+'/position',json={'position':7.25,'expected_revision':0},headers=token).status_code,200)
                url = prefix+f'/subtitles/{track}.vtt'
                original = client.get(url).content
                expected = client.get(url+'?offset_ms=1500')
                self.assertEqual(expected.status_code,200)
                self.assertIn('00:00:02.500 --> 00:00:03.500',expected.text)
                self.assertIn('00:00:03.500 --> 00:00:04.500',expected.text)
                self.assertIn('\n문장 경계\n',expected.text)
                saved = snapshot()
                # Only this isolated server's caption-read boundary fails once.
                with patch('media_clarity.jobs.Jobs.track',side_effect=MediaError('fixture_read_unavailable',503)) as fault:
                    failed = client.get(url+'?offset_ms=1500')
                    self.assertEqual(failed.status_code,503)
                    self.assertEqual(fault.call_count,1)
                for _ in range(2):  # Two explicit reads, no automatic retry loop.
                    reloaded = client.get(url+'?offset_ms=1500')
                    self.assertEqual(reloaded.status_code,200)
                    self.assertEqual(reloaded.content,expected.content)
                self.assertEqual(client.get(url).content,original)
                self.assertEqual(snapshot(),saved,'VTT failure/reload must not mutate any saved rows')
            with live_server(root) as client:
                self.assertEqual(client.get(url+'?offset_ms=1500').content,expected.content)
                restored = client.get(prefix).json()
                self.assertEqual((restored['position'],restored['position_revision']),(7.25,1))
                restored_view = client.get(prefix+'/subtitles').json()['view']
                self.assertEqual((restored_view['selection'],restored_view['offset_ms'],restored_view['revision']),(track,1500,1))
                media = client.get(f'/api/media/{item_id}/content')
                self.assertEqual(media.status_code,200)
                self.assertEqual(media.content,self.raw)
                self.assertEqual(snapshot(),saved,'restart and recovery must preserve original/user data')

    def test_newer_save_wins_over_delayed_request_and_survives_upgrade_restart(self):
        with tempfile.TemporaryDirectory() as data:
            root = Path(data) / '한글 보관함'
            app = create_app(root)
            with TestClient(app, base_url='http://127.0.0.1:8765') as client:
                token = {'X-Media-Token':client.get('/api/session').json()['token']}
                result = client.post('/api/import',content=self.raw,headers=token | {'X-Media-Filename':'sample.mp4','Content-Type':'application/octet-stream'})
                self.assertEqual(result.status_code,201,result.text)
                item_id = result.json()['item']['id']
                url = f'/api/library/{item_id}/position'
                self.assertEqual(result.json()['item']['position_revision'],0)
                store = app.state.store
                save = store.save_position
                entered, release = threading.Event(), threading.Event()
                def delayed(item, position, *args):
                    if position == 3:
                        entered.set()
                        if not release.wait(10): raise AssertionError('delay exceeded test bound')
                    return save(item,position,*args)
                with patch.object(store,'save_position',side_effect=delayed), ThreadPoolExecutor(1) as pool:
                    old = pool.submit(client.put,url,json={'position':3,'expected_revision':0},headers=token)
                    try:
                        self.assertTrue(entered.wait(5))
                        new = client.put(url,json={'position':7.25,'expected_revision':0},headers=token)
                        self.assertEqual(new.status_code,200,new.text)
                        self.assertEqual(new.json(),{'position':7.25,'position_revision':1})
                    finally:
                        release.set()
                    self.assertEqual(old.result(timeout=5).status_code,409)
                current = client.get(f'/api/library/{item_id}').json()
                self.assertEqual((current['position'],current['position_revision']),(7.25,1))
                for revision in (None,True,-1,1.5,'1',2**53-1):
                    self.assertEqual(client.put(url,json={'position':9,'expected_revision':revision},headers=token).status_code,422)
                self.assertEqual(client.put(url,json={'position':9,'expected_revision':1}).status_code,403)
                self.assertEqual(client.put(url,json={'position':9,'expected_revision':1},headers=token | {'Origin':'https://example.com'}).status_code,403)
                # A failed DB commit does not advance either position or revision.
                with store.db() as db:
                    db.execute("CREATE TRIGGER position_fail BEFORE UPDATE ON items BEGIN SELECT RAISE(ABORT,'fixture'); END")
                    db.commit()
                with self.assertRaises(sqlite3.IntegrityError): save(item_id,9,expected_revision=1)
                with store.db() as db:
                    row = db.execute('SELECT position,position_revision FROM items WHERE id=?',(item_id,)).fetchone()
                    self.assertEqual(tuple(row),(7.25,1))
                    db.execute('DROP TRIGGER position_fail');db.commit()
                self.assertEqual(hashlib.sha256(store.file_path(store._row(item_id)).read_bytes()).digest(),hashlib.sha256(self.raw).digest())
            with TestClient(create_app(root),base_url='http://127.0.0.1:8765') as client:
                item=client.get(f'/api/library/{item_id}').json()
                self.assertEqual((item['position'],item['position_revision']),(7.25,1))
            # Model the previous schema on this disposable library, preserving data.
            with closing(sqlite3.connect(root/'library.sqlite3')) as db, db:
                db.execute('ALTER TABLE items DROP COLUMN position_revision')
                db.execute('PRAGMA user_version=10')
            with TestClient(create_app(root),base_url='http://127.0.0.1:8765') as client:
                item=client.get(f'/api/library/{item_id}').json()
                self.assertEqual((item['position'],item['position_revision']),(7.25,0))
                self.assertEqual(item['sha256'],hashlib.sha256(self.raw).hexdigest())
