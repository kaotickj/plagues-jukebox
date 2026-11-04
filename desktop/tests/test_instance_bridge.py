"""Cross-process delivery used by Windows and Linux file associations."""

import json
import os
from pathlib import Path
import socket as native_socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtNetwork import QLocalSocket
from PyQt6.QtWidgets import QApplication

from instance_bridge import InstanceBridge, MAX_REQUEST_BYTES, _encode_request


DESKTOP = Path(__file__).resolve().parents[1]


class InstanceBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.bridge = InstanceBridge(profile_directory=self.directory.name)
        self.requests = []
        self.bridge.files_received.connect(self.requests.append)
        self.assertTrue(self.bridge.start_or_forward([]))

    def tearDown(self):
        self.bridge.close()
        self.app.processEvents()
        self.directory.cleanup()

    def pump_until(self, predicate, timeout=5):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertTrue(predicate(), "Timed out waiting for local file-open delivery")

    def connect_client(self):
        client = QLocalSocket()
        client.connectToServer(self.bridge.server_name)
        self.assertTrue(client.waitForConnected(1000), client.errorString())
        self.app.processEvents()
        self.addCleanup(client.abort)
        return client

    def test_fragmented_unicode_request_is_delivered_once(self):
        paths = ["/music/Blue sky.flac", "/music/Björk/音楽.mp3"]
        message = _encode_request(paths)
        client = self.connect_client()
        for fragment in (message[:9], message[9:-1]):
            client.write(fragment)
            client.flush()
            self.app.processEvents()
        self.assertEqual(self.requests, [])
        client.write(message[-1:])
        client.flush()
        self.pump_until(lambda: self.requests == [paths])
        self.pump_until(lambda: client.bytesAvailable() > 0)
        self.assertEqual(bytes(client.readAll()), b"OK\n")

    def test_second_process_forwards_files_and_activation(self):
        script = (
            "import json,sys; from PyQt6.QtCore import QCoreApplication; "
            "from instance_bridge import InstanceBridge; app=QCoreApplication([]); "
            "bridge=InstanceBridge(profile_directory=sys.argv[1]); "
            "print(bridge.start_or_forward(json.loads(sys.argv[2])))"
        )
        for paths in (["/music/Track one.mp3", "/music/音楽.flac"], []):
            child = subprocess.Popen(
                [sys.executable, "-c", script, self.directory.name, json.dumps(paths)],
                cwd=DESKTOP, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8",
            )
            try:
                self.pump_until(lambda: child.poll() is not None)
                output, error = child.communicate(timeout=1)
                self.assertEqual(child.returncode, 0, error)
                self.assertEqual(output.strip(), "False")
                self.assertEqual(self.requests[-1], paths)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.communicate()
        self.assertTrue(self.bridge._server.isListening())

    def test_malformed_requests_do_not_affect_the_live_server(self):
        for message in (
            b'{"version":1,"paths":"not a list"}\n',
            b'{"version":2,"paths":[]}\n',
            b'not JSON\n',
            b'{"version":1,"paths":[null]}\n',
            b'\xff\n',
        ):
            client = self.connect_client()
            client.write(message)
            client.flush()
            self.pump_until(lambda: client.state() == QLocalSocket.LocalSocketState.UnconnectedState)
        self.assertEqual(self.requests, [])
        self.assertTrue(self.bridge._server.isListening())

    def test_oversized_request_is_rejected_before_delivery(self):
        client = self.connect_client()
        self.pump_until(lambda: len(self.bridge._connections) == 1)
        buffer, _ = next(iter(self.bridge._connections.values()))
        # A single flush need not drain a large local-socket write on every OS.
        # Wait for each bounded chunk to reach the server so this exercises the
        # size limit, rather than the platform's socket-buffer capacity.
        sent = 0
        while sent < MAX_REQUEST_BYTES:
            chunk = b"x" * min(16 * 1024, MAX_REQUEST_BYTES - sent)
            self.assertEqual(client.write(chunk), len(chunk))
            client.flush()
            sent += len(chunk)
            self.pump_until(lambda: len(buffer) == sent and client.bytesToWrite() == 0)
        self.assertEqual(client.state(), QLocalSocket.LocalSocketState.ConnectedState)
        self.assertEqual(self.requests, [])
        # Exactly the limit may still be an incomplete message. The very next
        # byte must reject it immediately, before the request timeout expires.
        self.assertEqual(client.write(b"x"), 1)
        client.flush()
        self.pump_until(lambda: not self.bridge._connections)
        self.pump_until(lambda: client.state() == QLocalSocket.LocalSocketState.UnconnectedState)
        self.assertEqual(self.requests, [])

    def test_live_owner_lock_is_never_removed_while_it_initializes(self):
        self.bridge._server.close()
        contender = InstanceBridge(profile_directory=self.directory.name)
        try:
            with patch("instance_bridge.REQUEST_TIMEOUT_MS", 180), patch(
                "instance_bridge.QLocalServer.removeServer"
            ) as remove:
                with self.assertRaisesRegex(RuntimeError, "not responding"):
                    contender.start_or_forward(["/music/song.mp3"])
                remove.assert_not_called()
            self.assertTrue(self.bridge._lock.isLocked())
        finally:
            contender.close()

    def test_request_waits_for_owner_to_finish_starting(self):
        with tempfile.TemporaryDirectory() as profile:
            marker = Path(profile) / "starting"
            script = """
import json, sys, time
from pathlib import Path
from PyQt6.QtCore import QCoreApplication, QTimer
from instance_bridge import InstanceBridge
app = QCoreApplication([])
bridge = InstanceBridge(profile_directory=sys.argv[1])
assert bridge._lock.tryLock(0)
Path(sys.argv[2]).write_text("locked", encoding="utf-8")
time.sleep(0.2)
assert bridge._server.listen(bridge.server_name)
def received(paths):
    print(json.dumps(paths), flush=True)
    QTimer.singleShot(20, app.quit)
bridge.files_received.connect(received)
QTimer.singleShot(4000, app.quit)
app.exec()
bridge.close()
"""
            child = subprocess.Popen(
                [sys.executable, "-c", script, profile, str(marker)], cwd=DESKTOP,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8",
            )
            contender = InstanceBridge(profile_directory=profile)
            try:
                self.pump_until(marker.exists)
                self.assertFalse(contender.start_or_forward(["/music/First launch.mp3"]))
                output, error = child.communicate(timeout=5)
                self.assertEqual(child.returncode, 0, error)
                self.assertEqual(json.loads(output), ["/music/First launch.mp3"])
            finally:
                contender.close()
                if child.poll() is None:
                    child.kill()
                    child.communicate()

    @unittest.skipUnless(hasattr(native_socket, "AF_UNIX") and sys.platform != "win32", "Unix sockets only")
    def test_dead_process_socket_is_recovered_after_lock_acquisition(self):
        self.bridge.close()
        # Leave an unconnected Unix socket file, as a crashed player would.
        endpoint = Path(tempfile.gettempdir()) / self.bridge.server_name
        leftover = native_socket.socket(native_socket.AF_UNIX)
        try:
            leftover.bind(str(endpoint))
        finally:
            leftover.close()
        self.assertTrue(self.bridge.start_or_forward([]))
        client = self.connect_client()
        client.write(_encode_request([]))
        client.flush()
        self.pump_until(lambda: self.requests == [[]])

    def test_request_encoding_rejects_bad_paths_and_limits_payload(self):
        for paths in ([None], ["bad\0path"], "not a list", ["x" * MAX_REQUEST_BYTES]):
            with self.subTest(paths_type=type(paths).__name__):
                with self.assertRaises(ValueError):
                    _encode_request(paths)


if __name__ == "__main__":
    unittest.main()
