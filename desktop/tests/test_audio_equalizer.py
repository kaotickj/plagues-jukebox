import unittest

from audio_equalizer import (
    BANDS, PRESETS, EqualizerSettings, coefficients,
    peaking_biquad, recommended_headroom_db,
)


class EqualizerTests(unittest.TestCase):
    def test_ten_bands_and_presets(self):
        self.assertEqual(len(BANDS), 10)
        self.assertTrue(all(len(gains) == 10 for gains in PRESETS.values()))

    def test_round_trip(self):
        original = EqualizerSettings(True, -3.0, list(PRESETS["Blues"]))
        self.assertEqual(EqualizerSettings.from_dict(original.to_dict()), original)

    def test_invalid_gain_rejected(self):
        with self.assertRaises(ValueError):
            EqualizerSettings(True, 0, [30] * 10).validate()

    def test_flat_biquad_is_identity(self):
        self.assertEqual(peaking_biquad(1000, 0, 44100),
                         (1, 0, 0, 0, 0))

    def test_above_nyquist_is_identity(self):
        self.assertEqual(peaking_biquad(16000, 6, 22050),
                         (1, 0, 0, 0, 0))

    def test_bypass_and_headroom(self):
        eq = EqualizerSettings(False, 2, list(PRESETS["Bass Boost"]))
        self.assertEqual(coefficients(eq, 44100), [])
        self.assertEqual(recommended_headroom_db(eq), 8)
        eq.enabled = True
        self.assertEqual(len(coefficients(eq, 44100)), 10)


if __name__ == "__main__":
    unittest.main()
