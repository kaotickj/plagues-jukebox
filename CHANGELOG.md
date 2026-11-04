# Changelog

## Plague’s Jukebox 2.3.1 — initial repository snapshot

Desktop source version remains 2.3.1. Android is 0.1.1, versionCode 3. This entry
records the initial Plague’s Jukebox snapshot rather than inventing a version bump.

### Changed in this snapshot

- Rebranded visible desktop and Android names and supplied the shared jukebox icon.
- Preserved existing desktop profile paths, Android application ID and preferences,
  and Windows installer identity to protect upgrade compatibility.
- Repaired Linux libVLC initialization by locating installed plugins and using the
  system VLC library instead of bundling a core without its plugin directory.
- Added direct Goodneighbor Blues listening and user-added HTTP/HTTPS stream actions.
- Added stream URL validation, clearer playback errors, live engine metadata and
  bounded GNB now-playing requests with cleanup.
- Enabled HTTP as well as HTTPS streams on Android, while retaining its existing
  queue, library, device music scan filters, document access and playback service.
- Added stream/runtime regression checks and an isolated packaged Linux smoke check.
- Updated build assets and documentation for the new name.
- Added Linux application/dependency license collection to the package recipe after
  verification found the earlier DEB omitted those files. A rebuilt package must
  pass content checks before publication.

### Features carried forward

The desktop baseline already integrated audio and video in one player and supported
Open With/file associations, single-instance file delivery, persistent libraries,
playlists, optional metadata lookup and OBS Now Playing export. Android already
provided Media3 audio playback, queue persistence and configurable device scan
filtering. These are retained features, not newly implemented in the rebrand.

### Verification and limits

The pre-packaging-fix source passed 75 desktop tests and Android unit tests, and
fresh Windows, Linux and release-signed Android CI builds completed. Android's
signing certificate matches the prior release. Linux playback was checked using
isolated/offscreen and dummy-output probes. No fresh physical Android-device or
Windows desktop run is claimed. Windows artifacts are not Authenticode-signed.
