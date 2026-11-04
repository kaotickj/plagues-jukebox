# Playback patch validation, 2026-09-29

Version: 2.3.1, based on the recovered 2.3.0 Windows build project.

The full automated suite passed: 26 tests, including 11 new playback tests.
Tests cover queue and library double-click signals, the Play button, sorted
and filtered views, rapid activations, replacement during loading, Stop and
Clear cancellation, reentrant saved-position seeking, same-source activation,
metadata arrival during playback, and a stalled backend position.

A separate smoke check used the real Qt FFmpeg decoder with a generated
four-second stereo PCM WAV at 44.1 kHz. A queue double-click loaded the source
and started playback. At the check, Qt reported PlayingState, BufferedMedia,
duration 4,000 ms, actual position 1,671 ms, and no pending play request.

Environment: Linux, Python 3.12, PyQt6 6.11.0, Qt 6.11.2, Mutagen 1.48.1.
No audio output device was available here. These results verify control flow
and decoder progress, not audible output or the native Windows backend.
The reported Windows silence symptom still requires the source-run checklist
in TESTING.md. No Windows executable was built for this patch.

The metadata callback was traced and regression-tested; it does not call
play, stop, setSource, or setPosition. The library's artwork scan was retained.
The exact Windows root cause is not proven. This patch addresses source-loading
and event-order hazards and provides bounded diagnostics for the next test.
