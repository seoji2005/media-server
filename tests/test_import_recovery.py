"""Real loopback HTTP disconnect after upload, with an isolated import boundary."""
from contextlib import closing
import hashlib
from pathlib import Path
import socket
import sqlite3
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import quote

from media_clarity.storage import Store
from tests.test_position_recovery import live_server


class ImportRecoveryTests(unittest.TestCase):
    def test_lost_import_response_preserves_commit_and_explicit_duplicate_history(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'한글 원본 영상.mp4'
            root = Path(directory)/'체험 보관함'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=size=32x32:rate=1',
                '-t','3','-c:v','libx264',str(source)],check=True,capture_output=True,timeout=30)
            raw = source.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            def snapshot():
                with closing(sqlite3.connect(root/'library.sqlite3')) as db, closing(sqlite3.connect(':memory:')) as backup:
                    db.backup(backup)
                    return '\n'.join(backup.iterdump())
            with live_server(root) as client:
                token = client.get('/api/session').json()['token']
                headers = {'X-Media-Token':token,'Content-Type':'application/octet-stream','X-Media-Filename':quote(source.name)}
                entered, release, finished = threading.Event(), threading.Event(), threading.Event()
                owners = []
                finish = Store.finish_import
                def delayed(store, *args):
                    owners.append(store);entered.set()
                    try:
                        if not release.wait(5): raise AssertionError('fixture delay exceeded five seconds')
                        return finish(store,*args)
                    finally:
                        finished.set()
                # All bytes reached the server, but the user has no import receipt.
                with patch.object(Store,'finish_import',delayed):
                    with closing(socket.create_connection(('127.0.0.1',client.base_url.port),timeout=5)) as connection:
                        request = f'POST /api/import HTTP/1.1\r\nHost: 127.0.0.1:{client.base_url.port}\r\n'
                        request += ''.join(f'{key}: {value}\r\n' for key,value in headers.items())
                        connection.sendall((request+f'Content-Length: {len(raw)}\r\nConnection: close\r\n\r\n').encode('ascii')+raw)
                        try:
                            self.assertTrue(entered.wait(5),'uploaded body did not reach the import boundary')
                            self.assertEqual(client.get('/api/library').json()['items'],[],'an early result check cannot claim import failure')
                            connection.shutdown(socket.SHUT_RDWR)
                        finally:
                            release.set()
                    self.assertTrue(finished.wait(5),'import did not finish after client disconnect')
                self.assertTrue(owners[0].import_lock.acquire(timeout=5),'request cleanup did not release import ownership')
                owners[0].import_lock.release()
                listing = client.get('/api/library')
                self.assertEqual(listing.status_code,200)
                self.assertEqual(len(listing.json()['items']),1)
                item = listing.json()['items'][0]
                self.assertEqual((item['sha256'],item['title']),(digest,source.stem))
                prefix = '/api/library/'+item['id']
                caption = '1\n00:00:00,500 --> 00:00:02,000\n사용자가 보존할 자막\n'.encode()
                track = client.post(prefix+'/subtitles',content=caption,headers={'X-Media-Token':token})
                self.assertEqual(track.status_code,201,track.text)
                view = {'audio_index':0,'selection':track.json()['id'],'offset_ms':-500,'revision':0}
                self.assertEqual(client.put(prefix+'/caption-view',json=view,headers=headers).status_code,200)
                self.assertEqual(client.put(prefix+'/position',json={'position':1.25,'expected_revision':0},headers=headers).status_code,200)
                saved = snapshot()
                retry = client.post('/api/import',content=raw,headers=headers)
                self.assertEqual(retry.status_code,200,retry.text)
                self.assertTrue(retry.json()['duplicate'])
                self.assertEqual(retry.json()['item']['id'],item['id'])
                self.assertEqual(snapshot(),saved,'explicit duplicate must preserve every saved row')
                self.assertEqual(list((root/'staging').iterdir()),[])
            with live_server(root) as client:
                restored = client.get(prefix).json()
                self.assertEqual((restored['position'],restored['position_revision']),(1.25,1))
                restored_view = client.get(prefix+'/subtitles').json()['view']
                self.assertEqual((restored_view['selection'],restored_view['offset_ms']),(track.json()['id'],-500))
                response = client.get(f"/api/media/{item['id']}/content")
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.content,raw)
                self.assertEqual(snapshot(),saved)
                self.assertEqual(source.read_bytes(),raw)
