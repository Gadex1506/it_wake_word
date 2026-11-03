import os
import unittest
from unittest import mock

from wake_word import config


class ConfigTests(unittest.TestCase):
    def test_blank_values_fall_back_to_defaults(self):
        blank = {
            "WAKE_WORD_THRESHOLD": "", "MICROPHONE_INDEX": "",
            "UNITY_SOCKET_PORT": "", "WAKE_WORD_PATIENCE": "", "ENERGY_GATE_RMS": "",
        }
        with mock.patch.dict(os.environ, blank):
            s = config.load_settings()
        self.assertEqual(s.threshold, 0.5)
        self.assertIsNone(s.microphone_index)
        self.assertEqual(s.port, 9000)
        self.assertEqual(s.patience, 1)
        self.assertEqual(s.gate_rms, 0.0)

    def test_microphone_index_is_parsed(self):
        with mock.patch.dict(os.environ, {"MICROPHONE_INDEX": "4"}):
            self.assertEqual(config.load_settings().microphone_index, 4)

    def test_invalid_value_names_the_variable(self):
        with mock.patch.dict(os.environ, {"WAKE_WORD_THRESHOLD": "abc"}):
            with self.assertRaisesRegex(config.ConfigError, "WAKE_WORD_THRESHOLD"):
                config.load_settings()

    def test_out_of_range_threshold_is_rejected(self):
        with mock.patch.dict(os.environ, {"WAKE_WORD_THRESHOLD": "1.5"}):
            with self.assertRaises(config.ConfigError):
                config.load_settings()

    def test_unknown_model_is_rejected(self):
        with mock.patch.dict(os.environ, {"WAKE_WORD_MODEL": "no_existe_xyz"}):
            with self.assertRaisesRegex(config.ConfigError, "no_existe_xyz"):
                config.load_settings()

    def test_models_are_resolved_from_project_models_dir(self):
        with mock.patch.dict(os.environ, {"WAKE_WORD_MODEL": "meeah"}):
            path = config.load_settings().model_path
        self.assertEqual(path.parent, config.MODELS_DIR)
        self.assertTrue(config.MODELS_DIR.is_dir())


if __name__ == "__main__":
    unittest.main()
