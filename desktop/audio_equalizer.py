"""Portable equalizer configuration and DSP coefficients.

This module is backend-independent. No network access or proprietary components.
SciPy (BSD-3-Clause) is required only to design the digital filters.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import pi, sin, cos, sqrt
from typing import Sequence

BANDS = (31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
PRESETS = {
    "Flat": (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    "Blues": (2, 2, 1, 0, -1, 0, 1, 2, 1, 0),
    "Rock": (4, 3, 2, 0, -2, -1, 1, 3, 4, 3),
    "Metal": (4, 3, 1, -2, -3, -1, 2, 4, 4, 2),
    "Jazz": (2, 1, 0, 1, 2, 2, 1, 1, 2, 2),
    "Classical": (2, 1, 0, 0, 0, 0, 1, 2, 3, 3),
    "Vocal": (-2, -1, 0, 2, 3, 3, 2, 0, -1, -2),
    "Bass Boost": (6, 5, 4, 2, 0, 0, 0, 0, 0, 0),
}

@dataclass
class EqualizerSettings:
    enabled: bool = False
    preamp_db: float = 0.0
    gains_db: list[float] = field(default_factory=lambda: [0.0] * 10)

    def validate(self) -> None:
        if len(self.gains_db) != len(BANDS):
            raise ValueError("Equalizer must have ten bands")
        if not -12 <= self.preamp_db <= 12:
            raise ValueError("Preamp must be between -12 and 12 dB")
        if any(not -12 <= gain <= 12 for gain in self.gains_db):
            raise ValueError("Band gains must be between -12 and 12 dB")

    def to_dict(self) -> dict:
        self.validate()
        return {"enabled": self.enabled, "preamp_db": self.preamp_db,
                "gains_db": list(self.gains_db)}

    @classmethod
    def from_dict(cls, data: dict) -> "EqualizerSettings":
        result = cls(bool(data.get("enabled", False)),
                     float(data.get("preamp_db", 0)),
                     [float(x) for x in data.get("gains_db", [0] * 10)])
        result.validate()
        return result


def peaking_biquad(frequency: float, gain_db: float, sample_rate: int,
                   q: float = 1.41421356237) -> tuple[float, ...]:
    """RBJ peaking EQ coefficients (b0,b1,b2,a1,a2), normalized by a0.

    Filters above Nyquist are disabled rather than generating unstable coefficients.
    """
    if sample_rate <= 0:
        raise ValueError("Invalid sample rate")
    if frequency >= sample_rate / 2 or gain_db == 0:
        return (1.0, 0.0, 0.0, 0.0, 0.0)
    a = 10 ** (gain_db / 40)
    w = 2 * pi * frequency / sample_rate
    alpha = sin(w) / (2 * q)
    b0, b1, b2 = 1 + alpha * a, -2 * cos(w), 1 - alpha * a
    a0, a1, a2 = 1 + alpha / a, -2 * cos(w), 1 - alpha / a
    return (b0/a0, b1/a0, b2/a0, a1/a0, a2/a0)


def coefficients(settings: EqualizerSettings, sample_rate: int) -> list[tuple[float, ...]]:
    settings.validate()
    if not settings.enabled:
        return []
    return [peaking_biquad(freq, gain, sample_rate)
            for freq, gain in zip(BANDS, settings.gains_db)]


def recommended_headroom_db(settings: EqualizerSettings) -> float:
    """Conservative attenuation estimate for boosted EQ bands.

    Actual peak limiting belongs to the playback DSP engine.
    """
    settings.validate()
    return max(0.0, settings.preamp_db + max(settings.gains_db, default=0.0))
