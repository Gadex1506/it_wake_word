import unittest

import numpy as np

from wake_word import config
from wake_word.openwakeword_tuning import (
    _SampleRing,
    enable_ring_buffer,
    load_model_class,
)


class SampleRingTests(unittest.TestCase):
    def test_tail_returns_only_available_samples(self):
        ring = _SampleRing(100)
        ring.append(np.arange(10, dtype=np.int16))
        self.assertEqual(ring.tail(50).tolist(), list(range(10)))

    def test_tail_keeps_most_recent_after_wrap(self):
        ring = _SampleRing(100)
        for start in range(0, 300, 30):
            ring.append(np.arange(start, start + 30, dtype=np.int16))
        self.assertEqual(ring.tail(5).tolist(), [295, 296, 297, 298, 299])

    def test_clear_empties_the_ring(self):
        ring = _SampleRing(100)
        ring.append(np.ones(10, dtype=np.int16))
        ring.clear()
        self.assertEqual(ring.tail(10).size, 0)


class RingBufferEquivalenceTests(unittest.TestCase):
    def test_predictions_match_original_implementation(self):
        """El ring buffer debe dar exactamente los mismos scores que openwakeword."""
        s = config.load_settings()
        Model = load_model_class()
        rng = np.random.default_rng(7)
        audio = (rng.standard_normal((60, 1280)) * 2000).astype(np.int16)

        def run(patched):
            np.random.seed(0)  # el buffer inicial de features usa ruido aleatorio
            model = Model(wakeword_models=[str(s.model_path)], inference_framework="onnx")
            if patched:
                self.assertTrue(enable_ring_buffer(model))
            scores = [model.predict(chunk)[s.model_key] for chunk in audio[:30]]
            model.reset()
            return scores + [model.predict(chunk)[s.model_key] for chunk in audio[30:]]

        self.assertEqual(run(patched=False), run(patched=True))


if __name__ == "__main__":
    unittest.main()
