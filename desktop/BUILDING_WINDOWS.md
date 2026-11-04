# Building Kaos Tunes for Windows

Kaos Tunes 2.3.1 builds as a single, windowed `KaosTunes.exe` with its own
application icon, Windows version metadata, Python runtime, PyQt6, Qt
Multimedia backend, Mutagen metadata readers, and Chromaprint `fpcalc.exe`.

## PyCharm build

1. Open the KaosTunes project in PyCharm.
2. Confirm the project interpreter is `venv\Scripts\python.exe` or
   `.venv\Scripts\python.exe`.
3. Open PyCharm's Terminal in the project directory.
4. Run:

   ```powershell
   .\build_windows.bat
   ```

The build first downloads the official 64-bit Windows Chromaprint 1.6.1
package and verifies its pinned SHA-256 checksum. The completed application
will be written to:

```text
dist\KaosTunes.exe
```

## Manual equivalent

```powershell
python -m pip install -r requirements-build.txt
powershell -NoProfile -ExecutionPolicy Bypass -File .\prepare_dependencies.ps1
python -m PyInstaller --clean --noconfirm KaosTunes.spec
```

PyInstaller is platform-specific. Run this build on Windows to create the
Windows executable. Build artifacts in `build\` and `dist\` may be deleted at
any time and regenerated with the batch file.

## Distribution notes

- `KaosTunes.exe` is a one-file, GUI-only executable and does not open a console.
- The executable contains the redistributable Python, Qt, Mutagen, and
  Chromaprint components needed for metadata reading and fingerprinting.
- An AcoustID application client key is not a dependency and is not embedded.
  Users who want fingerprint matching enter their own key in Preferences.
- `THIRD_PARTY_NOTICES.txt` documents the bundled components and licensing.
- Runtime license texts for Python, PyQt6, Qt 6, SIP, Mutagen, PyInstaller,
  and Chromaprint are copied to `dist\licenses` by the build script.
- The executable is not code-signed. Windows SmartScreen may warn users until
  it is signed with a trusted Authenticode certificate or develops reputation.
- Test MP3, FLAC, WAV, OGG, M4A, and AAC playback on the Windows computer used
  for the release before distributing it.
- Test 44.1 kHz, 48 kHz, and 96 kHz PCM WAV files. Kaos Tunes uses Qt's native
  Windows backend by default because the FFmpeg backend can terminate natively
  on some high-sample-rate WAV files.
- Test both ordinary M3U8 track lists and HLS `.m3u8` streams because playback
  support depends on the codecs and Qt Multimedia backend available on that PC.
