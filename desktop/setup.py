"""Installation configuration for Plague’s Jukebox."""

from setuptools import setup


setup(
    name="kaos-tunes",
    version="2.3.1",
    description="Plague’s Jukebox Music Player for Windows and Linux",
    author="Kaotick Jay",
    url="https://github.com/kaotickj",
    py_modules=[
        "playTunes", "metadata_lookup", "instance_bridge", "audio_equalizer",
        "equalizer_dialog", "vlc_equalizer_engine", "vlc_player_adapter",
        "vlc_runtime", "stream_metadata", "runtime_smoke",
    ],
    data_files=[
        ("share/kaos-tunes", ["PlaguesJukebox.ico", "PlaguesJukebox.png"]),
        ("share/kaos-tunes", ["vendor/fpcalc/fpcalc.exe", "THIRD_PARTY_NOTICES.txt"]),
        (
            "share/kaos-tunes/licenses/chromaprint",
            ["vendor/fpcalc/LICENSE.md", "vendor/fpcalc/COPYING.LGPL-2.1.txt"],
        ),
    ],
    python_requires=">=3.10",
    install_requires=[
        "PyQt6>=6.8,<7",
        "mutagen>=1.47,<2",
        "python-vlc>=3.0.21203,<4",
    ],
    entry_points={
        "gui_scripts": [
            "kaos-tunes=playTunes:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Win32 (MS Windows)",
        "Environment :: X11 Applications :: Qt",
        "Intended Audience :: End Users/Desktop",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Multimedia :: Sound/Audio :: Players",
    ],
)
