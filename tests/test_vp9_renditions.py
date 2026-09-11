"""Real VP9 container/audio preparation, unchanged video and durable originals."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import test_renditions as fixtures
from media_clarity.jobs import Jobs
from media_clarity.renditions import playback_plan
from media_clarity.storage import MediaError


def ffmpeg(*args):
    return subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', *map(str, args)],
                          check=True, capture_output=True, timeout=30).stdout


def metadata(path):
    return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
                      '-show_format', '-of', 'json', str(path)], timeout=10))


class VP9RenditionTests(unittest.TestCase):
    setUp = fixtures.RenditionTests.setUp
    tearDown = fixtures.RenditionTests.tearDown
    load = fixtures.RenditionTests.load
    convert = fixtures.RenditionTests.convert

    @classmethod
    def setUpClass(cls):
        cls.fixtures = tempfile.TemporaryDirectory()
        root = Path(cls.fixtures.name)
        cls.source = root/'vp9-aac.mp4'
        cls.mkv = cls.source  # Reuse the real pre-commit crash/recovery fixture method.
        ffmpeg('-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=12', '-f', 'lavfi', '-i',
               'sine=frequency=440:sample_rate=48000', '-t', '4', '-c:v', 'libvpx-vp9',
               '-threads', '2', '-deadline', 'realtime', '-cpu-used', '8', '-c:a', 'aac', cls.source)
        cls.opus = root/'vp9-opus.mp4'
        ffmpeg('-i', cls.source, '-c:v', 'copy', '-c:a', 'libopus', cls.opus)
        cls.silent = root/'vp9-silent.mp4'
        ffmpeg('-i', cls.source, '-an', '-c:v', 'copy', cls.silent)
        cls.multi = root/'vp9-two-audio.mkv'
        ffmpeg('-i', cls.source, '-f', 'lavfi', '-i', 'sine=frequency=880:sample_rate=48000',
               '-map', '0:v', '-map', '0:a', '-map', '1:a', '-t', '4', '-c:v', 'copy',
               '-c:a:0', 'copy', '-c:a:1', 'libopus', cls.multi)

    @classmethod
    def tearDownClass(cls):
        cls.fixtures.cleanup()

    def test_mp4_aac_to_webm_preserves_video_captions_history_and_range(self):
        item = self.load(self.source)
        self.assertEqual((item['preparation'], item['unavailable_reason']), ('audio_webm', 'rendition_required'))
        jobs = Jobs(self.store)
        track = jobs.import_srt(item['id'], b'1\n00:00:00,500 --> 00:00:03,500\nPreserved caption\n')
        before_caption = jobs.track(item['id'], track)
        ready = self.convert(item); target = self.store.file_path(ready)
        self.assertEqual((ready['extension'], ready['mime']), ('webm', 'video/webm'))
        streams = metadata(target)['streams']
        self.assertEqual([(s['codec_name'], s.get('channels')) for s in streams], [('vp9', None), ('opus', 2)])
        fixtures.assert_stream_copy(self.source, target, '0:v:0')
        self.assertAlmostEqual(float(streams[0]['start_time']), 0, delta=.001)
        # Opus codec delay and container rounding must not shift the movie by a frame.
        self.assertAlmostEqual(ready['duration'], 4, delta=.04)
        body = target.read_bytes()
        response = self.client.get(f"/api/media/{item['id']}/content", headers={'Range':'bytes=128-255'})
        self.assertEqual(response.status_code, 206); self.assertEqual(response.content, body[128:256])
        self.assertEqual(response.headers['etag'], '"'+ready['sha256']+'"')
        self.store.save_position(item['id'], 2.25)
        with patch('media_clarity.renditions.run_media', side_effect=AssertionError('ready copy rebuilt')):
            again = self.convert(item)
        self.assertEqual(again['file_id'], ready['file_id'])
        self.assertEqual(self.store.item(item['id'])['position'], 2.25)
        self.assertEqual(jobs.track(item['id'], track), before_caption)
        self.assertEqual(self.store.file_path(self.store._row(item['id'])).read_bytes(), self.source.read_bytes())
        self.assertTrue(self.store.import_path(self.source)['duplicate'])

    def test_mp4_opus_and_silent_remux_without_video_reencoding(self):
        for source in (self.opus, self.silent):
            with self.subTest(source=source.name):
                item = self.load(source); self.assertEqual(item['preparation'], 'remux_webm')
                target = self.store.file_path(self.convert(item))
                fixtures.assert_stream_copy(source, target, '0:v:0')
                if source == self.opus:
                    # Encoded packets and full decoded codec frames remain identical.
                    self.assertEqual(fixtures.decoded_hash(source, '0:a:0'), fixtures.decoded_hash(target, '0:a:0'))
                    self.assertEqual(ffmpeg('-i', source, '-map', '0:a:0', '-c', 'copy', '-f', 'hash', 'pipe:1'),
                                     ffmpeg('-i', target, '-map', '0:a:0', '-c', 'copy', '-f', 'hash', 'pipe:1'))
                else:
                    self.assertEqual(len(metadata(target)['streams']), 1)

    def test_multi_audio_switch_keeps_original_and_reuses_each_derivative(self):
        item = self.load(self.multi)
        self.assertEqual(item['mime'], 'video/x-matroska')
        self.assertTrue(all(t['error'] is None for t in item['audio_tracks']))
        first = self.convert(item); self.store.save_position(item['id'], 1.5)
        response = self.client.post(f"/api/library/{item['id']}/audio/1", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        second = self.store.playback_row(item['id'])
        self.assertEqual(second['preparation'], 'remux_webm'); self.assertNotEqual(first['file_id'], second['file_id'])
        for ready in (first, second):
            fixtures.assert_stream_copy(self.multi, self.store.file_path(ready), '0:v:0')
        self.assertNotEqual(fixtures.decoded_hash(self.store.file_path(first), '0:a:0'),
                            fixtures.decoded_hash(self.store.file_path(second), '0:a:0'))
        self.assertEqual(fixtures.decoded_hash(self.multi, '0:a:1'),
                         fixtures.decoded_hash(self.store.file_path(second), '0:a:0'))
        with patch('media_clarity.renditions.run_media', side_effect=AssertionError('existing copy rebuilt')):
            response = self.client.post(f"/api/library/{item['id']}/audio/0", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.store.playback_row(item['id'])['file_id'], first['file_id'])
        self.assertEqual(response.json()['position'], 1.5)
        self.assertEqual(self.store.file_path(self.store._row(item['id'])).read_bytes(), self.multi.read_bytes())

    def test_failure_preserves_original_and_malformed_rendition_is_refused(self):
        item = self.load(self.source)
        for code, target in [('insufficient_space', 'space'), ('media_timeout', 'encode')]:
            context = patch.object(self.store, 'ensure_space', side_effect=MediaError(code, 507)) if target == 'space' else patch('media_clarity.renditions.run_media', side_effect=MediaError(code, 422))
            with context:
                response = self.client.post(f"/api/library/{item['id']}/playback", headers=self.headers)
            self.assertEqual(response.json()['error'], code)
            self.assertEqual(self.store.file_path(self.store._row(item['id'])).read_bytes(), self.source.read_bytes())
            self.assertEqual(len(list((self.root/'files').iterdir())), 1)
        ready = self.convert(item)
        with self.store.file_path(ready).open('r+b') as stream:
            stream.seek(128); stream.write(b'changed')
        response = self.client.get(f"/api/media/{item['id']}/content", headers={'Range':'bytes=0-255'})
        self.assertEqual(response.json()['error'], 'managed_file_changed')
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), item['sha256'])

    test_actual_exit_before_rendition_commit_recovers_original_and_retries = fixtures.RenditionTests.test_actual_exit_before_rendition_commit_recovers_original_and_retries

    def test_existing_depth_and_unknown_audio_boundaries_stay_closed(self):
        for codec, pixel, audio, code in [('vp9', 'yuv420p10le', 'opus', 'unsupported_video_depth'),
                                        ('hevc', 'yuv420p', 'aac', 'unsupported_hevc'),
                                        ('vp9', 'yuv420p', 'unknown', 'unsupported_audio_codec')]:
            with self.assertRaisesRegex(MediaError, code):
                playback_plan({'codec_name':codec, 'pix_fmt':pixel}, [{'codec_name':audio}], True)
