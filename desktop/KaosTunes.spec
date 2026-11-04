# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


fpcalc = Path("vendor/fpcalc/fpcalc.exe")
fpcalc_license = Path("vendor/fpcalc/LICENSE.md")
lgpl_license = Path("vendor/fpcalc/COPYING.LGPL-2.1.txt")
if not fpcalc.is_file():
    raise SystemExit(
        "vendor/fpcalc/fpcalc.exe is missing. Run prepare_dependencies.ps1 or build_windows.bat."
    )

binaries = [(str(fpcalc), ".")]
datas = [
    ("PlaguesJukebox.ico", "."),
    ("PlaguesJukebox.png", "."),
    ("THIRD_PARTY_NOTICES.txt", "."),
]
if fpcalc_license.is_file():
    datas.append((str(fpcalc_license), "licenses/chromaprint"))
if lgpl_license.is_file():
    datas.append((str(lgpl_license), "licenses/chromaprint"))


a = Analysis(
    ["playTunes.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "PyQt6.QtMultimedia",
        "vlc",
        "vlc_player_adapter",
        "vlc_equalizer_engine",
        "mutagen",
        "mutagen.id3",
        "mutagen.flac",
        "mutagen.mp3",
        "mutagen.mp4",
        "mutagen.oggvorbis",
        "mutagen.wave",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pygame"],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="KaosTunes",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="PlaguesJukebox.ico",
    version="version_info.txt",
    uac_admin=False,
    uac_uiaccess=False,
)
