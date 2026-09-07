"""Real mixed-time-base regression for moving-video metric pairing."""
import importlib.util
import math
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('video_filter_probe', Path(__file__).parents[1] / 'scripts/probe_video_filters.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class VideoFilterProbeTests(unittest.TestCase):
    def test_mkv_mp4_metrics_pair_decoded_frame_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            reference, candidate = root / 'reference.mkv', root / 'candidate.mp4'
            def ffmpeg(*args):
                return subprocess.check_output(['ffmpeg', '-v', 'error', '-nostdin', *map(str, args)], stderr=subprocess.DEVNULL)
            ffmpeg('-f', 'lavfi', '-i', 'testsrc2=size=128x96:rate=24:duration=2',
                   '-c:v', 'ffv1', '-threads', '1', '-n', reference)
            ffmpeg('-i', reference, '-vf', 'eq=brightness=0.01', '-fps_mode', 'passthrough',
                   '-c:v', 'libx264', '-crf', '0', '-threads', '1', '-n', candidate)
            def pixels(path):
                return ffmpeg('-i', path, '-fps_mode', 'passthrough', '-pix_fmt', 'yuv420p', '-f', 'rawvideo', '-')
            left, right = pixels(reference), pixels(candidate)
            size = 128 * 96 * 3 // 2
            self.assertEqual(len(left), 48 * size)
            self.assertEqual(len(right), len(left))
            expected = []
            for start in range(0, len(left), size):
                mse = sum((a - b) ** 2 for a, b in zip(left[start:start+size], right[start:start+size])) / size
                expected.append(10 * math.log10(255 ** 2 / mse))
            actual = probe.score(reference, candidate, root, 'mixed', 'psnr', 48)
            self.assertAlmostEqual(actual['mean'], sum(expected) / 48, delta=.006)
            self.assertAlmostEqual(actual['min'], min(expected), delta=.006)

    def test_subprocess_failure_keeps_only_stage_and_exit(self):
        with self.assertRaisesRegex(ValueError, '^inspect_exit_1$'):
            probe.inspect(Path('nonexistent-private-title.mkv'))
