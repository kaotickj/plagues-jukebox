import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import metadata_lookup


class MetadataLookupTests(unittest.TestCase):
    def test_filename_guess_handles_artist_separator(self):
        title, artist = metadata_lookup._filename_guess("03 - Artist - Song_Title.flac")
        self.assertEqual(title, "Song Title")
        self.assertEqual(artist, "Artist")

    def test_release_choice_prefers_matching_album_and_official_status(self):
        releases = [
            {"id": "bootleg", "title": "The Album", "status": "Bootleg", "date": "1990"},
            {"id": "other", "title": "Other", "status": "Official", "date": "1980"},
            {"id": "wanted", "title": "The Album", "status": "Official", "date": "2000"},
        ]
        self.assertEqual(metadata_lookup._choose_release(releases, "The Album")["id"], "wanted")

    def test_cached_cover_is_size_limited(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            cover = cache / "cover-release-release-id.img"
            cover.write_bytes(b"image-data")
            self.assertEqual(
                metadata_lookup.load_cached_cover(cache, "release-id", ""), b"image-data"
            )

    def test_text_search_builds_normalized_result(self):
        recording = {
            "title": "Found Song",
            "artist-credit": [{"name": "Found Artist"}],
            "genres": [{"name": "Blues", "count": 4}],
            "releases": [
                {
                    "id": "release-id",
                    "title": "Found Album",
                    "status": "Official",
                    "date": "2024-01-01",
                    "release-group": {"id": "group-id"},
                }
            ],
        }
        release = {
            "title": "Found Album",
            "date": "2024-01-01",
            "artist-credit": [{"name": "Found Artist"}],
            "release-group": {"id": "group-id"},
            "media": [
                {
                    "position": 1,
                    "tracks": [
                        {
                            "number": "7",
                            "recording": {"id": "recording-id"},
                        }
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory, patch.object(
            metadata_lookup, "_load_cache", return_value=None
        ), patch.object(
            metadata_lookup, "locate_fpcalc", return_value=""
        ), patch.object(
            metadata_lookup, "_musicbrainz_search", return_value=("recording-id", 98.0)
        ), patch.object(
            metadata_lookup, "_recording_lookup", return_value=recording
        ), patch.object(
            metadata_lookup, "_release_lookup", return_value=release
        ), patch.object(
            metadata_lookup, "_download_cover", return_value=(b"cover", "Cover Art Archive")
        ), patch.object(metadata_lookup, "_save_cache"):
            result = metadata_lookup.lookup_online_metadata(
                "Artist - Song.wav",
                {"title": "Song", "artist": "Artist", "duration_ms": 180000},
                "",
                directory,
            )
        self.assertEqual(result.title, "Found Song")
        self.assertEqual(result.artist, "Found Artist")
        self.assertEqual(result.album, "Found Album")
        self.assertEqual(result.track_number, "7")
        self.assertEqual(result.disc_number, "1")
        self.assertEqual(result.recording_id, "recording-id")
        self.assertEqual(result.cover_data, b"cover")
        self.assertEqual(result.confidence, 98.0)


if __name__ == "__main__":
    unittest.main()
