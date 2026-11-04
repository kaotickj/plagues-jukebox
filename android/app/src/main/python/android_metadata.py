"""Android bridge to the unchanged KaosTunes 2.3.1 metadata engine."""
import base64
import json
from dataclasses import asdict
from pathlib import Path

from metadata_lookup import lookup_online_metadata


def lookup(track_json: str, cache_directory: str) -> str:
    track = json.loads(track_json)
    # Android supplies tags through MediaStore or MediaMetadataRetriever. Its
    # content URIs are identities, not filesystem paths. Do not run fpcalc.exe.
    result = lookup_online_metadata(
        track["uri"],
        {"title": track.get("title", ""), "artist": track.get("artist", ""),
         "album": track.get("album", ""), "duration_ms": track.get("duration", 0)},
        "", Path(cache_directory),
    )
    payload = asdict(result)
    payload["cover_data"] = base64.b64encode(result.cover_data).decode("ascii")
    return json.dumps(payload)


def merge_missing(track_json: str, result_json: str) -> str:
    track, result = json.loads(track_json), json.loads(result_json)
    for key in ("title", "artist", "album", "year", "genre"):
        if not str(track.get(key, "")).strip():
            track[key] = result.get(key, "")
    track["metadata_source"] = result.get("source", "")
    track["confidence"] = result.get("confidence", 0)
    return json.dumps(track)
