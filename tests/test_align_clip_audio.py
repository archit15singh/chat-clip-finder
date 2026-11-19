import importlib.util
from pathlib import Path
import unittest

try:
    import numpy as np
except ImportError:
    np = None


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "align-clip-audio.py"
spec = importlib.util.spec_from_file_location("align_clip_audio", SCRIPT)
alignment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alignment)


@unittest.skipIf(np is None, "Audio alignment requires NumPy")
class AudioAlignmentTest(unittest.TestCase):
    def test_quiet_tail_uses_three_disjoint_signal_anchors(self):
        width = alignment.SAMPLE_RATE * alignment.ANCHOR_SECONDS
        signal = np.random.default_rng(12).integers(-5000, 5000, 3 * width).astype(float)
        replay_clip = np.r_[signal, np.zeros(width)]
        clip = replay_clip.copy()
        clip[-8] = 1
        replay = np.r_[np.zeros(width), replay_clip, np.zeros(width)]

        start, matches = alignment.align(clip, replay, np)

        self.assertEqual(start, alignment.ANCHOR_SECONDS)
        self.assertEqual([position for position, _, _ in matches], [0, width, 2 * width])
        self.assertTrue(all(score > 0.99 for _, _, score in matches))

    def test_silent_media_cannot_prove_alignment(self):
        samples = np.zeros(8 * alignment.SAMPLE_RATE)

        with self.assertRaisesRegex(ValueError, "Fewer than three"):
            alignment.align(samples, samples, np)
