import unittest

from wake_word.microphone import clean_device_name, match_device_index

DEVICES = [
    (1, "SteelSeries Sonar - Microphone "),
    (3, "Micrófono (4- Arctis Nova 7)"),
    (4, "Micrófono (USB Audio Device)"),
    (19, "Micrófono (4- Arctis Nova 7)"),
]


class MatchDeviceIndexTests(unittest.TestCase):
    def test_matches_a_fragment_of_the_name(self):
        self.assertEqual(match_device_index("Arctis", DEVICES), 3)

    def test_ignores_case_and_accents(self):
        self.assertEqual(match_device_index("MICROFONO (usb", DEVICES), 4)

    def test_first_match_wins_when_name_is_duplicated(self):
        # Mismo dispositivo expuesto por MME (3) y DirectSound (19)
        self.assertEqual(match_device_index("Arctis Nova 7", DEVICES), 3)

    def test_returns_none_without_a_match(self):
        self.assertIsNone(match_device_index("No Existe", DEVICES))

    def test_blank_query_matches_nothing(self):
        self.assertIsNone(match_device_index("   ", DEVICES))

    def test_full_unity_name_matches_a_name_truncated_by_mme(self):
        # MME recorta a 31 caracteres; Unity muestra el nombre completo.
        truncated = "Micrófono (Steam Streaming Micr"
        self.assertEqual(len(truncated), 31)
        full_name = "Micrófono (Steam Streaming Microphone)"
        self.assertEqual(match_device_index(full_name, [(2, truncated)]), 2)

    def test_pyaudio_mojibake_names_match_the_correct_text(self):
        # PyAudio entrega "Micrófono" como "MicrÃ³fono" en Windows
        broken = [(3, "MicrÃ³fono (4- Arctis Nova 7)")]
        self.assertEqual(match_device_index("Micrófono (4- Arctis Nova 7)", broken), 3)

    def test_clean_device_name_repairs_mojibake_and_keeps_ascii(self):
        self.assertEqual(clean_device_name("MicrÃ³fono (USB)"), "Micrófono (USB)")
        self.assertEqual(clean_device_name("Micrófono (USB)"), "Micrófono (USB)")
        self.assertEqual(clean_device_name("SteelSeries Sonar"), "SteelSeries Sonar")

    def test_short_names_are_not_treated_as_truncated(self):
        # Un nombre corto que no contiene la consulta no debe coincidir
        self.assertIsNone(match_device_index("Micrófono (USB Audio Device) 2", DEVICES))


if __name__ == "__main__":
    unittest.main()
