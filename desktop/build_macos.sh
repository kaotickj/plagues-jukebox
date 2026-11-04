#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
VERSION="$(python -c 'import ast; from pathlib import Path; t=ast.parse(Path("playTunes.py").read_text()); print(next(n.value.value for n in t.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=="APP_VERSION" for x in n.targets)))')"
ARCH="$(uname -m)"
mkdir -p dist/macos
python -m PyInstaller --clean --noconfirm --windowed --onedir \
  --name "KaosTunes" \
  --add-data "PlaguesJukebox.png:." \
  --add-data "PlaguesJukebox.ico:." \
  --hidden-import PyQt6.QtMultimedia \
  --hidden-import vlc \
  playTunes.py
APP="dist/KaosTunes.app"
test -d "$APP"
DMG="dist/macos/KaosTunes-${VERSION}-macOS-${ARCH}.dmg"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "Plague’s Jukebox" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
echo "Created $DMG"
