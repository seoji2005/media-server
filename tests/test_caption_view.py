"""Viewing choices and shifted responses never rewrite subtitle/job evidence."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from media_clarity.app import create_app
from media_clarity.caption_view import CaptionView, shifted
from media_clarity.jobs import Jobs, execute
from media_clarity.storage import MediaError
from tests import test_subtitles as fixtures


class CaptionViewTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.SubtitleTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.SubtitleTests.tearDownClass.__func__)
    setUp = fixtures.SubtitleTests.setUp
    tearDown = fixtures.SubtitleTests.tearDown

    def view(self):
        return CaptionView(self.store)

    def supplied(self):
        return self.jobs.import_srt(self.item['id'], fixtures.SRT.encode())

    def snapshot(self):
        with self.store.db() as db:
            tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='caption_views'")]
            return {t: [tuple(r) for r in db.execute('SELECT * FROM '+t)] for t in tables}

    def test_choice_audio_revision_restart_and_immutable_rows(self):
        item, view, track = self.item['id'], self.view(), self.supplied()
        with self.store.db() as db:
            db.execute('UPDATE files SET audio_tracks=?', (json.dumps([{'index':0},{'index':1}]),))
            db.commit()
        before = self.snapshot()
        self.assertEqual(view.read(item), {'selection':None,'offset_ms':0,'revision':0})
        first = view.save(item, 0, track, -500, 0)
        view.save(item, 1, '', 0, 0)
        self.store.close(); self.store.start()
        self.assertEqual(self.view().read(item, 0), first)
        self.assertEqual(self.view().read(item, 1)['selection'], '')
        with self.assertRaises(MediaError) as caught:
            view.save(item, 0, '', 0, 0)
        self.assertEqual(caught.exception.code, 'caption_view_changed')
        self.assertEqual(view.read(item), first)
        self.assertEqual(self.snapshot(), before)

    def test_concurrent_windows_cannot_overwrite_one_revision(self):
        item, view, track = self.item['id'], self.view(), self.supplied()
        def write(offset):
            try:
                return view.save(item, 0, track, offset, 0)
            except MediaError as exc:
                return exc.code
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(write, [-500, 500]))
        self.assertEqual(results.count('caption_view_changed'), 1)
        self.assertIn(view.read(item), results)

    def test_selection_cannot_reference_foreign_stale_or_missing_transcript(self):
        item, view, track = self.item['id'], self.view(), self.supplied()
        for selection in (track+':transcript', 'f'*32):
            with self.assertRaises(MediaError): view.save(item, 0, selection, 0, 0)
        with self.store.db() as db:
            db.execute('UPDATE subtitle_tracks SET input_sha=?', ('0'*64,));db.commit()
        with self.assertRaises(MediaError): view.save(item, 0, track, 0, 0)
        with self.store.db() as db:
            db.execute('UPDATE subtitle_tracks SET input_sha=?', (self.item['sha256'],))
            file = dict(db.execute('SELECT * FROM files').fetchone())
            file.update(id='d'*32, sha256='a'*64)
            db.execute('INSERT INTO files('+','.join(file)+') VALUES('+','.join('?' for _ in file)+')', tuple(file.values()))
            db.execute('INSERT INTO items(id,file_id,title) VALUES(?,?,?)', ('e'*32,'d'*32,'fixture'))
            db.execute('UPDATE subtitle_tracks SET item_id=?', ('e'*32,));db.commit()
        with self.assertRaises(MediaError): view.save(item, 0, track, 0, 0)
        self.assertEqual(view.read(item)['revision'], 0)

    def test_shift_clips_response_and_preserves_canonical_bytes(self):
        track, item = self.supplied(), self.item['id']
        original = self.jobs.track(item, track)
        before = self.snapshot()
        later = self.jobs.track(item, track, offset_ms=1000)
        self.assertIn('00:00:01.100 --> 00:00:02.900', later)
        self.assertIn('00:00:03.000 --> 00:00:04.000', later)
        earlier = self.jobs.track(item, track, offset_ms=-2000)
        self.assertNotIn('안녕하세요', earlier)
        self.assertIn('00:00:00.000 --> 00:00:01.500', earlier)
        self.assertEqual(self.jobs.track(item, track, offset_ms=10000), 'WEBVTT\n\n\n')
        self.assertEqual(self.jobs.track(item, track), original)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),self.item['sha256'])
        for value in (True, 0.5, float('nan'), '500', 10001, -10001):
            with self.assertRaises(MediaError): shifted([], 4, value)
        self.assertEqual(shifted([{'start':0,'end':1.0004,'text':'tiny'}],4,-1000),[])

    def test_generated_source_and_fallback_follow_shift_without_new_inference(self):
        with patch('media_clarity.models.local_models'):
            job = self.jobs.enqueue(self.item['id'])
        with patch.object(fixtures.FixtureModel, 'translate', side_effect=['안녕하세요', '']):
            execute(self.store, job, fixtures.FixtureModel)
        self.assertEqual(self.jobs.row(job)['state'], 'succeeded')
        track = self.jobs.status(self.item['id'])['tracks'][0]['id']
        before = self.snapshot()
        self.view().save(self.item['id'], 0, track+':transcript', 500, 0)
        text = self.jobs.track(self.item['id'], track, transcript=True, offset_ms=500)
        self.assertIn('00:00:00.600', text)
        self.assertIn('hello.', text)
        later = self.jobs.track(self.item['id'], track, offset_ms=-1900)
        self.assertIn('[원문] next.', later)
        self.assertEqual(self.snapshot(), before)

    def test_short_hold_publishes_after_resume_and_preserves_old_version_and_view(self):
        item = self.item['id']
        source = [{'start':.1,'end':.18,'text':'hello.'}, {'start':2,'end':3.5,'text':'next.'}]
        canonical = [{**c,'text':t} for c,t in zip(source,['안녕하세요','다음 장면입니다.'])]
        class Short(fixtures.FixtureModel):
            def transcribe(inner,*args):return source
        # A ready v1 track must retain its stored 80 ms presentation after upgrade.
        old_layout = {'profile':'ko-readable-v1','cues':canonical,'units':[0,1],
                      'issues':[{'cue':0,'codes':['short_duration','reading_speed']}]}
        with patch('media_clarity.models.local_models'):
            old_job = self.jobs.enqueue(item)
        with patch('media_clarity.jobs.generated_layout',return_value=old_layout):
            execute(self.store,old_job,Short)
        old = self.jobs.status(item)['tracks'][0]['id']
        old_vtt = self.jobs.track(item,old)
        old_view = self.view().save(item,0,old,500,0)
        self.store.save_position(item,2.25)
        supplied = self.jobs.import_srt(item,b'1\n00:00:00,100 --> 00:00:00,180\nprovided\n')
        supplied_vtt = self.jobs.track(item,supplied)
        with patch('media_clarity.models.local_models'):
            job = self.jobs.enqueue(item,force=True)
        (self.root/'fail').touch()
        execute(self.store,job,Short)
        self.assertEqual(self.jobs.row(job)['completed'],1)
        with self.store.db() as db:
            prefix = [tuple(r) for r in db.execute('SELECT * FROM subtitle_batches WHERE job_id=?',(job,))]
        class Resumed(Short):
            def transcribe(inner,*args):raise AssertionError('completed ASR repeated')
        (self.root/'fail').unlink()
        with patch('media_clarity.models.local_models'):self.jobs.action(job,'resume')
        execute(self.store,job,Resumed)
        self.assertEqual(self.jobs.row(job)['state'],'succeeded')
        self.assertEqual(self.view().read(item),old_view,'publication must not select the new version')
        with self.store.db() as db:
            row = dict(db.execute('SELECT * FROM subtitle_tracks WHERE job_id=?',(job,)).fetchone())
            after = [tuple(r) for r in db.execute('SELECT * FROM subtitle_batches WHERE job_id=? ORDER BY first_index',(job,))]
        self.assertEqual(after[:len(prefix)],prefix)
        self.assertEqual(json.loads(row['cues']),canonical)
        self.assertEqual(json.loads(self.jobs.row(job)['transcript']),source)
        self.assertEqual(json.loads(row['presentation'])['cues'],[{**canonical[0],'end':.934},canonical[1]])
        track = row['id']
        chosen = self.view().save(item,0,track,500,old_view['revision'])
        before = self.snapshot()
        rendered = self.jobs.track(item,track)
        self.jobs.close();self.store.close()
        try:
            # Two actual application lifespans over the saved SQLite store; no models.
            with patch('media_clarity.jobs.generated_layout',side_effect=AssertionError('saved layout regenerated')):
                for _ in range(2):
                    with TestClient(create_app(self.root),base_url='http://127.0.0.1:8765') as client:
                        url = f'/api/library/{item}/subtitles'
                        status = client.get(url).json()
                        self.assertEqual(status['view'],chosen)
                        self.assertEqual(len(status['tracks']),3)
                        self.assertEqual(next(t for t in status['tracks'] if t['id']==track)['layout'],'ko-readable-v2')
                        self.assertEqual(next(t for t in status['tracks'] if t['id']==old)['layout'],'ko-readable-v1')
                        self.assertEqual(client.get(url+'/'+old+'.vtt').text,old_vtt)
                        self.assertEqual(client.get(url+'/'+supplied+'.vtt').text,supplied_vtt)
                        self.assertEqual(client.get(url+'/'+track+'.vtt').text,rendered)
                        shifted = client.get(url+'/'+track+'.vtt?offset_ms=500')
                        self.assertEqual(shifted.status_code,200)
                        self.assertIn('00:00:00.600 --> 00:00:01.434',shifted.text)
        finally:
            self.store.start()
        self.assertEqual(self.snapshot(),before,'reads/restart must preserve rows and saved position')
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),self.item['sha256'])

    def test_v9_upgrade_and_failed_migration_preserve_existing_data(self):
        self.supplied(); before = self.snapshot()
        with self.store.db() as db:
            db.execute('DROP TABLE caption_views');db.execute('PRAGMA user_version=9');db.commit()
        self.store.close()
        from media_clarity import migrations
        with patch.object(migrations, 'companion_identity', side_effect=MediaError('library_identity_invalid',503)):
            with self.assertRaises(MediaError): self.store.start()
        with self.store.db() as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 9)
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='caption_views'").fetchone())
        self.store.start()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.view().read(self.item['id'])['revision'],0)

    def test_process_death_before_commit_keeps_last_view(self):
        item, track = self.item['id'], self.supplied()
        saved = self.view().save(item, 0, track, 500, 0)
        code = '''
from contextlib import contextmanager
from pathlib import Path
import os,sys
from media_clarity.storage import Store
from media_clarity.caption_view import CaptionView
s=Store(Path(sys.argv[1])); original=s.db
class Interrupt:
 def __init__(self,c):self.c=c
 def execute(self,*args):return self.c.execute(*args)
 def commit(self):os._exit(23)
@contextmanager
def broken():
 with original() as db:yield Interrupt(db)
s.db=broken
CaptionView(s).save(sys.argv[2],0,'',0,1)
'''
        result = subprocess.run([sys.executable,'-c',code,str(self.root),item], capture_output=True,timeout=15)
        self.assertEqual(result.returncode,23)
        self.assertEqual(self.view().read(item),saved)

    def test_http_validation_and_restart_restore(self):
        item, track = self.item['id'], self.supplied()
        self.store.close()
        try:
            for phase in range(2):
                with TestClient(create_app(self.root),base_url='http://127.0.0.1:8765') as client:
                    token = client.get('/api/session').json()['token'];headers={'X-Media-Token':token}
                    endpoint = f'/api/library/{item}/caption-view'
                    payload = {'selection':track,'audio_index':0,'offset_ms':500,'revision':0}
                    if not phase:
                        self.assertEqual(client.put(endpoint,json=payload).status_code,403)
                        self.assertEqual(client.put(endpoint,headers=headers|{'Origin':'https://example.com'},json=payload).status_code,403)
                        for field,values in {'offset_ms':[True,10001,0.1,None], 'audio_index':[True,None,-1,1], 'revision':[True,-1,2**53], 'selection':[[], True, 'private/path']}.items():
                            for value in values:
                                with self.subTest(field=field,value=value):
                                    self.assertEqual(client.put(endpoint,headers=headers,json=payload|{field:value}).status_code,422)
                        for body in ('null', '{}', 'x'*513, '{'):
                            self.assertEqual(client.put(endpoint,headers=headers,content=body).status_code,422)
                        self.assertEqual(client.put(endpoint,headers=headers,json=payload).status_code,200)
                    saved = client.get(f'/api/library/{item}/subtitles?audio_index=0').json()['view']
                    self.assertEqual(saved,{'selection':track,'offset_ms':500,'revision':1})
                    shifted_response=client.get(f'/api/library/{item}/subtitles/{track}.vtt?offset_ms=500')
                    self.assertEqual(shifted_response.status_code,200)
                    self.assertIn('00:00:00.600',shifted_response.text)
                    self.assertIn('00:00:00.100',client.get(f'/api/library/{item}/subtitles/{track}.vtt').text)
        finally:
            self.store.start()
