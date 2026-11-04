#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
VERSION=2.3.1
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
APP="$STAGE/opt/kaos-tunes"
mkdir -p "$APP" "$STAGE/usr/bin" "$STAGE/usr/share/applications" "$STAGE/usr/share/icons/hicolor/256x256/apps" "$STAGE/DEBIAN" dist/linux
# Bundle a Linux-native executable and Qt libraries, rather than depending on
# an arbitrary system Python environment.
python -m PyInstaller --clean --noconfirm PlaguesJukebox-linux.spec
python collect_licenses.py --destination dist/PlaguesJukebox/licenses
install -m 644 ../LICENSE dist/PlaguesJukebox/LICENSE
python collect_linux_native_licenses.py build/PlaguesJukebox-linux/Analysis-00.toc dist/PlaguesJukebox/licenses
cp -a dist/PlaguesJukebox/. "$APP/"
mkdir -p "$STAGE/usr/share/doc/kaos-tunes"
install -m 644 ../LICENSE "$STAGE/usr/share/doc/kaos-tunes/copyright"
install -m 644 PlaguesJukebox.png "$STAGE/usr/share/icons/hicolor/256x256/apps/plagues-jukebox.png"
cat > "$STAGE/usr/bin/kaos-tunes" <<'EOF'
#!/bin/sh
exec /opt/kaos-tunes/PlaguesJukebox "$@"
EOF
chmod 755 "$STAGE/usr/bin/kaos-tunes"
desktop-file-validate kaos-tunes.desktop
install -m 644 kaos-tunes.desktop "$STAGE/usr/share/applications/kaos-tunes.desktop"
cat > "$STAGE/DEBIAN/control" <<EOF
Package: kaos-tunes
Version: $VERSION
Section: sound
Priority: optional
Architecture: amd64
Maintainer: Kaotick Jay
Description: Plague’s Jukebox music and internet radio player
 PyQt6-based desktop music player for Linux.
Depends: libc6, libglib2.0-0, libx11-6, libxkbcommon0, libegl1, desktop-file-utils, libvlc5, vlc-plugin-base
EOF
cat > "$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = configure ]; then
    update-desktop-database -q /usr/share/applications
fi
exit 0
EOF
cat > "$STAGE/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
case "$1" in
    remove|purge)
        if command -v update-desktop-database >/dev/null 2>&1; then
            update-desktop-database -q /usr/share/applications
        fi
        ;;
esac
exit 0
EOF
chmod 755 "$STAGE/DEBIAN/postinst" "$STAGE/DEBIAN/postrm"
dpkg-deb --build --root-owner-group "$STAGE" "dist/linux/kaos-tunes_${VERSION}_amd64.deb"
