"""Deliver file-open requests to the current user's running desktop player."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from PyQt6.QtCore import (
    QElapsedTimer, QLockFile, QObject, QStandardPaths, QThread, QTimer, pyqtSignal,
)
from PyQt6.QtNetwork import QAbstractSocket, QLocalServer, QLocalSocket


MAX_REQUEST_BYTES = 1024 * 1024
MAX_REQUEST_PATHS = 4096
REQUEST_TIMEOUT_MS = 15_000


def _encode_request(paths: list[str]) -> bytes:
    if (
        not isinstance(paths, list)
        or len(paths) > MAX_REQUEST_PATHS
        or any(not isinstance(path, str) or "\0" in path for path in paths)
    ):
        raise ValueError("The file-open request contains invalid paths.")
    message = json.dumps({"version": 1, "paths": paths}, ensure_ascii=False).encode("utf-8") + b"\n"
    if len(message) > MAX_REQUEST_BYTES:
        raise ValueError("Too many files were selected to open at once.")
    return message


class InstanceBridge(QObject):
    """Own the per-profile server, or forward a launch to its current owner.

    Create this after setting the application's name and organization. Keep it
    alive until QApplication exits, and connect files_received before entering
    the event loop. An empty list is an activation request. Initial primary
    launch paths are handled by the caller, rather than emitted by this class.
    """

    files_received = pyqtSignal(list)

    def __init__(self, parent=None, profile_directory: str | Path | None = None):
        super().__init__(parent)
        profile = Path(profile_directory or QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation
        ))
        profile.mkdir(parents=True, exist_ok=True)
        identity = os.path.normcase(str(profile.resolve()))
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
        self.server_name = f"kaos-tunes-{digest}"
        self._lock = QLockFile(str(profile / "player-instance.lock"))
        # A listening player can run for days. Only a dead process, not an old
        # timestamp, should make its lock stale.
        self._lock.setStaleLockTime(0)
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self._server.newConnection.connect(self._accept_connections)
        self._connections: dict[QLocalSocket, tuple[bytearray, QTimer]] = {}

    def start_or_forward(self, paths: list[str]) -> bool:
        """Return True for the owner, False after another owner acknowledges.

        A lock serializes initial launches and stale-socket recovery. If another
        process is still initializing, retry its socket without removing it.
        A failed delivery raises RuntimeError instead of silently losing files.
        """
        request = _encode_request(paths)
        elapsed = QElapsedTimer()
        elapsed.start()
        while elapsed.elapsed() < REQUEST_TIMEOUT_MS:
            if self._lock.tryLock(0):
                if self._server.listen(self.server_name):
                    return True
                try:
                    if self._server.serverError() != QAbstractSocket.SocketError.AddressInUseError:
                        raise RuntimeError(f"Could not start file-open delivery: {self._server.errorString()}")
                    # If the lock was removed externally, a live server may
                    # still own the socket. Probe before stale recovery.
                    if self._forward(request, elapsed):
                        self._lock.unlock()
                        return False
                    QLocalServer.removeServer(self.server_name)
                    if self._server.listen(self.server_name):
                        return True
                    raise RuntimeError(f"Could not start file-open delivery: {self._server.errorString()}")
                except RuntimeError:
                    self._lock.unlock()
                    raise
            if self._lock.error() != QLockFile.LockError.LockFailedError:
                raise RuntimeError("Could not access the Kaos Tunes instance lock in the application-data folder.")
            if self._forward(request, elapsed):
                return False
            QThread.msleep(50)
        raise RuntimeError("The running Kaos Tunes player is not responding. Close it and try opening the files again.")

    def _forward(self, request: bytes, elapsed: QElapsedTimer) -> bool:
        socket = QLocalSocket()
        socket.setReadBufferSize(33)
        try:
            socket.connectToServer(self.server_name)
            if not socket.waitForConnected(150):
                return False
            if socket.write(request) != len(request):
                raise RuntimeError("Could not send the file-open request to Kaos Tunes.")
            remaining = lambda: max(1, REQUEST_TIMEOUT_MS - elapsed.elapsed())
            while socket.bytesToWrite():
                if elapsed.elapsed() >= REQUEST_TIMEOUT_MS or not socket.waitForBytesWritten(remaining()):
                    raise RuntimeError("Could not send the file-open request to Kaos Tunes.")
            reply = bytearray()
            while not reply.endswith(b"\n"):
                reply.extend(bytes(socket.readAll()))
                if reply.endswith(b"\n"):
                    break
                if (
                    len(reply) > 32
                    or elapsed.elapsed() >= REQUEST_TIMEOUT_MS
                    or not socket.waitForReadyRead(remaining())
                ):
                    raise RuntimeError("The running Kaos Tunes player did not acknowledge the file-open request.")
            if reply != b"OK\n":
                raise RuntimeError("The running Kaos Tunes player rejected the file-open request.")
            return True
        finally:
            socket.abort()

    def _accept_connections(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            socket.setReadBufferSize(MAX_REQUEST_BYTES + 1)
            timer = QTimer(socket)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda s=socket: self._drop_connection(s))
            socket.readyRead.connect(lambda s=socket: self._read_request(s))
            socket.disconnected.connect(lambda s=socket: self._drop_connection(s))
            self._connections[socket] = (bytearray(), timer)
            timer.start(REQUEST_TIMEOUT_MS)
            self._read_request(socket)

    def _read_request(self, socket: QLocalSocket) -> None:
        connection = self._connections.get(socket)
        if connection is None:
            return
        data, timer = connection
        data.extend(bytes(socket.readAll()))
        if len(data) > MAX_REQUEST_BYTES:
            self._drop_connection(socket)
            return
        if b"\n" not in data:
            return
        try:
            payload = json.loads(data.decode("utf-8"))
            if not isinstance(payload, dict) or payload.get("version") != 1:
                raise ValueError("Unknown request protocol")
            paths = payload["paths"]
            _encode_request(paths)
        except (UnicodeDecodeError, ValueError, TypeError, KeyError):
            self._drop_connection(socket)
            return
        self._connections.pop(socket)
        timer.stop()
        self.files_received.emit(paths)
        socket.write(b"OK\n")
        socket.disconnectFromServer()

    def _drop_connection(self, socket: QLocalSocket) -> None:
        connection = self._connections.pop(socket, None)
        if connection is not None:
            connection[1].stop()
        socket.abort()
        socket.deleteLater()

    def close(self) -> None:
        for socket in list(self._connections):
            self._drop_connection(socket)
        self._server.close()
        self._lock.unlock()
