"""Qt-compatible libVLC transport adapter for optional DSP playback.

The adapter owns libVLC and polls state on Qt's GUI thread. Qt remains the
default backend; opting in is explicit and restart-based.
"""
from __future__ import annotations

import sys

from PyQt6.QtCore import QEvent, QObject, QTimer, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtMultimedia import QMediaPlayer

from vlc_equalizer_engine import VLCEqualizerEngine


class VLCAudioOutput(QObject):
    mutedChanged = pyqtSignal(bool)
    volumeChanged = pyqtSignal(float)

    class _Device:
        def description(self):
            return "libVLC default audio output"

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._volume = 1.0
        self._muted = False

    def setVolume(self, value):
        self._volume = max(0.0, min(1.0, float(value)))
        self.engine.set_volume(round(self._volume * 100))
        self.volumeChanged.emit(self._volume)

    def volume(self):
        return self._volume

    def setMuted(self, value):
        self._muted = bool(value)
        self.engine.set_mute(self._muted)
        self.mutedChanged.emit(self._muted)

    def isMuted(self):
        return self._muted

    def device(self):
        return self._Device()


class VLCPlayerAdapter(QObject):
    streamMetadataChanged = pyqtSignal(str, str)
    positionChanged = pyqtSignal(int)
    durationChanged = pyqtSignal(int)
    playbackStateChanged = pyqtSignal(object)
    mediaStatusChanged = pyqtSignal(object)
    errorOccurred = pyqtSignal(object, str)
    sourceChanged = pyqtSignal(QUrl)
    hasVideoChanged = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        if sys.platform.startswith("linux") and QGuiApplication.platformName().startswith("wayland"):
            # LibVLC 3's embedding API accepts an XID, not a Wayland surface.
            # Raising here lets MusicPlayer use its normal Qt fallback safely.
            raise RuntimeError("VLC video embedding requires X11/XWayland; using the Qt engine on Wayland")
        self.engine = VLCEqualizerEngine()
        self.audio = VLCAudioOutput(self.engine, self)
        self._source = QUrl()
        self._state = QMediaPlayer.PlaybackState.StoppedState
        self._status = QMediaPlayer.MediaStatus.NoMedia
        self._duration = 0
        self._position = 0
        self._rate = 1.0
        self._error = ""
        self._last_metadata = None
        self._started = False
        self._has_video = False
        self._video_output = None
        self._closed = False
        self._video_rebind_timer = QTimer(self)
        self._video_rebind_timer.setSingleShot(True)
        self._video_rebind_timer.timeout.connect(self._rebind_video_output)
        self.timer = QTimer(self)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self._poll)
        self.timer.start()

    def setAudioOutput(self, output):
        raise RuntimeError("libVLC adapter owns its audio output")

    def setVideoOutput(self, output):
        self._video_rebind_timer.stop()
        if self._video_output is not None:
            self._video_output.removeEventFilter(self)
            self._video_output.destroyed.disconnect(self._video_surface_destroyed)
        self._video_output = output
        handle = 0
        if output is not None:
            # Create the native handle before observing handle changes to avoid
            # a second binding from the initial WinIdChange event.
            handle = int(output.winId())
            output.installEventFilter(self)
            output.destroyed.connect(self._video_surface_destroyed)
        self._bind_video_handle(handle)

    def _bind_video_handle(self, handle):
        if sys.platform == "win32":
            self.engine.player.set_hwnd(handle)
        elif sys.platform == "darwin":
            self.engine.player.set_nsobject(handle)
        else:
            self.engine.player.set_xwindow(handle)
        self.engine.player.video_set_mouse_input(False)
        self.engine.player.video_set_key_input(False)

    def _rebind_video_output(self):
        if self._closed:
            return
        output = self._video_output
        handle = 0
        if output is not None and output.testAttribute(Qt.WidgetAttribute.WA_WState_Created):
            # Unlike winId(), effectiveWinId() never creates a native window.
            # Wait for the WinIdChange transition to finish before reading it.
            handle = int(output.effectiveWinId() or 0)
        self._bind_video_handle(handle)

    def _video_surface_destroyed(self):
        self._video_output = None
        self._video_rebind_timer.stop()
        if not self._closed:
            self._bind_video_handle(0)

    def eventFilter(self, watched, event):
        if watched is self._video_output and event.type() == QEvent.Type.WinIdChange:
            self._bind_video_handle(0)
            self._video_rebind_timer.start(0)
        return super().eventFilter(watched, event)

    def hasVideo(self):
        return self._has_video

    def _set_has_video(self, available):
        if bool(available) != self._has_video:
            self._has_video = bool(available)
            self.hasVideoChanged.emit(self._has_video)

    def source(self):
        return QUrl(self._source)

    def setSource(self, source):
        self.engine.stop()
        self._set_has_video(False)
        self._source = QUrl(source)
        self._last_metadata = None
        self._started = False
        self._duration = self._position = 0
        self._set_state(QMediaPlayer.PlaybackState.StoppedState)
        self.sourceChanged.emit(self._source)
        if self._source.isEmpty():
            self._set_status(QMediaPlayer.MediaStatus.NoMedia)
            return
        target = self._source.toLocalFile() if self._source.isLocalFile() else self._source.toString()
        self.engine.set_source(target)
        self._set_status(QMediaPlayer.MediaStatus.LoadedMedia)

    def play(self):
        try:
            if self._state == QMediaPlayer.PlaybackState.PausedState:
                self.engine.resume()
            else:
                self.engine.play()
            self._started = True
            self._set_state(QMediaPlayer.PlaybackState.PlayingState)
        except Exception as exc:
            self._error = str(exc)
            self.errorOccurred.emit(QMediaPlayer.Error.ResourceError, self._error)

    def pause(self):
        self.engine.pause()
        self._set_state(QMediaPlayer.PlaybackState.PausedState)

    def stop(self):
        self.engine.stop()
        self._started = False
        self._set_state(QMediaPlayer.PlaybackState.StoppedState)

    def setPosition(self, position):
        self.engine.seek(position)
        self._position = max(0, int(position))
        self.positionChanged.emit(self._position)

    def position(self):
        return self._position

    def duration(self):
        return self._duration

    def playbackState(self):
        return self._state

    def mediaStatus(self):
        return self._status

    def bufferProgress(self):
        return 1.0

    def playbackRate(self):
        return self._rate

    def setPlaybackRate(self, rate):
        self._rate = float(rate)
        self.engine.set_rate(self._rate)

    def errorString(self):
        return self._error

    def _set_state(self, state):
        if state != self._state:
            self._state = state
            self.playbackStateChanged.emit(state)

    def _set_status(self, status):
        if status != self._status:
            self._status = status
            self.mediaStatusChanged.emit(status)

    def _poll(self):
        if self._source.isEmpty():
            return
        duration = self.engine.duration()
        position = self.engine.position()
        if duration != self._duration:
            self._duration = duration
            self.durationChanged.emit(duration)
        if position != self._position:
            self._position = position
            self.positionChanged.emit(position)
        media = self.engine.player.get_media()
        if media is not None:
            try:
                title = media.get_meta(self.engine.vlc.Meta.NowPlaying) or media.get_meta(self.engine.vlc.Meta.Title) or ""
                artist = media.get_meta(self.engine.vlc.Meta.Artist) or ""
                metadata = (title, artist)
                if metadata != self._last_metadata:
                    self._last_metadata = metadata
                    self.streamMetadataChanged.emit(title, artist)
            finally:
                media.release()
        state = self.engine.player.get_state()
        vlc = self.engine.vlc
        if state in (vlc.State.Playing, vlc.State.Paused):
            self._set_has_video(self.engine.player.has_vout() > 0)
        if state == vlc.State.Error:
            self._error = "libVLC playback error"
            self._set_status(QMediaPlayer.MediaStatus.InvalidMedia)
            self.errorOccurred.emit(QMediaPlayer.Error.ResourceError, self._error)
            self.stop()
        elif state == vlc.State.Ended and self._started:
            self._started = False
            self._set_state(QMediaPlayer.PlaybackState.StoppedState)
            self._set_status(QMediaPlayer.MediaStatus.EndOfMedia)
        elif state == vlc.State.Playing:
            self._set_state(QMediaPlayer.PlaybackState.PlayingState)
        elif state == vlc.State.Paused:
            self._set_state(QMediaPlayer.PlaybackState.PausedState)

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.timer.stop()
        self._video_rebind_timer.stop()
        self.setVideoOutput(None)
        self.engine.close()
