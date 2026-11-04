"""Online metadata lookup support for Kaos Tunes.

The module deliberately uses only Python's standard library.  Chromaprint's
``fpcalc`` program runs as an isolated subprocess, so a decoder failure cannot
take down the PyQt GUI process.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


APP_USER_AGENT = "KaosTunes/2.3.1 (https://github.com/kaotickj)"
ACOUSTID_LOOKUP_URL = "https://api.acoustid.org/v2/lookup"
MUSICBRAINZ_API_URL = "https://musicbrainz.org/ws/2"
COVER_ART_API_URL = "https://coverartarchive.org"
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_COVER_BYTES = 16 * 1024 * 1024
NETWORK_TIMEOUT = 20

_musicbrainz_lock = threading.Lock()
_last_musicbrainz_request = 0.0


@dataclass
class OnlineMetadataResult:
    path: str
    title: str = ""
    artist: str = ""
    album: str = ""
    album_artist: str = ""
    genre: str = ""
    year: str = ""
    track_number: str = ""
    disc_number: str = ""
    recording_id: str = ""
    release_id: str = ""
    release_group_id: str = ""
    confidence: float = 0.0
    source: str = ""
    artwork_source: str = ""
    cover_data: bytes = b""
    cached: bool = False
    error: str = ""

    @property
    def has_metadata(self) -> bool:
        return any((self.title, self.artist, self.album, self.year, self.recording_id))


def locate_fpcalc() -> str:
    """Locate the bundled or system Chromaprint fpcalc executable."""
    executable = "fpcalc.exe" if sys.platform == "win32" else "fpcalc"
    base = Path(__file__).resolve().parent
    candidates = [
        Path(getattr(sys, "_MEIPASS", base)) / executable,
        base / executable,
        base / "vendor" / "fpcalc" / executable,
        Path(sys.prefix) / "share" / "kaos-tunes" / executable,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return shutil.which(executable) or ""


def fpcalc_status() -> str:
    path = locate_fpcalc()
    return path if path else "Not available"


def _hidden_process_options() -> dict[str, Any]:
    if sys.platform != "win32":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {
        "startupinfo": startupinfo,
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
    }


def calculate_fingerprint(path: str, timeout: int = 180) -> tuple[int, str]:
    """Return duration and fingerprint without decoding media in-process."""
    fpcalc = locate_fpcalc()
    if not fpcalc:
        raise RuntimeError("Chromaprint fpcalc is not installed or bundled.")
    completed = subprocess.run(
        [fpcalc, "-json", os.fspath(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        **_hidden_process_options(),
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(detail or f"fpcalc exited with status {completed.returncode}.")
    output = completed.stdout.strip()
    try:
        payload = json.loads(output)
        duration = int(round(float(payload.get("duration") or 0)))
        fingerprint = str(payload.get("fingerprint") or "").strip()
    except (TypeError, ValueError, json.JSONDecodeError):
        values: dict[str, str] = {}
        for line in output.splitlines():
            key, separator, value = line.partition("=")
            if separator:
                values[key.strip().lower()] = value.strip()
        try:
            duration = int(round(float(values.get("duration", "0"))))
        except ValueError:
            duration = 0
        fingerprint = values.get("fingerprint", "")
    if duration <= 0 or not fingerprint:
        raise RuntimeError("fpcalc did not return a usable audio fingerprint.")
    return duration, fingerprint


def _read_limited(response: Any, limit: int) -> bytes:
    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            if int(content_length) > limit:
                raise RuntimeError("The server response exceeded the safety limit.")
        except ValueError:
            pass
    data = response.read(limit + 1)
    if len(data) > limit:
        raise RuntimeError("The server response exceeded the safety limit.")
    return data


def _request_json(url: str, params: dict[str, Any], *, musicbrainz: bool = False) -> dict[str, Any]:
    global _last_musicbrainz_request
    if musicbrainz:
        with _musicbrainz_lock:
            delay = 1.05 - (time.monotonic() - _last_musicbrainz_request)
            if delay > 0:
                time.sleep(delay)
            result = _request_json(url, params, musicbrainz=False)
            _last_musicbrainz_request = time.monotonic()
            return result

    request = Request(
        f"{url}?{urlencode(params)}" if params else url,
        headers={"Accept": "application/json", "User-Agent": APP_USER_AGENT},
    )
    try:
        with urlopen(request, timeout=NETWORK_TIMEOUT) as response:
            data = _read_limited(response, MAX_JSON_BYTES)
    except HTTPError as exc:
        raise RuntimeError(f"Metadata service returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach the metadata service: {exc.reason}") from exc
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("The metadata service returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("The metadata service returned an unexpected response.")
    return payload


def _request_cover(url: str) -> bytes:
    request = Request(url, headers={"Accept": "image/*", "User-Agent": APP_USER_AGENT})
    try:
        with urlopen(request, timeout=NETWORK_TIMEOUT) as response:
            content_type = str(response.headers.get("Content-Type", "")).lower()
            if content_type and not content_type.startswith("image/"):
                return b""
            return _read_limited(response, MAX_COVER_BYTES)
    except (HTTPError, URLError, TimeoutError, RuntimeError):
        return b""


def _artist_credit(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    bits: list[str] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "")
        if not name and isinstance(entry.get("artist"), dict):
            name = str(entry["artist"].get("name") or "")
        if name:
            bits.append(name)
        joinphrase = str(entry.get("joinphrase") or "")
        if joinphrase:
            bits.append(joinphrase)
    return "".join(bits).strip()


def _genre_name(entity: dict[str, Any]) -> str:
    genres = entity.get("genres") or entity.get("tags") or []
    if not isinstance(genres, list):
        return ""
    usable = [item for item in genres if isinstance(item, dict) and item.get("name")]
    usable.sort(key=lambda item: int(item.get("count") or 0), reverse=True)
    return str(usable[0].get("name") or "").strip() if usable else ""


def _simplify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _choose_release(releases: Any, known_album: str = "") -> dict[str, Any]:
    if not isinstance(releases, list):
        return {}
    usable = [release for release in releases if isinstance(release, dict) and release.get("id")]
    if not usable:
        return {}
    wanted = _simplify(known_album)
    if wanted:
        exact = [release for release in usable if _simplify(str(release.get("title") or "")) == wanted]
        if exact:
            usable = exact
    official = [release for release in usable if str(release.get("status") or "").casefold() == "official"]
    if official:
        usable = official
    usable.sort(key=lambda release: (str(release.get("date") or "9999"), str(release.get("country") or "")))
    return usable[0]


def _recording_lookup(recording_id: str) -> dict[str, Any]:
    return _request_json(
        f"{MUSICBRAINZ_API_URL}/recording/{recording_id}",
        {"fmt": "json", "inc": "artist-credits+releases+release-groups+genres"},
        musicbrainz=True,
    )


def _release_lookup(release_id: str) -> dict[str, Any]:
    return _request_json(
        f"{MUSICBRAINZ_API_URL}/release/{release_id}",
        {"fmt": "json", "inc": "artist-credits+recordings+release-groups+genres"},
        musicbrainz=True,
    )


def _find_track_numbers(release: dict[str, Any], recording_id: str) -> tuple[str, str]:
    media = release.get("media")
    if not isinstance(media, list):
        return "", ""
    for medium in media:
        if not isinstance(medium, dict):
            continue
        tracks = medium.get("tracks")
        if not isinstance(tracks, list):
            continue
        for track in tracks:
            if not isinstance(track, dict):
                continue
            recording = track.get("recording")
            if isinstance(recording, dict) and str(recording.get("id") or "") == recording_id:
                return str(track.get("number") or track.get("position") or ""), str(
                    medium.get("position") or ""
                )
    return "", ""


def _musicbrainz_search(title: str, artist: str, duration_ms: int) -> tuple[str, float]:
    clauses: list[str] = []
    if title:
        escaped = title.replace('"', "")
        clauses.append(f'recording:"{escaped}"')
    if artist:
        escaped = artist.replace('"', "")
        clauses.append(f'artist:"{escaped}"')
    if duration_ms > 0:
        clauses.append(f"dur:{duration_ms}")
    query = " AND ".join(clauses)
    if not query:
        return "", 0.0
    payload = _request_json(
        f"{MUSICBRAINZ_API_URL}/recording/",
        {"fmt": "json", "query": query, "limit": 10},
        musicbrainz=True,
    )
    recordings = payload.get("recordings")
    if not isinstance(recordings, list) or not recordings:
        return "", 0.0
    best = recordings[0]
    if not isinstance(best, dict):
        return "", 0.0
    try:
        score = float(best.get("score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    return str(best.get("id") or ""), score


def _acoustid_recording(client_key: str, duration: int, fingerprint: str) -> tuple[str, float]:
    payload = _request_json(
        ACOUSTID_LOOKUP_URL,
        {
            "client": client_key,
            "duration": duration,
            "fingerprint": fingerprint,
            "meta": "recordings+releasegroups+compress",
            "format": "json",
        },
    )
    if payload.get("status") != "ok":
        error = payload.get("error")
        message = error.get("message") if isinstance(error, dict) else "lookup failed"
        raise RuntimeError(f"AcoustID lookup failed: {message}")
    results = payload.get("results")
    if not isinstance(results, list):
        return "", 0.0
    for result in sorted(
        (item for item in results if isinstance(item, dict)),
        key=lambda item: float(item.get("score") or 0),
        reverse=True,
    ):
        recordings = result.get("recordings")
        if isinstance(recordings, list) and recordings and isinstance(recordings[0], dict):
            return str(recordings[0].get("id") or ""), float(result.get("score") or 0) * 100.0
    return "", 0.0


def _filename_guess(path: str) -> tuple[str, str]:
    stem = Path(path).stem.replace("_", " ").strip()
    stem = re.sub(r"^\s*\d{1,3}\s*[-._)]\s*", "", stem)
    parts = re.split(r"\s+-\s+", stem, maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip(), parts[0].strip()
    return stem, ""


def _cache_key(path: str) -> str:
    try:
        stat = os.stat(path)
        identity = f"{os.path.abspath(path)}|{stat.st_size}|{stat.st_mtime_ns}"
    except OSError:
        identity = os.path.abspath(path)
    return hashlib.sha256(identity.encode("utf-8", errors="surrogatepass")).hexdigest()


def _load_cache(path: str, cache_directory: Path) -> OnlineMetadataResult | None:
    cache_path = cache_directory / f"{_cache_key(path)}.json"
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        allowed = set(OnlineMetadataResult.__dataclass_fields__) - {"cover_data"}
        values = {key: value for key, value in payload.items() if key in allowed}
        values["path"] = path
        values["cached"] = True
        result = OnlineMetadataResult(**values)
        result.cover_data = load_cached_cover(
            cache_directory, result.release_id, result.release_group_id
        )
        return result
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _save_cache(result: OnlineMetadataResult, cache_directory: Path) -> None:
    cache_directory.mkdir(parents=True, exist_ok=True)
    payload = asdict(result)
    payload.pop("cover_data", None)
    payload["cached"] = False
    temporary = cache_directory / f"{_cache_key(result.path)}.tmp"
    destination = temporary.with_suffix(".json")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, destination)


def _cover_cache_path(cache_directory: Path, release_id: str, release_group_id: str) -> Path | None:
    identifier = release_id or release_group_id
    kind = "release" if release_id else "release-group"
    return cache_directory / f"cover-{kind}-{identifier}.img" if identifier else None


def load_cached_cover(
    cache_directory: str | Path, release_id: str = "", release_group_id: str = ""
) -> bytes:
    path = _cover_cache_path(Path(cache_directory), release_id, release_group_id)
    if path is None:
        return b""
    try:
        data = path.read_bytes()
        return data if len(data) <= MAX_COVER_BYTES else b""
    except OSError:
        return b""


def _download_cover(
    cache_directory: Path, release_id: str, release_group_id: str
) -> tuple[bytes, str]:
    cached = load_cached_cover(cache_directory, release_id, release_group_id)
    if cached:
        return cached, "Cover Art Archive cache"
    requests: list[tuple[str, str]] = []
    if release_id:
        requests.append((f"{COVER_ART_API_URL}/release/{release_id}/front-500", "release"))
    if release_group_id:
        requests.append(
            (f"{COVER_ART_API_URL}/release-group/{release_group_id}/front-500", "release group")
        )
    for url, label in requests:
        data = _request_cover(url)
        if not data:
            continue
        cache_directory.mkdir(parents=True, exist_ok=True)
        destination = _cover_cache_path(cache_directory, release_id, release_group_id)
        if destination is not None:
            try:
                destination.write_bytes(data)
            except OSError:
                pass
        return data, f"Cover Art Archive ({label})"
    return b"", ""


def lookup_online_metadata(
    path: str,
    known: dict[str, Any],
    acoustid_client_key: str,
    cache_directory: str | Path,
    *,
    use_cache: bool = True,
) -> OnlineMetadataResult:
    """Identify one file and return a normalized, reviewable metadata result."""
    cache_directory = Path(cache_directory)
    if use_cache:
        cached = _load_cache(path, cache_directory)
        if cached is not None:
            return cached

    result = OnlineMetadataResult(path=path)
    recording_id = ""
    confidence = 0.0
    source = ""
    fingerprint_error = ""

    client_key = acoustid_client_key.strip()
    if client_key and locate_fpcalc():
        try:
            duration, fingerprint = calculate_fingerprint(path)
            recording_id, confidence = _acoustid_recording(client_key, duration, fingerprint)
            if recording_id:
                source = "AcoustID fingerprint and MusicBrainz"
        except Exception as exc:
            fingerprint_error = str(exc)

    title = str(known.get("title") or "").strip()
    artist = str(known.get("artist") or "").strip()
    if not title:
        title, guessed_artist = _filename_guess(path)
        artist = artist or guessed_artist
    duration_ms = int(known.get("duration_ms") or 0)
    if not recording_id:
        try:
            recording_id, confidence = _musicbrainz_search(title, artist, duration_ms)
            if recording_id:
                source = "MusicBrainz text search"
        except Exception as exc:
            result.error = str(exc)
            return result

    if not recording_id:
        suffix = f" Fingerprint detail: {fingerprint_error}" if fingerprint_error else ""
        result.error = "No confident MusicBrainz match was found." + suffix
        return result

    try:
        recording = _recording_lookup(recording_id)
        release_summary = _choose_release(recording.get("releases"), str(known.get("album") or ""))
        release_id = str(release_summary.get("id") or "")
        release_group = release_summary.get("release-group")
        release_group_id = (
            str(release_group.get("id") or "") if isinstance(release_group, dict) else ""
        )
        release = _release_lookup(release_id) if release_id else {}
        if isinstance(release.get("release-group"), dict):
            release_group_id = str(release["release-group"].get("id") or release_group_id)
        track_number, disc_number = _find_track_numbers(release, recording_id)
        result.title = str(recording.get("title") or "").strip()
        result.artist = _artist_credit(recording.get("artist-credit"))
        result.album = str(release.get("title") or release_summary.get("title") or "").strip()
        result.album_artist = _artist_credit(release.get("artist-credit"))
        result.genre = _genre_name(recording) or _genre_name(release)
        result.year = str(release.get("date") or release_summary.get("date") or "").strip()
        result.track_number = track_number
        result.disc_number = disc_number
        result.recording_id = recording_id
        result.release_id = release_id
        result.release_group_id = release_group_id
        result.confidence = max(0.0, min(float(confidence), 100.0))
        result.source = source
        result.cover_data, result.artwork_source = _download_cover(
            cache_directory, release_id, release_group_id
        )
        _save_cache(result, cache_directory)
        return result
    except Exception as exc:
        result.error = str(exc)
        return result
