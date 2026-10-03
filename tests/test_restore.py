"""Exact missing-copy restore with real generated media, HTTP and SQLite."""
from contextlib import closing
import hashlib
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

from media_clarity.storage import MediaError, Store
from tests import test_app as fixtures
from tests.test_position_recovery import live_server


class RestoreTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.AppTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.AppTests.tearDownClass.__func__)
    setUp = fixtures.AppTests.setUp
    tearDown = fixtures.AppTests.tearDown
    imported = fixtures.AppTests.imported

    def snapshot(self):
        with self.store.db() as db:
            return list(db.iterdump())

    def missing(self):
        item = self.imported()
        target = self.store.file_path(self.store._row(item['id']))
        target.unlink()
        return item, target, f"/api/library/{item['id']}/restore"

    def released(self):
        self.assertTrue(self.store.import_lock.acquire(blocking=False))
        self.store.import_lock.release()
        self.assertEqual(list((self.root/'staging').iterdir()), [])

    def test_exact_restore_preserves_every_row_and_original_bytes(self):
        item = self.imported();iid = item['id']
        self.store.rename_item(iid, '보존할 제목', item['title'])
        self.store.save_position(iid, 2.25, 0)
        self.client.put(f'/api/library/{iid}/preference', headers=self.headers,
                        json={'included':True,'preference':'like','revision':0})
        track = self.app.state.jobs.import_srt(iid, '1\n00:00:00,500 --> 00:00:02,000\n보존할 자막\n'.encode())
        caption = self.app.state.jobs.track(iid,track)
        self.client.put(f'/api/library/{iid}/caption-view',headers=self.headers,
                        json={'audio_index':0,'selection':track,'offset_ms':500,'revision':0})
        saved = self.snapshot();target = self.store.file_path(self.store._row(iid));target.unlink()
        self.assertTrue(self.client.get(f'/api/library/{iid}').json()['original_missing'])
        result = self.client.post(f'/api/library/{iid}/restore',content=self.video_bytes,headers=self.headers)
        self.assertEqual(result.status_code,200,result.text)
        self.assertFalse(result.json()['item']['original_missing'])
        self.assertEqual(result.json()['item']['file_id'],item['file_id'])
        self.assertEqual(self.snapshot(),saved);self.assertEqual(self.app.state.jobs.track(iid,track),caption)
        self.assertEqual(target.read_bytes(),self.video_bytes);self.assertEqual(self.source.read_bytes(),self.video_bytes)
        self.assertNotEqual(target.stat().st_ino,self.source.stat().st_ino)
        self.assertEqual(target.stat().st_nlink,1)
        response=self.client.get(f'/api/media/{iid}/content',headers={'Range':'bytes=15-150'})
        self.assertEqual(response.content,self.video_bytes[15:151]);self.released()
        self.store._recover();self.assertEqual(self.snapshot(),saved)

    def test_wrong_size_hash_and_occupied_targets_never_overwrite(self):
        item,target,url=self.missing();saved=self.snapshot()
        for data in [b'',self.video_bytes[:-1],self.video_bytes+b'x',b'x'*len(self.video_bytes)]:
            response=self.client.post(url,content=data,headers=self.headers)
            self.assertEqual(response.status_code,422,response.text);self.assertFalse(target.exists())
            self.assertEqual(self.snapshot(),saved);self.released()
        response=self.client.post(url,content=self.video_bytes[:-1],headers=self.headers|{'Content-Length':str(len(self.video_bytes))})
        self.assertEqual(response.json()['error'],'incomplete_upload');self.assertFalse(target.exists());self.released()
        response=self.client.post('/api/library/'+('0'*32)+'/restore',content=self.video_bytes,headers=self.headers)
        self.assertEqual(response.status_code,404);self.released()
        for data in [self.video_bytes,b'changed']:
            target.write_bytes(data)
            response=self.client.post(url,content=self.video_bytes,headers=self.headers)
            self.assertEqual(response.json()['error'],'restore_not_missing')
            self.assertEqual(target.read_bytes(),data);target.unlink();self.released()
        target.mkdir()
        self.assertFalse(self.store.item(item['id'])['original_missing'])
        self.assertEqual(self.client.post(url,content=self.video_bytes,headers=self.headers).json()['error'],'restore_not_missing')
        self.assertTrue(target.is_dir());self.assertEqual(self.snapshot(),saved)

    def test_symlinks_and_concurrent_destination_creation_are_rejected(self):
        _,target,url=self.missing();saved=self.snapshot()
        for destination in [self.source,Path(self.temp.name)/'absent']:
            try:target.symlink_to(destination)
            except OSError:self.skipTest('symlinks unavailable')
            self.assertEqual(self.client.post(url,content=self.video_bytes,headers=self.headers).json()['error'],'unsafe_storage')
            self.assertTrue(target.is_symlink());target.unlink();self.released()
        original_link=os.link
        def race(source,destination,**options):
            target.write_bytes(b'competing copy')
            return original_link(source,destination,**options)
        with patch('media_clarity.storage.os.link',side_effect=race):
            response=self.client.post(url,content=self.video_bytes,headers=self.headers)
        self.assertEqual(response.json()['error'],'restore_not_missing');self.assertEqual(target.read_bytes(),b'competing copy')
        self.assertEqual(self.snapshot(),saved);self.released()

    def test_changed_stage_disk_failure_lock_and_origin_guards(self):
        _,target,url=self.missing();saved=self.snapshot();finish=self.store.finish_restore
        def changed(iid,stage,digest,size):
            stage.write_bytes(b'x'*size)
            return finish(iid,stage,digest,size)
        with patch.object(self.store,'finish_restore',side_effect=changed):
            self.assertEqual(self.client.post(url,content=self.video_bytes,headers=self.headers).json()['error'],'copy_changed')
        self.assertFalse(target.exists());self.released()
        with patch.object(self.store,'ensure_space',side_effect=MediaError('insufficient_space',507)):
            self.assertEqual(self.client.post(url,content=self.video_bytes,headers=self.headers).status_code,507)
        with self.store.import_lock:
            self.assertEqual(self.client.post(url,content=self.video_bytes,headers=self.headers).json()['error'],'import_busy')
        self.assertEqual(self.client.post(url,content=self.video_bytes).status_code,403)
        self.assertEqual(self.client.post(url,content=self.video_bytes,headers=self.headers|{'Origin':'http://other.test'}).status_code,403)
        self.assertEqual(self.snapshot(),saved);self.assertFalse(target.exists());self.released()

    def test_missing_parent_and_missing_rendition_have_distinct_eligibility(self):
        item,target,url=self.missing();saved=self.snapshot()
        # Only fixture-owned files are removed. Recreate the same managed ID.
        import shutil
        shutil.rmtree(target.parent)
        self.assertEqual(self.client.post(url,content=self.video_bytes,headers=self.headers).status_code,200)
        self.assertEqual(target.read_bytes(),self.video_bytes);self.assertEqual(self.snapshot(),saved)
        with self.store.db() as db:
            db.execute("UPDATE files SET preparation='remux_mp4' WHERE id=?",(item['file_id'],))
            db.execute('INSERT INTO renditions (id,item_id,input_sha,sha256,size,extension,mime,kind,duration,audio_index) VALUES (?,?,?,?,?,?,?,?,?,?)',
                       ('f'*32,item['id'],item['sha256'],item['sha256'],item['size'],'mp4','video/mp4','remux_mp4',item['duration'],0))
            db.commit()
        state=self.store.item(item['id'])
        self.assertEqual(state['unavailable_reason'],'managed_file_missing');self.assertFalse(state['original_missing'])
        self.assertEqual(self.client.post(url,content=self.video_bytes,headers=self.headers).json()['error'],'restore_not_missing')

    def test_missing_parent_symlink_is_not_followed(self):
        _,target,url=self.missing()
        original_dir=target.parent;elsewhere=Path(self.temp.name)/'elsewhere';original_dir.rename(elsewhere)
        try:original_dir.symlink_to(elsewhere,target_is_directory=True)
        except OSError:self.skipTest('symlinks unavailable')
        self.assertEqual(self.client.post(url,content=self.video_bytes,headers=self.headers).json()['error'],'unsafe_storage')
        self.assertFalse((elsewhere/target.name).exists());self.released()

    def test_cleanup_failure_keeps_published_copy_and_releases_lock(self):
        _,target,url=self.missing();saved=self.snapshot()
        with patch.object(self.store,'remove_stage',side_effect=MediaError('storage_unavailable',503)):
            result=self.client.post(url,content=self.video_bytes,headers=self.headers)
        self.assertEqual(result.status_code,503)
        self.assertEqual(target.read_bytes(),self.video_bytes);self.assertEqual(self.snapshot(),saved)
        self.assertTrue(self.store.import_lock.acquire(blocking=False));self.store.import_lock.release()
        self.store._recover();self.assertEqual(self.store.recovered,1)
        self.assertEqual(target.read_bytes(),self.video_bytes)

    def test_process_exit_before_or_after_publication_retains_recoverable_state(self):
        item,target,_=self.missing();saved=self.snapshot()
        code='''
import hashlib,os,sys
from pathlib import Path
from media_clarity.storage import Store
s=Store(Path(sys.argv[1]));raw=Path(sys.argv[2]).read_bytes()
stage,out=s.new_stage();out.write(raw);out.flush();os.fsync(out.fileno());out.close()
if sys.argv[4]=='after':s.finish_restore(sys.argv[3],stage,hashlib.sha256(raw).hexdigest(),len(raw))
os._exit(23)
'''
        for moment in ['before','after']:
            child=subprocess.run([sys.executable,'-c',code,str(self.root),str(self.source),item['id'],moment],capture_output=True,timeout=15)
            self.assertEqual(child.returncode,23,child.stderr);self.assertEqual(child.stdout,b'')
            self.store._recover();self.assertEqual(self.snapshot(),saved)
            self.assertEqual(target.exists(),moment=='after')
        self.assertEqual(target.read_bytes(),self.video_bytes)

    def test_live_lost_receipt_and_restart_preserve_saved_library(self):
        root=Path(self.temp.name)/'live'
        with live_server(root) as client:
            headers={'X-Media-Token':client.get('/api/session').json()['token'],'Content-Type':'application/octet-stream'}
            item=client.post('/api/import',headers=headers,content=self.video_bytes).json()['item']
            target=root/'files'/item['file_id']/'original.mp4'
            client.put(f"/api/library/{item['id']}/position",headers=headers,json={'position':1.25})
            with closing(sqlite3.connect(root/'library.sqlite3')) as db:saved=list(db.iterdump())
            target.unlink();entered=threading.Event();release=threading.Event();finished=threading.Event();owners=[]
            finish=Store.finish_restore
            def delayed(store,*args):
                owners.append(store);entered.set()
                try:
                    if not release.wait(5):raise AssertionError('fixture wait expired')
                    return finish(store,*args)
                finally:finished.set()
            with patch.object(Store,'finish_restore',delayed):
                with closing(socket.create_connection(('127.0.0.1',client.base_url.port),timeout=5)) as connection:
                    request=f"POST /api/library/{item['id']}/restore HTTP/1.1\r\nHost: 127.0.0.1:{client.base_url.port}\r\n"
                    request+=''.join(f'{key}: {value}\r\n' for key,value in headers.items())
                    connection.sendall((request+f'Content-Length: {len(self.video_bytes)}\r\nConnection: close\r\n\r\n').encode()+self.video_bytes)
                    try:
                        self.assertTrue(entered.wait(5))
                        self.assertTrue(client.get(f"/api/library/{item['id']}/playback-status").json()['busy'])
                        connection.shutdown(socket.SHUT_RDWR)
                    finally:release.set()
                self.assertTrue(finished.wait(5))
                self.assertTrue(owners[0].import_lock.acquire(timeout=5));owners[0].import_lock.release()
            self.assertEqual(target.read_bytes(),self.video_bytes)
        with live_server(root) as client:
            result=client.get(f"/api/library/{item['id']}").json()
            self.assertFalse(result['original_missing']);self.assertEqual(result['position'],1.25)
            self.assertEqual(client.get(f"/api/media/{item['id']}/content").content,self.video_bytes)
            with closing(sqlite3.connect(root/'library.sqlite3')) as db:self.assertEqual(list(db.iterdump()),saved)
