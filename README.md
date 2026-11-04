# Plague’s Jukebox

A local music, video and internet-radio player for Windows, Linux and Android,
by Kaotick Jay. Desktop and Android share metadata lookup code, with interfaces
and playback engines suited to each platform.

## Features and platform differences

| Capability | Windows / Linux desktop | Android |
| --- | --- | --- |
| Local music, library, queue and playlists | Yes | Yes; document picker, folders and device music scan |
| Video playback | Yes, inside the desktop player | No dedicated video interface |
| Internet radio | HTTP/HTTPS streams and HLS | HTTP/HTTPS streams and HLS |
| Goodneighbor Blues | Built-in listening action and live title feed | Built-in listening action and live title feed |
| Metadata lookup | MusicBrainz and Cover Art Archive; optional AcoustID fingerprinting | MusicBrainz and Cover Art Archive; no fingerprinting |
| Playback controls | Seek, volume, speed, shuffle/repeat and sleep timer | Seek, shuffle/repeat, notification and lock-screen controls |
| Equalizer | Optional installed VLC engine | No desktop equalizer interface |
| OBS Now Playing export | Yes | No |

Metadata edits affect the app catalog, not audio-file tags. Codec availability
varies with the playback engine and device. A stream must provide a supported
media format; a station's ordinary web page is not necessarily its stream URL.

## Versions and compatibility

This source snapshot is desktop **2.3.1** and Android **0.1.1 (versionCode 3)**.
The new name does not reset your existing library or settings.

Technical identifiers deliberately remain compatible with earlier installations:

- Android package: `com.kaosium.kaostunes`.
- Desktop profile: `Kaosium Interactive` / `Kaos Tunes`.
- Linux package/command: `kaos-tunes`; installation directory: `/opt/kaos-tunes`.
- Windows executable: `KaosTunes.exe` and the existing installer identity.

Some build and artifact filenames still contain KaosTunes or K-Tunes. The visible
application name and current icon are Plague’s Jukebox. Android upgrades also
require the same signing certificate and a compatible version code: do not
uninstall an existing app just to work around a signature mismatch.

## Install

**Windows:** run the Windows installer when a verified release is available.
The current workflow does **not** Authenticode-sign the Windows installer or EXE.
The optional VLC backend uses an independently installed VLC installation.

**Linux:** install the Debian/Ubuntu package with `sudo apt install ./<package>.deb`.
Its dependencies include system libVLC and VLC plugins. Start the application
from the menu or `kaos-tunes`. An older custom launcher earlier in `PATH` can
shadow the package's `/usr/bin/kaos-tunes`; use the menu or explicit package path.

**Android:** sideload the signed release APK on Android 7.0 or newer. The build
supports arm64-v8a and x86_64, not 32-bit ARM. Enable installation from your chosen
file manager/browser only as needed. The verified release APK uses the existing
Android signing identity; debug APKs generally cannot replace a release-signed
installation. No Google Play account is required for sideloading.

The public-source privacy audit is complete. Release artifacts are verified
separately before publication; their build provenance is documented with each release.

## Play radio

On desktop, choose **File → Listen to Goodneighbor Blues**, or **File → Add
internet stream** (`Ctrl+U`). On Android, use the equivalent actions under **More**.
User-added streams can be retained in the queue/playlists. Live metadata appears
when supplied by the engine; GNB also uses its public status feed.

## Network behavior

Local playback does not require an account. Selecting internet radio or another
remote source connects to that source. While GNB is playing, its public
now-playing endpoint is polled periodically. Optional metadata lookup connects
to MusicBrainz and Cover Art Archive; desktop fingerprint lookup can also use
AcoustID when configured. Build tools download dependencies from their upstream
repositories. This app does not promise zero third-party communication.

## Build and test

See [desktop build instructions](desktop/README.md) and
[Android build instructions](android/README.md). Build definitions are in
`ci/build-installers.yml`; they also include an additional macOS
job. This file is an inactive template: Actions is not configured in this new
repository yet because the current publishing credential cannot create workflow
files. No signing secrets have been migrated. CI builds are not a substitute for
testing on physical devices.

The current source passed desktop regression tests and Android unit tests.
Fresh Windows, Linux and signed Android CI builds were produced from the same
application source. No fresh physical Android-device or Windows desktop test is
claimed. The Linux app was previously checked offscreen with isolated settings,
and GNB audio decoding was checked using dummy outputs.

## License

The application source is [GPL-3.0](LICENSE). Bundled dependencies retain their
own licenses; see [third-party notices](desktop/THIRD_PARTY_NOTICES.txt),
`desktop/vendor/fpcalc/`, and `android/app/src/main/assets/licenses/`.

The Linux package recipe includes the application GPL text, Python package licenses,
and distribution copyright/common-license texts for bundled native libraries.
The corrected local package was rebuilt and inspected after the earlier CI DEB
was found to omit those files. That earlier incomplete DEB is not a release asset.
