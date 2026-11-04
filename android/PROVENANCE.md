# Source provenance

Android edition: K-Tunes 0.1.1, 2026-09-30.
Desktop baseline: KaosTunes 2.3.1 playback patch.

The desktop metadata engine was copied without modifications.
Its SHA-256 is `62faf92224b85ead6651036d52339012b034abf9f5df1ee4f2c34dc4189fdb70`.
The KaosTunes artwork was copied without image modifications.
The Java Android shell, Media3 service and bridge are new port code.

Version 0.1.1 rebrands the Android shell and filters device music scans.
The application ID, preference namespace and signing key remain unchanged
to preserve updates from Kaos Tunes 0.1.0 and existing user data.

Gradle wrapper distribution downloads are pinned by SHA-256.
Android builds use pinned dependency versions in the Gradle files.
