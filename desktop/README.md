# Plague’s Jukebox desktop — 2.3.1

The PyQt6 desktop application plays music, video and internet radio. It provides
a persistent library, queues, JSON/M3U playlists, optional online metadata,
shuffle/repeat, playback speed, sleep timer, video panel and OBS Now Playing export.
An optional installed VLC backend adds the equalizer. See the [project README](../README.md)
for platform differences, network behavior, compatibility identifiers and licensing.

## Run from source

Use Python 3.10 or newer (CI uses Python 3.12), a virtual environment and the
platform's Qt runtime prerequisites:

```sh
cd desktop
python -m venv .venv
# Activate the environment using your platform's activation command.
python -m pip install -r requirements-build.txt
python playTunes.py
```

For VLC playback, install VLC/libVLC separately. The Linux build uses the installed
system library and matching plugins rather than bundling an incomplete VLC tree.
Settings and catalog storage retain the existing Kaos Tunes profile identity.

## Test

```sh
cd desktop
python -m unittest discover -s tests -v
```

GUI tests use Qt's offscreen platform. For a dedicated test environment set
`QT_QPA_PLATFORM=offscreen` and isolated home/config/data directories. The optional
packaged `--self-test` command creates its own temporary profile and does not play
audio. The repository includes the Windows fingerprint binary and its licenses
for packaging validation.

## Linux package

Install the Linux prerequisites listed in the workflow, including desktop-file-utils,
Qt GUI libraries and libVLC with its base plugins. With the build virtual environment
active, run:

```sh
cd desktop
bash build_linux_deb.sh
```

The package is written to `dist/linux/`. The source version remains 2.3.1. The
license-file packaging fix recorded in the project README passed a fresh local
build and package-content checks.

## Windows installer

Use Python 3.12, the build requirements and Inno Setup 6. Run `build_windows.bat`
from a developer command prompt. The dependency preparation script verifies the
fingerprint tool download. The existing CI workflow demonstrates the complete
PyInstaller, license collection and Inno Setup sequence. Its installer is not
Authenticode-signed. Existing Windows install and application identities are
retained even though the visible product name changes.

## Radio

Use File → Listen to Goodneighbor Blues, or File → Add internet stream (`Ctrl+U`).
Provide a direct HTTP/HTTPS media or HLS URL. Connection failures may indicate an
offline station, an invalid URL, unavailable networking or an unsupported format.
