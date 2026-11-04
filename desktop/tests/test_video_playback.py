"""Video-output and transport regressions without a native audio device."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtCore import QSettings, QStandardPaths, Qt, QUrl
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtTest import QTest

import playTunes
import vlc_player_adapter


class UnifiedVideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QStandardPaths.setTestModeEnabled(True)
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        QSettings(playTunes.ORGANIZATION, playTunes.PROFILE_NAME).clear()
        self.temp = tempfile.TemporaryDirectory()
        self.window = playTunes.MusicPlayer()
        self.window.library_database_path = Path(self.temp.name) / "library.json"
        self.window.show()
        self.window.activateWindow()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        QSettings(playTunes.ORGANIZATION, playTunes.PROFILE_NAME).clear()
        self.temp.cleanup()

    def test_qt_video_surface_belongs_to_the_main_window(self):
        panel = self.window.video_panel
        self.assertIsInstance(panel.surface, QVideoWidget)
        self.assertIs(self.window.player.videoOutput(), panel.surface)
        self.assertIs(panel.window(), self.window)
        self.assertIs(panel.surface.window(), self.window)
        self.assertFalse(panel.isWindow())
        self.assertTrue(panel.isHidden())
        self.assertFalse(self.window.video_button.isEnabled())

    def test_video_and_audio_switch_inside_the_existing_gui(self):
        self.window._video_available_changed(True)
        self.app.processEvents()
        self.assertTrue(self.window.video_panel.isVisible())
        self.assertTrue(self.window.content_tabs.isVisible())
        self.assertTrue(self.window.now_card.isVisible())
        self.assertTrue(self.window.transport_card.isVisible())
        self.assertIs(self.window.video_panel.surface.window(), self.window)
        with patch.object(self.window.player, "stop") as stop:
            self.window._video_available_changed(False)
            stop.assert_not_called()
        self.assertTrue(self.window.video_panel.isHidden())
        self.assertTrue(self.window.content_tabs.isVisible())
        self.assertTrue(self.window.art_label.isVisible())

    def test_fullscreen_and_escape_reuse_surface_and_restore_layout(self):
        self.window._video_available_changed(True)
        self.app.processEvents()
        surface = self.window.video_panel.surface
        self.window.video_button.click()
        self.app.processEvents()
        self.assertTrue(self.window.isFullScreen())
        self.assertTrue(self.window.video_panel.isVisible())
        self.assertFalse(self.window.content_tabs.isVisible())
        self.assertFalse(self.window.now_card.isVisible())
        self.assertTrue(self.window.transport_card.isVisible())
        self.assertIs(self.window.player.videoOutput(), surface)
        self.assertIs(surface.window(), self.window)
        QTest.keyClick(self.window, Qt.Key.Key_Escape)
        self.app.processEvents()
        self.assertFalse(self.window.isFullScreen())
        self.assertTrue(self.window.content_tabs.isVisible())
        self.assertTrue(self.window.now_card.isVisible())
        self.assertTrue(self.window.top_toolbar.isVisible())
        self.assertTrue(self.window.video_panel.isVisible())
        self.assertIs(self.window.player.videoOutput(), surface)

    def test_audio_switch_leaves_video_fullscreen_and_restores_queue(self):
        self.window._video_available_changed(True)
        self.window.toggle_fullscreen()
        self.window._video_available_changed(False)
        self.app.processEvents()
        self.assertFalse(self.window.isFullScreen())
        self.assertFalse(self.window.video_panel.isVisible())
        self.assertTrue(self.window.content_tabs.isVisible())
        self.assertTrue(self.window.now_card.isVisible())
        self.assertFalse(self.window.escape_fullscreen.isEnabled())

    def test_fullscreen_restores_maximized_window_and_selected_tab(self):
        self.window.showMaximized()
        self.window.content_tabs.setCurrentIndex(1)
        self.window._video_available_changed(True)
        self.app.processEvents()
        self.window.toggle_fullscreen()
        self.window._leave_fullscreen()
        self.app.processEvents()
        self.assertTrue(self.window.isMaximized())
        self.assertEqual(self.window.content_tabs.currentIndex(), 1)

    def test_window_manager_fullscreen_exit_restores_controls(self):
        self.window._video_available_changed(True)
        self.window.toggle_fullscreen()
        self.window.setWindowState(Qt.WindowState.WindowNoState)
        self.app.processEvents()
        self.assertTrue(self.window.now_card.isVisible())
        self.assertTrue(self.window.content_tabs.isVisible())
        self.assertFalse(self.window.escape_fullscreen.isEnabled())
        self.assertEqual(self.window.video_button.text(), "Full screen")

    def test_audio_only_fullscreen_keeps_library_and_controls(self):
        self.window.toggle_fullscreen()
        self.assertTrue(self.window.isFullScreen())
        self.assertTrue(self.window.content_tabs.isVisible())
        self.assertTrue(self.window.transport_card.isVisible())
        self.window._leave_fullscreen()
        self.assertFalse(self.window.isFullScreen())

    def test_video_divider_size_survives_audio_and_fullscreen(self):
        self.window._video_available_changed(True)
        self.app.processEvents()
        self.window.media_splitter.setSizes([220, 330])
        sizes = self.window.media_splitter.sizes()
        self.window.toggle_fullscreen()
        self.window._leave_fullscreen()
        self.app.processEvents()
        self.assertLess(abs(self.window.media_splitter.sizes()[0] - sizes[0]), 12)
        self.window._video_available_changed(False)
        self.window._video_available_changed(True)
        self.app.processEvents()
        self.assertLess(abs(self.window.media_splitter.sizes()[0] - sizes[0]), 12)

    def test_source_change_preserves_video_detected_synchronously_by_backend(self):
        with patch.object(self.window.player, "hasVideo", return_value=True):
            self.window.player.sourceChanged.emit(QUrl.fromLocalFile("/tmp/movie.mp4"))
        self.assertTrue(self.window.video_button.isEnabled())
        self.assertTrue(self.window.video_panel.isVisible())
        with patch.object(self.window.player, "hasVideo", return_value=False):
            self.window.player.sourceChanged.emit(QUrl.fromLocalFile("/tmp/music.wav"))
        self.assertFalse(self.window.video_button.isEnabled())
        self.assertFalse(self.window.video_panel.isVisible())

    def test_video_uses_the_main_transport_seek_and_progress(self):
        self.window._video_available_changed(True)
        self.window._duration_changed(60_000)
        self.window._seek_started()
        self.window.position_slider.setValue(12_345)
        with patch.object(self.window.player, "setPosition") as seek:
            self.window._seek_finished()
            seek.assert_called_once_with(12_345)
        self.assertEqual(self.window.position_slider.value(), 12_345)
        self.assertEqual(self.window.elapsed_label.text(), "0:12")
        self.assertEqual(self.window.duration_label.text(), "1:00")

    def test_video_files_are_discovered_alongside_audio(self):
        root = Path(self.temp.name)
        for extension in playTunes.VIDEO_EXTENSIONS | {".mp3", ".flac"}:
            (root / f"clip{extension}").write_bytes(b"")
        (root / "notes.txt").write_text("Not media", encoding="utf-8")
        found = self.window._expand_paths([str(root)])
        self.assertEqual(
            {Path(path).suffix for path in found},
            playTunes.VIDEO_EXTENSIONS | {".mp3", ".flac"},
        )


class VLCVideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.engine = Mock()
        self.engine.duration.return_value = 60_000
        self.engine.position.return_value = 500
        self.engine.vlc = SimpleNamespace(State=SimpleNamespace(
            Playing="playing", Paused="paused", Error="error", Ended="ended",
        ))
        self.engine.player.get_media.return_value = None
        self.engine.player.get_state.return_value = "playing"
        self.engine.player.has_vout.return_value = 1
        self.factory = patch.object(vlc_player_adapter, "VLCEqualizerEngine", return_value=self.engine)
        self.factory.start()
        self.adapter = vlc_player_adapter.VLCPlayerAdapter()
        self.adapter.timer.stop()

    def tearDown(self):
        self.adapter.close()
        self.adapter.deleteLater()
        self.app.processEvents()
        self.factory.stop()

    def test_native_video_surface_binds_windows_and_linux_handles(self):
        surface = QWidget()
        for platform, method in (("win32", "set_hwnd"), ("linux", "set_xwindow")):
            with self.subTest(platform=platform), patch.object(vlc_player_adapter.sys, "platform", platform):
                self.adapter.setVideoOutput(surface)
                getattr(self.engine.player, method).assert_called_once_with(int(surface.winId()))
        self.engine.player.video_set_mouse_input.assert_called_with(False)
        self.engine.player.video_set_key_input.assert_called_with(False)
        self.adapter.setVideoOutput(None)

    def test_video_detection_and_new_audio_source_reset(self):
        detected = []
        self.adapter.hasVideoChanged.connect(detected.append)
        self.adapter.setSource(QUrl.fromLocalFile("/tmp/clip.mp4"))
        self.adapter._poll()
        self.assertTrue(self.adapter.hasVideo())
        self.adapter.setSource(QUrl.fromLocalFile("/tmp/song.mp3"))
        self.engine.player.has_vout.return_value = 0
        self.adapter._poll()
        self.assertFalse(self.adapter.hasVideo())
        self.assertEqual(detected, [True, False])

    def test_destroying_native_surface_does_not_recreate_its_handle(self):
        method = {"win32": "set_hwnd", "darwin": "set_nsobject"}.get(sys.platform, "set_xwindow")
        bind_handle = getattr(self.engine.player, method)
        surface = QWidget()
        self.adapter.setVideoOutput(surface)
        self.assertTrue(surface.testAttribute(Qt.WidgetAttribute.WA_WState_Created))
        bind_handle.reset_mock()
        surface.destroy()
        self.app.processEvents()
        self.assertFalse(surface.testAttribute(Qt.WidgetAttribute.WA_WState_Created))
        self.assertTrue(bind_handle.called)
        self.assertTrue(all(call.args == (0,) for call in bind_handle.call_args_list))
        # A later intentional native-window creation can bind the new handle.
        replacement = int(surface.winId())
        self.app.processEvents()
        bind_handle.assert_called_with(replacement)
        self.adapter.setVideoOutput(None)

    def test_wayland_uses_main_players_qt_fallback(self):
        with patch.object(vlc_player_adapter.sys, "platform", "linux"), patch.object(
            vlc_player_adapter.QGuiApplication, "platformName", return_value="wayland"
        ), self.assertRaisesRegex(RuntimeError, "Qt engine on Wayland"):
            vlc_player_adapter.VLCPlayerAdapter()


if __name__ == "__main__":
    unittest.main()
