import dataclasses
import unittest

import numpy as np

from wake_word import config
from wake_word.detector import (
    GATE_HANGOVER_CHUNKS,
    GATE_PREROLL_CHUNKS,
    WakeWordDetector,
)

LOUD = np.full(1280, 4000, dtype=np.int16)
QUIET = np.full(1280, 10, dtype=np.int16)


class FakeModel:
    """Modelo falso: devuelve scores programados y cuenta las llamadas."""

    def __init__(self, key, scores=()):
        self.key = key
        self.scores = list(scores)
        self.predict_calls = 0
        self.reset_calls = 0

    def predict(self, chunk):
        self.predict_calls += 1
        score = self.scores.pop(0) if self.scores else 0.0
        return {self.key: score}

    def reset(self):
        self.reset_calls += 1


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def make_detector(scores=(), **overrides):
    settings = dataclasses.replace(config.load_settings(), **overrides)
    model = FakeModel(settings.model_key, scores)
    clock = FakeClock()
    return WakeWordDetector(settings, model, clock), model, clock


class ThresholdTests(unittest.TestCase):
    def test_scores_below_threshold_never_fire(self):
        det, _, _ = make_detector([0.1, 0.4, 0.49], threshold=0.5, gate_rms=0)
        self.assertEqual([det.process(QUIET) for _ in range(3)], [None] * 3)

    def test_fires_and_resets_model(self):
        det, model, _ = make_detector([0.2, 0.9], threshold=0.5, patience=1, gate_rms=0)
        self.assertIsNone(det.process(QUIET))
        self.assertEqual(det.process(QUIET), 0.9)
        self.assertEqual(model.reset_calls, 1)

    def test_patience_requires_consecutive_frames(self):
        det, _, _ = make_detector(
            [0.9, 0.1, 0.9, 0.9], threshold=0.5, patience=2, gate_rms=0
        )
        results = [det.process(QUIET) for _ in range(4)]
        self.assertEqual(results, [None, None, None, 0.9])

    def test_debounce_blocks_repeats_until_time_passes(self):
        det, _, clock = make_detector([0.9] * 3, threshold=0.5, patience=1, gate_rms=0)
        self.assertIsNotNone(det.process(QUIET))
        clock.now += config.MIN_SECONDS_BETWEEN_DETECTIONS - 0.1
        self.assertIsNone(det.process(QUIET))
        clock.now += 0.2
        self.assertIsNotNone(det.process(QUIET))


class EnergyGateTests(unittest.TestCase):
    def test_gate_skips_model_while_silent(self):
        det, model, _ = make_detector(gate_rms=1000)
        for _ in range(50):
            det.process(QUIET)
        self.assertEqual(model.predict_calls, 0)

    def test_gate_warms_model_with_preroll_on_sound_onset(self):
        det, model, _ = make_detector(gate_rms=1000)
        for _ in range(50):
            det.process(QUIET)
        det.process(LOUD)
        self.assertEqual(model.predict_calls, GATE_PREROLL_CHUNKS + 1)

    def test_gate_stays_open_during_hangover_then_closes(self):
        det, model, _ = make_detector(gate_rms=1000)
        det.process(LOUD)
        base = model.predict_calls
        for _ in range(GATE_HANGOVER_CHUNKS - 1):
            det.process(QUIET)
        self.assertEqual(model.predict_calls - base, GATE_HANGOVER_CHUNKS - 1)
        det.process(QUIET)
        self.assertEqual(model.predict_calls - base, GATE_HANGOVER_CHUNKS - 1)

    def test_gate_disabled_always_runs_model(self):
        det, model, _ = make_detector(gate_rms=0)
        for _ in range(10):
            det.process(QUIET)
        self.assertEqual(model.predict_calls, 10)


if __name__ == "__main__":
    unittest.main()
