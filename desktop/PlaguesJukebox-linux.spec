# Linux uses the installed libVLC and its matching plugin tree.
a = Analysis(['playTunes.py'], pathex=['.'],
    binaries=[], datas=[('PlaguesJukebox.png', '.'), ('THIRD_PARTY_NOTICES.txt', '.')],
    hiddenimports=['vlc', 'vlc_player_adapter', 'vlc_equalizer_engine', 'PyQt6.QtMultimedia'],
    excludes=['tkinter', 'pygame'], noarchive=False)
a.binaries = [entry for entry in a.binaries
              if not entry[0].startswith(('libvlc.so', 'libvlccore.so'))]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='PlaguesJukebox',
          debug=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='PlaguesJukebox')
