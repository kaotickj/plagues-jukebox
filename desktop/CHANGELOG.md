# Changelog

## Unreleased

- Integrated audio and video in one player window, with a resizable video area
  above the queue and a single set of transport controls. Full screen stays in
  the same window; Esc or switching to audio restores the normal layout.
- Added video playback through the Qt Multimedia and optional VLC backends.
- Added Windows and Linux Open With registration for supported audio/video files and
  M3U/M3U8 playlists, preserving the user's current default applications.
- Added command-line file opening and forwarding to an already running player.
- Added regression checks for external file requests and installer associations.

## 2.3.1, 2026-09-29

- Deferred track activation until the table's double-click event has finished.
- Waited for the requested Qt media source to load before starting playback.
- Coalesced rapid track activations and canceled pending starts on Stop or Clear.
- Consumed saved-position seeks before calling Qt, preventing reentrant seeking.
- Limited seek display interpolation to 500 ms beyond the last backend position.
- Added a rotating local playback log, accessible through Help > Open playback log.
- Added deterministic playback regression tests. Metadata scanning and online
  identification remain available.

## 2.3.0, 2026-09-29

- Added manual MusicBrainz metadata lookup for selected queue and library tracks.
- Added optional AcoustID audio-fingerprint identification.
- Added Cover Art Archive artwork retrieval and a persistent metadata cache.
- Added single-track review before applying online results.
- Added confidence-gated batch lookup that fills missing values by default.
- Kept online results inside the Kaos Tunes catalog without modifying audio files.
- Isolated Chromaprint decoding in an `fpcalc` subprocess to protect the GUI.
- Bundled the verified Chromaprint 1.6.1 Windows executable and license files.
- Updated application and Windows version information to 2.3.0.
- Added repeatable GUI, library scan, metadata workflow, and packaging tests.
- Added automatic collection of runtime license files for Windows builds.

