"""Optional libVLC equalizer playback engine.

Requires an independently installed VLC/libVLC and the python-vlc bindings.
No VLC binaries are bundled or downloaded. libVLC supports 10-band EQ
and exposes playback transport, volume, position and rate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from audio_equalizer import EqualizerSettings
from vlc_runtime import configure_vlc_plugins


@dataclass(frozen=True)
class VLCAvailability:
    available: bool
    reason: str


def availability() -> VLCAvailability:
    configure_vlc_plugins()
    try:
        import vlc
    except (ImportError, OSError) as exc:
        return VLCAvailability(False, f"python-vlc is not installed: {exc}")
    try:
        instance = vlc.Instance("--quiet", "--no-video-title-show")
        if instance is None:
            return VLCAvailability(False, "libVLC could not be initialized")
        player = instance.media_player_new()
        equalizer = vlc.AudioEqualizer()
        if player is None or equalizer is None:
            return VLCAvailability(False, "libVLC audio equalizer is unavailable")
        if vlc.libvlc_audio_equalizer_get_band_count() < 10:
            return VLCAvailability(False, "libVLC does not expose ten equalizer bands")
    except Exception as exc:
        return VLCAvailability(False, f"libVLC could not be initialized: {exc}")
    finally:
        try:
            player.release()
            instance.release()
        except (NameError, AttributeError):
            pass
    return VLCAvailability(True, "libVLC equalizer is available")


class VLCEqualizerEngine:
    """Actual libVLC audio DSP, not a simulation of EQ settings."""

    def __init__(self):
        configure_vlc_plugins()
        import vlc
        self.vlc = vlc
        self.instance = vlc.Instance("--quiet", "--no-video-title-show")
        if self.instance is None:
            raise RuntimeError("libVLC initialization failed")
        self.player = self.instance.media_player_new()
        if self.player is None:
            raise RuntimeError("libVLC media player initialization failed")
        self.equalizer = vlc.AudioEqualizer()
        if self.vlc.libvlc_audio_equalizer_get_band_count() < 10:
            raise RuntimeError("libVLC ten-band EQ is unavailable")

    def set_source(self, source: str) -> None:
        media = self.instance.media_new(source)
        self.player.set_media(media)
        media.release()

    def set_equalizer(self, settings: EqualizerSettings) -> None:
        settings.validate()
        if not settings.enabled:
            self.vlc.libvlc_media_player_set_equalizer(self.player, None)
            return
        # VLC provides its own frequency mapping. Map each requested frequency
        # to the nearest available band rather than assuming index alignment.
        for index in range(self.vlc.libvlc_audio_equalizer_get_band_count()):
            self.vlc.libvlc_audio_equalizer_set_amp_at_index(self.equalizer, 0.0, index)
        frequencies = (31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
        for frequency, gain in zip(frequencies, settings.gains_db):
            closest = min(
                range(self.vlc.libvlc_audio_equalizer_get_band_count()),
                key=lambda i: abs(self.vlc.libvlc_audio_equalizer_get_band_frequency(i) - frequency),
            )
            self.vlc.libvlc_audio_equalizer_set_amp_at_index(self.equalizer, float(gain), closest)
        # VLC's preamp and bands accept -20 to +20 dB; settings are -12 to +12.
        self.vlc.libvlc_audio_equalizer_set_preamp(self.equalizer, float(settings.preamp_db))
        result = self.vlc.libvlc_media_player_set_equalizer(self.player, self.equalizer)
        if result != 0:
            raise RuntimeError("libVLC rejected equalizer settings")

    def play(self) -> None:
        if self.player.play() == -1:
            raise RuntimeError("libVLC could not start playback")

    def pause(self) -> None:
        self.player.set_pause(1)

    def resume(self) -> None:
        self.player.set_pause(0)

    def stop(self) -> None:
        self.player.stop()

    def seek(self, milliseconds: int) -> None:
        self.player.set_time(max(0, int(milliseconds)))

    def set_volume(self, volume: int) -> None:
        self.player.audio_set_volume(max(0, min(100, int(volume))))

    def set_mute(self, muted: bool) -> None:
        self.player.audio_set_mute(bool(muted))

    def set_rate(self, rate: float) -> None:
        self.player.set_rate(float(rate))

    def position(self) -> int:
        return max(0, self.player.get_time())

    def duration(self) -> int:
        return max(0, self.player.get_length())

    def close(self) -> None:
        self.player.stop()
        self.player.release()
        self.instance.release()
