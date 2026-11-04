"""Collect redistributable runtime license files beside the Windows build."""

from __future__ import annotations

import argparse
import importlib.metadata
import re
import shutil
import sys
from pathlib import Path


DISTRIBUTIONS = ("PyQt6", "PyQt6-Qt6", "PyQt6-sip", "mutagen", "PyInstaller", "python-vlc")
LICENSE_PREFIXES = ("license", "copying", "notice")


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "component"


def collect_distribution_licenses(destination: Path) -> list[Path]:
    copied: list[Path] = []
    for distribution_name in DISTRIBUTIONS:
        distribution = importlib.metadata.distribution(distribution_name)
        component = destination / _safe_name(distribution_name)
        count_before = len(copied)
        for relative in distribution.files or []:
            basename = Path(str(relative)).name.lower()
            if not basename.startswith(LICENSE_PREFIXES):
                continue
            source = Path(distribution.locate_file(relative))
            if not source.is_file():
                continue
            component.mkdir(parents=True, exist_ok=True)
            target_name = _safe_name(str(relative).replace("\\", "__").replace("/", "__"))
            target = component / target_name
            shutil.copy2(source, target)
            copied.append(target)
        if len(copied) == count_before:
            distro_package = {"PyQt6": "python3-pyqt6", "mutagen": "python3-mutagen"}.get(distribution_name)
            fallback = Path("/usr/share/doc") / (distro_package or "missing") / "copyright"
            if not fallback.is_file():
                raise RuntimeError("No license files found for " + distribution_name)
            component.mkdir(parents=True, exist_ok=True)
            target = component / "copyright"
            shutil.copy2(fallback, target)
            copied.append(target)
    return copied


def collect_python_license(destination: Path) -> Path | None:
    candidates = [
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sys.base_prefix) / "lib" / ("python" + str(sys.version_info.major) + "." + str(sys.version_info.minor)) / "LICENSE.txt",
        Path("/usr/share/doc/python3.12/copyright"),
        Path("/usr/share/doc/python3.13/copyright"),
        Path(sys.base_prefix) / "LICENSE",
        Path(sys.executable).resolve().parent / "LICENSE.txt",
        Path(sys.executable).resolve().parent / "LICENSE",
    ]
    for source in candidates:
        if not source.is_file():
            continue
        target_dir = destination / "Python"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / source.name
        shutil.copy2(source, target)
        return target
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path("dist") / "licenses",
        help="Directory that will receive component license files.",
    )
    args = parser.parse_args()
    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    copied = collect_distribution_licenses(destination)
    python_license = collect_python_license(destination)
    if python_license:
        copied.append(python_license)
    if not copied:
        raise SystemExit("No dependency license files were found.")
    print(f"Collected {len(copied)} dependency license files in {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
