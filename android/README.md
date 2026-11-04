# Plague’s Jukebox for Android

Version **0.1.1**, Android **versionCode 3**. This is the native Android music and
internet-radio port, using Media3 with the shared Python metadata module through
Chaquopy. It does not provide the desktop video interface, EQ, fingerprinting,
OBS export, sleep timer or desktop themes.

## Use

Android 7.0 or newer is required. Builds support arm64-v8a and x86_64.
Add files through the document picker, add a folder, or scan the device's music
index. Tap a track to play; hold it for queue, information and metadata actions.
The library and queue persist. Background playback uses a foreground media
service with notification and lock-screen controls. Codec support varies by device.

More → Add internet stream accepts HTTP/HTTPS direct media and HLS URLs.
More → Listen to Goodneighbor Blues adds the built-in station. Network metadata
updates when supplied by the playback engine or GNB's public status feed.
More also imports JSON/M3U playlists and exports the queue as JSON. Device music
scan filters are heuristic; explicit folder/document imports give more control.
Catalog metadata edits do not rewrite the original audio files.

## Build locally

Use JDK 17, Python 3.12, Android SDK platform 35 and build-tools 35.0.0.
Configure your local SDK location without committing `local.properties`, then:

```sh
cd android
chmod +x gradlew
./gradlew --no-daemon testDebugUnitTest assembleDebug
python -m unittest discover -s tests -v
./gradlew --no-daemon assembleRelease
```

The release output is unsigned unless an authorized existing signing configuration
is supplied. The verified release pipeline uses its existing signing identity;
keys and passwords are not part of this snapshot. Do not paste signing passwords
into chat, source files or command history, or generate a replacement identity
as a routine build step. Debug signing is for development and is not equivalent
to the release certificate.

## Upgrade compatibility

`com.kaosium.kaostunes` and the `kaostunes` preferences namespace remain unchanged.
A data-preserving update requires the same signing certificate as the installed
app. Do not uninstall to work around a mismatch. Legacy K-Tunes artifact names
remain in the existing workflow. No fresh physical-device test is claimed for
this snapshot; historical emulator results are explicitly labeled in their files.

See the [project README](../README.md) for network behavior and source licensing.
Android dependency notices and license texts are under `app/src/main/assets/`.
