"""Locate the installed Linux VLC plugins without changing system settings."""
import os
from pathlib import Path
import sys
import sysconfig


def configure_vlc_plugins():
    if not sys.platform.startswith("linux") or os.environ.get("VLC_PLUGIN_PATH"):
        return
    multiarch = sysconfig.get_config_var("MULTIARCH")
    candidates = []
    if multiarch:
        candidates.append(Path("/usr/lib") / multiarch / "vlc/plugins")
    candidates.extend((Path("/usr/lib64/vlc/plugins"), Path("/usr/lib/vlc/plugins")))
    for path in candidates:
        if (path / "plugins.dat").is_file():
            os.environ["VLC_PLUGIN_PATH"] = str(path)
            return
