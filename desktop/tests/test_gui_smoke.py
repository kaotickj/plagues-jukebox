import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEventLoop, QSettings, QStandardPaths, QTimer
from PyQt6.QtWidgets import QApplication

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import playTunes
from metadata_lookup import OnlineMetadataResult


class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QStandardPaths.setTestModeEnabled(True)
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        QSettings(playTunes.ORGANIZATION, playTunes.PROFILE_NAME).clear()

    def tearDown(self):
        QSettings(playTunes.ORGANIZATION, playTunes.PROFILE_NAME).clear()
        self.app.processEvents()

    def test_main_window_starts_with_expected_models_and_timers(self):
        window = playTunes.MusicPlayer()
        self.app.processEvents()
        try:
            self.assertEqual(window.windowTitle(), "Plague’s Jukebox")
            self.assertEqual(window.content_tabs.count(), 2)
            self.assertIs(window.table.model(), window.proxy)
            self.assertIs(window.library_table.model(), window.library_proxy)
            self.assertTrue(window.progress_timer.isActive())
        finally:
            window.close()

    def test_library_scan_worker_discovers_supported_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "nested"
            nested.mkdir()
            (root / "song.mp3").write_bytes(b"")
            (nested / "song.flac").write_bytes(b"")
            (nested / "notes.txt").write_text("not audio", encoding="utf-8")

            completed = []
            worker = playTunes.LibraryScanWorker([str(root)])
            worker.signals.completed.connect(completed.append)
            worker.run()

            self.assertEqual(len(completed), 1)
            result = completed[0]
            self.assertEqual(result["errors"], [])
            self.assertEqual(result["missing_roots"], [])
            self.assertEqual(
                {Path(path).name for path in result["paths"]},
                {"song.mp3", "song.flac"},
            )

    def test_window_completes_async_library_scan_and_metadata_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            song = root / "library-96khz.wav"
            with wave.open(str(song), "wb") as audio:
                audio.setnchannels(2)
                audio.setsampwidth(2)
                audio.setframerate(96_000)
                audio.writeframes(b"\0\0" * 2 * 9_600)

            window = playTunes.MusicPlayer()
            window.library_database_path = root / "library.json"
            window.library_roots = [str(root)]
            loop = QEventLoop()
            poll = QTimer()
            poll.setInterval(10)

            def finish_when_idle():
                if (
                    window.library_scan_worker is None
                    and not window.metadata_workers
                    and not window.metadata_queue
                ):
                    loop.quit()

            poll.timeout.connect(finish_when_idle)
            poll.start()
            QTimer.singleShot(5_000, loop.quit)
            window.scan_library()
            loop.exec()
            poll.stop()

            try:
                self.assertIsNone(window.library_scan_worker)
                self.assertFalse(window.metadata_workers)
                self.assertEqual(len(window.library_model.tracks), 1)
                self.assertEqual(window.library_model.tracks[0].sample_rate, 96_000)
                self.assertEqual(window.library_model.tracks[0].channels, 2)
            finally:
                window.close()

    def test_online_metadata_preserves_existing_tags_by_default(self):
        model = playTunes.PlaylistModel()
        model.add_tracks(
            [playTunes.Track(path="example.mp3", title="Local Title", artist="")]
        )
        result = OnlineMetadataResult(
            path="example.mp3",
            title="Online Title",
            artist="Online Artist",
            album="Online Album",
            source="MusicBrainz",
            confidence=96.0,
        )

        row = model.apply_online_metadata(result)

        self.assertEqual(row, 0)
        self.assertEqual(model.tracks[0].title, "Local Title")
        self.assertEqual(model.tracks[0].artist, "Online Artist")
        self.assertEqual(model.tracks[0].album, "Online Album")
        self.assertEqual(model.tracks[0].metadata_source, "MusicBrainz")

    def test_online_lookup_worker_converts_exception_to_result(self):
        worker = playTunes.OnlineLookupWorker(
            playTunes.Track(path="bad.wav"), "", Path(tempfile.gettempdir())
        )
        completed = []
        worker.signals.result.connect(completed.append)

        with patch.object(playTunes, "lookup_online_metadata", side_effect=RuntimeError("boom")):
            worker.run()

        self.assertEqual(len(completed), 1)
        self.assertIn("Unexpected lookup error", completed[0].error)


if __name__ == "__main__":
    unittest.main()
