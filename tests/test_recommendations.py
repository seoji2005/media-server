"""Real SQLite/HTTP/FFmpeg fixtures; no private preference or model data."""
from contextlib import closing, contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from media_clarity.app import create_app
from media_clarity.recommendations import title_terms


class RecommendationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = tempfile.TemporaryDirectory()
        source = Path(cls.fixtures.name)/'synthetic.mp4'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=10',
                        '-t','2','-c:v','libx264','-pix_fmt','yuv420p',str(source)],check=True,capture_output=True)
        cls.content = source.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.fixtures.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)/'app'
        self.counter = 0; self.start()

    def start(self):
        self.app = create_app(self.root); self.store = self.app.state.store
        self.client = TestClient(self.app,base_url='http://127.0.0.1:8765'); self.client.__enter__()
        self.headers = {'X-Media-Token':self.client.get('/api/session').json()['token']}

    def tearDown(self):
        self.client.__exit__(None,None,None); self.temp.cleanup()

    def add(self, title):
        self.counter += 1
        # A valid trailing MP4 free box makes distinct, otherwise identical fixtures.
        content = self.content + struct.pack('>I4sI',12,b'free',self.counter)
        source = Path(self.temp.name)/f'fixture-{self.counter}.mp4'; source.write_bytes(content)
        item = self.store.import_path(source)['item']
        with self.store.db() as db:
            db.execute('UPDATE items SET title=? WHERE id=?',(title,item['id'])); db.commit()
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),item['sha256'])
        return item['id']

    def save(self, item, preference='neutral', included=True):
        response = self.client.put(f'/api/library/{item}/preference',headers=self.headers,
                                   json={'included':included,'preference':preference,'revision':self.client.get(f'/api/library/{item}/preference').json()['revision']})
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def suggestions(self):
        response = self.client.get('/api/recommendations'); self.assertEqual(response.status_code,200)
        return response.json()

    def test_existing_and_new_items_are_excluded_until_explicitly_included(self):
        first = self.add('PUBLIC_TITLE')
        self.assertEqual(self.client.get(f'/api/library/{first}/preference').json(),{'included':False,'preference':'neutral','revision':0})
        self.save(first,'like',False)
        self.assertEqual(self.suggestions(),{'items':[],'included_count':0})
        self.save(first)
        self.assertEqual([x['id'] for x in self.suggestions()['items']],[first])
        second = self.add('NEW_TITLE')
        self.assertNotIn(second,[x['id'] for x in self.suggestions()['items']])

    def test_feedback_changes_related_ranking_and_leaves_room_for_discovery(self):
        seed = self.add('요리 집밥'); self.save(seed,'like')
        cooking = [self.add(f'요리 집밥 {i}') for i in range(5)]
        unrelated = self.add('숲 산책')
        for iid in cooking+[unrelated]:self.save(iid)
        initial = self.suggestions()['items']
        self.assertIn(initial[0]['id'],cooking); self.assertEqual(initial[0]['recommendation_reason'],'liked_title')
        self.assertEqual(initial[3]['id'],unrelated,'reserve a discovery place when a candidate exists')
        self.assertNotIn(seed,[x['id'] for x in initial])
        self.save(seed,'less')
        lowered = self.suggestions()['items']
        self.assertEqual(lowered[0]['id'],unrelated)
        self.assertTrue(all(x['recommendation_reason']=='lower_priority' for x in lowered[1:]))
        self.save(seed,'dislike')
        self.assertEqual(self.suggestions()['items'][0]['id'],unrelated)
        self.save(seed,'neutral')
        self.assertIn(seed,[x['id'] for x in self.suggestions()['items']])
        self.assertTrue(all(x['recommendation_reason']=='explore' for x in self.suggestions()['items']))

    def test_excluded_titles_and_preferences_do_not_enter_candidates_or_signals(self):
        secret = self.add('DO_NOT_EXPOSE 우주'); self.save(secret,'like',False)
        candidate = self.add('우주 여행'); self.save(candidate)
        unrelated = self.add('바다 수영'); self.save(unrelated)
        hidden_candidate = self.add('DO_NOT_EXPOSE 별빛')
        before = self.suggestions()
        self.assertNotIn('DO_NOT_EXPOSE',json.dumps(before,ensure_ascii=False))
        self.assertNotIn(hidden_candidate,json.dumps(before))
        self.assertEqual([x['id'] for x in before['items']],[unrelated,candidate])
        self.save(secret,'like',True)
        self.assertEqual(self.suggestions()['items'][0]['id'],candidate)
        self.save(secret,'like',False)
        self.assertEqual(self.suggestions(),before,'exclusion also removes influence without erasing the preference')
        self.assertEqual(self.client.get(f'/api/library/{secret}/preference').json(),{'included':False,'preference':'like','revision':3})

    def test_restart_preserves_feedback_original_position_and_subtitles(self):
        seed = self.add('여행 기차'); candidate = self.add('여행 바다')
        self.save(seed,'like'); self.save(candidate)
        initial = self.suggestions()
        self.store.save_position(candidate,1.25)
        srt=b'1\n00:00:00,000 --> 00:00:01,500\nPRIVATE_SUBTITLE_TERM\n'
        tid=self.app.state.jobs.import_srt(candidate,srt)
        vtt=self.app.state.jobs.track(candidate,tid)
        self.assertEqual([x['id'] for x in self.suggestions()['items']],[x['id'] for x in initial['items']])
        before=self.suggestions()
        self.client.__exit__(None,None,None); self.start()
        self.assertEqual(self.suggestions(),before)
        self.assertEqual(self.client.get(f'/api/library/{seed}/preference').json(),{'included':True,'preference':'like','revision':1})
        self.assertEqual(self.store.item(candidate)['position'],1.25)
        self.assertEqual(self.app.state.jobs.track(candidate,tid),vtt)
        item=self.store.item(candidate)
        self.assertEqual(hashlib.sha256(self.client.get(f'/api/media/{candidate}/content').content).hexdigest(),item['sha256'])

    def test_validation_auth_and_failed_commit_preserve_saved_preference(self):
        iid=self.add('PRIVATE_REQUEST_MARKER'); url=f'/api/library/{iid}/preference'
        for body in ({'included':1,'preference':'like'},{'included':True,'preference':[]},
                     {'included':True,'preference':'PRIVATE_REQUEST_MARKER'},None,
                     {'included':True,'preference':'like','extra':1}):
            response=self.client.put(url,headers=self.headers,json=({**body,'revision':0} if isinstance(body,dict) else body))
            self.assertEqual(response.status_code,422); self.assertNotIn('PRIVATE_REQUEST_MARKER',response.text)
        self.assertEqual(self.client.put(url,headers=self.headers,content=b'x'*257).status_code,422)
        self.assertEqual(self.client.put(url,json={'included':True,'preference':'like','revision':1}).status_code,403)
        self.assertEqual(self.client.put(url,headers={**self.headers,'Origin':'https://external.invalid'},json={'included':True,'preference':'like','revision':1}).status_code,403)
        self.assertEqual(self.client.get('/api/library/'+'a'*32+'/preference').status_code,404)
        self.save(iid,'like')
        real_db=self.store.db
        @contextmanager
        def failed_db():
            with real_db() as db:
                class Connection:
                    def execute(self,*args):return db.execute(*args)
                    def commit(self):raise sqlite3.OperationalError('PRIVATE_REQUEST_MARKER')
                yield Connection()
        with patch.object(self.store,'db',failed_db):
            response=self.client.put(url,headers=self.headers,json={'included':False,'preference':'dislike','revision':1})
        self.assertEqual(response.status_code,503); self.assertNotIn('PRIVATE_REQUEST_MARKER',response.text)
        self.assertEqual(self.client.get(url).json(),{'included':True,'preference':'like','revision':1})

    def test_unavailable_candidates_are_skipped_and_unicode_titles_match(self):
        self.assertEqual(title_terms('ＴＨＥ ＴＲＡＶＥＬ_２０２６ 한글.mp4'),{'travel','한글'})
        seed=self.add('ＴＲＡＶＥＬ'); self.save(seed,'like')
        available=self.add('Travel ocean'); self.save(available)
        missing=self.add('Travel'); self.save(missing)
        original=self.store.file_path(self.store._row(missing)); original.rename(original.with_suffix('.missing'))
        suggestions=self.suggestions()['items']
        self.assertEqual([x['id'] for x in suggestions],[available])
        self.assertEqual(suggestions[0]['recommendation_reason'],'liked_title')

    def test_stale_write_cannot_undo_newer_exclusion(self):
        iid=self.add('공개 여행');url=f'/api/library/{iid}/preference'
        initial=self.save(iid,'like')
        old={'included':True,'preference':'neutral','revision':initial['revision']}
        latest=self.save(iid,'like',False)
        response=self.client.put(url,headers=self.headers,json=old)
        self.assertEqual(response.status_code,409);self.assertEqual(response.json(),{'error':'preference_changed'})
        self.assertEqual(self.client.get(url).json(),latest)
        self.assertEqual(self.suggestions(),{'items':[],'included_count':0})
        for revision in (True,-1,1.5,'1',2**53):
            response=self.client.put(url,headers=self.headers,json={**old,'revision':revision})
            self.assertEqual(response.status_code,422)
        new=self.add('미지정 여행')
        response=self.client.put(f'/api/library/{new}/preference',headers=self.headers,json={**old,'revision':99})
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.client.get(f'/api/library/{new}/preference').json(),{'included':False,'preference':'neutral','revision':0})

    def test_pre_revision_database_upgrades_without_erasing_exclusion(self):
        iid=self.add('저장한 선호');self.save(iid,'like',False)
        self.client.__exit__(None,None,None)
        with closing(sqlite3.connect(self.root/'library.sqlite3')) as db, db:
            db.execute('PRAGMA user_version=0')
            db.execute('ALTER TABLE item_preferences DROP COLUMN revision')
        self.start()
        self.assertEqual(self.client.get(f'/api/library/{iid}/preference').json(),{'included':False,'preference':'like','revision':0})
        self.assertEqual(self.suggestions(),{'items':[],'included_count':0})
        self.assertEqual(self.save(iid,'like')['revision'],1)


if __name__=='__main__':unittest.main()
