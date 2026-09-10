"""Real SQLite/API provided-caption retries and opt-in bounded library queries."""
import hashlib
import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from media_clarity.app import create_app
from media_clarity.jobs import Jobs, execute, PROVIDED_PROFILE
from media_clarity.storage import MediaError
from media_clarity.subtitles import parse_webvtt
from tests import test_gemini as fixtures


VTT = 'WEBVTT\n\nNOTE source note\nignored\n\ncue-one\n00:00.100 --> 00:01.500 align:start\n<v Speaker><c.green>おめでとう。</c></v>\n'.encode()


class CompanionSubtitleTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.GeminiJobTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.GeminiJobTests.tearDownClass.__func__)
    setUp=fixtures.GeminiJobTests.setUp
    tearDown=fixtures.GeminiJobTests.tearDown

    def parameters(self):
        return {'file_id':self.item['file_id'], 'file_sha256':self.item['sha256'],
            'content_sha256':hashlib.sha256(VTT).hexdigest(), 'format':'webvtt',
            'language':'ja', 'timebase':'original-file'}

    def test_lost_response_retry_restart_language_and_original_preservation(self):
        before=self.store.file_path(self.store._row(self.item['id'])).read_bytes()
        self.store.save_position(self.item['id'],1)
        args=self.parameters()
        first=self.jobs.import_provided(self.item['id'],VTT,**args)
        self.assertFalse(first['duplicate']);self.assertTrue(first['ready'])
        self.store.close();self.store.start();self.jobs=Jobs(self.store)
        retry=self.jobs.import_provided(self.item['id'],VTT,**args)
        self.assertTrue(retry['duplicate']);self.assertEqual(first['id'],retry['id'])
        status=self.jobs.status(self.item['id'])
        self.assertEqual(len(status['tracks']),1);self.assertEqual(status['tracks'][0]['language'],'ja')
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT source_srt FROM subtitle_tracks').fetchone()[0],VTT)
        self.assertIn('おめでとう。',self.jobs.track(self.item['id'],first['id']))
        self.assertEqual(self.store.item(self.item['id'])['position'],1)
        self.assertEqual(self.store.file_path(self.store._row(self.item['id'])).read_bytes(),before)
        for key in ('file_id','file_sha256','content_sha256'):
            bad={**args,key:'0'*len(args[key])}
            with self.assertRaises(MediaError):self.jobs.import_provided(self.item['id'],VTT,**bad)
        self.assertEqual(len(self.jobs.status(self.item['id'])['tracks']),1)
        # Foreign supplied captions do not masquerade as a ready Korean translation.
        with patch('media_clarity.qwen.local_models'):
            from media_clarity.qwen import PROFILE
            self.jobs.enqueue(self.item['id'],provider='gemini',speech_profile=PROFILE)

    def test_provided_http_token_bounds_and_inert_markup(self):
        self.store.close()
        with patch.object(Jobs,'start',lambda jobs:jobs.init()),TestClient(create_app(self.root),base_url='http://127.0.0.1:8765') as client:
            url=f"/api/companion/library/{self.item['id']}/subtitles"
            headers={'X-Media-Token':client.get('/api/session').json()['token']}
            self.assertEqual(client.post(url,params=self.parameters(),content=VTT).status_code,403)
            first=client.post(url,params=self.parameters(),content=VTT,headers=headers)
            self.assertEqual(first.status_code,201,first.text)
            self.assertEqual(client.post(url,params=self.parameters(),content=VTT,headers=headers).status_code,200)
            result=client.post(url,params={**self.parameters(),'timebase':'rendition'},content=VTT,headers=headers)
            self.assertEqual(result.status_code,422)
            result=client.post(url,params=self.parameters(),content=b'x'*(2*1024*1024+1),headers=headers)
            self.assertEqual(result.status_code,413)
        for raw in (b'WEBVTT\nX-TIMESTAMP-MAP=LOCAL:00:00.000,MPEGTS:9\n\n',
                    b'WEBVTT\n\nREGION\nid:test\n\n'):
            with self.assertRaises(MediaError):parse_webvtt(raw,4)

    def test_provided_foreign_caption_translates_without_asr_and_keeps_source(self):
        receipt=self.jobs.import_provided(self.item['id'],VTT,**self.parameters())
        before=self.jobs.track(self.item['id'],receipt['id'])
        self.assertTrue(self.jobs.status(self.item['id'])['tracks'][0]['can_retranslate'])
        jid=self.jobs.retranslate(self.item['id'],receipt['id'],'gemini')
        self.assertEqual(self.jobs.row(jid)['speech_profile'],PROVIDED_PROFILE)
        with patch('media_clarity.qwen.QwenSpeech',side_effect=AssertionError('ASR must not run')),patch('media_clarity.models.LocalModels',side_effect=AssertionError('local model must not run')),patch('media_clarity.gemini.request',side_effect=fixtures.reply) as call:
            execute(self.store,jid)
        self.assertEqual(self.jobs.row(jid)['state'],'succeeded')
        call.assert_called_once()
        self.assertEqual(self.jobs.track(self.item['id'],receipt['id']),before)
        self.assertEqual(len(self.jobs.status(self.item['id'])['tracks']),2)

    def test_ruby_annotations_are_not_translated_as_dialogue(self):
        data='WEBVTT\n\n00:00.100 --> 00:01.500\n<ruby>東京<rt>とうきょう</rt></ruby>に行きます。\n'.encode()
        self.assertEqual(parse_webvtt(data,4)[0]['text'],'東京に行きます。')
        args={**self.parameters(),'content_sha256':hashlib.sha256(data).hexdigest()}
        receipt=self.jobs.import_provided(self.item['id'],data,**args)
        jid=self.jobs.retranslate(self.item['id'],receipt['id'],'gemini')
        self.assertEqual(json.loads(self.jobs.row(jid)['transcript'])[0]['text'],'東京に行きます。')
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT source_srt FROM subtitle_tracks WHERE id=?',(receipt['id'],)).fetchone()[0],data)
        with self.assertRaisesRegex(MediaError,'invalid_subtitles'):
            parse_webvtt(data.replace(b'</rt>',b''),4)

    def test_ruby_structure_cannot_consume_later_dialogue(self):
        prefix='WEBVTT\n\n00:00.100 --> 00:01.500\n'
        for malformed in (
                '<ruby>東京<rt>とうきょう</ruby>に行きます。<ruby>大阪<rt>おおさか</rt></ruby>',
                '<ruby>東京<rt>とうきょう</rt ></ruby>に行きます。<ruby>大阪<rt>おおさか</rt></ruby>',
                '<ruby>東京<rt>とうきょう</rt ></ruby>',
                '<ruby>東京<rt>とうきょう</rt extra></ruby>',
                '<ruby>東京<rt>とう<rt>きょう</rt></rt></ruby>',
                '<ruby>東京<ruby>大阪</ruby></ruby>',
                '東京<rt>とうきょう</rt>',
                '<ruby>東京<rt>とうきょう</rt>'):
            with self.subTest(markup=malformed),self.assertRaisesRegex(MediaError,'invalid_subtitles'):
                parse_webvtt((prefix+malformed).encode(),4)
        valid='<ruby>東京<rt>とうきょう</rt></ruby>から<ruby>大阪<rt>おおさか</rt></ruby>へ。'
        self.assertEqual(parse_webvtt((prefix+valid).encode(),4)[0]['text'],'東京から大阪へ。')

    def test_korean_language_variants_preserve_receipt_and_skip_new_processing(self):
        data='WEBVTT\n\n00:00.100 --> 00:01.500\n축하해.\n'.encode()
        for language in ('ko-KR','kor','kor-KR','ko'):
            with self.subTest(language=language):
                args={**self.parameters(),'language':language,'content_sha256':hashlib.sha256(data).hexdigest()}
                receipt=self.jobs.import_provided(self.item['id'],data,**args)
                track=next(t for t in self.jobs.status(self.item['id'])['tracks'] if t['id']==receipt['id'])
                self.assertEqual(track['language'],language)
                self.assertFalse(track['can_retranslate'])
                self.assertEqual(self.jobs.import_provided(self.item['id'],data,**args)['id'],receipt['id'])
                with self.assertRaisesRegex(MediaError,'subtitle_not_found'):
                    self.jobs.retranslate(self.item['id'],receipt['id'],'gemini')
                with self.assertRaisesRegex(MediaError,'subtitles_already_available'):
                    self.jobs.enqueue(self.item['id'],provider='gemini')

    def test_pages_and_lookup_include_only_opted_in_rows_and_stable_cursor(self):
        # Database-only cards: this endpoint reports metadata, never playback readiness.
        with self.store.db() as db:
            for i in range(205):
                fid=f'{i+1:032x}';iid=f'{i+1001:032x}'
                db.execute("INSERT INTO files(id,sha256,size,extension,mime,duration,width,height) VALUES(?,?,1,'mp4','video/mp4',4,16,16)",(fid,f'{i+1:064x}'))
                db.execute('INSERT INTO items(id,file_id,title,created_at) VALUES(?,?,?,?)',
                           (iid,fid,f'Included {i}','2026-09-01T00:00:00.000Z'))
                db.execute("INSERT INTO item_preferences(item_id,included,preference,revision) VALUES(?,1,'neutral',1)",(iid,))
            db.commit()
        self.store.close()
        with patch.object(Jobs,'start',lambda jobs:jobs.init()),TestClient(create_app(self.root),base_url='http://127.0.0.1:8765') as client:
            headers={'X-Media-Token':client.get('/api/session').json()['token']}
            url='/api/companion/library'
            self.assertEqual(client.get(url).status_code,403)
            seen=[];cursor=None
            for page in range(11):
                params={'limit':20}
                if cursor:params['cursor']=cursor
                result=client.get(url,params=params,headers=headers)
                self.assertEqual(result.status_code,200,result.text)
                body=result.json();seen.extend(v['id'] for v in body['items']);cursor=body['next_cursor']
            self.assertIsNone(cursor);self.assertEqual(len(seen),205);self.assertEqual(len(set(seen)),205)
            self.assertNotIn(self.item['id'],seen)
            with client.app.state.store.db() as db:
                db.execute('UPDATE item_preferences SET included=0,revision=2 WHERE item_id=?',(seen[-1],));db.commit()
            body=client.post(url+'/lookup',json={'ids':[seen[0],seen[-1],self.item['id']]},headers=headers).json()
            self.assertEqual([v['id'] for v in body['items']],[seen[0]])
            self.assertEqual(body['unavailable'],[seen[-1],self.item['id']])
            self.assertEqual(client.get(url,params={'limit':101},headers=headers).status_code,422)
            self.assertEqual(client.get(url,params={'cursor':'bad'},headers=headers).status_code,422)
            self.assertEqual(client.post(url+'/lookup',json={'ids':seen[:21]},headers=headers).status_code,422)
