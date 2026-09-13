"""Actual loopback reads after isolated startup faults; no browser/model claims."""
from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from media_clarity.storage import MediaError, Store
from tests.test_position_recovery import live_server


class StartupConnectionTests(unittest.TestCase):
    def test_failed_startup_reads_and_explicit_reconnect_preserve_saved_library(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'연결 복구 보관함'
            source=Path(directory)/'sample.mp4'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=size=32x32:rate=1',
                '-t','3','-c:v','libx264',str(source)],check=True,capture_output=True,timeout=30)
            raw=source.read_bytes()
            def snapshot():
                with closing(sqlite3.connect(root/'library.sqlite3')) as db, closing(sqlite3.connect(':memory:')) as backup:
                    db.backup(backup)
                    return '\n'.join(backup.iterdump())
            with live_server(root) as client:
                token=client.get('/api/session').json()['token'];headers={'X-Media-Token':token}
                imported=client.post('/api/import',content=raw,headers=headers|{
                    'X-Media-Filename':'sample.mp4','Content-Type':'application/octet-stream'})
                self.assertEqual(imported.status_code,201,imported.text)
                item_id=imported.json()['item']['id'];prefix='/api/library/'+item_id
                supplied=client.post(prefix+'/subtitles',content=b'1\n00:00:01,000 --> 00:00:02,000\nSaved caption.\n',headers=headers)
                self.assertEqual(supplied.status_code,201,supplied.text)
                track=supplied.json()['id']
                self.assertEqual(client.put(prefix+'/caption-view',json={
                    'audio_index':0,'selection':track,'offset_ms':500,'revision':0},headers=headers).status_code,200)
                self.assertEqual(client.put(prefix+'/position',json={'position':1.25,'expected_revision':0},headers=headers).status_code,200)
                caption=client.get(prefix+f'/subtitles/{track}.vtt').content
                saved=snapshot()
                # Fault only the temporary app's read boundaries, once each.
                for method,url in [('diagnostics','/api/session'),('list_items','/api/library')]:
                    with patch.object(Store,method,side_effect=MediaError('storage_unavailable',503)) as fault:
                        failed=client.get(url)
                        self.assertEqual(failed.status_code,503)
                        self.assertEqual(fault.call_count,1)
                    session=client.get('/api/session')
                    self.assertEqual(session.status_code,200)
                    self.assertEqual(session.json()['token'],token)
                    self.assertEqual([i['id'] for i in client.get('/api/library').json()['items']],[item_id])
                    self.assertEqual(snapshot(),saved,'failed/repeated initial reads must preserve every row')
            with live_server(root) as client:
                session=client.get('/api/session')
                self.assertEqual(session.status_code,200)
                self.assertNotEqual(session.json()['token'],token)
                self.assertEqual(client.get('/api/session',headers={'Origin':'https://example.invalid'}).status_code,403)
                self.assertEqual(client.get('/api/session',headers={'Host':'example.invalid'}).status_code,403)
                self.assertEqual(client.put(prefix+'/position',json={'position':0,'expected_revision':1},headers=headers).status_code,403)
                item=client.get('/api/library').json()['items'][0]
                self.assertEqual((item['id'],item['position'],item['position_revision']),(item_id,1.25,1))
                view=client.get(prefix+'/subtitles').json()['view']
                self.assertEqual((view['selection'],view['offset_ms']),(track,500))
                self.assertEqual(client.get(prefix+f'/subtitles/{track}.vtt').content,caption)
                self.assertEqual(client.get(f'/api/media/{item_id}/content').content,raw)
                self.assertEqual(snapshot(),saved,'reconnect/restart must not replay an import or saved edit')
