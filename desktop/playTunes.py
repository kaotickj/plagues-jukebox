"""Kaos Tunes 2 - a modern, single-file PyQt6 music player.

Install:
    pip install PyQt6 mutagen

Mutagen is optional, but enables tags, durations, and embedded cover art.
Playback uses Qt Multimedia and the codecs installed on the operating system.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import random
import re
import sys
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Iterable, Optional
from urllib.parse import urlparse

from equalizer_dialog import EqualizerDialog
from audio_equalizer import EqualizerSettings
from vlc_equalizer_engine import availability as vlc_availability
from instance_bridge import InstanceBridge

from metadata_lookup import (
    OnlineMetadataResult,
    fpcalc_status,
    load_cached_cover,
    lookup_online_metadata,
)

# Qt documents the native Windows backend as the fallback when its FFmpeg
# backend has platform-specific failures. Users can still override this before
# launch with QT_MEDIA_BACKEND=ffmpeg.
if sys.platform == "win32":
    os.environ.setdefault("QT_MEDIA_BACKEND", "windows")

try:
    from PyQt6.QtCore import (
        QAbstractTableModel, QElapsedTimer, QEvent, QModelIndex, QObject, QRunnable, QSettings,
        QSortFilterProxyModel, QStandardPaths, QThreadPool, QTimer, Qt, QUrl, pyqtSignal,
    )
    from PyQt6.QtGui import (
        QAction, QColor, QCloseEvent, QDesktopServices, QDragEnterEvent,
        QDropEvent, QFont, QIcon, QKeySequence, QLinearGradient, QPainter,
        QPixmap, QShortcut,
    )
    from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    from PyQt6.QtWidgets import (
        QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog,
        QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
        QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton,
        QSlider, QSplitter, QStyle, QTabWidget, QTableView, QToolButton, QVBoxLayout,
        QWidget,
    )
except ImportError as exc:
    raise SystemExit(
        "PyQt6 is required. Install it with:  pip install PyQt6\n"
        f"Original import error: {exc}"
    ) from exc

try:
    from mutagen import File as MutagenFile
except ImportError:
    MutagenFile = None


APP_NAME = "Plague’s Jukebox"
# Keep the established profile identity: no settings or library migration.
PROFILE_NAME = "Kaos Tunes"
APP_TITLE = APP_NAME
GNB_STREAM_URL = "https://goodneighborblues.com/radio-stream"
APP_VERSION = "2.3.1"
ORGANIZATION = "Kaosium Interactive"
AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".ogg", ".oga", ".opus", ".m4a",
    ".aac", ".wma", ".aiff", ".aif",
}
VIDEO_EXTENSIONS = {
    ".mp4", ".m4v", ".mkv", ".webm", ".mov", ".avi", ".wmv",
    ".mpg", ".mpeg", ".ogv", ".3gp",
}
SUPPORTED_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS


def resource_path(filename: str) -> str:
    """Resolve a bundled PyInstaller resource or a source-tree asset."""
    candidates = [
        Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / filename,
        Path(__file__).resolve().parent / filename,
        Path(sys.prefix) / "share" / "kaos-tunes" / filename,
    ]
    return str(next((candidate for candidate in candidates if candidate.is_file()), candidates[0]))

DARK_STYLE = """
QMainWindow, QDialog, QWidget { background: #101316; color: #e8edf2; }
QFrame#Card { background: #171b20; border: 1px solid #282f37; border-radius: 14px; }
QLabel#Eyebrow { color: #73e6a5; font-size: 11px; font-weight: 700; }
QLabel#TrackTitle { font-size: 24px; font-weight: 700; color: #f7fafc; }
QLabel#TrackMeta { color: #aeb8c2; font-size: 13px; }
QLabel#TimeLabel { color: #9ca8b4; font-family: monospace; }
QLineEdit, QComboBox { background: #1b2026; border: 1px solid #343d47;
    border-radius: 7px; padding: 7px; selection-background-color: #2cbf73; }
QLineEdit:focus, QComboBox:focus { border-color: #39d98a; }
QTableView { background: #13171b; alternate-background-color: #171c21;
    border: 1px solid #293039; border-radius: 9px; gridline-color: transparent;
    selection-background-color: #24563d; selection-color: white; }
QTableView::item { padding: 7px; border-bottom: 1px solid #20262d; }
QHeaderView::section { background: #1b2026; color: #9eabb7; border: 0;
    border-bottom: 1px solid #313943; padding: 8px; font-weight: 600; }
QPushButton, QToolButton { background: #20262d; border: 1px solid #343d47;
    border-radius: 8px; padding: 7px 11px; }
QPushButton:hover, QToolButton:hover { background: #29313a; border-color: #4b5866; }
QPushButton:pressed, QToolButton:pressed { background: #15191e; }
QPushButton#PrimaryButton { background: #28b86f; color: #07120c; border: 0; font-weight: 700; }
QPushButton#PrimaryButton:hover { background: #39d98a; }
QToolButton#Transport { border-radius: 20px; min-width: 40px; min-height: 40px; }
QToolButton#PlayButton { background: #36d486; color: #07120c; border: 0;
    border-radius: 25px; min-width: 50px; min-height: 50px; }
QSlider::groove:horizontal { height: 5px; background: #343c45; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #39d98a; border-radius: 2px; }
QSlider::handle:horizontal { background: #e9fff3; width: 14px; margin: -5px 0; border-radius: 7px; }
QMenuBar { background: #101316; }
QMenuBar::item:selected, QMenu::item:selected { background: #26583f; }
QMenu { background: #1a1f25; border: 1px solid #343c45; padding: 5px; }
QTabWidget::pane { border: 0; }
QTabBar::tab { background: #171b20; color: #aeb8c2; border: 1px solid #282f37;
    padding: 8px 16px; margin-right: 3px; border-top-left-radius: 7px;
    border-top-right-radius: 7px; }
QTabBar::tab:selected { background: #24563d; color: white; }
QStatusBar { color: #9da8b3; }
QSplitter::handle { background: #101316; width: 8px; }
QToolTip { background: #222a31; color: white; border: 1px solid #46525f; }
"""

LIGHT_STYLE = """
QMainWindow, QDialog, QWidget { background: #f4f6f8; color: #17202a; }
QFrame#Card { background: white; border: 1px solid #dce2e8; border-radius: 14px; }
QLabel#Eyebrow { color: #08783f; font-size: 11px; font-weight: 700; }
QLabel#TrackTitle { font-size: 24px; font-weight: 700; color: #17202a; }
QLabel#TrackMeta { color: #536170; font-size: 13px; }
QLabel#TimeLabel { color: #647383; font-family: monospace; }
QLineEdit, QComboBox { background: white; border: 1px solid #cbd3dc;
    border-radius: 7px; padding: 7px; }
QLineEdit:focus, QComboBox:focus { border-color: #15965a; }
QTableView { background: white; alternate-background-color: #f8fafb;
    border: 1px solid #d8dee5; border-radius: 9px; gridline-color: transparent;
    selection-background-color: #bcebd2; }
QTableView::item { padding: 7px; border-bottom: 1px solid #edf0f3; }
QHeaderView::section { background: #edf1f4; color: #4a5865; border: 0;
    border-bottom: 1px solid #d5dce3; padding: 8px; font-weight: 600; }
QPushButton, QToolButton { background: white; border: 1px solid #cbd3dc;
    border-radius: 8px; padding: 7px 11px; }
QPushButton:hover, QToolButton:hover { background: #eaf0f4; }
QPushButton#PrimaryButton { background: #15965a; color: white; border: 0; font-weight: 700; }
QToolButton#Transport { border-radius: 20px; min-width: 40px; min-height: 40px; }
QToolButton#PlayButton { background: #19a963; color: white; border: 0;
    border-radius: 25px; min-width: 50px; min-height: 50px; }
QSlider::groove:horizontal { height: 5px; background: #cfd7de; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #15965a; border-radius: 2px; }
QSlider::handle:horizontal { background: #137b4d; width: 14px; margin: -5px 0; border-radius: 7px; }
QMenu { background: white; border: 1px solid #ccd4dc; padding: 5px; }
QMenu::item:selected { background: #ccefdc; }
QTabWidget::pane { border: 0; }
QTabBar::tab { background: #e7ebef; color: #536170; border: 1px solid #d2d9e0;
    padding: 8px 16px; margin-right: 3px; border-top-left-radius: 7px;
    border-top-right-radius: 7px; }
QTabBar::tab:selected { background: #bcebd2; color: #17202a; }
"""


def format_time(milliseconds: int) -> str:
    seconds = max(0, int(milliseconds // 1000))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def canonical_path(path: str | Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def validate_stream_url(source: str) -> str:
    source = source.strip()
    try:
        parsed = urlparse(source)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError
        if any(c.isspace() or ord(c) < 32 for c in source) or parsed.fragment:
            raise ValueError
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError
    except ValueError:
        raise ValueError("Enter a complete HTTP or HTTPS stream URL without embedded login credentials or spaces.") from None
    return source


def is_remote_source(source: str) -> bool:
    return urlparse(source).scheme.lower() in {"http", "https", "rtsp"}


def canonical_source(source: str) -> str:
    if is_remote_source(source):
        parsed = urlparse(source)
        return parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower()).geturl()
    return canonical_path(source)


def path_is_within(path: str | Path, directory: str | Path) -> bool:
    """Return whether a local path is inside a directory, across Windows drives."""
    try:
        return os.path.commonpath((canonical_path(path), canonical_path(directory))) == canonical_path(directory)
    except (OSError, ValueError):
        return False


def source_name(source: str) -> str:
    if is_remote_source(source):
        parsed = urlparse(source)
        return Path(parsed.path).stem or parsed.netloc or "Network stream"
    return Path(source).stem


def normalize_playlist_source(entry: str, playlist_directory: Path) -> str:
    value = entry.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()
    if not value:
        return ""
    if value.lower().startswith("file:"):
        local = QUrl(value).toLocalFile()
        # QUrl returns /C:/... outside Windows; normalize it for portable tests
        # and for playlists copied between operating systems.
        if re.match(r"^/[A-Za-z]:[/\\]", local):
            local = local[1:]
        return os.path.normpath(local)
    if is_remote_source(value):
        return value
    value = os.path.expandvars(os.path.expanduser(value))
    path = Path(value)
    if not path.is_absolute():
        path = playlist_directory / path
    return str(path.resolve(strict=False))


def is_audio_file(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def tag_text(tags: object, *keys: str) -> str:
    if not tags:
        return ""
    for key in keys:
        try:
            value = tags.get(key)  # type: ignore[attr-defined]
        except (AttributeError, KeyError):
            continue
        if value is None:
            continue
        if hasattr(value, "text"):
            value = value.text
        while isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        text = str(value).strip()
        if text:
            return text
    return ""


@dataclass
class Track:
    path: str
    title: str = ""
    artist: str = ""
    album: str = ""
    album_artist: str = ""
    genre: str = ""
    composer: str = ""
    comment: str = ""
    year: str = ""
    track_number: str = ""
    disc_number: str = ""
    duration_ms: int = 0
    codec: str = ""
    bitrate: int = 0
    sample_rate: int = 0
    channels: int = 0
    bits_per_sample: int = 0
    file_size: int = 0
    artwork_source: str = ""
    metadata_error: str = ""
    metadata_source: str = ""
    metadata_confidence: float = 0.0
    musicbrainz_recording_id: str = ""
    musicbrainz_release_id: str = ""
    musicbrainz_release_group_id: str = ""
    cover_data: bytes = field(default=b"", repr=False, compare=False)

    @property
    def display_title(self) -> str:
        return self.title or source_name(self.path)

    def clone(self) -> "Track":
        return Track(**asdict(self))

    def library_record(self) -> dict[str, object]:
        record = asdict(self)
        record.pop("cover_data", None)
        return record


@dataclass
class MetadataResult:
    path: str
    title: str = ""
    artist: str = ""
    album: str = ""
    album_artist: str = ""
    genre: str = ""
    composer: str = ""
    comment: str = ""
    year: str = ""
    track_number: str = ""
    disc_number: str = ""
    duration_ms: int = 0
    codec: str = ""
    bitrate: int = 0
    sample_rate: int = 0
    channels: int = 0
    bits_per_sample: int = 0
    file_size: int = 0
    artwork_source: str = ""
    error: str = ""
    cover_data: bytes = b""


@dataclass
class PlaylistEntry:
    source: str
    title: str = ""
    duration_ms: int = 0


def parse_m3u_playlist(path: str) -> tuple[list[PlaylistEntry], bool]:
    """Parse M3U/M3U8 entries and report whether the file is an HLS manifest."""
    playlist_path = Path(path)
    raw = playlist_path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Legacy .m3u files are often saved in the active Windows code page.
        # M3U8 is UTF-8 by definition, but replacement is safer than dropping it.
        text = raw.decode("cp1252", errors="replace")

    lines = [line.strip() for line in text.splitlines()]
    is_hls = any(line.upper().startswith("#EXT-X-") for line in lines)
    if is_hls:
        return [], True

    entries: list[PlaylistEntry] = []
    pending_title = ""
    pending_duration = 0
    for line in lines:
        if not line:
            continue
        if line.upper().startswith("#EXTINF:"):
            payload = line.partition(":")[2]
            duration_text, separator, title = payload.partition(",")
            try:
                seconds = float(duration_text.strip())
                pending_duration = max(0, int(seconds * 1000))
            except (ValueError, OverflowError):
                pending_duration = 0
            pending_title = title.strip() if separator else ""
            continue
        if line.startswith("#"):
            continue
        source = normalize_playlist_source(line, playlist_path.parent)
        if source:
            entries.append(PlaylistEntry(source, pending_title, pending_duration))
        pending_title = ""
        pending_duration = 0
    return entries, False


def read_playlist_entries(path: str) -> list[PlaylistEntry]:
    """Read a local JSON/M3U playlist without changing the current queue."""
    playlist_path = Path(path)
    if playlist_path.suffix.lower() != ".json":
        entries, is_hls = parse_m3u_playlist(path)
        if is_hls:
            return [PlaylistEntry(str(playlist_path.resolve()), playlist_path.stem)]
        return entries

    payload = json.loads(playlist_path.read_text(encoding="utf-8-sig"))
    raw_entries = payload.get("playlist") if isinstance(payload, dict) else payload
    if not isinstance(raw_entries, list):
        raise TypeError("The JSON playlist must contain a list of tracks.")
    entries = []
    for item in raw_entries:
        if isinstance(item, dict):
            raw_source = item.get("path") or item.get("source")
            title = str(item.get("title") or "")
            try:
                duration_ms = max(0, int(item.get("duration_ms") or 0))
            except (TypeError, ValueError, OverflowError):
                duration_ms = 0
        else:
            raw_source = item
            title, duration_ms = "", 0
        if not isinstance(raw_source, str):
            continue
        source = normalize_playlist_source(raw_source, playlist_path.parent)
        if source:
            entries.append(PlaylistEntry(source, title, duration_ms))
    return entries


def normalize_open_sources(arguments: Iterable[str]) -> list[str]:
    """Resolve launch paths in the sender's working directory before IPC."""
    sources = []
    for value in arguments:
        if value == "--":
            continue
        if value.lower().startswith("file:"):
            value = QUrl(value).toLocalFile()
        if not value:
            continue
        sources.append(value if is_remote_source(value) else str(Path(value).expanduser().resolve()))
    return sources


def extract_cover_art(audio: object, path: str) -> tuple[bytes, str]:
    """Return embedded artwork bytes and a description of where they came from."""
    tags = getattr(audio, "tags", None) if audio is not None else None
    pictures = getattr(audio, "pictures", None) if audio is not None else None
    if pictures:
        return bytes(pictures[0].data), "Embedded FLAC picture"

    if tags is not None:
        try:
            getall = getattr(tags, "getall", None)
            if callable(getall):
                pictures = getall("APIC")
                if pictures:
                    return bytes(pictures[0].data), "Embedded ID3 APIC"
        except Exception:
            pass

        try:
            for value in tags.values():
                if getattr(value, "FrameID", "") == "APIC" and getattr(value, "data", None):
                    return bytes(value.data), "Embedded ID3 APIC"
        except Exception:
            pass

        try:
            covers = tags.get("covr")
            if covers:
                return bytes(covers[0]), "Embedded MP4 cover"
        except Exception:
            pass

        for key in ("metadata_block_picture", "METADATA_BLOCK_PICTURE"):
            try:
                encoded = tags.get(key)
                if encoded:
                    from mutagen.flac import Picture
                    raw = encoded[0] if isinstance(encoded, (list, tuple)) else encoded
                    picture = Picture(base64.b64decode(raw))
                    return bytes(picture.data), "Embedded Vorbis picture"
            except Exception:
                pass

        try:
            encoded = tags.get("coverart")
            if encoded:
                raw = encoded[0] if isinstance(encoded, (list, tuple)) else encoded
                return base64.b64decode(raw), "Embedded Vorbis cover"
        except Exception:
            pass

    # Direct ID3 parsing is a useful fallback for unusual MP3 and WAV layouts.
    try:
        from mutagen.id3 import ID3
        pictures = ID3(path).getall("APIC")
        if pictures:
            return bytes(pictures[0].data), "Embedded ID3 APIC"
    except Exception:
        pass

    # Common external artwork is used only when no embedded picture exists.
    parent = Path(path).parent
    for name in ("cover.jpg", "cover.png", "folder.jpg", "folder.png", "front.jpg", "front.png"):
        candidate = parent / name
        try:
            if candidate.is_file():
                return candidate.read_bytes(), f"External artwork: {candidate.name}"
        except OSError:
            pass
    return b"", "None"


def scan_metadata(path: str) -> MetadataResult:
    """Read normalized tags, technical media information, and cover artwork."""
    result = MetadataResult(path=path)
    try:
        result.file_size = os.path.getsize(path)
    except OSError:
        pass
    if MutagenFile is None:
        result.error = "Mutagen is not installed in this Python interpreter."
        return result

    raw_audio = None
    easy_audio = None
    errors: list[str] = []
    try:
        raw_audio = MutagenFile(path, easy=False)
    except Exception as exc:
        errors.append(f"raw tags: {exc}")
    try:
        easy_audio = MutagenFile(path, easy=True)
    except Exception as exc:
        errors.append(f"normalized tags: {exc}")

    raw_tags = getattr(raw_audio, "tags", None)
    easy_tags = getattr(easy_audio, "tags", None)
    if raw_tags is None:
        try:
            from mutagen.id3 import ID3
            raw_tags = ID3(path)
        except Exception:
            pass

    # Easy tags normalize ID3, FLAC/Vorbis, MP4, and other container names.
    result.title = tag_text(easy_tags, "title") or tag_text(raw_tags, "TIT2", "\xa9nam", "title")
    result.artist = tag_text(easy_tags, "artist") or tag_text(raw_tags, "TPE1", "\xa9ART", "artist")
    result.album = tag_text(easy_tags, "album") or tag_text(raw_tags, "TALB", "\xa9alb", "album")
    result.album_artist = (
        tag_text(easy_tags, "albumartist", "album artist")
        or tag_text(raw_tags, "TPE2", "aART", "albumartist")
    )
    result.genre = tag_text(easy_tags, "genre") or tag_text(raw_tags, "TCON", "\xa9gen", "genre")
    result.composer = tag_text(easy_tags, "composer") or tag_text(raw_tags, "TCOM", "\xa9wrt", "composer")
    result.comment = tag_text(easy_tags, "comment", "description") or tag_text(
        raw_tags, "COMM::eng", "COMM", "\xa9cmt", "comment", "description"
    )
    if not result.comment and raw_tags is not None:
        try:
            comments = raw_tags.getall("COMM")
            if comments:
                result.comment = tag_text({"comment": comments[0]}, "comment")
        except Exception:
            pass
    result.year = tag_text(easy_tags, "date", "year") or tag_text(
        raw_tags, "TDRC", "TYER", "\xa9day", "date", "year"
    )
    result.track_number = tag_text(easy_tags, "tracknumber") or tag_text(raw_tags, "TRCK", "trkn")
    result.disc_number = tag_text(easy_tags, "discnumber") or tag_text(raw_tags, "TPOS", "disk")

    media = raw_audio if raw_audio is not None else easy_audio
    info = getattr(media, "info", None)
    if info is not None:
        length = getattr(info, "length", 0) or 0
        result.duration_ms = int(float(length) * 1000)
        result.bitrate = int(getattr(info, "bitrate", 0) or 0)
        result.sample_rate = int(getattr(info, "sample_rate", 0) or 0)
        result.channels = int(getattr(info, "channels", 0) or 0)
        result.bits_per_sample = int(
            getattr(info, "bits_per_sample", 0)
            or getattr(info, "sample_size", 0)
            or 0
        )
    if media is not None:
        mime = getattr(media, "mime", None)
        result.codec = str(mime[0]) if mime else type(media).__name__
        result.cover_data, result.artwork_source = extract_cover_art(media, path)
    else:
        result.cover_data, result.artwork_source = extract_cover_art(None, path)

    if len(result.cover_data) > 32 * 1024 * 1024:
        result.cover_data = b""
        result.artwork_source = "Embedded artwork exceeded the 32 MiB safety limit"
    if media is None:
        result.error = "; ".join(errors) or "Mutagen did not recognize this file."
    return result


class WorkerSignals(QObject):
    result = pyqtSignal(object)


class MetadataWorker(QRunnable):
    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            result = scan_metadata(self.path)
        except Exception as exc:
            # Never allow a malformed media file or decoder edge case to let an
            # exception escape a Qt worker thread.
            result = MetadataResult(path=self.path, error=f"Unexpected metadata error: {exc}")
        self.signals.result.emit(result)


class OnlineLookupWorker(QRunnable):
    """Identify one track without decoding it inside the GUI process."""

    def __init__(self, track: Track, client_key: str, cache_directory: Path):
        super().__init__()
        self.path = track.path
        self.client_key = client_key
        self.cache_directory = cache_directory
        self.known = {
            "title": track.title,
            "artist": track.artist,
            "album": track.album,
            "duration_ms": track.duration_ms,
        }
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            result = lookup_online_metadata(
                self.path,
                self.known,
                self.client_key,
                self.cache_directory,
            )
        except Exception as exc:
            result = OnlineMetadataResult(path=self.path, error=f"Unexpected lookup error: {exc}")
        self.signals.result.emit(result)


class LibraryScanSignals(QObject):
    completed = pyqtSignal(object)


class LibraryScanWorker(QRunnable):
    """Discover supported media beneath configured library folders."""

    def __init__(self, roots: Iterable[str]):
        super().__init__()
        self.roots = list(roots)
        self.signals = LibraryScanSignals()

    def run(self) -> None:
        discovered: set[str] = set()
        available_roots: list[str] = []
        missing_roots: list[str] = []
        errors: list[str] = []
        for root in self.roots:
            directory = Path(root)
            if not directory.is_dir():
                missing_roots.append(root)
                continue
            available_roots.append(root)
            try:
                def record_walk_error(error: OSError) -> None:
                    errors.append(f"{error.filename or root}: {error}")

                for current, directories, filenames in os.walk(
                    directory, topdown=True, onerror=record_walk_error, followlinks=False
                ):
                    safe_directories: list[str] = []
                    for name in directories:
                        child = Path(current) / name
                        try:
                            is_junction = getattr(child, "is_junction", lambda: False)()
                            if not child.is_symlink() and not is_junction:
                                safe_directories.append(name)
                        except (OSError, RuntimeError) as exc:
                            errors.append(f"{child}: {exc}")
                    directories[:] = safe_directories

                    for filename in filenames:
                        item = Path(current) / filename
                        if not is_audio_file(item):
                            continue
                        try:
                            if item.is_file():
                                discovered.add(str(item.resolve(strict=False)))
                        except (OSError, RuntimeError) as exc:
                            errors.append(f"{item}: {exc}")
            except Exception as exc:
                # An exception escaping QRunnable.run can terminate some PyQt
                # builds. Return it as a scan error instead.
                errors.append(f"{root}: {exc}")
        self.signals.completed.emit(
            {
                "roots": self.roots,
                "paths": sorted(discovered, key=str.casefold),
                "available_roots": available_roots,
                "missing_roots": missing_roots,
                "errors": errors,
            }
        )


class PlaylistModel(QAbstractTableModel):
    HEADERS = ("#", "Title", "Artist", "Album", "Duration")

    def __init__(self) -> None:
        super().__init__()
        self.tracks: list[Track] = []
        self.current_row = -1

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.tracks)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.tracks)):
            return None
        track = self.tracks[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            values = (
                "▶" if index.row() == self.current_row else str(index.row() + 1),
                track.display_title, track.artist or "Unknown artist",
                track.album or "Unknown album",
                format_time(track.duration_ms) if track.duration_ms else "—",
            )
            return values[index.column()]
        if role == Qt.ItemDataRole.UserRole:
            return track.path
        if role == Qt.ItemDataRole.ToolTipRole:
            return track.path
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() in (0, 4):
            return int(Qt.AlignmentFlag.AlignCenter)
        if role == Qt.ItemDataRole.BackgroundRole and index.row() == self.current_row:
            return QColor("#183c2b")
        if role == Qt.ItemDataRole.FontRole and index.row() == self.current_row and index.column() == 1:
            font = QFont()
            font.setBold(True)
            return font
        return None

    def set_current(self, row: int) -> None:
        previous = self.current_row
        self.current_row = row
        for changed in {previous, row}:
            if 0 <= changed < len(self.tracks):
                self.dataChanged.emit(self.index(changed, 0), self.index(changed, 4))

    def add_tracks(self, tracks: list[Track]) -> None:
        if not tracks:
            return
        first = len(self.tracks)
        self.beginInsertRows(QModelIndex(), first, first + len(tracks) - 1)
        self.tracks.extend(tracks)
        self.endInsertRows()

    def update_metadata(self, result: MetadataResult, include_cover: bool = True) -> int:
        wanted = canonical_source(result.path)
        for row, track in enumerate(self.tracks):
            if canonical_source(track.path) == wanted:
                track.title = result.title or track.title
                track.artist = result.artist or track.artist
                track.album = result.album or track.album
                track.album_artist = result.album_artist or track.album_artist
                track.genre = result.genre or track.genre
                track.composer = result.composer or track.composer
                track.comment = result.comment or track.comment
                track.year = result.year or track.year
                track.track_number = result.track_number or track.track_number
                track.disc_number = result.disc_number or track.disc_number
                track.duration_ms = result.duration_ms or track.duration_ms
                track.codec = result.codec or track.codec
                track.bitrate = result.bitrate or track.bitrate
                track.sample_rate = result.sample_rate or track.sample_rate
                track.channels = result.channels or track.channels
                track.bits_per_sample = result.bits_per_sample or track.bits_per_sample
                track.file_size = result.file_size or track.file_size
                if result.artwork_source and result.artwork_source != "None":
                    track.artwork_source = result.artwork_source
                track.metadata_error = result.error
                if include_cover:
                    track.cover_data = result.cover_data or track.cover_data
                self.dataChanged.emit(self.index(row, 1), self.index(row, 4))
                return row
        return -1

    def apply_online_metadata(
        self,
        result: OnlineMetadataResult,
        *,
        replace_existing: bool = False,
        include_cover: bool = True,
    ) -> int:
        wanted = canonical_source(result.path)
        for row, track in enumerate(self.tracks):
            if canonical_source(track.path) != wanted:
                continue
            for name in (
                "title", "artist", "album", "album_artist", "genre", "year",
                "track_number", "disc_number",
            ):
                found = str(getattr(result, name, "") or "").strip()
                if found and (replace_existing or not str(getattr(track, name, "") or "").strip()):
                    setattr(track, name, found)
            track.metadata_source = result.source
            track.metadata_confidence = result.confidence
            track.musicbrainz_recording_id = result.recording_id
            track.musicbrainz_release_id = result.release_id
            track.musicbrainz_release_group_id = result.release_group_id
            if result.artwork_source and (replace_existing or not track.artwork_source or track.artwork_source == "None"):
                track.artwork_source = result.artwork_source
            if include_cover and result.cover_data and (replace_existing or not track.cover_data):
                track.cover_data = result.cover_data
            track.metadata_error = ""
            self.dataChanged.emit(self.index(row, 1), self.index(row, 4))
            return row
        return -1

    def remove_rows(self, rows: Iterable[int]) -> None:
        for row in sorted(set(rows), reverse=True):
            if 0 <= row < len(self.tracks):
                self.beginRemoveRows(QModelIndex(), row, row)
                del self.tracks[row]
                self.endRemoveRows()

    def clear(self) -> None:
        if self.tracks:
            self.beginResetModel()
            self.tracks.clear()
            self.current_row = -1
            self.endResetModel()

    def replace_tracks(self, tracks: Iterable[Track]) -> None:
        self.beginResetModel()
        self.tracks = list(tracks)
        self.current_row = -1
        self.endResetModel()

    def move(self, source: int, destination: int) -> int:
        if source == destination or not (0 <= source < len(self.tracks)):
            return source
        destination = max(0, min(destination, len(self.tracks) - 1))
        self.beginResetModel()
        track = self.tracks.pop(source)
        self.tracks.insert(destination, track)
        self.endResetModel()
        return destination


class PreferencesDialog(QDialog):
    def __init__(self, parent: "MusicPlayer") -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.restore_queue = QCheckBox("Restore the queue at startup")
        self.restore_queue.setChecked(parent.pref_restore_queue)
        self.resume_position = QCheckBox("Remember the last playback position")
        self.resume_position.setChecked(parent.pref_resume_position)
        self.recursive_scan = QCheckBox("Include subfolders when adding a folder")
        self.recursive_scan.setChecked(parent.pref_recursive_scan)
        self.confirm_clear = QCheckBox("Ask before clearing a populated queue")
        self.confirm_clear.setChecked(parent.pref_confirm_clear)
        self.online_lookup = QCheckBox("Allow manual online metadata lookups")
        self.online_lookup.setChecked(parent.pref_online_lookup)
        self.acoustid_key = QLineEdit(parent.acoustid_client_key)
        self.acoustid_key.setPlaceholderText("Optional, enables audio fingerprint matching")
        self.acoustid_key.setClearButtonEnabled(True)
        self.batch_replace = QCheckBox("Allow batch lookup to replace existing tag values")
        self.batch_replace.setChecked(parent.pref_online_replace_existing)
        self.theme = QComboBox()
        self.theme.addItems(["Dark", "Light"])
        self.theme.setCurrentText(parent.theme.title())
        form.addRow("Startup", self.restore_queue)
        form.addRow("Playback", self.resume_position)
        form.addRow("Folder scanning", self.recursive_scan)
        form.addRow("Queue", self.confirm_clear)
        form.addRow("Online metadata", self.online_lookup)
        form.addRow("AcoustID client key", self.acoustid_key)
        form.addRow("Online metadata", self.batch_replace)
        form.addRow("Appearance", self.theme)
        layout.addLayout(form)
        note = QLabel(
            "Mutagen reads local tags and embedded artwork. MusicBrainz supplies online metadata. "
            "An AcoustID application key enables fingerprint identification when filenames and tags "
            f"are missing. Bundled fingerprint tool: {fpcalc_status()}. Online changes are saved to "
            "the Plague’s Jukebox library catalog; audio files are never modified."
        )
        note.setWordWrap(True)
        note.setObjectName("TrackMeta")
        layout.addWidget(note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class OnlineMetadataDialog(QDialog):
    def __init__(
        self, parent: "MusicPlayer", track: Track, result: OnlineMetadataResult
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Review online song information")
        self.setMinimumWidth(620)
        layout = QVBoxLayout(self)
        heading = QLabel(f"<h3>{track.display_title}</h3>")
        layout.addWidget(heading)
        source = QLabel(
            f"Source: {result.source or 'Unknown'} | Match confidence: {result.confidence:.0f}%"
            + (" | Cached" if result.cached else "")
        )
        source.setObjectName("TrackMeta")
        source.setWordWrap(True)
        layout.addWidget(source)

        form = QFormLayout()
        for label, name in (
            ("Title", "title"),
            ("Artist", "artist"),
            ("Album", "album"),
            ("Album artist", "album_artist"),
            ("Genre", "genre"),
            ("Date", "year"),
            ("Track", "track_number"),
            ("Disc", "disc_number"),
        ):
            current = str(getattr(track, name, "") or "Not present")
            found = str(getattr(result, name, "") or "Not found")
            value = QLabel(f"{current}  →  <b>{found}</b>")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(f"{label}:", value)
        form.addRow("Artwork:", QLabel(result.artwork_source or "Not found"))
        form.addRow("MusicBrainz recording:", QLabel(result.recording_id or "Not found"))
        layout.addLayout(form)

        self.replace_existing = QCheckBox("Replace existing values with the online result")
        self.replace_existing.setChecked(parent.pref_online_replace_existing)
        layout.addWidget(self.replace_existing)
        note = QLabel(
            "Applying this result updates the Plague’s Jukebox catalog only. The original audio file "
            "and its embedded tags are not changed."
        )
        note.setObjectName("TrackMeta")
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Apply result")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class VideoPanel(QWidget):
    """Video output embedded beside the shared queue and transport controls."""

    fullscreen_requested = pyqtSignal()

    def __init__(self, parent: QWidget, native_output: bool = False) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 180)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        self.title_label = QLabel("Video")
        self.title_label.setWordWrap(True)
        self.fullscreen_button = QPushButton("Full screen")
        self.fullscreen_button.setToolTip("Full screen (F11); Esc returns to the player")
        self.fullscreen_button.clicked.connect(self.fullscreen_requested)
        header.addWidget(self.title_label, 1)
        header.addWidget(self.fullscreen_button)
        layout.addLayout(header)
        self.surface = QWidget(self) if native_output else QVideoWidget(self)
        self.surface.setStyleSheet("background: black;")
        if native_output:
            self.surface.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        else:
            self.surface.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        layout.addWidget(self.surface, 1)


class MusicPlayer(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings(ORGANIZATION, PROFILE_NAME)
        self.model = PlaylistModel()
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)
        self.library_model = PlaylistModel()
        self.library_proxy = QSortFilterProxyModel(self)
        self.library_proxy.setSourceModel(self.library_model)
        self.library_proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.library_proxy.setFilterKeyColumn(-1)
        self.library_proxy.setDynamicSortFilter(True)
        self.thread_pool = QThreadPool.globalInstance()
        # Keep QRunnable wrappers alive until their queued result is delivered.
        self.metadata_workers: dict[str, MetadataWorker] = {}
        self.metadata_queue: deque[str] = deque()
        self.metadata_queued: set[str] = set()
        # Leave a thread available for folder discovery and cap memory usage on
        # large libraries instead of constructing one worker per file at once.
        self.max_metadata_workers = max(1, min(4, self.thread_pool.maxThreadCount() - 1))
        self.online_lookup_queue: deque[tuple[str, bool]] = deque()
        self.online_lookup_queued: set[str] = set()
        self.online_lookup_worker: Optional[OnlineLookupWorker] = None
        self.online_lookup_batch_total = 0
        self.online_lookup_batch_done = 0
        self.online_lookup_batch_applied = 0
        self.online_lookup_batch_failed = 0
        self.library_scan_worker: Optional[LibraryScanWorker] = None
        self.library_roots: list[str] = []
        app_data_value = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
        app_data = Path(app_data_value) if app_data_value else Path.home() / ".kaos-tunes"
        self.library_database_path = app_data / "music-library.json"
        self.metadata_cache_directory = app_data / "metadata-cache"
        self.library_save_timer = QTimer(self)
        self.library_save_timer.setSingleShot(True)
        self.library_save_timer.setInterval(2000)
        self.library_save_timer.timeout.connect(self._save_library_now)
        self.vlc_enabled = False
        self.vlc_adapter = None
        if self.settings.value("audio/backend", "qt") == "vlc":
            status = vlc_availability()
            if status.available:
                try:
                    from vlc_player_adapter import VLCPlayerAdapter
                    self.vlc_adapter = VLCPlayerAdapter(self)
                    self.vlc_enabled = True
                except Exception as exc:
                    logging.warning("VLC audio backend unavailable: %s", exc)
        if self.vlc_enabled:
            self.player = self.vlc_adapter
            self.audio = self.vlc_adapter.audio
            try:
                data = json.loads(str(self.settings.value("audio/equalizer", "{}")))
                self.vlc_adapter.engine.set_equalizer(EqualizerSettings.from_dict(data))
            except (ValueError, TypeError, RuntimeError, KeyError) as exc:
                logging.warning("Could not restore VLC equalizer: %s", exc)
        else:
            self.audio = QAudioOutput(self)
            self.player = QMediaPlayer(self)
            self.player.setAudioOutput(self.audio)
        self.playback_log_path = app_data / "playback.log"
        self.playback_logger = logging.Logger("kaostunes.playback")
        try:
            app_data.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                self.playback_log_path, maxBytes=256 * 1024, backupCount=2, encoding="utf-8"
            )
            handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            self.playback_logger.addHandler(handler)
        except OSError:
            self.playback_logger.addHandler(logging.NullHandler())
        self.playback_log_clock = QElapsedTimer()
        self.playback_log_clock.start()
        self.requested_source: Optional[QUrl] = None
        self.playback_start_timer = QTimer(self)
        self.playback_start_timer.setSingleShot(True)
        self.playback_start_timer.setInterval(0)
        self.playback_start_timer.timeout.connect(self._start_requested_playback)

        self.current_index = -1
        self.pending_seek = 0
        self.resume_path = ""
        self.seeking = False
        self.position_anchor = 0
        self.position_clock = QElapsedTimer()
        self.progress_timer = QTimer(self)
        self.progress_timer.setInterval(100)
        self.progress_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.progress_timer.timeout.connect(self._update_progress_display)
        self.shuffle_enabled = False
        self.shuffle_order: list[int] = []
        self.shuffle_cursor = -1
        self.repeat_mode = "off"
        self.sleep_at_track_end = False
        self.sleep_timer = QTimer(self)
        self.sleep_timer.setSingleShot(True)
        self.sleep_timer.timeout.connect(self._sleep_timer_fired)
        self.now_playing_path = str(self.settings.value("export/path", ""))
        self.export_enabled = self.settings.value("export/enabled", False, bool)

        self.pref_restore_queue = self.settings.value("preferences/restore_queue", True, bool)
        self.pref_resume_position = self.settings.value("preferences/resume_position", True, bool)
        self.pref_recursive_scan = self.settings.value("preferences/recursive_scan", True, bool)
        self.pref_confirm_clear = self.settings.value("preferences/confirm_clear", True, bool)
        self.pref_online_lookup = self.settings.value("preferences/online_lookup", True, bool)
        self.pref_online_replace_existing = self.settings.value(
            "preferences/online_replace_existing", False, bool
        )
        self.acoustid_client_key = str(self.settings.value("metadata/acoustid_client_key", ""))
        self.theme = str(self.settings.value("appearance/theme", "dark")).lower()

        self.setWindowTitle(APP_TITLE)
        icon_path = resource_path("PlaguesJukebox.png")
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setMinimumSize(900, 600)
        self.resize(1180, 760)
        self.setAcceptDrops(True)
        self._build_ui()
        self._build_actions()
        self._connect_player()
        self.progress_timer.start()
        self.apply_theme(self.theme)
        self._load_library_state()
        self._restore_state()

    def _standard_icon(self, pixmap: QStyle.StandardPixmap) -> QIcon:
        return self.style().standardIcon(pixmap)

    def _tool_button(self, icon: QStyle.StandardPixmap, tooltip: str, slot,
                     name: str = "Transport") -> QToolButton:
        button = QToolButton()
        button.setObjectName(name)
        button.setIcon(self._standard_icon(icon))
        button.setIconSize(button.iconSize() * 1.35)
        button.setToolTip(tooltip)
        button.clicked.connect(slot)
        return button

    def _build_ui(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(18, 14, 18, 12)
        outer.setSpacing(12)

        self.top_toolbar = QWidget()
        toolbar = QHBoxLayout(self.top_toolbar)
        toolbar.setContentsMargins(0, 0, 0, 0)
        brand = QLabel("PLAGUE’S JUKEBOX")
        brand.setObjectName("Eyebrow")
        brand.setFont(QFont("Arial", 13, 700))
        toolbar.addWidget(brand)
        toolbar.addStretch()
        folder_button = QPushButton("Add folder to queue")
        folder_button.clicked.connect(self.add_folder_dialog)
        add_button = QPushButton("＋  Add media")
        add_button.setObjectName("PrimaryButton")
        add_button.clicked.connect(self.add_files_dialog)
        toolbar.addWidget(folder_button)
        toolbar.addWidget(add_button)
        outer.addWidget(self.top_toolbar)

        self.main_splitter = splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        self.now_card = now_card = QFrame()
        now_card.setObjectName("Card")
        now_layout = QVBoxLayout(now_card)
        now_layout.setContentsMargins(18, 18, 18, 18)
        now_layout.setSpacing(10)
        eyebrow = QLabel("NOW PLAYING")
        eyebrow.setObjectName("Eyebrow")
        now_layout.addWidget(eyebrow)
        self.art_label = QLabel()
        self.art_label.setFixedSize(270, 270)
        self.art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.art_label.setPixmap(self._default_artwork(270))
        now_layout.addWidget(self.art_label, 0, Qt.AlignmentFlag.AlignHCenter)
        self.video_panel = VideoPanel(self, native_output=self.vlc_enabled)
        self.video_panel.fullscreen_requested.connect(self.toggle_fullscreen)
        self.video_button = self.video_panel.fullscreen_button
        self.video_button.setEnabled(False)
        self.video_panel.hide()
        self._video_split_sizes = [360, 220]
        self._fullscreen_snapshot = None
        self._window_state_before_fullscreen = Qt.WindowState.WindowNoState
        self.escape_fullscreen = QShortcut(QKeySequence("Escape"), self)
        self.escape_fullscreen.setEnabled(False)
        self.escape_fullscreen.activated.connect(self._leave_fullscreen)
        self.title_label = QLabel("Nothing playing")
        self.title_label.setObjectName("TrackTitle")
        self.title_label.setWordWrap(True)
        self.artist_label = QLabel("Add audio or video files, or drop a folder into the window")
        self.artist_label.setObjectName("TrackMeta")
        self.artist_label.setWordWrap(True)
        self.album_label = QLabel("")
        self.album_label.setObjectName("TrackMeta")
        self.album_label.setWordWrap(True)
        now_layout.addWidget(self.title_label)
        now_layout.addWidget(self.artist_label)
        now_layout.addWidget(self.album_label)
        now_layout.addStretch()
        mode_row = QHBoxLayout()
        self.shuffle_button = QPushButton("Shuffle: Off")
        self.shuffle_button.setCheckable(True)
        self.shuffle_button.clicked.connect(self.toggle_shuffle)
        self.repeat_button = QPushButton("Repeat: Off")
        self.repeat_button.clicked.connect(self.cycle_repeat)
        mode_row.addWidget(self.shuffle_button)
        mode_row.addWidget(self.repeat_button)
        now_layout.addLayout(mode_row)

        queue_card = QFrame()
        queue_card.setObjectName("Card")
        queue_layout = QVBoxLayout(queue_card)
        queue_layout.setContentsMargins(14, 14, 14, 14)
        queue_top = QHBoxLayout()
        queue_title = QLabel("PLAY QUEUE")
        queue_title.setObjectName("Eyebrow")
        self.queue_summary = QLabel("0 tracks")
        self.queue_summary.setObjectName("TrackMeta")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search title, artist, album…")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self.filter_queue)
        queue_top.addWidget(queue_title)
        queue_top.addWidget(self.queue_summary)
        queue_top.addStretch()
        queue_top.addWidget(self.search_box, 1)
        queue_layout.addLayout(queue_top)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().hide()
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(1, header.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 46)
        self.table.setColumnWidth(2, 170)
        self.table.setColumnWidth(3, 190)
        self.table.setColumnWidth(4, 82)
        self.table.doubleClicked.connect(self.play_proxy_index)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_queue_menu)
        queue_layout.addWidget(self.table)

        queue_buttons = QHBoxLayout()
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self.remove_selected)
        up_button = QPushButton("Move up")
        up_button.clicked.connect(lambda: self.move_selected(-1))
        down_button = QPushButton("Move down")
        down_button.clicked.connect(lambda: self.move_selected(1))
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.clear_queue)
        queue_buttons.addWidget(remove_button)
        queue_buttons.addWidget(up_button)
        queue_buttons.addWidget(down_button)
        queue_buttons.addStretch()
        queue_buttons.addWidget(clear_button)
        queue_layout.addLayout(queue_buttons)

        library_card = QFrame()
        library_card.setObjectName("Card")
        library_layout = QVBoxLayout(library_card)
        library_layout.setContentsMargins(14, 14, 14, 14)
        library_top = QHBoxLayout()
        library_title = QLabel("MEDIA LIBRARY")
        library_title.setObjectName("Eyebrow")
        self.library_summary = QLabel("0 tracks")
        self.library_summary.setObjectName("TrackMeta")
        self.library_search_box = QLineEdit()
        self.library_search_box.setPlaceholderText("Search library by title, artist, album…")
        self.library_search_box.setClearButtonEnabled(True)
        self.library_search_box.textChanged.connect(self.filter_library)
        library_top.addWidget(library_title)
        library_top.addWidget(self.library_summary)
        library_top.addStretch()
        library_top.addWidget(self.library_search_box, 1)
        library_layout.addLayout(library_top)

        self.library_table = QTableView()
        self.library_table.setModel(self.library_proxy)
        self.library_table.setAlternatingRowColors(True)
        self.library_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.library_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.library_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.library_table.setSortingEnabled(True)
        self.library_table.sortByColumn(1, Qt.SortOrder.AscendingOrder)
        self.library_table.verticalHeader().hide()
        library_header = self.library_table.horizontalHeader()
        library_header.setStretchLastSection(False)
        library_header.setSectionResizeMode(1, library_header.ResizeMode.Stretch)
        self.library_table.setColumnWidth(0, 46)
        self.library_table.setColumnWidth(2, 170)
        self.library_table.setColumnWidth(3, 190)
        self.library_table.setColumnWidth(4, 82)
        self.library_table.doubleClicked.connect(self.play_library_proxy_index)
        self.library_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.library_table.customContextMenuRequested.connect(self.show_library_menu)
        library_layout.addWidget(self.library_table)

        library_buttons = QHBoxLayout()
        add_library_folder_button = QPushButton("Add library folder")
        add_library_folder_button.setObjectName("PrimaryButton")
        add_library_folder_button.clicked.connect(self.add_library_folder_dialog)
        remove_library_folder_button = QPushButton("Remove folder")
        remove_library_folder_button.clicked.connect(self.remove_library_folder_dialog)
        self.rescan_library_button = QPushButton("Rescan library")
        self.rescan_library_button.clicked.connect(self.scan_library)
        identify_button = QPushButton("Find missing info")
        identify_button.clicked.connect(self.find_online_selected_metadata)
        add_selected_button = QPushButton("Add selected to queue")
        add_selected_button.clicked.connect(self.add_library_selected_to_queue)
        play_selected_button = QPushButton("Play now")
        play_selected_button.clicked.connect(self.play_library_selected)
        library_buttons.addWidget(add_library_folder_button)
        library_buttons.addWidget(remove_library_folder_button)
        library_buttons.addWidget(self.rescan_library_button)
        library_buttons.addWidget(identify_button)
        library_buttons.addStretch()
        library_buttons.addWidget(add_selected_button)
        library_buttons.addWidget(play_selected_button)
        library_layout.addLayout(library_buttons)

        self.content_tabs = QTabWidget()
        self.content_tabs.setDocumentMode(True)
        self.content_tabs.addTab(queue_card, "Play Queue")
        self.content_tabs.addTab(library_card, "Media Library")

        self.media_splitter = QSplitter(Qt.Orientation.Vertical)
        self.media_splitter.setChildrenCollapsible(False)
        self.media_splitter.addWidget(self.video_panel)
        self.media_splitter.addWidget(self.content_tabs)
        self.media_splitter.setStretchFactor(0, 3)
        self.media_splitter.setStretchFactor(1, 2)
        splitter.addWidget(now_card)
        splitter.addWidget(self.media_splitter)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 800])
        outer.addWidget(splitter, 1)

        self.transport_card = transport_card = QFrame()
        transport_card.setObjectName("Card")
        transport = QVBoxLayout(transport_card)
        transport.setContentsMargins(16, 10, 16, 10)
        seek_row = QHBoxLayout()
        self.elapsed_label = QLabel("0:00")
        self.elapsed_label.setObjectName("TimeLabel")
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderPressed.connect(self._seek_started)
        self.position_slider.sliderReleased.connect(self._seek_finished)
        self.position_slider.sliderMoved.connect(
            lambda value: self.elapsed_label.setText(format_time(value))
        )
        self.duration_label = QLabel("0:00")
        self.duration_label.setObjectName("TimeLabel")
        seek_row.addWidget(self.elapsed_label)
        seek_row.addWidget(self.position_slider, 1)
        seek_row.addWidget(self.duration_label)
        transport.addLayout(seek_row)

        controls = QHBoxLayout()
        controls.addStretch()
        self.previous_button = self._tool_button(
            QStyle.StandardPixmap.SP_MediaSkipBackward, "Previous (Ctrl+Left)", self.previous_track
        )
        self.play_button = self._tool_button(
            QStyle.StandardPixmap.SP_MediaPlay, "Play / Pause (Space)", self.toggle_playback, "PlayButton"
        )
        self.stop_button = self._tool_button(
            QStyle.StandardPixmap.SP_MediaStop, "Stop (Ctrl+.)", self.stop_playback
        )
        self.next_button = self._tool_button(
            QStyle.StandardPixmap.SP_MediaSkipForward, "Next (Ctrl+Right)", self.next_track
        )
        controls.addWidget(self.previous_button)
        controls.addWidget(self.play_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.next_button)
        controls.addStretch()
        self.mute_button = QPushButton("Mute")
        self.mute_button.setCheckable(True)
        self.mute_button.clicked.connect(self.toggle_mute)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setFixedWidth(120)
        self.volume_slider.valueChanged.connect(lambda value: self.audio.setVolume(value / 100.0))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5×", "0.75×", "1×", "1.25×", "1.5×", "2×"])
        self.speed_combo.setToolTip("Playback speed")
        self.speed_combo.currentTextChanged.connect(self.change_speed)
        controls.addWidget(self.mute_button)
        controls.addWidget(self.volume_slider)
        controls.addSpacing(10)
        controls.addWidget(QLabel("Speed"))
        controls.addWidget(self.speed_combo)
        transport.addLayout(controls)
        outer.addWidget(transport_card)
        self.setCentralWidget(central)
        self.player.setVideoOutput(self.video_panel.surface)
        self.statusBar().showMessage("Ready — drop audio, video, or folders anywhere in this window")

    def _build_actions(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        add_action = QAction("Add &media…", self, shortcut=QKeySequence.StandardKey.Open)
        add_action.triggered.connect(self.add_files_dialog)
        folder_action = QAction("Add &folder…", self, shortcut="Ctrl+Shift+O")
        folder_action.triggered.connect(self.add_folder_dialog)
        load_action = QAction("Open &playlist…", self, shortcut="Ctrl+Alt+O")
        load_action.triggered.connect(self.load_playlist_dialog)
        save_action = QAction("&Save playlist…", self, shortcut=QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_playlist_dialog)
        file_menu.addActions([add_action, folder_action])
        stream_action = QAction("Add internet stream…", self, shortcut="Ctrl+U")
        stream_action.triggered.connect(self.add_stream_dialog)
        gnb_action = QAction("Listen to Goodneighbor Blues", self)
        gnb_action.triggered.connect(lambda: self.add_stream(GNB_STREAM_URL, "Goodneighbor Blues"))
        file_menu.addActions([stream_action, gnb_action])
        file_menu.addSeparator()
        file_menu.addActions([load_action, save_action])
        file_menu.addSeparator()
        exit_action = QAction("E&xit", self, shortcut=QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        playback_menu = self.menuBar().addMenu("&Playback")
        play_action = QAction("Play / Pause", self, shortcut="Space")
        play_action.triggered.connect(self.toggle_playback)
        stop_action = QAction("Stop", self, shortcut="Ctrl+.")
        stop_action.triggered.connect(self.stop_playback)
        previous_action = QAction("Previous", self, shortcut="Ctrl+Left")
        previous_action.triggered.connect(self.previous_track)
        next_action = QAction("Next", self, shortcut="Ctrl+Right")
        next_action.triggered.connect(self.next_track)
        mute_action = QAction("Mute", self, shortcut="M")
        mute_action.triggered.connect(self.toggle_mute)
        playback_menu.addActions([play_action, stop_action, previous_action, next_action, mute_action])
        playback_menu.addSeparator()
        sleep_menu = playback_menu.addMenu("Sleep timer")
        for minutes in (15, 30, 45, 60, 90):
            action = QAction(f"{minutes} minutes", self)
            action.triggered.connect(lambda checked=False, m=minutes: self.set_sleep_timer(m))
            sleep_menu.addAction(action)
        end_action = QAction("At end of current track", self)
        end_action.triggered.connect(self.sleep_after_track)
        cancel_sleep_action = QAction("Cancel sleep timer", self)
        cancel_sleep_action.triggered.connect(self.cancel_sleep_timer)
        sleep_menu.addSeparator()
        sleep_menu.addAction(end_action)
        sleep_menu.addAction(cancel_sleep_action)

        library_menu = self.menuBar().addMenu("&Library")
        show_library_action = QAction("Show media library", self, shortcut="Ctrl+L")
        show_library_action.triggered.connect(lambda: self.content_tabs.setCurrentIndex(1))
        add_library_action = QAction("Add library folder…", self, shortcut="Ctrl+Shift+L")
        add_library_action.triggered.connect(self.add_library_folder_dialog)
        rescan_library_action = QAction("Rescan library", self, shortcut="F5")
        rescan_library_action.triggered.connect(self.scan_library)
        add_library_selection_action = QAction("Add selected to queue", self)
        add_library_selection_action.triggered.connect(self.add_library_selected_to_queue)
        play_library_selection_action = QAction("Play selected", self)
        play_library_selection_action.triggered.connect(self.play_library_selected)
        identify_library_action = QAction("Find missing song information online…", self)
        identify_library_action.triggered.connect(self.find_online_selected_metadata)
        remove_library_action = QAction("Remove library folder…", self)
        remove_library_action.triggered.connect(self.remove_library_folder_dialog)
        library_menu.addActions(
            [show_library_action, add_library_action, rescan_library_action]
        )
        library_menu.addSeparator()
        library_menu.addActions(
            [add_library_selection_action, play_library_selection_action, identify_library_action]
        )
        library_menu.addSeparator()
        library_menu.addAction(remove_library_action)

        tools_menu = self.menuBar().addMenu("&Tools")
        export_menu = tools_menu.addMenu("Now Playing text export")
        self.export_action = QAction("Enable export", self, checkable=True)
        self.export_action.setChecked(self.export_enabled)
        self.export_action.toggled.connect(self.set_export_enabled)
        choose_export_action = QAction("Choose text file…", self)
        choose_export_action.triggered.connect(self.choose_export_file)
        export_menu.addAction(self.export_action)
        export_menu.addAction(choose_export_action)
        equalizer_action = QAction("Audio equalizer…", self, shortcut="Ctrl+E")
        equalizer_action.triggered.connect(self.show_equalizer)
        tools_menu.addAction(equalizer_action)
        vlc_backend_action = QAction("Use VLC playback engine (restart required)", self)
        vlc_backend_action.setCheckable(True)
        vlc_backend_action.setChecked(self.settings.value("audio/backend", "qt") == "vlc")
        vlc_backend_action.triggered.connect(self._toggle_vlc_backend)
        tools_menu.addAction(vlc_backend_action)
        preferences_action = QAction("Preferences…", self)
        preferences_action.triggered.connect(self.show_preferences)
        media_info_action = QAction("Media information…", self, shortcut="Alt+Return")
        media_info_action.triggered.connect(lambda checked=False: self.show_media_information())
        refresh_metadata_action = QAction("Refresh selected metadata", self, shortcut="Ctrl+Alt+R")
        refresh_metadata_action.triggered.connect(
            lambda checked=False: self.refresh_visible_metadata()
        )
        online_metadata_action = QAction(
            "Find missing song information online…", self, shortcut="Ctrl+Alt+M"
        )
        online_metadata_action.triggered.connect(self.find_online_selected_metadata)
        tools_menu.addAction(media_info_action)
        tools_menu.addAction(refresh_metadata_action)
        tools_menu.addAction(online_metadata_action)
        tools_menu.addAction(preferences_action)

        view_menu = self.menuBar().addMenu("&View")
        theme_action = QAction("Toggle light / dark theme", self, shortcut="Ctrl+Shift+T")
        theme_action.triggered.connect(self.toggle_theme)
        fullscreen_action = QAction("Full screen", self, shortcut=QKeySequence.StandardKey.FullScreen)
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addActions([theme_action, fullscreen_action])

        help_menu = self.menuBar().addMenu("&Help")
        shortcuts_action = QAction("Keyboard shortcuts", self)
        shortcuts_action.triggered.connect(self.show_shortcuts)
        about_action = QAction(f"About {APP_NAME}", self)
        about_action.triggered.connect(self.show_about)
        playback_log_action = QAction("Open playback log", self)
        playback_log_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.playback_log_path)))
        )
        help_menu.addActions([shortcuts_action, playback_log_action, about_action])
        # Menu shortcuts are normally window-scoped. Explicit application scope
        # keeps them active when a queue, library, or docked control has focus.
        # QAction objects remain owned by their menus, preventing garbage collection.
        def register_menu_shortcuts(menu):
            for action in menu.actions():
                if action.menu() is not None:
                    register_menu_shortcuts(action.menu())
                elif not action.shortcut().isEmpty():
                    action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)

        for menu_action in self.menuBar().actions():
            if menu_action.menu() is not None:
                register_menu_shortcuts(menu_action.menu())

        # Keep QShortcut instances alive and give them explicit focus scopes.
        self.keyboard_shortcuts = []
        def add_shortcut(sequence, callback, parent, context):
            shortcut = QShortcut(QKeySequence(sequence), parent)
            shortcut.setContext(context)
            shortcut.activated.connect(callback)
            self.keyboard_shortcuts.append(shortcut)

        add_shortcut("Delete", self.remove_selected, self.table, Qt.ShortcutContext.WidgetWithChildrenShortcut)
        add_shortcut("Ctrl+Up", lambda: self.adjust_volume(5), self, Qt.ShortcutContext.WindowShortcut)
        add_shortcut("Ctrl+Down", lambda: self.adjust_volume(-5), self, Qt.ShortcutContext.WindowShortcut)

    def _connect_player(self) -> None:
        from stream_metadata import StationMetadata
        self.station_metadata = StationMetadata(self.player, self)
        self.station_metadata.updated.connect(self._stream_metadata_changed)
        if hasattr(self.player, "streamMetadataChanged"):
            self.player.streamMetadataChanged.connect(self._stream_metadata_changed)
        elif hasattr(self.player, "metaDataChanged"):
            self.player.metaDataChanged.connect(self._qt_stream_metadata_changed)
        self.player.positionChanged.connect(self._position_changed)
        self.player.durationChanged.connect(self._duration_changed)
        self.player.playbackStateChanged.connect(self._playback_state_changed)
        self.player.mediaStatusChanged.connect(self._media_status_changed)
        self.player.errorOccurred.connect(self._playback_error)
        self.player.sourceChanged.connect(lambda _: self._log_playback("source-changed"))
        self.player.sourceChanged.connect(
            lambda _: self._video_available_changed(getattr(self.player, "hasVideo", lambda: False)())
        )
        if hasattr(self.player, "hasVideoChanged"):
            self.player.hasVideoChanged.connect(self._video_available_changed)
        self.audio.mutedChanged.connect(lambda _: self._log_playback("mute-changed"))
        self.audio.volumeChanged.connect(lambda _: self._log_playback("volume-changed"))

    def _video_available_changed(self, available: bool) -> None:
        self.video_button.setEnabled(available)
        if available:
            was_hidden = self.video_panel.isHidden()
            self.video_panel.show()
            if was_hidden:
                self.media_splitter.setSizes(self._video_split_sizes)
        else:
            # Restore the normal layout before an audio track replaces a video.
            if self._fullscreen_snapshot is not None:
                self._leave_fullscreen()
            if not self.video_panel.isHidden():
                self._video_split_sizes = self.media_splitter.sizes()
            self.video_panel.hide()

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self._leave_fullscreen()
            return
        self._window_state_before_fullscreen = self.windowState()
        if self.video_button.isEnabled():
            # Keep the native video surface in place: reparenting it can destroy
            # VLC's output handle. Hide the surrounding panels instead.
            chrome = [self.top_toolbar, self.now_card, self.content_tabs,
                      self.menuBar(), self.statusBar()]
            self._fullscreen_snapshot = (
                [(widget, widget.isHidden()) for widget in chrome],
                self.main_splitter.sizes(), self.media_splitter.sizes(),
            )
            for widget in chrome:
                widget.hide()
        self.showFullScreen()
        self.video_button.setText("Leave full screen")
        self.escape_fullscreen.setEnabled(True)

    def _leave_fullscreen(self) -> None:
        if self.isFullScreen():
            self.setWindowState(self._window_state_before_fullscreen)
        self._restore_fullscreen_layout()

    def _restore_fullscreen_layout(self) -> None:
        if self._fullscreen_snapshot is not None:
            chrome, main_sizes, media_sizes = self._fullscreen_snapshot
            self._fullscreen_snapshot = None
            for widget, was_hidden in chrome:
                widget.setVisible(not was_hidden)
            self.main_splitter.setSizes(main_sizes)
            self.media_splitter.setSizes(media_sizes)
        self.video_button.setText("Full screen")
        self.escape_fullscreen.setEnabled(False)

    def changeEvent(self, event: QEvent) -> None:
        # The window manager can also leave full screen without our shortcut.
        if (event.type() == QEvent.Type.WindowStateChange
                and hasattr(self, "escape_fullscreen") and not self.isFullScreen()):
            self._restore_fullscreen_layout()
        super().changeEvent(event)

    def _log_playback(self, event: str, **details) -> None:
        snapshot = {
            "event": event, "version": APP_VERSION,
            "backend": os.environ.get("QT_MEDIA_BACKEND", "default"),
            "source": self.player.source().toString(),
            "requested_source": self.requested_source.toString() if self.requested_source else "",
            "state": self.player.playbackState().name,
            "status": self.player.mediaStatus().name,
            "position_ms": self.player.position(), "duration_ms": self.player.duration(),
            "display_ms": self._estimated_position(),
            "buffer_progress": self.player.bufferProgress(),
            "volume": self.audio.volume(), "muted": self.audio.isMuted(),
            "audio_device": self.audio.device().description(),
            "error": self.player.errorString(), **details,
        }
        self.playback_logger.info(json.dumps(snapshot, ensure_ascii=False))

    def _restore_state(self) -> None:
        geometry = self.settings.value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        volume = self.settings.value("playback/volume", 72, int)
        self.volume_slider.setValue(max(0, min(volume, 100)))
        self.shuffle_enabled = self.settings.value("playback/shuffle", False, bool)
        self.shuffle_button.setChecked(self.shuffle_enabled)
        self.shuffle_button.setText(f"Shuffle: {'On' if self.shuffle_enabled else 'Off'}")
        self.repeat_mode = str(self.settings.value("playback/repeat", "off"))
        if self.repeat_mode not in ("off", "all", "one"):
            self.repeat_mode = "off"
        self.repeat_button.setText(f"Repeat: {self.repeat_mode.title()}")
        speed = float(self.settings.value("playback/speed", 1.0))
        speed_text = f"{speed:g}×"
        if self.speed_combo.findText(speed_text) >= 0:
            self.speed_combo.setCurrentText(speed_text)
        if not self.pref_restore_queue:
            return
        raw = self.settings.value("queue/paths", "[]")
        try:
            paths = json.loads(str(raw))
        except (TypeError, json.JSONDecodeError):
            paths = []
        self.add_paths(
            (path for path in paths if is_remote_source(path) or os.path.isfile(path)),
            announce=False,
        )
        saved_path = str(self.settings.value("queue/current_path", ""))
        index = self._index_for_path(saved_path)
        if index >= 0:
            self.current_index = index
            self.model.set_current(index)
            self._select_source_row(index)
            self._show_track(self.model.tracks[index])
            # Restore the selection and pending position without opening the
            # decoder. QMediaPlayer is loaded only after the user presses Play.
            self.resume_path = self.model.tracks[index].path
            if self.pref_resume_position:
                self.pending_seek = self.settings.value("playback/position", 0, int)

    def _save_state(self) -> None:
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue("appearance/theme", self.theme)
        self.settings.setValue("playback/volume", self.volume_slider.value())
        self.settings.setValue("playback/speed", self.player.playbackRate())
        self.settings.setValue("playback/shuffle", self.shuffle_enabled)
        self.settings.setValue("playback/repeat", self.repeat_mode)
        saved_position = self.player.position()
        if self.player.source().isEmpty() and self.pending_seek and self.resume_path:
            saved_position = self.pending_seek
        self.settings.setValue("playback/position", saved_position)
        self.settings.setValue("queue/paths", json.dumps([track.path for track in self.model.tracks]))
        current_path = self.model.tracks[self.current_index].path \
            if 0 <= self.current_index < len(self.model.tracks) else ""
        self.settings.setValue("queue/current_path", current_path)
        self.settings.setValue("export/path", self.now_playing_path)
        self.settings.setValue("export/enabled", self.export_enabled)

    def _load_library_state(self) -> None:
        if not self.library_database_path.is_file():
            self._update_library_summary()
            return
        try:
            payload = json.loads(self.library_database_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise TypeError("The music library database is not a JSON object.")
            raw_roots = payload.get("folders", [])
            raw_tracks = payload.get("tracks", [])
            if not isinstance(raw_roots, list) or not isinstance(raw_tracks, list):
                raise TypeError("The music library database has an invalid structure.")

            roots: list[str] = []
            seen_roots: set[str] = set()
            for value in raw_roots:
                if not isinstance(value, str) or not value.strip():
                    continue
                root = str(Path(value).resolve(strict=False))
                key = canonical_path(root)
                if key not in seen_roots:
                    roots.append(root)
                    seen_roots.add(key)

            allowed_fields = set(Track.__dataclass_fields__) - {"cover_data"}
            tracks: list[Track] = []
            seen_tracks: set[str] = set()
            for record in raw_tracks:
                if not isinstance(record, dict) or not isinstance(record.get("path"), str):
                    continue
                values = {key: value for key, value in record.items() if key in allowed_fields}
                try:
                    track = Track(**values)
                except TypeError:
                    continue
                key = canonical_source(track.path)
                if key not in seen_tracks:
                    tracks.append(track)
                    seen_tracks.add(key)

            self.library_roots = roots
            self.library_model.replace_tracks(tracks)
            self._update_library_summary()
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self.statusBar().showMessage(f"Could not load the music library: {exc}", 9000)

    def _schedule_library_save(self) -> None:
        self.library_save_timer.start()

    def _save_library_now(self) -> None:
        payload = {
            "application": APP_NAME,
            "version": 1,
            "folders": self.library_roots,
            # Artwork bytes are intentionally re-read on demand rather than
            # inflating the persistent catalog by many megabytes per album.
            "tracks": [track.library_record() for track in self.library_model.tracks],
        }
        try:
            self.library_database_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.library_database_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(temporary, self.library_database_path)
        except OSError as exc:
            self.statusBar().showMessage(f"Could not save the music library: {exc}", 9000)

    def add_library_folder_dialog(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Add a music library folder", str(Path.home())
        )
        if not directory:
            return
        root = str(Path(directory).resolve())
        if any(path_is_within(root, existing) for existing in self.library_roots):
            self.content_tabs.setCurrentIndex(1)
            self.statusBar().showMessage("That folder is already covered by the music library", 5000)
            return

        # A newly selected parent supersedes any narrower roots below it.
        self.library_roots = [
            existing for existing in self.library_roots if not path_is_within(existing, root)
        ]
        self.library_roots.append(root)
        self.library_roots.sort(key=str.casefold)
        self.content_tabs.setCurrentIndex(1)
        self._schedule_library_save()
        self.scan_library()

    def remove_library_folder_dialog(self) -> None:
        if not self.library_roots:
            QMessageBox.information(
                self, "Music library", "No folders have been added to the music library."
            )
            return
        selected, accepted = QInputDialog.getItem(
            self,
            "Remove library folder",
            "Folder to remove (music files will not be deleted):",
            self.library_roots,
            0,
            False,
        )
        if not accepted or not selected:
            return
        answer = QMessageBox.question(
            self,
            "Remove library folder",
            f"Remove this folder and its tracks from the library?\n\n{selected}\n\n"
            "No music files will be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.library_roots = [root for root in self.library_roots if root != selected]
        tracks = [
            track
            for track in self.library_model.tracks
            if not path_is_within(track.path, selected)
            or any(path_is_within(track.path, root) for root in self.library_roots)
        ]
        self.library_model.replace_tracks(tracks)
        self._update_library_summary()
        self._schedule_library_save()
        self.statusBar().showMessage("Library folder removed; music files were left untouched", 5000)

    def scan_library(self) -> None:
        if self.library_scan_worker is not None:
            self.statusBar().showMessage("A music library scan is already running", 4000)
            return
        if not self.library_roots:
            QMessageBox.information(
                self,
                "Music library",
                "Add at least one music folder before scanning the library.",
            )
            return
        self.rescan_library_button.setEnabled(False)
        self.statusBar().showMessage("Scanning music library folders…")
        worker = LibraryScanWorker(self.library_roots)
        worker.signals.completed.connect(self._library_scan_finished)
        self.library_scan_worker = worker
        self.thread_pool.start(worker)

    def _library_scan_finished(self, result: object) -> None:
        self.library_scan_worker = None
        self.rescan_library_button.setEnabled(True)
        if not isinstance(result, dict):
            self.statusBar().showMessage("The music library scan returned an invalid result", 7000)
            return

        scanned_roots = [root for root in result.get("roots", []) if isinstance(root, str)]
        if {canonical_path(root) for root in scanned_roots} != {
            canonical_path(root) for root in self.library_roots
        }:
            self.statusBar().showMessage("Library folders changed; restarting the scan", 4000)
            QTimer.singleShot(0, self.scan_library)
            return

        paths = [path for path in result.get("paths", []) if isinstance(path, str)]
        missing_roots = [root for root in result.get("missing_roots", []) if isinstance(root, str)]
        errors = [error for error in result.get("errors", []) if isinstance(error, str)]
        existing = {canonical_source(track.path): track for track in self.library_model.tracks}
        scanned_keys = {canonical_source(path) for path in paths}
        preserved = [
            track
            for track in self.library_model.tracks
            if any(path_is_within(track.path, root) for root in missing_roots)
            and canonical_source(track.path) not in scanned_keys
        ]
        tracks = [existing.get(canonical_source(path), Track(path=path)) for path in paths]
        tracks.extend(preserved)
        tracks.sort(key=lambda track: canonical_source(track.path).casefold())
        self.library_model.replace_tracks(tracks)
        self._update_library_summary()
        self._schedule_library_save()

        for track in tracks:
            if canonical_source(track.path) in scanned_keys:
                self._start_metadata_scan(track.path)

        new_count = sum(1 for key in scanned_keys if key not in existing)
        removed_count = sum(
            1
            for key, track in existing.items()
            if key not in scanned_keys
            and not any(path_is_within(track.path, root) for root in missing_roots)
        )
        details = [f"{len(paths)} tracks found", f"{new_count} new", f"{removed_count} removed"]
        if missing_roots:
            details.append(f"{len(missing_roots)} folder{'s' if len(missing_roots) != 1 else ''} offline")
        if errors:
            details.append(f"{len(errors)} scan error{'s' if len(errors) != 1 else ''}")
        self.statusBar().showMessage("Library scan complete: " + ", ".join(details), 9000)

    def _update_library_summary(self) -> None:
        tracks = self.library_model.tracks
        artists = {track.artist.casefold() for track in tracks if track.artist}
        albums = {track.album.casefold() for track in tracks if track.album}
        total_ms = sum(track.duration_ms for track in tracks)
        bits = [f"{len(tracks)} track{'s' if len(tracks) != 1 else ''}"]
        if artists:
            bits.append(f"{len(artists)} artist{'s' if len(artists) != 1 else ''}")
        if albums:
            bits.append(f"{len(albums)} album{'s' if len(albums) != 1 else ''}")
        if total_ms:
            bits.append(format_time(total_ms))
        self.library_summary.setText(" • ".join(bits))

    def filter_library(self, text: str) -> None:
        self.library_proxy.setFilterFixedString(text)

    def _selected_library_rows(self) -> list[int]:
        rows = {
            self.library_proxy.mapToSource(index).row()
            for index in self.library_table.selectionModel().selectedRows()
        }
        return sorted(row for row in rows if row >= 0)

    def _queue_library_tracks(self, tracks: Iterable[Track]) -> tuple[int, int, int]:
        existing = {canonical_source(track.path): index for index, track in enumerate(self.model.tracks)}
        additions: list[Track] = []
        first_index = -1
        duplicates = 0
        missing = 0
        for library_track in tracks:
            if not os.path.isfile(library_track.path):
                missing += 1
                continue
            key = canonical_source(library_track.path)
            if key in existing:
                duplicates += 1
                if first_index < 0:
                    first_index = existing[key]
                continue
            if first_index < 0:
                first_index = len(self.model.tracks) + len(additions)
            existing[key] = len(self.model.tracks) + len(additions)
            clone = library_track.clone()
            if not clone.cover_data and (
                clone.musicbrainz_release_id or clone.musicbrainz_release_group_id
            ):
                clone.cover_data = load_cached_cover(
                    self.metadata_cache_directory,
                    clone.musicbrainz_release_id,
                    clone.musicbrainz_release_group_id,
                )
            additions.append(clone)

        self.model.add_tracks(additions)
        for track in additions:
            self._start_metadata_scan(track.path)
        if additions:
            self._queue_changed()
        return first_index, len(additions), missing + duplicates

    def add_library_selected_to_queue(self) -> None:
        rows = self._selected_library_rows()
        if not rows:
            self.statusBar().showMessage("Select one or more library tracks first", 4000)
            return
        tracks = [self.library_model.tracks[row] for row in rows]
        _, added, skipped = self._queue_library_tracks(tracks)
        message = f"Added {added} library track{'s' if added != 1 else ''} to the queue"
        if skipped:
            message += f"; skipped {skipped} missing or duplicate"
        self.statusBar().showMessage(message, 6000)

    def play_library_proxy_index(self, index: QModelIndex) -> None:
        self._log_playback("library-double-click")
        row = self.library_proxy.mapToSource(index).row()
        if 0 <= row < len(self.library_model.tracks):
            self._play_library_track(self.library_model.tracks[row])

    def play_library_selected(self) -> None:
        rows = self._selected_library_rows()
        if not rows:
            self.statusBar().showMessage("Select a library track to play", 4000)
            return
        self._play_library_track(self.library_model.tracks[rows[0]])

    def _play_library_track(self, track: Track) -> None:
        queue_index, _, _ = self._queue_library_tracks([track])
        if queue_index >= 0:
            self.play_index(queue_index)
        else:
            QMessageBox.warning(
                self, "Missing file", f"This library track can no longer be found:\n\n{track.path}"
            )

    def refresh_library_selected_metadata(self) -> None:
        rows = self._selected_library_rows()
        if not rows:
            return
        for row in rows:
            self._start_metadata_scan(self.library_model.tracks[row].path)
        self.statusBar().showMessage(
            f"Refreshing metadata for {len(rows)} library track{'s' if len(rows) != 1 else ''}",
            5000,
        )

    def refresh_visible_metadata(self) -> None:
        if self.content_tabs.currentIndex() == 1:
            self.refresh_library_selected_metadata()
        else:
            self.rescan_selected_metadata()

    def _selected_tracks_for_online_lookup(self) -> list[Track]:
        if self.content_tabs.currentIndex() == 1:
            rows = self._selected_library_rows()
            tracks = [self.library_model.tracks[row] for row in rows]
        else:
            rows = self._selected_source_rows()
            tracks = [self.model.tracks[row] for row in rows]
        unique: list[Track] = []
        seen: set[str] = set()
        for track in tracks:
            key = canonical_source(track.path)
            if key not in seen:
                unique.append(track)
                seen.add(key)
        return unique

    def find_online_selected_metadata(self) -> None:
        if not self.pref_online_lookup:
            QMessageBox.information(
                self,
                "Online metadata disabled",
                "Enable manual online metadata lookups in Tools > Preferences first.",
            )
            return
        if self.online_lookup_worker is not None or self.online_lookup_queue:
            self.statusBar().showMessage("An online metadata lookup is already running", 5000)
            return
        tracks = [
            track for track in self._selected_tracks_for_online_lookup()
            if not is_remote_source(track.path) and os.path.isfile(track.path)
        ]
        if not tracks:
            self.statusBar().showMessage(
                "Select one or more local tracks before looking up song information", 5000
            )
            return
        review_each = len(tracks) == 1
        if not review_each:
            mode = (
                "Existing values may be replaced."
                if self.pref_online_replace_existing
                else "Only missing values will be filled."
            )
            answer = QMessageBox.question(
                self,
                "Identify selected tracks",
                f"Look up information for {len(tracks)} selected tracks?\n\n{mode}\n"
                "High-confidence matches will be applied to the Plague’s Jukebox catalog. "
                "Audio files will not be modified.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self.online_lookup_batch_total = len(tracks)
        self.online_lookup_batch_done = 0
        self.online_lookup_batch_applied = 0
        self.online_lookup_batch_failed = 0
        for track in tracks:
            key = canonical_source(track.path)
            if key in self.online_lookup_queued:
                continue
            self.online_lookup_queue.append((track.path, review_each))
            self.online_lookup_queued.add(key)
        self.statusBar().showMessage(
            f"Looking up song information for {len(tracks)} track{'s' if len(tracks) != 1 else ''}…"
        )
        self._pump_online_lookup()

    def _track_for_path(self, path: str) -> Optional[Track]:
        wanted = canonical_source(path)
        for model in (self.library_model, self.model):
            for track in model.tracks:
                if canonical_source(track.path) == wanted:
                    return track
        return None

    def _pump_online_lookup(self) -> None:
        if self.online_lookup_worker is not None:
            return
        while self.online_lookup_queue:
            path, review = self.online_lookup_queue.popleft()
            self.online_lookup_queued.discard(canonical_source(path))
            track = self._track_for_path(path)
            if track is None or not os.path.isfile(path):
                self.online_lookup_batch_done += 1
                self.online_lookup_batch_failed += 1
                continue
            worker = OnlineLookupWorker(
                track, self.acoustid_client_key, self.metadata_cache_directory
            )
            worker.review_result = review
            worker.signals.result.connect(self._online_lookup_finished)
            self.online_lookup_worker = worker
            self.thread_pool.start(worker)
            return
        self._finish_online_lookup_batch()

    def _apply_online_result(
        self, result: OnlineMetadataResult, replace_existing: bool
    ) -> None:
        queue_row = self.model.apply_online_metadata(
            result, replace_existing=replace_existing, include_cover=True
        )
        library_row = self.library_model.apply_online_metadata(
            result, replace_existing=replace_existing, include_cover=False
        )
        if queue_row >= 0 and queue_row == self.current_index:
            self._show_track(self.model.tracks[queue_row])
        self._update_queue_summary()
        if library_row >= 0:
            self._update_library_summary()
            self._schedule_library_save()

    def _online_lookup_finished(self, result: object) -> None:
        worker = self.online_lookup_worker
        review = bool(getattr(worker, "review_result", False))
        self.online_lookup_worker = None
        self.online_lookup_batch_done += 1

        applied = False
        if not isinstance(result, OnlineMetadataResult):
            self.online_lookup_batch_failed += 1
        elif result.error or not result.has_metadata:
            self.online_lookup_batch_failed += 1
            if review:
                QMessageBox.warning(
                    self,
                    "Song information not found",
                    result.error or "No usable online match was found for this track.",
                )
        else:
            track = self._track_for_path(result.path)
            if track is None:
                self.online_lookup_batch_failed += 1
            elif review:
                dialog = OnlineMetadataDialog(self, track, result)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    self._apply_online_result(result, dialog.replace_existing.isChecked())
                    applied = True
            elif result.confidence >= 75.0:
                self._apply_online_result(result, self.pref_online_replace_existing)
                applied = True
            else:
                self.online_lookup_batch_failed += 1

        if applied:
            self.online_lookup_batch_applied += 1
        if self.online_lookup_queue:
            self.statusBar().showMessage(
                f"Online metadata: {self.online_lookup_batch_done} of "
                f"{self.online_lookup_batch_total} completed…"
            )
        self._pump_online_lookup()

    def _finish_online_lookup_batch(self) -> None:
        if not self.online_lookup_batch_total:
            return
        skipped = self.online_lookup_batch_total - self.online_lookup_batch_applied
        message = (
            f"Online metadata lookup complete: {self.online_lookup_batch_applied} applied"
        )
        if skipped:
            message += f", {skipped} not applied or not found"
        self.statusBar().showMessage(message, 10000)
        self.online_lookup_batch_total = 0

    def show_library_menu(self, position) -> None:
        index = self.library_table.indexAt(position)
        if not index.isValid():
            return
        selected_proxy_rows = {
            item.row() for item in self.library_table.selectionModel().selectedRows()
        }
        if index.row() not in selected_proxy_rows:
            self.library_table.clearSelection()
            self.library_table.selectRow(index.row())
        menu = QMenu(self)
        play_action = menu.addAction("Play now")
        queue_action = menu.addAction("Add to play queue")
        menu.addSeparator()
        info_action = menu.addAction("Media information…")
        refresh_action = menu.addAction("Refresh metadata")
        identify_action = menu.addAction("Find missing song information online…")
        reveal_action = menu.addAction("Show in file manager")
        copy_action = menu.addAction("Copy file path")
        chosen = menu.exec(self.library_table.viewport().mapToGlobal(position))
        rows = self._selected_library_rows()
        if chosen == play_action:
            self.play_library_selected()
        elif chosen == queue_action:
            self.add_library_selected_to_queue()
        elif chosen == info_action:
            self.show_media_information()
        elif chosen == refresh_action:
            self.refresh_library_selected_metadata()
        elif chosen == identify_action:
            self.find_online_selected_metadata()
        elif chosen == reveal_action and rows:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(Path(self.library_model.tracks[rows[0]].path).parent))
            )
        elif chosen == copy_action and rows:
            QApplication.clipboard().setText(self.library_model.tracks[rows[0]].path)

    def _default_artwork(self, size: int) -> QPixmap:
        branded_art = QPixmap(resource_path("PlaguesJukebox.png"))
        if not branded_art.isNull():
            return branded_art.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        # Code-drawn fallback in case the external asset is ever unavailable.
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        gradient = QLinearGradient(0, 0, size, size)
        gradient.setColorAt(0, QColor("#163d2b"))
        gradient.setColorAt(0.55, QColor("#151c22"))
        gradient.setColorAt(1, QColor("#32203c"))
        painter.fillRect(pixmap.rect(), gradient)
        painter.setPen(QColor("#58eaa1"))
        painter.setFont(QFont("Arial", max(32, size // 4), 800))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "PJ")
        painter.end()
        return pixmap

    def _cover_pixmap(self, data: bytes) -> QPixmap:
        pixmap = QPixmap()
        if data and pixmap.loadFromData(data):
            return pixmap.scaled(
                self.art_label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        return self._default_artwork(self.art_label.width())

    def add_stream(self, url: str, title: str = "") -> None:
        url = validate_stream_url(url)
        self.add_playlist_entries([PlaylistEntry(source=url, title=title)])
        index = self._index_for_path(url)
        if index >= 0:
            self.play_index(index)

    def add_stream_dialog(self) -> None:
        url, accepted = QInputDialog.getText(
            self, "Add internet stream", "HTTP or HTTPS stream URL (including HLS):"
        )
        if accepted and url.strip():
            try:
                self.add_stream(url)
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid stream URL", str(exc))

    def _stream_metadata_changed(self, title: str, artist: str = "") -> None:
        if not (0 <= self.current_index < len(self.model.tracks)):
            return
        track = self.model.tracks[self.current_index]
        if not is_remote_source(track.path) or not title:
            return
        track.title, track.artist = title, artist
        self._show_track(track)
        self._write_now_playing(track)
        self.model.dataChanged.emit(self.model.index(self.current_index, 0), self.model.index(self.current_index, self.model.columnCount()-1))

    def _qt_stream_metadata_changed(self) -> None:
        from PyQt6.QtMultimedia import QMediaMetaData
        data = self.player.metaData()
        self._stream_metadata_changed(data.stringValue(QMediaMetaData.Key.Title), data.stringValue(QMediaMetaData.Key.ContributingArtist))

    def add_files_dialog(self) -> None:
        patterns = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_EXTENSIONS))
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add media", str(Path.home()), f"Media files ({patterns});;All files (*)"
        )
        self.add_paths(paths)

    def add_folder_dialog(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Add a media folder", str(Path.home()))
        if directory:
            self.add_paths([directory])

    def _expand_paths(self, paths: Iterable[str]) -> list[str]:
        found: list[str] = []
        for raw_path in paths:
            if is_remote_source(raw_path):
                found.append(raw_path)
                continue
            path = Path(raw_path)
            if path.is_dir():
                iterator = path.rglob("*") if self.pref_recursive_scan else path.glob("*")
                found.extend(str(item.resolve()) for item in iterator
                             if item.is_file() and is_audio_file(item))
            elif path.is_file() and (is_audio_file(path) or path.suffix.lower() == ".m3u8"):
                found.append(str(path.resolve()))
        return sorted(found, key=lambda value: value.casefold())

    def add_paths(self, paths: Iterable[str], announce: bool = True) -> None:
        expanded = self._expand_paths(paths)
        existing = {canonical_source(track.path) for track in self.model.tracks}
        new_paths = [path for path in expanded if canonical_source(path) not in existing]
        self.model.add_tracks([Track(path=path) for path in new_paths])
        for path in new_paths:
            self._start_metadata_scan(path)
        self._queue_changed()
        if announce:
            duplicates = len(expanded) - len(new_paths)
            message = f"Added {len(new_paths)} track{'s' if len(new_paths) != 1 else ''}"
            if duplicates:
                message += f"; skipped {duplicates} duplicate{'s' if duplicates != 1 else ''}"
            self.statusBar().showMessage(message, 5000)

    def open_sources(self, sources: Iterable[str]) -> None:
        """Append an OS file-open request and play its first available entry."""
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.show()
        self.raise_()
        self.activateWindow()
        entries: list[PlaylistEntry] = []
        errors = []
        for source in sources:
            try:
                path = Path(source)
                if not is_remote_source(source) and path.suffix.lower() in {".json", ".m3u", ".m3u8"}:
                    playlist_entries = read_playlist_entries(source)
                    if not playlist_entries:
                        errors.append(f"{path.name}: the playlist is empty.")
                    entries.extend(playlist_entries)
                elif not is_remote_source(source) and path.is_dir():
                    entries.extend(PlaylistEntry(item) for item in self._expand_paths([source]))
                else:
                    entries.append(PlaylistEntry(source))
            except (OSError, UnicodeError, TypeError, ValueError, OverflowError) as exc:
                errors.append(f"{Path(source).name}: {exc}")

        if entries:
            self.add_playlist_entries(entries)
            first_index = next(
                (index for entry in entries
                 if (is_remote_source(entry.source) or os.path.isfile(entry.source))
                 and (index := self._index_for_path(entry.source)) >= 0),
                -1,
            )
            if first_index >= 0:
                self.search_box.clear()
                self.content_tabs.setCurrentIndex(0)
                # Explicit file opens start at the beginning, even if this was
                # the selected track saved by a previous session.
                self.pending_seek = 0
                self.resume_path = ""
                track = self.model.tracks[first_index]
                wanted = QUrl(track.path) if is_remote_source(track.path) else QUrl.fromLocalFile(track.path)
                if self.player.source() == wanted:
                    self.player.setPosition(0)
                self.play_index(first_index)
            else:
                errors.append("None of the selected files could be opened. Check their paths and formats.")
        if errors:
            QMessageBox.warning(self, "Could not open some files", "\n".join(errors))

    def add_playlist_entries(
        self, entries: Iterable[PlaylistEntry], announce: bool = True
    ) -> tuple[int, int, int]:
        """Add parsed playlist entries while preserving EXTINF metadata."""
        existing = {canonical_source(track.path) for track in self.model.tracks}
        tracks: list[Track] = []
        missing = 0
        unsupported = 0
        duplicates = 0

        for entry in entries:
            source = entry.source.strip()
            if not source:
                unsupported += 1
                continue
            key = canonical_source(source)
            if key in existing:
                duplicates += 1
                continue

            if is_remote_source(source):
                track = Track(
                    path=source,
                    title=entry.title,
                    duration_ms=entry.duration_ms,
                    codec="Network stream",
                )
            else:
                local_path = Path(source)
                if not local_path.is_file():
                    missing += 1
                    continue
                suffix = local_path.suffix.lower()
                if not is_audio_file(local_path) and suffix != ".m3u8":
                    unsupported += 1
                    continue
                track = Track(
                    path=str(local_path.resolve()),
                    title=entry.title,
                    duration_ms=entry.duration_ms,
                    codec="HLS stream" if suffix == ".m3u8" else "",
                )

            tracks.append(track)
            existing.add(key)

        self.model.add_tracks(tracks)
        for track in tracks:
            self._start_metadata_scan(track.path)
        self._queue_changed()

        if announce:
            details = []
            if missing:
                details.append(f"{missing} missing")
            if unsupported:
                details.append(f"{unsupported} unsupported")
            if duplicates:
                details.append(f"{duplicates} duplicate{'s' if duplicates != 1 else ''}")
            message = f"Loaded {len(tracks)} playlist entr{'ies' if len(tracks) != 1 else 'y'}"
            if details:
                message += "; skipped " + ", ".join(details)
            self.statusBar().showMessage(message, 7000)
        return len(tracks), missing, unsupported

    def _start_metadata_scan(self, path: str) -> None:
        if is_remote_source(path) or Path(path).suffix.lower() in {".m3u", ".m3u8"}:
            return
        key = canonical_source(path)
        if key in self.metadata_workers or key in self.metadata_queued:
            return
        self.metadata_queue.append(path)
        self.metadata_queued.add(key)
        self._pump_metadata_queue()

    def _pump_metadata_queue(self) -> None:
        while self.metadata_queue and len(self.metadata_workers) < self.max_metadata_workers:
            path = self.metadata_queue.popleft()
            key = canonical_source(path)
            self.metadata_queued.discard(key)
            if not os.path.isfile(path):
                continue
            worker = MetadataWorker(path)
            worker.signals.result.connect(self.metadata_loaded)
            self.metadata_workers[key] = worker
            self.thread_pool.start(worker)

    def rescan_selected_metadata(self) -> None:
        rows = self._selected_source_rows()
        if not rows:
            self.statusBar().showMessage("Select one or more tracks to refresh their metadata", 3000)
            return
        for row in rows:
            self._start_metadata_scan(self.model.tracks[row].path)
        self.statusBar().showMessage(
            f"Refreshing metadata for {len(rows)} track{'s' if len(rows) != 1 else ''}", 4000
        )

    def metadata_loaded(self, result: MetadataResult) -> None:
        self._log_playback("metadata-loaded", metadata_path=result.path)
        self.metadata_workers.pop(canonical_source(result.path), None)
        row = self.model.update_metadata(result)
        # The catalog stores tags and technical data, but not artwork bytes.
        # Retaining one embedded image per track caused unbounded memory growth
        # during large scans. Queue entries still receive their cover artwork.
        library_row = self.library_model.update_metadata(result, include_cover=False)
        if row >= 0 and row == self.current_index:
            self._show_track(self.model.tracks[row])
        self._update_queue_summary()
        if library_row >= 0:
            self._update_library_summary()
            self._schedule_library_save()
        if result.error:
            self.statusBar().showMessage(
                f"Metadata could not be read for {source_name(result.path)}: {result.error}", 8000
            )
        self._pump_metadata_queue()

    def _queue_changed(self) -> None:
        self._reset_shuffle_order()
        self._update_queue_summary()

    def _update_queue_summary(self) -> None:
        count = len(self.model.tracks)
        total_ms = sum(track.duration_ms for track in self.model.tracks)
        duration = f" • {format_time(total_ms)}" if total_ms else ""
        self.queue_summary.setText(f"{count} track{'s' if count != 1 else ''}{duration}")

    def filter_queue(self, text: str) -> None:
        self.proxy.setFilterFixedString(text)

    def _source_row_from_proxy(self, index: QModelIndex) -> int:
        return self.proxy.mapToSource(index).row()

    def _selected_source_rows(self) -> list[int]:
        rows = {self._source_row_from_proxy(index)
                for index in self.table.selectionModel().selectedRows()}
        return sorted(row for row in rows if row >= 0)

    def _select_source_row(self, row: int) -> None:
        source = self.model.index(row, 0)
        proxy_index = self.proxy.mapFromSource(source)
        if proxy_index.isValid():
            self.table.selectRow(proxy_index.row())
            self.table.scrollTo(proxy_index, QAbstractItemView.ScrollHint.EnsureVisible)

    def play_proxy_index(self, index: QModelIndex) -> None:
        self._log_playback("queue-double-click")
        self.play_index(self._source_row_from_proxy(index))

    def toggle_playback(self) -> None:
        self._log_playback("play-button")
        if self.requested_source is not None:
            self.stop_playback()
            return
        state = self.player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            return
        if state == QMediaPlayer.PlaybackState.PausedState and not self.player.source().isEmpty():
            self.player.play()
            return
        selected = self._selected_source_rows()
        index = selected[0] if selected else (self.current_index if self.current_index >= 0 else 0)
        if self.model.tracks:
            self.play_index(index)
        else:
            self.statusBar().showMessage("The play queue is empty", 4000)

    def play_index(self, index: int) -> None:
        if not (0 <= index < len(self.model.tracks)):
            return
        track = self.model.tracks[index]
        if not is_remote_source(track.path) and not os.path.isfile(track.path):
            QMessageBox.warning(self, "Missing file", f"This track can no longer be found:\n\n{track.path}")
            return
        self.current_index = index
        self.model.set_current(index)
        self._select_source_row(index)
        self._show_track(track)
        wanted = QUrl(track.path) if is_remote_source(track.path) else QUrl.fromLocalFile(track.path)
        if self.player.source() != wanted:
            if not self.resume_path or canonical_source(track.path) != canonical_source(self.resume_path):
                self.pending_seek = 0
        self.requested_source = wanted
        # Leave the view's double-click event before touching the decoder.
        # Restarting this single-shot timer also coalesces rapid activations.
        self.playback_start_timer.start()
        self._log_playback("play-request", track_path=track.path)
        self._sync_shuffle_cursor(index)
        self._write_now_playing(track)

    def _start_requested_playback(self) -> None:
        wanted = self.requested_source
        if wanted is None:
            return
        if self.player.source() != wanted:
            self.player.stop()
            self._set_position_anchor(0, running=False)
            self.resume_path = ""
            self.player.setSource(wanted)
        # setSource is asynchronous. Only the current, ready source may start.
        if self.player.source() != wanted or self.requested_source != wanted:
            return
        status = self.player.mediaStatus()
        if status in (
            QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia,
            QMediaPlayer.MediaStatus.BufferingMedia, QMediaPlayer.MediaStatus.EndOfMedia,
        ):
            self._apply_pending_seek()
            self.requested_source = None
            if status == QMediaPlayer.MediaStatus.EndOfMedia:
                self.player.setPosition(0)
            self._log_playback("play-start")
            self.player.play()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self.requested_source = None

    def _apply_pending_seek(self) -> None:
        if self.pending_seek:
            target = self.pending_seek
            # Consume first: seeking can synchronously emit another status.
            self.pending_seek = 0
            self.player.setPosition(target)
            self._set_position_anchor(target, running=False)

    def _cancel_play_request(self) -> None:
        self.playback_start_timer.stop()
        self.requested_source = None

    def _show_track(self, track: Track) -> None:
        if not track.cover_data and (
            track.musicbrainz_release_id or track.musicbrainz_release_group_id
        ):
            track.cover_data = load_cached_cover(
                self.metadata_cache_directory,
                track.musicbrainz_release_id,
                track.musicbrainz_release_group_id,
            )
        self.title_label.setText(track.display_title)
        self.artist_label.setText(track.artist or "Unknown artist")
        album_bits = [bit for bit in (track.album, track.year) if bit]
        if album_bits:
            source_detail = " • ".join(album_bits)
        elif is_remote_source(track.path):
            source_detail = urlparse(track.path).netloc or "Network stream"
        else:
            source_detail = Path(track.path).parent.name
        self.album_label.setText(source_detail)
        self.art_label.setPixmap(self._cover_pixmap(track.cover_data))
        self.video_panel.title_label.setText(track.display_title)
        self.setWindowTitle(f"{track.display_title} — {APP_NAME}")

    def stop_playback(self) -> None:
        self._cancel_play_request()
        self.player.stop()
        self._log_playback("stop")
        self._set_position_anchor(0, running=False)
        self.position_slider.setValue(0)
        self.elapsed_label.setText("0:00")

    def next_track(self, automatic: bool = False) -> None:
        if not self.model.tracks:
            return
        if automatic and self.repeat_mode == "one" and self.current_index >= 0:
            self.player.setPosition(0)
            self.player.play()
            return
        next_index = self._adjacent_index(1)
        if next_index is None:
            self.stop_playback()
            self.statusBar().showMessage("End of queue", 3000)
            return
        self.play_index(next_index)

    def previous_track(self) -> None:
        if not self.model.tracks:
            return
        if self.player.position() > 5000:
            self.player.setPosition(0)
            return
        previous = self._adjacent_index(-1)
        if previous is not None:
            self.play_index(previous)

    def _adjacent_index(self, direction: int) -> Optional[int]:
        count = len(self.model.tracks)
        if not count:
            return None
        if self.shuffle_enabled:
            if not self.shuffle_order:
                self._reset_shuffle_order()
            target = self.shuffle_cursor + direction
            if 0 <= target < len(self.shuffle_order):
                self.shuffle_cursor = target
                return self.shuffle_order[target]
            if direction > 0 and self.repeat_mode == "all":
                self._reset_shuffle_order(new_cycle=True)
                return self.shuffle_order[0] if self.shuffle_order else None
            if direction < 0 and self.repeat_mode == "all":
                self.shuffle_cursor = len(self.shuffle_order) - 1
                return self.shuffle_order[self.shuffle_cursor]
            return None
        current = self.current_index if self.current_index >= 0 else (-1 if direction > 0 else 0)
        target = current + direction
        if 0 <= target < count:
            return target
        if self.repeat_mode == "all":
            return 0 if direction > 0 else count - 1
        return None

    def _reset_shuffle_order(self, new_cycle: bool = False) -> None:
        count = len(self.model.tracks)
        order = list(range(count))
        random.shuffle(order)
        if 0 <= self.current_index < count and not new_cycle:
            order.remove(self.current_index)
            order.insert(0, self.current_index)
            self.shuffle_cursor = 0
        else:
            self.shuffle_cursor = 0 if new_cycle and order else -1
        self.shuffle_order = order

    def _sync_shuffle_cursor(self, index: int) -> None:
        if not self.shuffle_enabled:
            return
        if index not in self.shuffle_order:
            self._reset_shuffle_order()
        if index in self.shuffle_order:
            self.shuffle_cursor = self.shuffle_order.index(index)

    def toggle_shuffle(self, checked: bool) -> None:
        self.shuffle_enabled = checked
        self.shuffle_button.setText(f"Shuffle: {'On' if checked else 'Off'}")
        self._reset_shuffle_order()
        self.statusBar().showMessage(f"Shuffle {'enabled' if checked else 'disabled'}", 2500)

    def cycle_repeat(self) -> None:
        modes = ("off", "all", "one")
        self.repeat_mode = modes[(modes.index(self.repeat_mode) + 1) % len(modes)]
        self.repeat_button.setText(f"Repeat: {self.repeat_mode.title()}")
        self.statusBar().showMessage(f"Repeat {self.repeat_mode}", 2500)

    def remove_selected(self) -> None:
        rows = self._selected_source_rows()
        if not rows:
            return
        removing_current = self.current_index in rows
        before_current = sum(1 for row in rows if row < self.current_index)
        if removing_current:
            self.stop_playback()
            self.current_index = -1
            self.model.set_current(-1)
        elif self.current_index >= 0:
            self.current_index -= before_current
            self.model.set_current(self.current_index)
        self.model.remove_rows(rows)
        self._queue_changed()
        if not self.model.tracks:
            self._show_empty_state()

    def clear_queue(self, force: bool = False) -> None:
        if not self.model.tracks:
            return
        if not force and self.pref_confirm_clear:
            answer = QMessageBox.question(
                self, "Clear play queue", "Remove every track from the play queue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._cancel_play_request()
        self.player.stop()
        self.player.setSource(QUrl())
        self.pending_seek = 0
        self.resume_path = ""
        self.current_index = -1
        self.model.clear()
        self._queue_changed()
        self._show_empty_state()

    def _show_empty_state(self) -> None:
        self.title_label.setText("Nothing playing")
        self.artist_label.setText("Add audio or video files, or drop a folder into the window")
        self._video_available_changed(False)
        self.album_label.clear()
        self.art_label.setPixmap(self._default_artwork(self.art_label.width()))
        self.setWindowTitle(APP_TITLE)
        self._write_now_playing(None)

    def move_selected(self, offset: int) -> None:
        rows = self._selected_source_rows()
        if len(rows) != 1:
            self.statusBar().showMessage("Select one track to move", 2500)
            return
        source = rows[0]
        destination = max(0, min(source + offset, len(self.model.tracks) - 1))
        if source == destination:
            return
        current_path = self.model.tracks[self.current_index].path if self.current_index >= 0 else ""
        selected_path = self.model.tracks[source].path
        self.model.move(source, destination)
        self.current_index = self._index_for_path(current_path)
        self.model.set_current(self.current_index)
        self._select_source_row(self._index_for_path(selected_path))
        self._queue_changed()

    def move_selected_next(self) -> None:
        rows = self._selected_source_rows()
        if len(rows) != 1:
            return
        source = rows[0]
        destination = min(self.current_index + 1 if self.current_index >= 0 else 0,
                          len(self.model.tracks) - 1)
        current_path = self.model.tracks[self.current_index].path if self.current_index >= 0 else ""
        self.model.move(source, destination)
        self.current_index = self._index_for_path(current_path)
        self.model.set_current(self.current_index)
        self._queue_changed()

    def show_queue_menu(self, position) -> None:
        index = self.table.indexAt(position)
        if not index.isValid():
            return
        selected_proxy_rows = {item.row() for item in self.table.selectionModel().selectedRows()}
        if index.row() not in selected_proxy_rows:
            self.table.clearSelection()
            self.table.selectRow(index.row())
        menu = QMenu(self)
        play_action = menu.addAction("Play now")
        next_action = menu.addAction("Play next")
        menu.addSeparator()
        info_action = menu.addAction("Media information…")
        refresh_action = menu.addAction("Refresh metadata")
        identify_action = menu.addAction("Find missing song information online…")
        reveal_action = menu.addAction("Show in file manager")
        copy_action = menu.addAction("Copy file path")
        menu.addSeparator()
        remove_action = menu.addAction("Remove from queue")
        chosen = menu.exec(self.table.viewport().mapToGlobal(position))
        rows = self._selected_source_rows()
        if chosen == play_action and rows:
            self.play_index(rows[0])
        elif chosen == next_action:
            self.move_selected_next()
        elif chosen == info_action and rows:
            self.show_media_information(rows[0])
        elif chosen == refresh_action:
            self.rescan_selected_metadata()
        elif chosen == identify_action:
            self.find_online_selected_metadata()
        elif chosen == reveal_action and rows:
            source = self.model.tracks[rows[0]].path
            if is_remote_source(source):
                QDesktopServices.openUrl(QUrl(source))
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(source).parent)))
        elif chosen == copy_action and rows:
            QApplication.clipboard().setText(self.model.tracks[rows[0]].path)
        elif chosen == remove_action:
            self.remove_selected()

    def show_media_information(self, row: Optional[int] = None) -> None:
        track: Optional[Track] = None
        if row is None and self.content_tabs.currentIndex() == 1:
            library_rows = self._selected_library_rows()
            if not library_rows:
                self.statusBar().showMessage(
                    "Select a library track to view its media information", 3000
                )
                return
            track = self.library_model.tracks[library_rows[0]]
        if row is None:
            rows = self._selected_source_rows() if track is None else []
            if track is None and not rows:
                self.statusBar().showMessage("Select a track to view its media information", 3000)
                return
            if track is None:
                row = rows[0]
        if track is None:
            if row is None or not (0 <= row < len(self.model.tracks)):
                return
            track = self.model.tracks[row]

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Media Information — {track.display_title}")
        dialog.resize(620, 520)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        def add_field(label: str, value: object, fallback: str = "Not present") -> None:
            text = str(value).strip() if value not in (None, "", 0) else fallback
            widget = QLabel(text)
            widget.setWordWrap(True)
            widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(f"{label}:", widget)

        add_field("Title", track.title, source_name(track.path))
        add_field("Artist", track.artist)
        add_field("Album", track.album)
        add_field("Album artist", track.album_artist)
        add_field("Genre", track.genre)
        add_field("Composer", track.composer)
        add_field("Year/date", track.year)
        add_field("Track", track.track_number)
        add_field("Disc", track.disc_number)
        add_field("Comment", track.comment)
        add_field("Duration", format_time(track.duration_ms), "Unknown")
        add_field("Format/codec", track.codec, "Unknown")
        add_field("Bitrate", f"{track.bitrate / 1000:.0f} kbps" if track.bitrate else "", "Unknown")
        add_field(
            "Sample rate",
            f"{track.sample_rate / 1000:g} kHz" if track.sample_rate else "",
            "Unknown",
        )
        add_field("Channels", track.channels, "Unknown")
        add_field("Bit depth", f"{track.bits_per_sample}-bit" if track.bits_per_sample else "", "Unknown")
        add_field(
            "File size",
            f"{track.file_size / (1024 * 1024):.2f} MiB" if track.file_size else "",
            "Unknown",
        )
        add_field("Artwork", track.artwork_source or "None")
        add_field("Artwork data", f"{len(track.cover_data) / 1024:.1f} KiB" if track.cover_data else "None")
        if track.metadata_source:
            add_field("Online metadata source", track.metadata_source)
            add_field("Match confidence", f"{track.metadata_confidence:.0f}%")
        if track.musicbrainz_recording_id:
            add_field("MusicBrainz recording ID", track.musicbrainz_recording_id)
        if track.musicbrainz_release_id:
            add_field("MusicBrainz release ID", track.musicbrainz_release_id)
        add_field("File", track.path)
        if track.metadata_error:
            add_field("Metadata warning", track.metadata_error)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def save_playlist_dialog(self) -> None:
        if not self.model.tracks:
            QMessageBox.information(self, "Empty queue", "Add some tracks before saving a playlist.")
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self, "Save playlist", str(Path.home() / "Plague’s Jukebox Playlist.json"),
            "Plague’s Jukebox playlist (*.json);;M3U playlist (*.m3u8 *.m3u)",
        )
        if not path:
            return
        if "M3U" in selected_filter and Path(path).suffix.lower() not in (".m3u", ".m3u8"):
            path += ".m3u8"
        elif "*.json" in selected_filter and Path(path).suffix.lower() != ".json":
            path += ".json"
        try:
            if Path(path).suffix.lower() in (".m3u", ".m3u8"):
                lines = ["#EXTM3U"]
                for track in self.model.tracks:
                    seconds = track.duration_ms // 1000 if track.duration_ms else -1
                    label = f"{track.artist} - {track.display_title}" if track.artist else track.display_title
                    lines.extend((f"#EXTINF:{seconds},{label}", track.path))
                Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
            else:
                payload = {
                    "application": APP_NAME,
                    "version": 2,
                    "playlist": [track.path for track in self.model.tracks],
                }
                Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            self.statusBar().showMessage(f"Playlist saved to {path}", 5000)
        except OSError as exc:
            QMessageBox.critical(self, "Could not save playlist", str(exc))

    def load_playlist_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open playlist", str(Path.home()),
            "Playlists (*.json *.m3u *.m3u8);;All files (*)",
        )
        if not path:
            return
        try:
            entries = read_playlist_entries(path)
            if not entries:
                QMessageBox.information(
                    self, "Empty playlist", "This playlist does not contain any media entries."
                )
                return

            self.clear_queue(force=True)
            loaded, missing, unsupported = self.add_playlist_entries(entries)
            if not loaded and (missing or unsupported):
                QMessageBox.warning(
                    self,
                    "No playable entries",
                    "The playlist was read, but none of its entries could be added. "
                    "Check that local files still exist and use supported media formats.",
                )
        except (OSError, UnicodeError, TypeError, ValueError) as exc:
            QMessageBox.critical(self, "Could not open playlist", str(exc))

    def _position_changed(self, position: int) -> None:
        running = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        # Repeated identical positions are not evidence of decoder progress.
        if position != self.position_anchor or not self.position_clock.isValid():
            self._set_position_anchor(position, running=running)
        self._update_progress_display()

    def _duration_changed(self, duration: int) -> None:
        self.position_slider.setRange(0, max(0, duration))
        self.duration_label.setText(format_time(duration))
        self._update_progress_display()

    def _seek_started(self) -> None:
        self.seeking = True

    def _seek_finished(self) -> None:
        target = self.position_slider.value()
        self.player.setPosition(target)
        running = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self._set_position_anchor(target, running=running)
        self.seeking = False
        self._update_progress_display()

    def _set_position_anchor(self, position: int, running: Optional[bool] = None) -> None:
        self.position_anchor = max(0, int(position))
        if running is None:
            running = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        if running:
            self.position_clock.restart()
        else:
            self.position_clock.invalidate()

    def _estimated_position(self) -> int:
        position = self.position_anchor
        if (
            self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
            and self.position_clock.isValid()
        ):
            # Smooth between backend updates, but never invent ongoing playback
            # when Qt reports PlayingState while its position has stopped.
            if self.player.mediaStatus() != QMediaPlayer.MediaStatus.StalledMedia:
                position += int(min(self.position_clock.elapsed(), 500) * self.player.playbackRate())
        duration = self.player.duration()
        return max(0, min(position, duration)) if duration > 0 else max(0, position)

    def _update_progress_display(self) -> None:
        if self.playback_log_clock.elapsed() >= 1000:
            self.playback_log_clock.restart()
            if self.requested_source is not None or self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self._log_playback("progress")
        if self.seeking:
            return
        position = self._estimated_position()
        self.position_slider.setValue(position)
        self.elapsed_label.setText(format_time(position))

    def _playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        self._log_playback("state-changed", signal_state=state.name)
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self._set_position_anchor(self.player.position(), running=playing)
        self._update_progress_display()
        icon = QStyle.StandardPixmap.SP_MediaPause if playing else QStyle.StandardPixmap.SP_MediaPlay
        self.play_button.setIcon(self._standard_icon(icon))
        self.play_button.setToolTip("Pause (Space)" if playing else "Play (Space)")

    def _media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        self._log_playback("status-changed", signal_status=status.name)
        if self.requested_source is not None:
            if self.player.source() == self.requested_source and status in (
                QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia,
                QMediaPlayer.MediaStatus.BufferingMedia,
            ):
                self.playback_start_timer.start()
            return
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.sleep_at_track_end:
                self.stop_playback()
                self.cancel_sleep_timer()
            else:
                self.next_track(automatic=True)

    def _playback_error(self, error: QMediaPlayer.Error, error_text: str) -> None:
        if error == QMediaPlayer.Error.NoError:
            return
        self._cancel_play_request()
        self._log_playback("error", error_text=error_text)
        self.statusBar().showMessage(f"Playback error: {error_text}", 8000)
        QMessageBox.warning(
            self, "Playback error",
            "Could not play this source. For streams, check the URL, network connection, and station availability. For files, check access and codec support."
            f"\n\n{error_text}",
        )

    def change_speed(self, text: str) -> None:
        try:
            rate = float(text.rstrip("×x"))
        except ValueError:
            rate = 1.0
        position = self._estimated_position()
        self.player.setPlaybackRate(rate)
        self._set_position_anchor(position)

    def adjust_volume(self, amount: int) -> None:
        self.volume_slider.setValue(max(0, min(100, self.volume_slider.value() + amount)))

    def toggle_mute(self, checked: Optional[bool] = None) -> None:
        if checked is None:
            checked = not self.audio.isMuted()
        self.audio.setMuted(bool(checked))
        self.mute_button.setChecked(bool(checked))
        self.mute_button.setText("Unmute" if checked else "Mute")

    def set_sleep_timer(self, minutes: int) -> None:
        self.sleep_at_track_end = False
        self.sleep_timer.start(minutes * 60 * 1000)
        self.statusBar().showMessage(f"Sleep timer set for {minutes} minutes", 5000)

    def sleep_after_track(self) -> None:
        self.sleep_timer.stop()
        self.sleep_at_track_end = True
        self.statusBar().showMessage("Playback will stop at the end of this track", 5000)

    def cancel_sleep_timer(self) -> None:
        self.sleep_timer.stop()
        self.sleep_at_track_end = False
        self.statusBar().showMessage("Sleep timer cancelled", 3000)

    def _sleep_timer_fired(self) -> None:
        self.stop_playback()
        self.statusBar().showMessage("Sleep timer stopped playback", 5000)

    def choose_export_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Now Playing text file",
            self.now_playing_path or str(Path.home() / "now_playing.txt"),
            "Text files (*.txt);;All files (*)",
        )
        if path:
            if not Path(path).suffix:
                path += ".txt"
            self.now_playing_path = path
            self.export_enabled = True
            self.export_action.setChecked(True)
            track = self.model.tracks[self.current_index] \
                if 0 <= self.current_index < len(self.model.tracks) else None
            self._write_now_playing(track)
            self.statusBar().showMessage("Now Playing export enabled", 4000)

    def set_export_enabled(self, enabled: bool) -> None:
        if enabled and not self.now_playing_path:
            self.choose_export_file()
            return
        self.export_enabled = enabled
        if enabled and 0 <= self.current_index < len(self.model.tracks):
            self._write_now_playing(self.model.tracks[self.current_index])

    def _write_now_playing(self, track: Optional[Track]) -> None:
        if not self.export_enabled or not self.now_playing_path:
            return
        text = ""
        if track:
            text = f"{track.artist} — {track.display_title}" if track.artist else track.display_title
        try:
            Path(self.now_playing_path).write_text(text + ("\n" if text else ""), encoding="utf-8")
        except OSError as exc:
            self.statusBar().showMessage(f"Could not update Now Playing file: {exc}", 7000)

    def show_preferences(self) -> None:
        dialog = PreferencesDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.pref_restore_queue = dialog.restore_queue.isChecked()
        self.pref_resume_position = dialog.resume_position.isChecked()
        self.pref_recursive_scan = dialog.recursive_scan.isChecked()
        self.pref_confirm_clear = dialog.confirm_clear.isChecked()
        self.pref_online_lookup = dialog.online_lookup.isChecked()
        self.pref_online_replace_existing = dialog.batch_replace.isChecked()
        self.acoustid_client_key = dialog.acoustid_key.text().strip()
        self.settings.setValue("preferences/restore_queue", self.pref_restore_queue)
        self.settings.setValue("preferences/resume_position", self.pref_resume_position)
        self.settings.setValue("preferences/recursive_scan", self.pref_recursive_scan)
        self.settings.setValue("preferences/confirm_clear", self.pref_confirm_clear)
        self.settings.setValue("preferences/online_lookup", self.pref_online_lookup)
        self.settings.setValue(
            "preferences/online_replace_existing", self.pref_online_replace_existing
        )
        self.settings.setValue("metadata/acoustid_client_key", self.acoustid_client_key)
        self.apply_theme(dialog.theme.currentText().lower())

    def apply_theme(self, theme: str) -> None:
        self.theme = "light" if theme == "light" else "dark"
        QApplication.instance().setStyleSheet(LIGHT_STYLE if self.theme == "light" else DARK_STYLE)
        if self.current_index < 0:
            self.art_label.setPixmap(self._default_artwork(self.art_label.width()))

    def toggle_theme(self) -> None:
        self.apply_theme("light" if self.theme == "dark" else "dark")

    def _toggle_vlc_backend(self, enabled: bool) -> None:
        if enabled:
            status = vlc_availability()
            if not status.available:
                self.sender().setChecked(False)
                missing = ("not installed" in status.reason.lower()
                           or "could not be loaded" in status.reason.lower()
                           or "no module named" in status.reason.lower())
                if missing:
                    choice = QMessageBox.question(
                        self, "VLC installation required",
                        status.reason + "\\n\\nOpen the official VLC download page?",
                    )
                    if choice == QMessageBox.StandardButton.Yes:
                        QDesktopServices.openUrl(QUrl("https://www.videolan.org/vlc/download-windows.html"))
                else:
                    QMessageBox.warning(
                        self, "VLC initialization error",
                        status.reason + "\\n\\nThis may be an application compatibility issue. "
                        "Reinstalling VLC is not necessarily required.",
                    )
                return
        self.settings.setValue("audio/backend", "vlc" if enabled else "qt")
        QMessageBox.information(
            self, "Restart required",
            "Restart K-Tunes to switch audio engines. The existing Qt engine "
            "remains available as a fallback.",
        )

    def _apply_equalizer(self, state: EqualizerSettings) -> None:
        if self.vlc_enabled:
            try:
                self.vlc_adapter.engine.set_equalizer(state)
            except RuntimeError as exc:
                QMessageBox.warning(self, "Equalizer error", str(exc))

    def show_equalizer(self) -> None:
        dialog = EqualizerDialog(
            self.settings, self,
            apply_callback=self._apply_equalizer if self.vlc_enabled else None,
        )
        dialog.exec()

    def show_shortcuts(self) -> None:
        QMessageBox.information(
            self, "Keyboard shortcuts",
            "Space — Play / pause\n"
            "Ctrl+Left / Ctrl+Right — Previous / next\n"
            "Ctrl+Up / Ctrl+Down — Volume up / down\n"
            "M — Mute\nDelete — Remove selected tracks\n"
            "Ctrl+O — Add music\nCtrl+Shift+O — Add folder\n"
            "Ctrl+L — Show music library\nCtrl+Shift+L — Add library folder\n"
            "F5 — Rescan library\nCtrl+Alt+M — Find song information online\n"
            "Ctrl+S — Save playlist\n"
            "Ctrl+Shift+T — Toggle theme\nCtrl+E — Audio equalizer\nF11 — Full screen",
        )

    def show_about(self) -> None:
        metadata_status = "available" if MutagenFile is not None else "not installed"
        media_backend = os.environ.get("QT_MEDIA_BACKEND", "Qt default")
        fingerprint_status = fpcalc_status()
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<h2>{APP_NAME} {APP_VERSION}</h2>"
            "<p>A modern PyQt6 music player by Kaotick Jay.</p>"
            "<p>A persistent, searchable music library, asynchronous metadata and artwork scanning, "
            "drag-and-drop, searchable queues, "
            "JSON, M3U, M3U8, and HLS playlists, shuffle/repeat modes, a sleep timer, playback speed, "
            "session recovery, and OBS-friendly Now Playing export.</p>"
            f"<p><b>Mutagen metadata support:</b> {metadata_status}</p>"
            "<p><b>Online metadata:</b> MusicBrainz, AcoustID, and Cover Art Archive</p>"
            f"<p><b>Chromaprint fpcalc:</b> {fingerprint_status}</p>"
            f"<p><b>Qt media backend:</b> {media_backend}</p>"
            '<p><a href="https://github.com/kaotickj">github.com/kaotickj</a></p>',
        )

    def _index_for_path(self, path: str) -> int:
        if not path:
            return -1
        wanted = canonical_source(path)
        return next(
            (i for i, track in enumerate(self.model.tracks)
             if canonical_source(track.path) == wanted),
            -1,
        )

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        self.add_paths(paths)
        event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._leave_fullscreen()
        self._save_state()
        self.library_save_timer.stop()
        self._save_library_now()
        self._cancel_play_request()
        self.player.stop()
        self.video_panel.hide()
        self.station_metadata.close()
        if self.vlc_adapter is not None:
            self.vlc_adapter.close()
        self.progress_timer.stop()
        for handler in self.playback_logger.handlers[:]:
            self.playback_logger.removeHandler(handler)
            handler.close()
        event.accept()


def main() -> int:
    if sys.argv[1:] == ["--self-test"]:
        from runtime_smoke import run
        return run(MusicPlayer, ORGANIZATION, PROFILE_NAME, APP_NAME)
    app = QApplication(sys.argv)
    app.setApplicationName(PROFILE_NAME)
    app.setApplicationDisplayName(APP_TITLE)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORGANIZATION)
    icon_path = resource_path("PlaguesJukebox.png")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    app.setStyle("Fusion")
    bridge = None
    try:
        sources = normalize_open_sources(app.arguments()[1:])
        bridge = InstanceBridge(parent=app)
        if not bridge.start_or_forward(sources):
            return 0
    except (OSError, RuntimeError, ValueError) as exc:
        if bridge is not None:
            bridge.close()
        QMessageBox.critical(None, "Could not open Plague’s Jukebox", str(exc))
        return 1
    window = MusicPlayer()
    bridge.files_received.connect(window.open_sources, Qt.ConnectionType.QueuedConnection)
    app.aboutToQuit.connect(bridge.close)
    window.show()
    if sources:
        QTimer.singleShot(0, lambda: window.open_sources(sources))
    try:
        return app.exec()
    finally:
        bridge.close()


if __name__ == "__main__":
    raise SystemExit(main())
