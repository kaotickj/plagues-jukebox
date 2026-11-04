# Kaos Tunes 2.3.1 Testing Guide

## Test the double-click patch first

Extract this archive into a fresh project folder, use your existing PyCharm
Python environment with the dependencies installed, and run `playTunes.py`.
An executable rebuild is unnecessary for this first test.

1. In the play queue, select a WAV and press Play. Listen for at least 30 seconds.
2. Stop, then double-click the same WAV. Listen for at least 30 seconds.
3. Repeat from the Music Library, including a track not yet in the queue.
4. While audio is playing, double-click a different song. Try several quick
   track changes, and repeat with a sorted or filtered table.
5. Check pause/resume, seeking, Stop during loading, and restored playback position.

If audio drops out, choose **Help > Open playback log**. Keep the log and note
which table you used, the file type and sample rate, and whether Play-button
playback worked. The log records actual Qt position, display position, media
status, source, mute, volume, and audio device. It stays local and rotates at
256 KiB with two backups. It includes song paths and device names.

The regression suite exercises playback control using deterministic Qt signals.
It cannot establish whether the native Windows audio backend remains audible
on a particular device. This release is a candidate fix awaiting that check.

## Automated checks in PyCharm

1. Open the extracted project folder in PyCharm.
2. Select a 64-bit Python 3.10 or newer virtual environment.
3. Open PyCharm's Terminal and run:

   ```powershell
   python -m pip install -r requirements-build.txt
   python -m unittest discover -s tests -v
   ```

All tests should report `OK`. Qt may print an audio-backend diagnostic on a
computer without an audio device. That is not a test failure.

## Source-run checklist

Run `python playTunes.py`, then verify:

- The window opens with the Kaos Tunes icon and fallback artwork.
- MP3, FLAC, OGG, M4A, AAC, and WAV files can be added and played.
- Title, artist, album, duration, codec, bitrate, sample rate, channels, file
  size, and embedded artwork appear in Media Information.
- A 96 kHz PCM WAV file plays without closing the application.
- The elapsed-time label and seek slider stay aligned during play, pause,
  resume, and manual seeking.
- Standard M3U and UTF-8 M3U8 playlists load relative and absolute entries.
- HLS M3U8 manifests open as streams when the Windows media backend supports
  the stream codecs.
- Adding and rescanning a library folder finds audio in subfolders, leaves the
  interface responsive, and preserves entries for temporarily offline drives.
- Library search, sorting, double-click playback, and adding selections to the
  queue work as expected.
- Online lookup previews a single result, fills missing fields, retrieves cover
  art when available, and does not modify the source audio file.
- Closing and reopening restores the configured library and queue according to
  Preferences.

## Windows executable checklist

Build on Windows from PyCharm's Terminal:

```powershell
.\build_windows.bat
```

Then test `dist\KaosTunes.exe` on a Windows account that does not have Python,
PyQt6, Mutagen, or Chromaprint installed:

- The application starts without a console window.
- Windows Properties shows product version 2.3.1 and the Kaosium Interactive
  product information.
- The executable and taskbar use the Kaos Tunes icon.
- Playback, library scanning, embedded tags, artwork, playlists, and online
  lookup pass the source-run checklist.
- `dist\THIRD_PARTY_NOTICES.txt` and the component files under
  `dist\licenses` are present.

The executable is not code-signed, so Windows SmartScreen can display a warning
on a newly built file. Record the Windows version, audio format, sample rate,
and exact steps if a playback or scanning failure occurs.

## File-manager Open With checks

The automated suite verifies the registered extensions, command quoting,
desktop-entry MIME types and Linux package contents. It also exercises startup
file requests and forwarding to a running player. Run the checks above, then
verify each target operating system's shell integration on that system.

### Windows installer

1. Build the executable and compile `installer.iss` with Inno Setup 6. Install
   the generated setup program as a normal user.
2. Right-click MP3, WAV, FLAC, OGG, Opus, M4A, MP4, AAC, WMA and AIFF files,
   then choose **Open with > Kaos Tunes**. Also check M3U and M3U8 playlists.
   Confirm the previous default player is unchanged.
   Repeat with video containers such as MKV, WebM, MOV, AVI and MPEG.
3. Test a path containing spaces and Unicode characters. Test a selection of
   multiple tracks, including while Kaos Tunes is already open; confirm one
   player window receives the requests and the requested audio starts.
4. Launch an M3U8 playlist containing relative paths. Confirm the queue follows
   playlist order; test an HLS manifest separately if the backend supports it.
5. Uninstall Kaos Tunes. Confirm its Open With choice is removed while other
   players and the existing defaults remain available.

### Linux Debian package

1. Install `desktop-file-utils` and the Python build requirements, run
   `bash build_linux_deb.sh`, and install the generated `.deb` with `apt`.
2. In the desktop file manager, check **Open with > Kaos Tunes** for audio
   files, videos and M3U/M3U8 playlists. Confirm your current default player remains.
3. Repeat the spaces, Unicode, multiple-file, running-window and playlist
   checks above. Check both `kaos-tunes "/path/to/a song.flac"` and the file
   manager launcher.
4. Remove the package with `apt remove kaos-tunes`. Confirm the launcher and
   Open With choice disappear after the application cache refreshes.

### Video playback on each desktop

- Open a known-good video with the Qt backend. Confirm the picture appears in
  the main window above the queue. Drag the video/queue divider and confirm
  seeking, pause/resume, volume, speed, previous and next use the shared controls.
- Use **Full screen** or F11, then Esc. Confirm there is still only one player
  window, the shared transport remains visible, and the original window size,
  maximized state, selected tab and divider position return afterward. Repeat
  using the window manager to leave full screen.
- Switch to audio while video is full screen. Confirm the normal artwork/queue
  layout returns, the video area hides, and playback continues in the same player.
- Switch between audio and video tracks and check that the appropriate artwork
  or video appears without a second playback session.
- Repeat with the optional VLC backend after restarting the player. Confirm
  that playback remains usable when a selected backend cannot decode a file.

