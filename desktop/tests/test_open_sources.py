"""File-manager opens use the same deferred playback path as the UI."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings, QStandardPaths
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import QApplication

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import playTunes
from test_playback_paths import ControlledPlayer


class OpenSourcesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QStandardPaths.setTestModeEnabled(True)
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        QSettings(playTunes.ORGANIZATION, playTunes.PROFILE_NAME).clear()
        self.temp = tempfile.TemporaryDirectory()
        # Windows temporary paths may use 8.3 aliases, and macOS /var is a
        # symlink. Match the resolved paths stored by playlist imports.
        self.root = Path(self.temp.name).resolve()
        self.scan = patch.object(playTunes.MusicPlayer, "_start_metadata_scan")
        self.scan.start()
        self.window = playTunes.MusicPlayer()
        self.window.library_database_path = self.root / "library.json"
        self.window.library_model.clear()
        self.window.model.clear()
        self.player = ControlledPlayer()
        self.window.player = self.player
        self.window._connect_player()
        self.warning = patch.object(playTunes.QMessageBox, "warning")
        self.warnings = self.warning.start()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.warning.stop()
        self.scan.stop()
        QSettings(playTunes.ORGANIZATION, playTunes.PROFILE_NAME).clear()
        self.temp.cleanup()

    def media(self, name):
        path = self.root / name
        path.write_bytes(b"")
        return str(path.resolve())

    def assert_media_path(self, actual, expected):
        # QUrl uses forward slashes on Windows; file identity is the contract.
        self.assertEqual(Path(actual).resolve(), Path(expected).resolve())

    def start_requested(self):
        for _ in range(3):
            self.app.processEvents()
        self.player.set_status(QMediaPlayer.MediaStatus.LoadedMedia)
        for _ in range(3):
            self.app.processEvents()

    def test_multiple_audio_video_files_preserve_request_order_and_start_first(self):
        paths = [self.media("Zulu 音楽.mp4"), self.media("Alpha song.flac")]
        self.window.open_sources(paths)
        self.assertEqual([t.path for t in self.window.model.tracks], paths)
        self.assertEqual(self.player.calls, [])
        self.start_requested()
        started = [c[1] for c in self.player.calls if c[0] == "play"]
        self.assertEqual(len(started), 1)
        self.assert_media_path(started[0], paths[0])
        self.warnings.assert_not_called()

    def test_reopening_existing_track_preserves_queue_and_restarts_selected_file(self):
        old, selected = self.media("old.wav"), self.media("selected.wav")
        self.window.model.add_tracks([playTunes.Track(path=old), playTunes.Track(path=selected)])
        self.window.play_index(1)
        self.start_requested()
        self.player.setPosition(22_000)
        self.player.calls.clear()
        self.window.pending_seek = 12_345
        self.window.resume_path = selected
        self.window.search_box.setText("hidden by filter")
        self.window.open_sources([selected])
        self.start_requested()
        self.assertEqual(len(self.window.model.tracks), 2)
        self.assertEqual(self.window.search_box.text(), "")
        self.assertEqual(self.window.pending_seek, 0)
        self.assertEqual(self.player.pos, 0)
        self.assertEqual([c for c in self.player.calls if c[0] == "seek"], [("seek", 0)])

    def test_m3u_uses_relative_entries_and_extinf_and_skips_missing_first_track(self):
        song = self.media("song with spaces.wav")
        playlist = self.root / "mix.m3u8"
        playlist.write_text("#EXTM3U\nmissing.wav\n#EXTINF:42,My song\nsong with spaces.wav\n", encoding="utf-8")
        self.window.open_sources([str(playlist)])
        self.assertEqual(self.window.model.tracks[0].path, song)
        self.assertEqual(self.window.model.tracks[0].title, "My song")
        self.assertEqual(self.window.model.tracks[0].duration_ms, 42_000)
        self.start_requested()
        self.assert_media_path(self.player.source().toLocalFile(), song)

    def test_hls_manifest_stays_a_single_stream(self):
        playlist = self.root / "live.m3u8"
        playlist.write_text("#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXTINF:6,\nsegment.ts\n", encoding="utf-8")
        self.window.open_sources([str(playlist)])
        self.assertEqual([t.path for t in self.window.model.tracks], [str(playlist)])
        self.assertEqual(self.window.model.tracks[0].codec, "HLS stream")

    def test_explicit_json_playlist_is_supported_without_generic_json_association(self):
        song = self.media("song.mp3")
        playlist = self.root / "mix.json"
        playlist.write_text('{"playlist":[{"path":"song.mp3","title":"Saved title"}]}', encoding="utf-8")
        self.window.open_sources([str(playlist)])
        self.assertEqual(self.window.model.tracks[0].path, song)
        self.assertEqual(self.window.model.tracks[0].title, "Saved title")

    def test_bad_playlist_does_not_erase_existing_queue_and_other_files_still_open(self):
        old, song = self.media("old.wav"), self.media("new.wav")
        self.window.model.add_tracks([playTunes.Track(path=old)])
        playlist = self.root / "broken.json"
        playlist.write_text("{invalid", encoding="utf-8")
        self.window.open_sources([str(playlist), song])
        self.assertEqual([t.path for t in self.window.model.tracks], [old, song])
        self.assertEqual(self.window.current_index, 1)
        self.warnings.assert_called_once()

    def test_missing_and_unsupported_files_do_not_start_unrelated_restored_track(self):
        old = self.media("old.wav")
        self.window.model.add_tracks([playTunes.Track(path=old)])
        unsupported = self.media("notes.txt")
        self.window.open_sources([str(self.root / "missing.mp3"), unsupported])
        self.assertIsNone(self.window.requested_source)
        self.assertEqual(self.player.calls, [])
        self.assertEqual(len(self.window.model.tracks), 1)
        self.warnings.assert_called_once()

    def test_empty_request_only_activates_existing_window(self):
        self.window.open_sources([])
        self.assertEqual(self.player.calls, [])
        self.warnings.assert_not_called()

    def test_missing_duplicate_does_not_block_later_available_playlist_entry(self):
        missing = str(self.root / "missing.wav")
        song = self.media("available.wav")
        self.window.model.add_tracks([playTunes.Track(path=missing)])
        playlist = self.root / "mix.m3u"
        playlist.write_text("missing.wav\navailable.wav\n", encoding="utf-8")
        self.window.open_sources([str(playlist)])
        self.start_requested()
        self.assert_media_path(self.player.source().toLocalFile(), song)
        self.warnings.assert_not_called()

    def test_overflowing_playlist_durations_are_treated_as_unknown(self):
        self.media("song.wav")
        for name, content in (
            ("mix.m3u", "#EXTM3U\n#EXTINF:1e309,Song\nsong.wav\n"),
            ("mix.json", '{"playlist":[{"path":"song.wav","duration_ms":1e309}]}'),
        ):
            with self.subTest(name=name):
                playlist = self.root / name
                playlist.write_text(content, encoding="utf-8")
                entries = playTunes.read_playlist_entries(str(playlist))
                self.assertEqual(entries[0].duration_ms, 0)

    def test_launch_normalization_resolves_sender_paths_and_decodes_local_uris(self):
        song = self.media("Björk space.wav")
        with patch("os.getcwd", return_value=str(self.root)):
            sources = playTunes.normalize_open_sources(["--", "relative song.mp3", Path(song).as_uri(), "https://example.com/live.m3u8"])
        self.assertEqual(sources, [str(self.root / "relative song.mp3"), song, "https://example.com/live.m3u8"])


if __name__ == "__main__":
    unittest.main()
