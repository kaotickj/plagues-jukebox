# Android device checklist

1. Install and launch. Confirm the screen fits and all bottom controls are visible.
2. Add an MP3 and one of your Goodneighbor Blues WAVs through **Add files**.
3. Tap a song and listen for at least a minute. Switch songs several times.
4. Pause, resume, seek, repeat a song and shuffle the queue.
5. Press Home and turn the screen off. Verify audio continues and the playback
   notification/lock-screen controls work. Disconnect headphones to verify pause.
6. Close and reopen the app. Confirm the library and queue are restored. After
   a process restart, confirm audio waits for Play and resumes at the saved position.
7. Scan device audio and add a folder. Deny scan permission once and confirm
   **Add files** still works with Android's document picker.
8. Check embedded artwork and metadata. Hold a song, choose online lookup and
   inspect its result before applying. Confirm the source audio file is unchanged.
9. Export the queue, clear it, and import the JSON export. Try an existing M3U8
   playlist after adding its music to the catalog.

For a failure, note your phone model, Android version, file format, sample rate,
and exact steps. A connected computer can capture diagnostics with:

```sh
adb logcat -d > k-tunes-android-log.txt
```

Codec, sound output, battery restrictions and notification behavior can vary
between devices. The APK has no account requirement and no telemetry.

## Rebrand and scanner regression checks

- Update the existing 0.1.0 installation without uninstalling. Confirm K-Tunes
  on the launcher and in the app, and retention of catalog/queue/permissions.
- Scan with a short song, a long saved voicemail and a recording. Confirm the
  song is kept by default and recognizable voice files are skipped.
- Rescan an old catalog containing voicemail. Confirm rejected device imports
  disappear from the library and queue, with source files still present.
- Enable a 30-second minimum, rescan and check the boundary; turn it off and
  rescan to restore short music. Manually add an excluded file and confirm it
  remains after another scan. Repeat with permission denied.
- Test Android 7/8 (legacy path), Android 10/11 (relative path) and Android 12+
  (voice recording flag), plus an SD card if available.
