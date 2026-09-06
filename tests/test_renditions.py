from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from media_clarity.app import create_app
from media_clarity.jobs import Jobs
from media_clarity.renditions import prepare
from media_clarity.storage import MediaError, Store


def ffmpeg(*args):
    return subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', *map(str, args)], check=True, capture_output=True).stdout


def decoded_hash(source, stream):
    # Full codec frames; assert_stream_copy checks presentation trimming separately.
    return ffmpeg('-flags2', '+skip_manual', '-i', source, '-map', stream,
                  *(['-fps_mode', 'passthrough'] if ':v:' in stream else []),
                  '-f', 'hash', 'pipe:1')


def assert_stream_copy(source, target, stream, target_stream=None):
    target_stream = target_stream or stream
    if decoded_hash(source, stream) != decoded_hash(target, target_stream):
        raise AssertionError('decoded codec frames changed')
    if (ffmpeg('-i', source, '-map', stream, '-c', 'copy', '-f', 'hash', 'pipe:1') !=
            ffmpeg('-i', target, '-map', target_stream, '-c', 'copy', '-f', 'hash', 'pipe:1')):
        raise AssertionError('encoded packets changed')
    if ':a:' in stream:
        packets, priming, origins = [], [], []
        for path, selected in [(source, stream), (target, target_stream)]:
            audio = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', selected[2:],
                '-show_packets', '-show_streams', '-show_format', '-of', 'json', str(path)]))
            sides = [s for p in audio['packets'] for s in p.get('side_data_list', [])]
            rate = int(audio['streams'][0]['sample_rate'])
            priming.append(sum(s.get('skip_samples', 0) for s in sides) / rate)
            packets.append(audio['packets'])
            origins.append(float(audio['format']['start_time']))
        # FFmpeg 9 expresses a short final MKV packet as MP4 discard_padding.
        # Compare every packet's declared time/duration and existing priming;
        # rounding is bounded to the source Matroska timebase, never an AAC frame.
        if abs(priming[0] - priming[1]) > .001001 or len(packets[0]) != len(packets[1]):
            raise AssertionError('audio priming or packet count changed')
        for before, after in zip(*packets):
            for field in ('pts_time', 'duration_time'):
                # Match the video's common playback origin, not each audio's
                # first packet, so an independently shifted voice still fails.
                shift = origins[0] - origins[1] if field == 'pts_time' else 0
                if abs(float(before[field]) - float(after[field]) - shift) > .001001:
                    raise AssertionError('audio packet timing changed by more than 1 ms')


class RenditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = tempfile.TemporaryDirectory()
        cls.source = Path(cls.fixtures.name) / 'source.mp4'
        ffmpeg('-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=12', '-f', 'lavfi', '-i',
               'sine=frequency=440:sample_rate=48000', '-t', '4', '-c:v', 'libx264', '-c:a', 'aac', cls.source)
        cls.mkv = cls.source.with_suffix('.mkv')
        ffmpeg('-i', cls.source, '-c', 'copy', cls.mkv)
        cls.ac3 = cls.source.with_name('audio-ac3.mp4')
        ffmpeg('-i', cls.source, '-c:v', 'copy', '-c:a', 'ac3', cls.ac3)
        cls.multi = cls.source.with_name('two-audio.mkv')
        ffmpeg('-i', cls.source, '-f', 'lavfi', '-i', 'sine=frequency=880:sample_rate=48000',
               '-map', '0:v', '-map', '0:a', '-map', '1:a', '-t', '4', '-c:v', 'copy',
               '-c:a', 'aac', '-disposition:a:0', '0', '-disposition:a:1', 'default', cls.multi)

    @classmethod
    def tearDownClass(cls):
        cls.fixtures.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'data'
        self.app = create_app(self.root)
        self.client = TestClient(self.app, base_url='http://127.0.0.1:8765')
        self.client.__enter__()
        self.store = self.app.state.store
        self.headers = {'X-Media-Token':self.client.get('/api/session').json()['token']}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def load(self, source):
        return self.store.import_path(source)['item']

    def convert(self, item):
        response = self.client.post(f"/api/library/{item['id']}/playback", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return self.store.playback_row(item['id'])

    def test_real_mkv_remux_preserves_frames_audio_original_and_http_identity(self):
        source_bytes = self.mkv.read_bytes()
        item = self.load(self.mkv)
        self.assertEqual(item['unavailable_reason'], 'rendition_required')
        url = f"/api/media/{item['id']}/content"
        self.assertEqual(self.client.get(url).status_code, 409)
        self.assertEqual(self.client.post(f"/api/library/{item['id']}/playback").status_code, 403)
        ready = self.convert(item)
        target = self.store.file_path(ready)
        self.assertNotEqual(ready['file_id'], item['file_id'])
        self.assertNotEqual(ready['sha256'], item['sha256'])
        for stream in ['0:v:0', '0:a:0']:
            assert_stream_copy(self.mkv, target, stream)
        response = self.client.get(url, headers={'Range':'bytes=128-255'})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, target.read_bytes()[128:256])
        self.assertEqual(response.headers['etag'], '"'+ready['sha256']+'"')
        self.assertEqual(self.store.file_path(self.store._row(item['id'])).read_bytes(), source_bytes)
        self.assertEqual(self.mkv.read_bytes(), source_bytes)
        self.store.save_position(item['id'], 2.25)
        self.assertTrue(self.store.import_path(self.mkv)['duplicate'])
        self.convert(item)  # Idempotent preparation does not append extra copies.
        self.assertEqual(len(list((self.root / 'files').iterdir())), 2)
        self.assertEqual(self.store.item(item['id'])['position'], 2.25)
        end = self.store.item(item['id'])['duration']
        self.assertEqual(self.store.save_position(item['id'],end)['position'],end)
        with self.assertRaisesRegex(MediaError,'invalid_position'):
            self.store.save_position(item['id'],end+.1)

    def test_ac3_becomes_aac_stereo_without_video_encoding(self):
        item = self.load(self.ac3)
        self.assertEqual(item['preparation'], 'audio_mp4')
        ready = self.convert(item)
        target = self.store.file_path(ready)
        raw = subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(target)])
        audio = [s for s in json.loads(raw)['streams'] if s['codec_type']=='audio']
        self.assertEqual([(s['codec_name'],s['channels']) for s in audio], [('aac',2)])
        assert_stream_copy(self.ac3, target, '0:v:0')
        self.assertEqual(hashlib.sha256(self.ac3.read_bytes()).hexdigest(), item['sha256'])

    def test_first_audio_matches_asr_even_when_second_is_default(self):
        item = self.load(self.multi)
        target = self.store.file_path(self.convert(item))
        assert_stream_copy(self.multi, target, '0:a:0')
        second = decoded_hash(self.multi, '0:a:1')
        actual = decoded_hash(target, '0:a:0')
        self.assertNotEqual(second, actual)

    def test_space_conversion_and_validation_failures_keep_original_and_allow_retry(self):
        item = self.load(self.mkv)
        original = self.store.file_path(self.store._row(item['id'])).read_bytes()
        for code, target in [('insufficient_space','space'),('media_timeout','process'),('rendition_validation_failed','probe')]:
            with self.subTest(code=code):
                if target == 'space':
                    context = patch.object(self.store, 'ensure_space', side_effect=MediaError(code,507))
                elif target == 'process':
                    context = patch('media_clarity.renditions.run_media', side_effect=MediaError(code,422))
                else:
                    actual_probe = self.store.probe
                    def mismatched(path):
                        result = actual_probe(path)
                        if result['extension']=='mp4':result['duration'] += 2
                        return result
                    context = patch.object(self.store, 'probe', side_effect=mismatched)
                with context:
                    response = self.client.post(f"/api/library/{item['id']}/playback", headers=self.headers)
                self.assertEqual(response.json()['error'], code)
                self.assertEqual(self.store.item(item['id'])['preparation_error'], code)
                self.assertEqual(self.store.file_path(self.store._row(item['id'])).read_bytes(), original)
                self.assertEqual(len(list((self.root/'files').iterdir())), 1)
        self.convert(item)
        self.assertIsNone(self.store.item(item['id'])['preparation_error'])

    def test_import_lock_and_changed_derived_bytes_fail_closed(self):
        item = self.load(self.mkv)
        with self.store.import_lock:
            response = self.client.post(f"/api/library/{item['id']}/playback", headers=self.headers)
        self.assertEqual(response.status_code, 409)
        ready = self.convert(item)
        path = self.store.file_path(ready)
        with path.open('r+b') as stream:
            stream.seek(128); stream.write(b'changed')
        response = self.client.get(f"/api/media/{item['id']}/content", headers={'Range':'bytes=0-255'})
        self.assertEqual(response.json()['error'], 'managed_file_changed')
        self.assertFalse(self.store.item(item['id'])['available'])
        self.assertEqual(hashlib.sha256(self.mkv.read_bytes()).hexdigest(), item['sha256'])

    def test_actual_exit_before_rendition_commit_recovers_original_and_retries(self):
        item = self.load(self.mkv)
        code = '''
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
  if sql.startswith('INSERT INTO renditions'):os._exit(23)
  return result
 def commit(self):self.c.commit()
@contextmanager
def crash():
 with original() as c:yield Crash(c)
s.db=crash
prepare(s,sys.argv[2])
'''
        result = subprocess.run([sys.executable,'-c',code,str(self.root),item['id']], capture_output=True)
        self.assertEqual(result.returncode,23,result.stderr)
        self.assertEqual(result.stdout,b'')
        self.store._recover()
        self.assertEqual(self.store.recovered,1)
        self.assertEqual(self.store.item(item['id'])['unavailable_reason'],'rendition_required')
        ready = self.convert(item)
        self.store._recover()
        self.assertTrue(self.store.file_path(ready).is_file())
        self.assertEqual(hashlib.sha256(self.store.file_path(self.store._row(item['id'])).read_bytes()).hexdigest(),item['sha256'])
        with self.store.db() as db:
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_old_database_migration_preserves_ready_subtitle_and_original(self):
        item = self.load(self.source)
        self.assertEqual(item['preparation'],'original')
        self.assertEqual(self.store.playback_row(item['id'])['file_id'],item['file_id'])
        # Recreate the prior files schema with actual content, then migrate it.
        other = Store(Path(self.temp.name)/'legacy'); other.start()
        legacy = other.import_path(self.source)['item']
        other.save_position(legacy['id'],2.25)
        jobs = Jobs(other); jobs.init()
        jobs.import_srt(legacy['id'], '1\n00:00:00,500 --> 00:00:02,000\n보존할 자막\n'.encode())
        with other.db() as db: before = tuple(db.execute('SELECT * FROM subtitle_tracks').fetchone())
        other.close()
        with closing(sqlite3.connect(other.root/'library.sqlite3')) as db, db:
            db.execute('PRAGMA user_version=0')
            db.execute('ALTER TABLE files DROP COLUMN preparation')
            db.execute('ALTER TABLE files DROP COLUMN preparation_error')
        other.start()
        try:
            self.assertEqual(other.item(legacy['id'])['preparation'],'unchecked')
            legacy = prepare(other,legacy['id'])
            self.assertTrue(legacy['available'])
            self.assertEqual(legacy['sha256'],item['sha256'])
            self.assertEqual(legacy['position'],2.25)
            with other.db() as db:self.assertEqual(tuple(db.execute('SELECT * FROM subtitle_tracks').fetchone()),before)
        finally:other.close()

    def test_discarded_longer_audio_does_not_reject_intact_selected_timeline(self):
        source = Path(self.temp.name)/'long-secondary.mkv'
        ffmpeg('-i',self.source,'-f','lavfi','-i','sine=frequency=880:sample_rate=48000',
               '-map','0:v','-map','0:a','-map','1:a','-t','6','-c:v','copy','-c:a','aac',source)
        item = self.load(source)
        self.assertGreater(item['duration'],6)
        target = self.store.file_path(self.convert(item))
        playable = self.store.item(item['id'])
        self.assertAlmostEqual(playable['duration'],4,delta=.1)
        self.assertAlmostEqual(self.store.probe(target)['duration'],playable['duration'])
        self.assertEqual(self.store.save_position(item['id'],playable['duration'])['position'],playable['duration'])
        with self.assertRaisesRegex(MediaError,'invalid_position'):
            self.store.save_position(item['id'],item['duration'])
        for stream in ['0:v:0','0:a:0']:
            assert_stream_copy(source, target, stream)

    def test_legacy_multi_audio_is_classified_on_first_use_without_history_rewrite(self):
        source = Path(self.temp.name)/'legacy-multi.mp4'
        ffmpeg('-i',self.multi,'-map','0','-c','copy',source)
        other = Store(Path(self.temp.name)/'legacy');other.start()
        item = other.import_path(source)['item'];other.save_position(item['id'],2.25);other.close()
        with closing(sqlite3.connect(other.root/'library.sqlite3')) as db, db:
            db.execute('PRAGMA user_version=0')
            db.execute('ALTER TABLE files DROP COLUMN preparation')
            db.execute('ALTER TABLE files DROP COLUMN preparation_error')
        other.start()
        try:
            self.assertEqual(other.item(item['id'])['preparation'],'unchecked')
            ready = prepare(other,item['id'])
            self.assertEqual(ready['preparation'],'remux_mp4')
            self.assertTrue(ready['available']);self.assertEqual(ready['position'],2.25)
            target = other.file_path(other.playback_row(item['id']))
            assert_stream_copy(source, target, '0:a:0')
            self.assertEqual(other.file_path(other._row(item['id'])).read_bytes(),source.read_bytes())
        finally:other.close()

    def test_real_hevc_and_10bit_are_rejected_with_specific_codes(self):
        for encoder,pixel,code in [('libx265','yuv420p','unsupported_hevc'),('libx264','yuv420p10le','unsupported_video_depth')]:
            with self.subTest(code=code):
                path = Path(self.temp.name)/(encoder+'.mp4')
                options = ['-x265-params','pools=1:frame-threads=1:log-level=error'] if encoder=='libx265' else []
                ffmpeg('-f','lavfi','-i','testsrc2=size=64x64:rate=5','-t','1','-c:v',encoder,'-pix_fmt',pixel,*options,path)
                original = path.read_bytes()
                with self.assertRaisesRegex(MediaError,code):self.load(path)
                self.assertEqual(path.read_bytes(),original)
        self.assertEqual(self.store.list_items(),[])
