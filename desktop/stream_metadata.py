"""Bounded, asynchronous now-playing lookup for GNB's public stream."""
import json
from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest

GNB_STREAM = 'https://goodneighborblues.com/radio-stream'

class StationMetadata(QObject):
    updated = pyqtSignal(str, str)

    def __init__(self, player, parent=None):
        super().__init__(parent)
        self.player = player
        self.network = QNetworkAccessManager(self)
        self.pending = None
        self.timer = QTimer(self)
        self.timer.setInterval(10000)
        self.timer.timeout.connect(self.poll)
        self.timer.start()
        player.playbackStateChanged.connect(lambda _: self.poll())

    def poll(self):
        if self.pending or self.player.source().toString() != GNB_STREAM or self.player.playbackState().name != 'PlayingState':
            return
        request = QNetworkRequest(QUrl('https://goodneighborblues.com/radio/status'))
        request.setTransferTimeout(6000)
        reply = self.pending = self.network.get(request)
        reply.readyRead.connect(lambda: reply.abort() if reply.bytesAvailable() > 65536 else None)
        reply.finished.connect(lambda: self.finish(reply))

    def finish(self, reply):
        try:
            if not reply.error().value and self.player.source().toString() == GNB_STREAM:
                value = json.loads(bytes(reply.readAll()))
                title, artist = value.get('title', ''), value.get('artist', '')
                if isinstance(title, str) and isinstance(artist, str):
                    self.updated.emit(title[:512], artist[:512])
        except (ValueError, TypeError, AttributeError):
            pass
        finally:
            self.pending = None
            reply.deleteLater()

    def close(self):
        self.timer.stop()
        if self.pending is not None:
            self.pending.abort()
