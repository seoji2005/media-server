"""Actual HTTP restart and session identity; separate from browser event mocks."""
from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest

from tests.test_position_recovery import live_server


class SessionRecoveryTests(unittest.TestCase):
    def test_reconnect_identifies_same_library_without_writes_and_keeps_old_token_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'같은 보관함'
            source=Path(directory)/'sample.mp4'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=size=32x32:rate=1',
                '-t','3','-c:v','libx264',str(source)],check=True,capture_output=True,timeout=30)
            raw=source.read_bytes()
            def snapshot():
                with closing(sqlite3.connect(root/'library.sqlite3')) as db, closing(sqlite3.connect(':memory:')) as backup:
                    db.backup(backup)
                    return '\n'.join(backup.iterdump())
            with live_server(root) as client:
                session=client.get('/api/session').json();old={'X-Media-Token':session['token']}
                identity=session['identity']
                self.assertEqual(identity,client.get('/api/companion/identity',headers=old).json())
                result=client.post('/api/import',content=raw,headers=old|{'X-Media-Filename':'sample.mp4','Content-Type':'application/octet-stream'})
                self.assertEqual(result.status_code,201,result.text)
                item=result.json()['item'];prefix='/api/library/'+item['id']
                supplied=client.post(prefix+'/subtitles',content=b'1\n00:00:01,000 --> 00:00:02,000\nSaved correction.\n',headers=old)
                self.assertEqual(supplied.status_code,201,supplied.text);track=supplied.json()['id']
                self.assertEqual(client.put(prefix+'/caption-view',json={'audio_index':0,'selection':track,'offset_ms':-500,'revision':0},headers=old).status_code,200)
                self.assertEqual(client.put(prefix+'/position',json={'position':1.25,'expected_revision':0},headers=old).status_code,200)
                caption=client.get(prefix+f'/subtitles/{track}.vtt').content;saved=snapshot()
            with live_server(root) as client:
                rejected=client.put(prefix+'/position',json={'position':2,'expected_revision':1},headers=old)
                self.assertEqual((rejected.status_code,rejected.json()['error']),(403,'session_required'))
                new_session=client.get('/api/session').json()
                self.assertEqual(new_session['identity'],identity)
                self.assertNotEqual(new_session['token'],session['token'])
                self.assertEqual(snapshot(),saved,'session recovery cannot replay writes or change any row')
                self.assertEqual(client.get('/api/session',headers={'Host':'example.invalid'}).status_code,403)
                self.assertEqual(client.get('/api/session',headers={'Origin':'https://example.invalid'}).status_code,403)
                self.assertEqual(client.put(prefix+'/position',json={'position':2,'expected_revision':1},headers=old).status_code,403)
                self.assertEqual(client.get(prefix+f'/subtitles/{track}.vtt').content,caption)
                restored=client.get(prefix+'/subtitles').json()['view']
                self.assertEqual((restored['selection'],restored['offset_ms']),(track,-500))
                self.assertEqual(client.get(f'/api/media/{item["id"]}/content').content,raw)
                self.assertEqual(snapshot(),saved)
                # Only an explicit subsequent operation uses the new credential.
                new={'X-Media-Token':new_session['token']}
                self.assertEqual(client.put(prefix+'/position',json={'position':2,'expected_revision':1},headers=new).status_code,200)
                self.assertEqual(client.get(prefix).json()['position'],2)
            with live_server(Path(directory)/'다른 보관함') as client:
                other=client.get('/api/session').json()
                self.assertNotEqual(other['identity']['library_id'],identity['library_id'])
                self.assertNotEqual(other['identity']['server_id'],identity['server_id'])
