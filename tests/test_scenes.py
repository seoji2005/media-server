"""Real SQLite/checkpoint/lifetime boundaries. Test encoders do not claim retrieval quality."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import test_previews as fixtures
from media_clarity import scenes
from media_clarity.jobs import worker_guard
from media_clarity.storage import MediaError


class Encoder:
    seen=[]
    def __init__(self,*args):pass
    def images(self,frames):
        self.seen.extend(f['ordinal'] for f in frames)
        return [[float(i==f['ordinal']) for i in range(scenes.DIM)] for f in frames]
    def text(self,query):return [float(i==2) for i in range(scenes.DIM)]


class SceneTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.PreviewTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.PreviewTests.tearDownClass.__func__)
    tearDown=fixtures.PreviewTests.tearDown
    load=fixtures.PreviewTests.load

    def setUp(self):
        fixtures.PreviewTests.setUp(self)
        # These tests own scene children; an empty subtitle poll can briefly hold
        # jobs.lock. Subtitle supervision is exercised in test_subtitles.py.
        self.app.state.jobs.close()
        self.item=self.load(self.source)['id']
        self.url=f'/api/library/{self.item}/scenes'
        p=self.app.state.previews
        p.prepare(self.item);p.prepare(self.item)
        self.identity=patch.object(scenes,'identity',return_value=(self.root/'models/scene','cpu','a'*64))
        self.identity.start();self.addCleanup(self.identity.stop);Encoder.seen=[]

    def test_saved_vectors_reused_after_restart_and_input_changes(self):
        self.assertEqual(scenes.execute(self.store,self.item,encoder_type=Encoder)['state'],'ready')
        self.assertEqual(Encoder.seen,list(range(5)));Encoder.seen=[]
        self.assertEqual(scenes.execute(self.store,self.item,encoder_type=Encoder)['completed'],5)
        self.assertEqual(Encoder.seen,[])
        results=scenes.execute(self.store,self.item,'PRIVATE_QUERY',Encoder)
        self.assertEqual(results['candidates'][0]['time'],25)
        self.assertNotIn('PRIVATE_QUERY',json.dumps(results))
        with self.store.db() as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],7)
            db.execute("UPDATE scene_vectors SET vector=x'0001' WHERE ordinal=1");db.commit()
        self.assertEqual(scenes.status(self.store,self.item)['completed'],4)
        with self.assertRaisesRegex(MediaError,'scene_index_required'):scenes.execute(self.store,self.item,'text',Encoder)
        scenes.execute(self.store,self.item,encoder_type=Encoder);self.assertEqual(Encoder.seen,[1])
        with patch.object(scenes,'identity',return_value=(self.root/'models/scene','cpu','b'*64)):
            self.assertEqual(scenes.status(self.store,self.item)['completed'],0)
        with self.store.db() as db:
            db.execute("UPDATE preview_frames SET image=x'0001' WHERE ordinal=0");db.commit()
        with self.assertRaisesRegex(MediaError,'preview_changed'):scenes.execute(self.store,self.item,'text',Encoder)

    def test_actual_exit_after_batch_resumes_without_reencoding_saved_images(self):
        code='''
import os,sys
from pathlib import Path
from media_clarity import scenes
from media_clarity.storage import Store
scenes.identity=lambda root:(root/'models/scene','cpu','a'*64)
class Encoder:
 def __init__(self,*args):pass
 def images(self,frames):
  if frames[0]['ordinal']==4:os._exit(29)
  return [[float(i==f['ordinal']) for i in range(scenes.DIM)] for f in frames]
scenes.execute(Store(Path(sys.argv[1])),sys.argv[2],encoder_type=Encoder)
'''
        child=subprocess.run([sys.executable,'-c',code,str(self.root),self.item],capture_output=True)
        self.assertEqual(child.returncode,29,child.stderr);self.assertEqual(child.stdout,b'')
        with self.store.db() as db:before=[tuple(r) for r in db.execute('SELECT * FROM scene_vectors ORDER BY ordinal')]
        self.assertEqual(len(before),4)
        scenes.execute(self.store,self.item,encoder_type=Encoder);self.assertEqual(Encoder.seen,[4])
        with self.store.db() as db:
            self.assertEqual([tuple(r) for r in db.execute('SELECT * FROM scene_vectors ORDER BY ordinal LIMIT 4')],before)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.assertEqual(self.store.file_path(self.store._row(self.item)).read_bytes(),self.source.read_bytes())

    def test_http_query_is_bounded_post_only_and_item_scoped(self):
        self.assertEqual(self.client.post(self.url+'/search',json={'query':'SECRET'}).status_code,403)
        with patch.object(self.app.state.scenes,'run',side_effect=lambda item,query=None:scenes.execute(self.store,item,query,Encoder)):
            self.assertEqual(self.client.post(self.url+'/prepare',headers=self.headers).status_code,200)
            response=self.client.post(self.url+'/search',headers=self.headers,json={'query':'SECRET'})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.headers['cache-control'],'no-store')
            self.assertNotIn('SECRET',response.text)
            candidate=response.json()['candidates'][0]
            self.assertEqual(self.client.get(candidate['image']).status_code,200)
            self.assertEqual(self.client.get(candidate['image'].replace(self.item,'f'*32)).status_code,404)
            for body in ({'query':'x'*201},{'query':'x\nSECRET'},{'query':''},{'query':3},{'query':'a','other':1}):
                self.assertEqual(self.client.post(self.url+'/search',headers=self.headers,json=body).status_code,422)
            self.assertEqual(self.client.post(self.url+'/search',headers=self.headers,content=b'x'*2049).status_code,422)
            self.assertEqual(self.client.get(self.url+'/search').status_code,405)
        with self.store.db() as db:self.assertNotIn('SECRET','\n'.join(db.iterdump()))

    def test_real_child_missing_model_is_quiet_and_releases_lease(self):
        response=self.client.post(self.url+'/prepare',headers=self.headers)
        self.assertEqual(response.json(),{'error':'scene_model_missing'})
        with worker_guard(self.root):pass
        self.assertIsNone(self.app.state.scenes.process)

    def test_close_kills_real_child_without_blocking_viewing_or_losing_lease(self):
        actual=subprocess.Popen;entered=self.root/'entered';holder={}
        code='''
import pathlib,sys,time
from media_clarity.jobs import worker_guard
with worker_guard(pathlib.Path(sys.argv[1])):
 pathlib.Path(sys.argv[2]).write_text('ready')
 time.sleep(60)
'''
        def launch(*args,**kwargs):
            p=actual([sys.executable,'-c',code,str(self.root),str(entered)],**kwargs);holder['p']=p;return p
        with ThreadPoolExecutor(2) as pool,patch.object(scenes.subprocess,'Popen',side_effect=launch):
            future=pool.submit(self.app.state.scenes.run,self.item)
            deadline=time.monotonic()+5
            while not entered.exists() and time.monotonic()<deadline:time.sleep(.01)
            self.assertTrue(entered.exists())
            self.assertEqual(self.client.get(f'/api/media/{self.item}/content',headers={'Range':'bytes=0-31'}).status_code,206)
            with self.assertRaisesRegex(MediaError,'processing_worker_active'):self.app.state.scenes.run(self.item)
            self.app.state.scenes.close()
            with self.assertRaisesRegex(MediaError,'scene_failed'):future.result(5)
        self.assertIsNotNone(holder['p'].poll())
        with worker_guard(self.root):pass

    def test_offline_hook_denies_connections_without_private_errors(self):
        code='''
import socket
from media_clarity.scenes import offline
from media_clarity.storage import MediaError
offline()
try:socket.create_connection(('private-query.invalid',443))
except MediaError as e:print(e.code)
'''
        result=subprocess.run([sys.executable,'-c',code],capture_output=True)
        self.assertEqual(result.returncode,0);self.assertEqual(result.stdout,('scene_network_disabled' + os.linesep).encode());self.assertEqual(result.stderr,b'')

    def test_child_exits_before_input_flush_still_releases_supervisor(self):
        actual=subprocess.Popen
        def exited(*args,**kwargs):
            process=actual([sys.executable,'-c','pass'],**kwargs)
            process.wait(timeout=5)
            return process
        with patch.object(scenes.subprocess,'Popen',side_effect=exited):
            with self.assertRaisesRegex(MediaError,'scene_failed'):
                self.app.state.scenes.run(self.item,'비공개 검색어')
        self.assertIsNone(self.app.state.scenes.process)
        def acquire_elsewhere():
            acquired=self.app.state.jobs.lock.acquire(timeout=2)
            if acquired:self.app.state.jobs.lock.release()
            return acquired
        with ThreadPoolExecutor(1) as pool:
            self.assertTrue(pool.submit(acquire_elsewhere).result(5))

    def test_black_frame_is_excluded_but_dark_detail_and_titles_are_kept(self):
        from PIL import Image,ImageDraw
        def jpeg(image):
            output=io.BytesIO();image.save(output,format='JPEG',quality=95);return output.getvalue()
        black=jpeg(Image.new('RGB',(160,90),(1,1,1)))
        self.assertTrue(scenes.black_preview(black))
        title=Image.new('RGB',(160,90));ImageDraw.Draw(title).text((10,30),'TITLE',fill='white')
        self.assertFalse(scenes.black_preview(jpeg(title)))
        dark=Image.new('RGB',(160,90));ImageDraw.Draw(dark).rectangle((20,30,40,60),fill=(16,16,16))
        self.assertFalse(scenes.black_preview(jpeg(dark)))
        with self.store.db() as db:
            db.execute('UPDATE preview_frames SET image=?,sha256=? WHERE ordinal=2',(black,hashlib.sha256(black).hexdigest()));db.commit()
        scenes.execute(self.store,self.item,encoder_type=Encoder)
        result=scenes.execute(self.store,self.item,'frame',Encoder)
        self.assertEqual((result['searched'],result['sampled'],result['black_skipped']),(4,5,1))
        self.assertNotIn(2,[f['ordinal'] for f in result['candidates']])
        # Still available in chronological previews; source/caption data untouched.
        self.assertEqual(self.app.state.previews.status(self.item)['completed'],5)
        with self.store.db() as db:
            db.execute('UPDATE preview_frames SET image=?,sha256=?',(black,hashlib.sha256(black).hexdigest()));db.commit()
        scenes.execute(self.store,self.item,encoder_type=Encoder)
        with patch.object(Encoder,'text',side_effect=AssertionError('needless query inference')):
            result=scenes.execute(self.store,self.item,'frame',Encoder)
        self.assertEqual(result['candidates'],[]);self.assertEqual(result['searched'],0)
