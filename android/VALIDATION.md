# K-Tunes Android 0.1.1 validation

Performed on 2026-09-30.

- Gradle `assembleDebug testDebugUnitTest lintDebug`: passed.
- 23 Java tests passed: 12 music-filter tests, 5 catalog reconciliation tests
  and the existing 6 playlist tests. Coverage includes short songs, long voice
  recordings, system-sound flags, voicemail paths/names, exact duration boundaries,
  unknown duration, legacy URI migration, retained manual imports, retained
  corrected tags, duplicate prevention and unavailable rows.
- 3 Python metadata bridge tests passed; the original desktop engine is unchanged.
- Android lint: zero errors, 16 warnings. Warnings concern pinned dependencies,
  English strings, backup configuration and the exported media session service.
- APK ZIP integrity and v2 signature verification passed. The signing certificate
  exactly matches the delivered 0.1.0 APK, and the application ID is unchanged:
  `com.kaosium.kaostunes`. Version code 2, version name 0.1.1, minimum SDK 24,
  target SDK 35. Launcher label is `K-Tunes`.
- Both arm64-v8a and x86_64 runtimes are present. Updated branding, scanner policy,
  duration setting and origin persistence strings were confirmed in APK bytecode.

The new scanner and upgrade have not been run on a physical phone or emulator
in this revision. Android media flags and file names cannot identify every saved
voicemail: anonymous, misclassified files can still appear. The manual folder
import offers precise selection. See TESTING.md for phone checks.

APK SHA-256: `0dbefdfa58b9d1c25d862b208798e0690f2a06ee767221fec1d7c40edcd05248`.

## Historical 0.1.0 validation

The following emulator results belong to the previous APK, not the 0.1.1 scan changes.

# Android 0.1.0 validation (historical)

Performed on 2026-09-30.

- Gradle `assembleDebug`: passed. The delivered APK is a compiled Android app,
  with the Python runtime included, not a desktop build or source-only placeholder.
- Six Java playlist tests passed, including desktop path resolution, Unicode,
  unavailable entries and duplicate-filename ambiguity.
- Three Python tests passed, including content-URI handling, disabled Windows
  fingerprint execution, fill-missing behavior and desktop engine identity.
- Android lint: zero errors. Remaining warnings cover pinned older dependencies,
  English strings, backup configuration and the exported media session service.
- APK ZIP integrity and APK v2 signature verification passed. Package ID:
  `com.kaosium.kaostunes`, version 0.1.0, minimum SDK 24, target SDK 35.
- Both arm64-v8a and x86_64 native runtimes are present in the APK.

## Android 15 x86_64 emulator

The device smoke test passed (`ANDROID_SMOKE_OK`):

1. Main activity launched.
2. A generated 96 kHz stereo PCM WAV decoded and playback position advanced.
3. Pause held the actual player position.
4. Seeking and resuming succeeded.
5. Rapid queue track switching succeeded.
6. Playback continued after pressing Home.
7. The bundled Android Python runtime imported and executed the metadata bridge.

An initial device-test run had an exception in its cleanup code: the test
released MediaController on the instrumentation thread. The cleanup was moved
to the main thread and the complete test was rerun successfully.

The emulator used software CPU emulation and no host audio output. Tests verify
decoder progress and playback control, not audible output on a phone. A physical
arm64 device, document-provider permissions, battery behavior and live online
metadata service responses still require the checklist in TESTING.md.

The test instrumentation source is included under `app/src/androidTest`. To run
it with a connected Android 15 test device or emulator:

```sh
./gradlew connectedDebugAndroidTest
```

The test creates a temporary WAV in MediaStore and deletes it after the run.
It replaces and clears the test device's Kaos Tunes queue. Use a test installation.
