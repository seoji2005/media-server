"""Guard the observed upstream geometry failure without model dependencies in CI."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest


spec = importlib.util.spec_from_file_location('enhancement_probe', Path(__file__).parents[1] / 'scripts/probe_enhancement.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class EnhancementProbeTests(unittest.TestCase):
    def test_compressed_padding_counterexample_never_reaches_upstream(self):
        source = SimpleNamespace(shape=(1, 3, 34, 42))
        def upstream(_):
            self.fail('This upstream forward misaligns its two reconstruction branches')
        with self.assertRaisesRegex(ValueError, '^compressed_whole_frame_requires_multiple_of_8$'):
            probe.predict(upstream, source, 0, 4)

    def test_legacy_whole_frame_keeps_non_window_dimensions(self):
        source = SimpleNamespace(shape=(1, 3, 34, 42))
        output = SimpleNamespace(shape=(1, 3, 68, 84))
        self.assertIs(probe.predict(lambda _: output, source, 0), output)

    def test_compressed_primary_image_and_channel_shape(self):
        source = SimpleNamespace(shape=(1, 3, 32, 40))
        output = SimpleNamespace(shape=(1, 3, 128, 160))
        self.assertIs(probe.predict(lambda _: (output, source), source, 0, 4), output)
        wrong_channels = SimpleNamespace(shape=(1, 1, 128, 160))
        with self.assertRaisesRegex(ValueError, '^invalid_prediction_shape$'):
            probe.predict(lambda _: (wrong_channels, source), source, 0, 4)
