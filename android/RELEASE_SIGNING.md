# K-Tunes Android release signing

The CI workflow builds a signed release APK when the repository's four Actions secrets are configured. Without them, it only publishes the debug APK. Pull requests do not receive signing credentials.

## One-time key creation (keep it private)

Run on your own trusted computer with Java installed:

```sh
keytool -genkeypair -v -keystore ktunes-release.jks -alias ktunes -keyalg RSA -keysize 3072 -validity 10000
```

Choose strong passwords, save the keystore and passwords securely, and back them up offline. **Never commit the keystore or passwords to Git.** Losing the keystore prevents publishing updates that use the same Android signing identity.

Encode the keystore for GitHub Actions:

Linux/macOS:
```sh
base64 < ktunes-release.jks | tr -d '\n'
```

Windows PowerShell:
```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes((Resolve-Path .\ktunes-release.jks)))
```

In repository **Settings → Secrets and variables → Actions**, create these repository secrets:

- `KTUNES_RELEASE_KEYSTORE_BASE64`: the base64 text from above
- `KTUNES_KEYSTORE_PASSWORD`: the keystore password
- `KTUNES_KEY_ALIAS`: `ktunes` (or the alias you selected)
- `KTUNES_KEY_PASSWORD`: the key password

After setting all four secrets, use **Actions → Build K-Tunes installers → Run workflow** or push to `main`. Download the `K-Tunes-Android-signed-release` artifact, containing `K-Tunes-release.apk` and `SHA256SUMS.txt`. Publish those files through your own channels.

The workflow verifies the APK with Android SDK `apksigner verify --print-certs` before upload. The signature does not remove Android's sideload permission prompts or guarantee Play Protect acceptance.

**Important:** Existing debug-signed installs generally cannot be updated in place with a newly release-signed APK. Back up any app data and uninstall the debug build before installing the first release build. Later builds signed with the same release key can update one another if their versionCode increases.

The APK uses the package ID `com.kaosium.kaostunes`. Do not change it casually.
