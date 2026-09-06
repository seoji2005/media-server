"""Real FFmpeg/JPEG, bounded incremental preview work and interruption recovery."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import test_renditions as fixtures
from media_clarity.previews import Previews, MAX_IMAGE
from media_clarity.storage import MediaError

ffmpeg=fixtures.ffmpeg


class PreviewTests(unittest.TestCase):
    setUp=fixtures.RenditionTests.setUp
    tearDown=fixtures.RenditionTests.tearDown
    load=fixtures.RenditionTests.load

    @classmethod
    def setUpClass(cls):
        cls.fixtures=tempfile.TemporaryDirectory();cls.source=Path(cls.fixtures.name)/'changes.mp4'
        ffmpeg('-f','lavfi','-i',"color=red:size=160x90:rate=5:d=10[r];color=green:size=160x90:rate=5:d=10[g];color=blue:size=160x90:rate=5:d=10[b];color=yellow:size=160x90:rate=5:d=10[y];color=white:size=160x90:rate=5:d=10[w];[r][g][b][y][w]concat=n=5:v=1:a=0",
               '-c:v','libx264','-pix_fmt','yuv420p',cls.source)

    @classmethod
    def tearDownClass(cls):cls.fixtures.cleanup()

    def test_real_grid_is_incremental_and_images_are_item_scoped(self):
        item=self.load(self.source);url=f"/api/library/{item['id']}/previews"
        self.assertEqual(self.client.get(url).json()['state'],'empty')
        self.assertEqual(self.client.post(url).status_code,403)
        first=self.client.post(url,headers=self.headers).json()
        self.assertEqual((first['state'],first['completed'],first['total']),('partial',4,5))
        self.assertEqual([f['time'] for f in first['frames']],[5,15,25,35])
        expected=[(255,0,0),(0,128,0),(0,0,255),(255,255,0)]
        hashes=[]
        for frame,color in zip(first['frames'],expected):
            response=self.client.get(frame['image']);self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers['content-type'],'image/jpeg')
            self.assertEqual(response.headers['cache-control'],'no-store')
            self.assertLess(len(response.content),MAX_IMAGE)
            hashes.append(hashlib.sha256(response.content).hexdigest())
            self.assertEqual(response.headers['etag'],'"'+hashes[-1]+'"')
            raw=subprocess.run(['ffmpeg','-v','error','-i','pipe:0','-vf','scale=1:1','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],input=response.content,capture_output=True,check=True).stdout
            self.assertTrue(all(abs(a-b)<8 for a,b in zip(raw[:3],color)),(raw[:3],color))
        self.assertEqual(len(set(hashes)),4)
        with self.store.db() as db:before=[tuple(r) for r in db.execute('SELECT * FROM preview_frames ORDER BY ordinal')]
        result=self.client.post(url,headers=self.headers).json();self.assertEqual(result['state'],'ready')
        with patch('media_clarity.previews.run_media',side_effect=AssertionError('completed grid decoded again')):
            self.assertEqual(self.client.post(url,headers=self.headers).json(),result)
        with self.store.db() as db:self.assertEqual([tuple(r) for r in db.execute('SELECT * FROM preview_frames ORDER BY ordinal LIMIT 4')],before)
        self.assertEqual(self.store.file_path(self.store._row(item['id'])).read_bytes(),self.source.read_bytes())
        self.assertEqual(self.client.get(first['frames'][0]['image'].replace(item['id'],'f'*32)).status_code,404)
        with self.store.db() as db:db.execute("UPDATE preview_frames SET image=x'0102' WHERE ordinal=0");db.commit()
        self.assertEqual(self.client.get(first['frames'][0]['image']).json()['error'],'preview_changed')
        self.assertEqual(self.client.post(url+'/0/retry',headers=self.headers).status_code,200)
        self.assertEqual(hashlib.sha256(self.client.get(first['frames'][0]['image']).content).hexdigest(),hashes[0])
        self.assertEqual(self.client.get(f"/api/media/{item['id']}/content",headers={'Range':'bytes=0-127'}).status_code,206)

    def test_bad_frame_can_retry_without_losing_other_images(self):
        item=self.load(self.source);previews=self.app.state.previews
        from media_clarity import previews as module
        actual=module.run_media;calls=0
        def fail_one(*args,**kwargs):
            nonlocal calls
            calls+=1
            if calls==2:raise MediaError('invalid_media',422)
            return actual(*args,**kwargs)
        with patch.object(module,'run_media',side_effect=fail_one):first=previews.prepare(item['id'])
        self.assertEqual(first['failed'],1);self.assertFalse(first['frames'][1]['available'])
        with self.store.db() as db:before=tuple(db.execute('SELECT * FROM preview_frames WHERE ordinal=0').fetchone())
        retry=self.client.post(f"/api/library/{item['id']}/previews/1/retry",headers=self.headers)
        self.assertEqual(retry.status_code,200);self.assertEqual(retry.json()['failed'],0)
        with self.store.db() as db:self.assertEqual(tuple(db.execute('SELECT * FROM preview_frames WHERE ordinal=0').fetchone()),before)
        self.assertEqual(self.client.post(f"/api/library/{item['id']}/previews/99/retry",headers=self.headers).status_code,404)

    def test_preparing_does_not_block_media_or_saved_captions(self):
        item=self.load(self.source);url=f"/api/library/{item['id']}"
        caption=self.client.post(url+'/subtitles',headers=self.headers,
                                 content='1\n00:00:01,000 --> 00:00:04,000\n감상 유지\n'.encode()).json()['id']
        expected=self.client.get(url+f'/subtitles/{caption}.vtt').content
        entered,released=threading.Event(),threading.Event()
        from media_clarity import previews as module
        actual=module.run_media
        def held(*args,**kwargs):
            entered.set()
            if not released.wait(8):raise AssertionError('preview check did not release')
            return actual(*args,**kwargs)
        with ThreadPoolExecutor(2) as pool,patch.object(module,'run_media',side_effect=held):
            build=pool.submit(self.client.post,url+'/previews',headers=self.headers)
            try:
                self.assertTrue(entered.wait(5))
                media=pool.submit(self.client.get,f"/api/media/{item['id']}/content",headers={'Range':'bytes=0-127'}).result(5)
                self.assertEqual(media.status_code,206)
                saved=pool.submit(self.client.get,url+f'/subtitles/{caption}.vtt').result(5)
                self.assertEqual(saved.content,expected)
            finally:released.set()
            self.assertEqual(build.result(5).json()['completed'],4)

    def test_space_failure_and_shutdown_keep_committed_frames(self):
        item=self.load(self.source);previews=self.app.state.previews
        ensure=self.store.ensure_space;calls=0
        def limited(size):
            nonlocal calls
            calls+=1
            if calls==2:raise MediaError('insufficient_space',507)
            ensure(size)
        with patch.object(self.store,'ensure_space',side_effect=limited),self.assertRaisesRegex(MediaError,'insufficient_space'):
            previews.prepare(item['id'])
        self.assertEqual(previews.status(item['id'])['completed'],1)
        with previews.lock,self.assertRaisesRegex(MediaError,'preview_busy'):previews.prepare(item['id'])
        previews.close()
        with self.assertRaisesRegex(MediaError,'preview_interrupted'):previews.prepare(item['id'])
        resumed=Previews(self.store);self.assertEqual(resumed.prepare(item['id'])['completed'],5)

    def test_actual_exit_after_checkpoint_reuses_images_on_restart(self):
        item=self.load(self.source)
        code='''
from contextlib import contextmanager
import os,sys
from pathlib import Path
from media_clarity.storage import Store
from media_clarity.previews import Previews
s=Store(Path(sys.argv[1]));orig=s.db
class Exit:
 def __init__(self,c):self.c=c;self.image=False
 def execute(self,sql,*args):
  if sql.startswith('INSERT INTO preview_frames'):self.image=True
  return self.c.execute(sql,*args)
 def commit(self):
  self.c.commit()
  if self.image:os._exit(29)
@contextmanager
def exiting():
 with orig() as c:yield Exit(c)
s.db=exiting
Previews(s).prepare(sys.argv[2])
'''
        child=subprocess.run([sys.executable,'-c',code,str(self.root),item['id']],capture_output=True)
        self.assertEqual(child.returncode,29,child.stderr);self.assertEqual(child.stdout,b'')
        previous=self.app.state.previews.status(item['id']);self.assertEqual(previous['completed'],1)
        before=self.client.get(previous['frames'][0]['image']).content
        self.assertEqual(Previews(self.store).prepare(item['id'])['state'],'ready')
        self.assertEqual(self.client.get(previous['frames'][0]['image']).content,before)
        with self.store.db() as db:self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_long_audio_does_not_make_blank_previews_beyond_video(self):
        source=Path(self.temp.name)/'extra-audio.mkv'
        ffmpeg('-i',self.source,'-f','lavfi','-i','sine=frequency=440:duration=70',
               '-map','0:v','-map','1:a','-c:v','copy','-c:a','aac',source)
        item=self.load(source);self.assertGreater(item['duration'],69)
        result=self.app.state.previews.prepare(item['id']);self.assertEqual(result['total'],5)  # Sample the 50 s video, excluding its initial mux gap.
        self.assertLess(result['frames'][-1]['time'],50.1)
        self.assertTrue(all(f['available'] for f in result['frames']))

    def test_source_change_never_publishes_unverified_preview(self):
        item=self.load(self.source);previews=self.app.state.previews
        source=self.store.file_path(self.store._row(item['id']))
        from media_clarity import previews as module
        actual=module.run_media
        def changed(*args,**kwargs):
            output=actual(*args,**kwargs)
            with source.open('r+b') as f:f.seek(100);f.write(b'changed')
            return output
        with patch.object(module,'run_media',side_effect=changed),self.assertRaisesRegex(MediaError,'managed_file_changed'):
            previews.prepare(item['id'])
        self.assertEqual(previews.status(item['id'])['completed'],0)

    def test_nonzero_start_matches_original_and_compatible_playback(self):
        from media_clarity.renditions import prepare
        for extension in ('mp4','mkv'):
            with self.subTest(extension=extension):
                source=Path(self.temp.name)/('offset.'+extension)
                ffmpeg('-i',self.source,'-c','copy','-output_ts_offset','5',source)
                item=self.load(source);prepare(self.store,item['id'])
                frames=self.app.state.previews.prepare(item['id'])['frames']
                playback=self.store.file_path(self.store.playback_row(item['id']))
                for frame in frames:
                    self.assertGreaterEqual(frame['time'],5 if extension=='mp4' else 0)
                    # Absolute seeking matches the browser behavior reproduced on
                    # this offset MP4; compare each thumbnail to the ready rendition.
                    image=self.client.get(frame['image']).content
                    thumbnail=subprocess.run(['ffmpeg','-v','error','-i','pipe:0','-vf','scale=1:1','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],input=image,capture_output=True,check=True).stdout
                    actual=subprocess.run(['ffmpeg','-v','error','-seek_timestamp','1','-ss',str(frame['time']),'-i',str(playback),'-frames:v','1','-vf','scale=1:1','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],capture_output=True,check=True).stdout
                    self.assertEqual(len(actual),3)
                    self.assertTrue(all(abs(a-b)<8 for a,b in zip(thumbnail,actual)),(extension,frame['time'],thumbnail,actual))
