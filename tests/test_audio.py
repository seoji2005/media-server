"""Real audio selection, pinned HTTP bytes, migration rollback and ASR input binding."""
import array
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

import test_renditions as fixtures
from media_clarity import migrations
from media_clarity.jobs import Jobs, execute
from media_clarity.models import LocalModels
from media_clarity.renditions import prepare
from media_clarity.storage import MediaError, Store

ffmpeg = fixtures.ffmpeg


class AudioTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.RenditionTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.RenditionTests.tearDownClass.__func__)
    setUp = fixtures.RenditionTests.setUp
    tearDown = fixtures.RenditionTests.tearDown
    load = fixtures.RenditionTests.load
    convert = fixtures.RenditionTests.convert

    def select(self, item, index):
        response = self.client.post(f"/api/library/{item['id']}/audio/{index}",headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['audio_index'],index)
        return self.store.playback_row(item['id'])

    def test_switch_preserves_both_streams_and_pins_range_across_selection(self):
        item = self.load(self.multi)
        first = self.convert(item); first_bytes=self.store.file_path(first).read_bytes()
        second = self.select(item,1); second_bytes=self.store.file_path(second).read_bytes()
        self.assertEqual(ffmpeg('-i',self.multi,'-map','0:a:1','-f','hash','pipe:1'),
                         ffmpeg('-i',self.store.file_path(second),'-map','0:a:0','-f','hash','pipe:1'))
        self.assertNotEqual(first['file_id'],second['file_id'])
        for index,data,ready in [(0,first_bytes,first),(1,second_bytes,second)]:
            response=self.client.get(f"/api/media/{item['id']}/content?audio_index={index}",headers={'Range':'bytes=100-200'})
            self.assertEqual(response.content,data[100:201]);self.assertEqual(response.headers['etag'],'"'+ready['sha256']+'"')
        self.store.save_position(item['id'],2.25,0)
        self.assertEqual(self.select(item,0)['file_id'],first['file_id'])
        self.assertEqual(len(list((self.root/'files').iterdir())),3)
        self.assertEqual(self.store.item(item['id'])['position'],2.25)
        self.assertEqual(self.store.file_path(self.store._row(item['id'])).read_bytes(),self.multi.read_bytes())
        self.store._recover();self.assertEqual(self.store.recovered,0)
        self.assertEqual(len(self.client.get(f"/api/library/{item['id']}").json()['audio_tracks']),2)

    def test_failed_or_invalid_selection_keeps_current_playable_and_retryable(self):
        item=self.load(self.multi);first=self.convert(item)
        url=f"/api/library/{item['id']}/audio/1"
        self.assertEqual(self.client.post(url).status_code,403)
        for index in [-1,2,128,'not-an-index']:
            self.assertEqual(self.client.post(f"/api/library/{item['id']}/audio/{index}",headers=self.headers).status_code,422)
        with patch('media_clarity.renditions.run_media',side_effect=MediaError('media_timeout',422)):
            self.assertEqual(self.client.post(url,headers=self.headers).json()['error'],'media_timeout')
        self.assertEqual(self.store.playback_row(item['id'])['file_id'],first['file_id'])
        self.assertTrue(self.store.item(item['id'])['available'])
        self.assertEqual(len(list((self.root/'files').iterdir())),2)
        self.select(item,1)
        with self.store.db() as db:self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_process_exit_during_second_copy_keeps_selection_until_commit(self):
        item=self.load(self.multi);first=self.convert(item)
        code='''
from contextlib import contextmanager
import os,sys
from pathlib import Path
from media_clarity.storage import Store
from media_clarity.renditions import prepare
s=Store(Path(sys.argv[1])); original=s.db
class Crash:
 def __init__(self,c):self.c=c
 def execute(self,sql,*args):
  result=self.c.execute(sql,*args)
  if sql.startswith('UPDATE items SET audio_index'):os._exit(23)
  return result
 def commit(self):self.c.commit()
@contextmanager
def crash():
 with original() as c:yield Crash(c)
s.db=crash
prepare(s,sys.argv[2],1)
'''
        child=subprocess.run([sys.executable,'-c',code,str(self.root),item['id']],capture_output=True)
        self.assertEqual(child.returncode,23,child.stderr)
        self.assertEqual(child.stdout,b'');self.store._recover()
        self.assertEqual(self.store.recovered,1)
        self.assertEqual(self.store.playback_row(item['id'])['file_id'],first['file_id'])
        self.select(item,1)

    def test_alternate_ac3_and_delayed_asr_keep_the_selected_timeline(self):
        source=Path(self.temp.name)/'delayed.mkv'
        ffmpeg('-i',self.source,'-itsoffset','1','-f','lavfi','-i','sine=frequency=880:sample_rate=16000',
               '-map','0:v','-map','0:a','-map','1:a','-t','4','-c:v','copy','-c:a:0','copy','-c:a:1','ac3',
               '-metadata:s:a:0','language=eng','-metadata:s:a:1','language=jpn',
               '-metadata:s:a:1','title=Second <voice>',source)
        item=self.load(source);self.convert(item);ready=self.select(item,1)
        self.assertEqual(ready['preparation'],'audio_mp4')
        tracks=self.store.item(item['id'])['audio_tracks'];self.assertEqual(tracks[1]['language'],'jpn')
        captured={}
        class Whisper:
            def __init__(self,*args,**kwargs):pass
            def transcribe(self,samples,**kwargs):captured['samples']=samples;return [],None
        backend=object.__new__(LocalModels);backend.paths={'asr':self.root/'unused'};backend.device='cpu'
        np=types.SimpleNamespace(frombuffer=lambda data,dtype:array.array('f',data))
        with patch.dict(sys.modules,{'numpy':np,'faster_whisper':types.SimpleNamespace(WhisperModel=Whisper)}),patch.object(backend,'speech_clips',return_value=[0.,4.]):
            backend.transcribe(source,item['duration'],1)
        samples=captured['samples'];first=next(i for i,x in enumerate(samples) if abs(x)>.01)/16000
        self.assertGreater(first,.9);self.assertLess(first,1.15)
        audible=array.array('f',ffmpeg('-copyts','-start_at_zero','-i',self.store.file_path(ready),'-map','0:a:0',
                             '-ac','1','-ar','16000','-af','aresample=async=1:first_pts=0','-f','f32le','pipe:1'))
        playback_first=next(i for i,x in enumerate(audible) if abs(x)>.01)/16000
        self.assertAlmostEqual(first,playback_first,delta=.05)

    def test_job_resume_and_restart_remain_bound_to_original_audio_choice(self):
        # Run deterministically in the foreground; this tests real DB/FFmpeg, synthetic words.
        self.app.state.jobs.close()
        item=self.load(self.multi);self.convert(item);self.select(item,1)
        jobs=Jobs(self.store)
        with patch('media_clarity.models.local_models'):jid=jobs.enqueue(item['id'])
        calls=[]
        class Model:
            def __init__(self,root):pass
            def identity(self):return 'audio-fixture-v1'
            def transcribe(self,path,duration,index):
                calls.append(index)
                self_bytes=ffmpeg('-i',path,'-map',f'0:a:{index}','-f','hash','pipe:1')
                if self_bytes!=ffmpeg('-i',AudioTests.multi,'-map','0:a:1','-f','hash','pipe:1'):raise AssertionError('wrong audio')
                return [{'start':.1,'end':1.8,'text':'hello.'},{'start':2.,'end':3.7,'text':'next.'}]
            def translate(self,text):
                if text=='next.' and len(calls)==1:raise RuntimeError('fixture interruption')
                return '선택한 음성입니다.'
            def close(self):pass
        self.select(item,0)
        with patch('media_clarity.models.local_models'),self.assertRaisesRegex(MediaError,'processing_audio_conflict'):
            jobs.enqueue(item['id'])
        execute(self.store,jid,Model)
        row=jobs.row(jid);self.assertEqual(row['state'],'failed');self.assertEqual(row['completed'],1)
        class Resume(Model):
            def transcribe(self,*args):raise AssertionError('ASR repeated')
            def translate(self,text):return '재개한 번역입니다.'
        with patch('media_clarity.models.local_models'):jobs.action(jid,'resume')
        execute(self.store,jid,Resume)
        self.assertEqual(jobs.row(jid)['state'],'succeeded');self.assertEqual(calls,[1])
        self.assertEqual(jobs.status(item['id'])['tracks'][0]['audio_index'],1)
        # Another voice's track must not prevent track 0 generation.
        with patch('media_clarity.models.local_models'):other=jobs.enqueue(item['id'])
        self.assertEqual(jobs.row(other)['audio_index'],0)
        jobs.action(other,'pause');self.select(item,1)
        with patch('media_clarity.models.local_models'):jobs.action(other,'restart')
        queued=next(j for j in jobs.status(item['id'])['jobs'] if j['state']=='queued')
        self.assertEqual(queued['audio_index'],0)
        supplied=jobs.import_srt(item['id'],'1\n00:00:00,100 --> 00:00:02,000\n보존 자막\n'.encode(),0)
        self.assertEqual(next(t for t in jobs.status(item['id'])['tracks'] if t['id']==supplied)['audio_index'],0)

    def test_versioned_migration_rolls_back_and_preserves_legacy_rows(self):
        other=Store(Path(self.temp.name)/'legacy');other.start()
        item=other.import_path(self.multi)['item'];prepare(other,item['id']);other.save_position(item['id'],2.25)
        Jobs(other).import_srt(item['id'],'1\n00:00:00,100 --> 00:00:02,000\n이전 자막\n'.encode())
        other.close()
        with sqlite3.connect(other.root/'library.sqlite3') as db:
            # Restore the actual pre-audio columns and one-copy uniqueness.
            db.execute('ALTER TABLE renditions RENAME TO old_audio')
            db.execute('CREATE TABLE renditions (id TEXT PRIMARY KEY,item_id TEXT NOT NULL UNIQUE REFERENCES items(id),input_sha TEXT NOT NULL,sha256 TEXT NOT NULL,size INTEGER NOT NULL,extension TEXT NOT NULL,mime TEXT NOT NULL,kind TEXT NOT NULL,duration REAL)')
            db.execute('INSERT INTO renditions SELECT id,item_id,input_sha,sha256,size,extension,mime,kind,duration FROM old_audio');db.execute('DROP TABLE old_audio')
            for table,column in [('files','audio_tracks'),('items','audio_index'),('subtitle_jobs','audio_index'),('subtitle_tracks','audio_index')]:db.execute(f'ALTER TABLE {table} DROP COLUMN {column}')
            db.execute('PRAGMA user_version=0')
            before={t:db.execute(f'SELECT * FROM {t}').fetchall() for t in ('renditions','items','subtitle_tracks')}
            schema=db.execute('SELECT name,sql FROM sqlite_master ORDER BY name').fetchall()
        migrate=migrations._audio_tracks
        def fail(db):migrate(db);raise MediaError('fixture_abort',503)
        with patch.object(migrations,'_audio_tracks',side_effect=fail),self.assertRaisesRegex(MediaError,'fixture_abort'):other.start()
        with sqlite3.connect(other.root/'library.sqlite3') as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT name,sql FROM sqlite_master ORDER BY name').fetchall(),schema)
            for t,rows in before.items():self.assertEqual(db.execute(f'SELECT * FROM {t}').fetchall(),rows)
        other.start()
        try:
            ready=prepare(other,item['id']);self.assertTrue(ready['available']);self.assertEqual(ready['position'],2.25)
            with other.db() as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],2)
                self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
                for t,rows in before.items():self.assertEqual([tuple(r)[:-1] for r in db.execute(f'SELECT * FROM {t}')],rows)
            prepare(other,item['id'],1)
        finally:other.close()
        with sqlite3.connect(other.root/'library.sqlite3') as db:db.execute('PRAGMA user_version=999')
        with self.assertRaisesRegex(MediaError,'database_version_newer'):other.start()
        with sqlite3.connect(other.root/'library.sqlite3') as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],999)
