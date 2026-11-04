import base64
import tempfile
import unittest
import wave
from pathlib import Path

from mutagen.id3 import APIC, COMM, TALB, TCON, TDRC, TIT2, TPE1, TPOS, TRCK
from mutagen.wave import WAVE

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import playTunes


ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "/x8AAusB9Wl2n2kAAAAASUVORK5CYII="
)


class MediaIntegrationTests(unittest.TestCase):
    def test_tagged_96khz_wave_exposes_tags_technical_info_and_artwork(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tagged-96khz.wav"
            with wave.open(str(path), "wb") as audio:
                audio.setnchannels(2)
                audio.setsampwidth(2)
                audio.setframerate(96_000)
                audio.writeframes(b"\0\0" * 2 * 9_600)

            tagged = WAVE(path)
            tagged.add_tags()
            tagged.tags.add(TIT2(encoding=3, text="Integration Song"))
            tagged.tags.add(TPE1(encoding=3, text="Integration Artist"))
            tagged.tags.add(TALB(encoding=3, text="Integration Album"))
            tagged.tags.add(TCON(encoding=3, text="Blues"))
            tagged.tags.add(TDRC(encoding=3, text="2026"))
            tagged.tags.add(TRCK(encoding=3, text="4/12"))
            tagged.tags.add(TPOS(encoding=3, text="1/2"))
            tagged.tags.add(COMM(encoding=3, lang="eng", desc="", text="Test comment"))
            tagged.tags.add(
                APIC(
                    encoding=3,
                    mime="image/png",
                    type=3,
                    desc="Front cover",
                    data=ONE_PIXEL_PNG,
                )
            )
            tagged.save()

            result = playTunes.scan_metadata(str(path))

            self.assertEqual(result.error, "")
            self.assertEqual(result.title, "Integration Song")
            self.assertEqual(result.artist, "Integration Artist")
            self.assertEqual(result.album, "Integration Album")
            self.assertEqual(result.genre, "Blues")
            self.assertEqual(result.year, "2026")
            self.assertEqual(result.track_number, "4/12")
            self.assertEqual(result.disc_number, "1/2")
            self.assertEqual(result.comment, "Test comment")
            self.assertEqual(result.sample_rate, 96_000)
            self.assertEqual(result.channels, 2)
            self.assertEqual(result.bits_per_sample, 16)
            self.assertGreater(result.duration_ms, 0)
            self.assertGreater(result.file_size, 0)
            self.assertEqual(result.cover_data, ONE_PIXEL_PNG)
            self.assertEqual(result.artwork_source, "Embedded ID3 APIC")

    def test_utf8_m3u8_resolves_relative_entries_and_extinf(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            music = root / "Música"
            music.mkdir()
            song = music / "canción.mp3"
            song.write_bytes(b"")
            playlist = root / "favorites.m3u8"
            playlist.write_text(
                "#EXTM3U\n#EXTINF:123,Artista – Canción\nMúsica/canción.mp3\n",
                encoding="utf-8",
            )

            entries, is_hls = playTunes.parse_m3u_playlist(str(playlist))

            self.assertFalse(is_hls)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].source, str(song.resolve()))
            self.assertEqual(entries[0].title, "Artista – Canción")
            self.assertEqual(entries[0].duration_ms, 123_000)


if __name__ == "__main__":
    unittest.main()
