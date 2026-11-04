"""Playback race regressions with deterministic Qt signals, no audio device required."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtCore import QObject, QSettings, QStandardPaths, QUrl, Qt, pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import QApplication
import playTunes


class ControlledPlayer(QObject):
    positionChanged = pyqtSignal(int)
    durationChanged = pyqtSignal(int)
    playbackStateChanged = pyqtSignal(object)
    mediaStatusChanged = pyqtSignal(object)
    errorOccurred = pyqtSignal(object, str)
    sourceChanged = pyqtSignal(QUrl)

    def __init__(self):
        super().__init__()
        self.url = QUrl()
        self.status = QMediaPlayer.MediaStatus.NoMedia
        self.state = QMediaPlayer.PlaybackState.StoppedState
        self.pos = 0
        self.calls = []
        self.reentrant_seek = False

    def source(self): return self.url
    def mediaStatus(self): return self.status
    def playbackState(self): return self.state
    def position(self): return self.pos
    def duration(self): return 60_000
    def playbackRate(self): return 1.0
    def bufferProgress(self): return 1.0
    def errorString(self): return ""

    def setSource(self, url):
        self.calls.append(("source", url.toLocalFile()))
        self.url = url
        self.pos = 0
        self.sourceChanged.emit(url)
        self.set_status(QMediaPlayer.MediaStatus.LoadingMedia)

    def set_status(self, status):
        self.status = status
        self.mediaStatusChanged.emit(status)

    def play(self):
        self.calls.append(("play", self.url.toLocalFile()))
        self.state = QMediaPlayer.PlaybackState.PlayingState
        self.playbackStateChanged.emit(self.state)

    def stop(self):
        self.calls.append(("stop", self.url.toLocalFile()))
        self.state = QMediaPlayer.PlaybackState.StoppedState
        self.pos = 0
        self.playbackStateChanged.emit(self.state)

    def pause(self):
        self.state = QMediaPlayer.PlaybackState.PausedState
        self.playbackStateChanged.emit(self.state)

    def setPosition(self, position):
        self.calls.append(("seek", position))
        self.pos = position
        if self.reentrant_seek:
            self.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.LoadedMedia)
        self.positionChanged.emit(position)


class PlaybackPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QStandardPaths.setTestModeEnabled(True)
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        QSettings(playTunes.ORGANIZATION, playTunes.PROFILE_NAME).clear()
        self.temp = tempfile.TemporaryDirectory()
        self.window = playTunes.MusicPlayer()
        self.window.library_database_path = Path(self.temp.name) / "library.json"
        self.window.library_model.clear()
        self.player = ControlledPlayer()
        self.window.player = self.player
        self.window._connect_player()
        self.paths = []
        for name in ("a.wav", "b.wav"):
            path = Path(self.temp.name) / name
            path.write_bytes(b"")
            self.paths.append(str(path))
        self.window.model.add_tracks([playTunes.Track(path=p, title=Path(p).stem) for p in self.paths])

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        QSettings(playTunes.ORGANIZATION, playTunes.PROFILE_NAME).clear()
        self.temp.cleanup()

    def drain(self):
        for _ in range(3):
            self.app.processEvents()

    def ready(self):
        self.player.set_status(QMediaPlayer.MediaStatus.LoadedMedia)
        self.drain()

    def assert_started_once(self, path):
        self.assertEqual([os.path.normpath(c[1]) for c in self.player.calls if c[0] == "play"], [os.path.normpath(path)])

    def test_queue_double_click_defers_until_view_event_and_load_finish(self):
        clicked = self.window.proxy.mapFromSource(self.window.model.index(1, 0))
        self.window.table.doubleClicked.emit(clicked)
        self.assertEqual(self.player.calls, [])
        self.drain()
        self.assertEqual(os.path.normpath(self.player.source().toLocalFile()), os.path.normpath(self.paths[1]))
        self.assertFalse(any(c[0] == "play" for c in self.player.calls))
        self.ready()
        self.assert_started_once(self.paths[1])

    def test_play_button_uses_same_load_aware_path(self):
        selected = self.window.proxy.mapFromSource(self.window.model.index(1, 0))
        self.window.table.selectRow(selected.row())
        self.window.toggle_playback()
        self.drain()
        self.assertFalse(any(c[0] == "play" for c in self.player.calls))
        self.ready()
        self.assert_started_once(self.paths[1])

    def test_sorted_filtered_library_double_click_and_metadata_do_not_restart_audio(self):
        self.window.model.clear()
        self.window.library_model.add_tracks([
            playTunes.Track(path=p, title=title) for p, title in zip(self.paths, ("Zulu", "Alpha"))
        ])
        self.window.library_proxy.sort(1, Qt.SortOrder.AscendingOrder)
        self.window.library_proxy.setFilterFixedString("Alpha")
        with patch.object(self.window, "_start_metadata_scan") as scan:
            self.window.library_table.doubleClicked.emit(self.window.library_proxy.index(0, 1))
            scan.assert_called_once_with(self.paths[1])
        self.drain()
        self.ready()
        before = list(self.player.calls)
        self.window.metadata_loaded(playTunes.MetadataResult(path=self.paths[1], title="Updated"))
        self.assertEqual(self.player.calls, before)
        self.assert_started_once(self.paths[1])
        self.assertEqual(self.window.model.tracks[0].title, "Updated")

    def test_rapid_activations_start_only_last_request(self):
        self.window.play_index(0)
        self.window.play_index(1)
        self.drain()
        self.ready()
        self.assert_started_once(self.paths[1])
        self.assertFalse(any(c[0] == "source" and os.path.normpath(c[1]) == os.path.normpath(self.paths[0]) for c in self.player.calls))

    def test_switch_during_loading_does_not_start_old_track(self):
        self.window.play_index(0)
        self.drain()
        self.window.play_index(1)
        self.player.set_status(QMediaPlayer.MediaStatus.LoadedMedia)
        self.drain()
        self.assertFalse(any(c[0] == "play" for c in self.player.calls))
        self.ready()
        self.assert_started_once(self.paths[1])

    def test_stop_cancels_late_load_completion(self):
        self.window.play_index(0)
        self.drain()
        self.window.stop_playback()
        self.ready()
        self.assertIsNone(self.window.requested_source)
        self.assertFalse(any(c[0] == "play" for c in self.player.calls))

    def test_clear_queue_cancels_deferred_activation(self):
        self.window.play_index(0)
        self.window.clear_queue(force=True)
        self.drain()
        self.assertIsNone(self.window.requested_source)
        self.assertFalse(any(c[0] == "play" for c in self.player.calls))

    def test_restored_seek_is_consumed_once_even_with_reentrant_status(self):
        self.window.resume_path = self.paths[0]
        self.window.pending_seek = 12_345
        self.player.reentrant_seek = True
        self.window.play_index(0)
        self.window.play_index(0)
        self.drain()
        self.ready()
        self.assertEqual([c for c in self.player.calls if c[0] == "seek"], [("seek", 12_345)])
        self.assertEqual(self.window.pending_seek, 0)
        self.assert_started_once(self.paths[0])

    def test_different_track_discards_saved_seek(self):
        self.window.resume_path = self.paths[0]
        self.window.pending_seek = 12_345
        self.window.play_index(1)
        self.drain()
        self.ready()
        self.assertFalse(any(c[0] == "seek" for c in self.player.calls))

    def test_same_source_activation_does_not_reload_decoder(self):
        self.window.play_index(0)
        self.drain()
        self.ready()
        self.player.calls.clear()
        self.window.play_index(0)
        self.drain()
        self.assert_started_once(self.paths[0])
        self.assertFalse(any(c[0] in ("source", "stop") for c in self.player.calls))

    def test_stalled_backend_cannot_advance_display_indefinitely(self):
        self.player.state = QMediaPlayer.PlaybackState.PlayingState
        self.player.status = QMediaPlayer.MediaStatus.BufferedMedia
        self.window.position_anchor = 1_000
        self.window.position_clock = Mock()
        self.window.position_clock.isValid.return_value = True
        self.window.position_clock.elapsed.return_value = 60_000
        self.assertEqual(self.window._estimated_position(), 1_500)
        self.player.status = QMediaPlayer.MediaStatus.StalledMedia
        self.assertEqual(self.window._estimated_position(), 1_000)
        self.window._position_changed(1_000)
        self.window.position_clock.restart.assert_not_called()


if __name__ == "__main__":
    unittest.main()
