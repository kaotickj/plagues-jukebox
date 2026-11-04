"""Validate shell registrations without changing the host's file associations."""

import ast
import configparser
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]


def registered_extensions():
    tree = ast.parse((PROJECT / "playTunes.py").read_text(encoding="utf-8"))
    values = {}

    def extension_set(expression):
        if isinstance(expression, ast.Name):
            return values[expression.id]
        if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.BitOr):
            return extension_set(expression.left) | extension_set(expression.right)
        return ast.literal_eval(expression)

    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name) and target.id in {
                    "AUDIO_EXTENSIONS", "VIDEO_EXTENSIONS", "SUPPORTED_EXTENSIONS"
                }:
                    values[target.id] = extension_set(statement.value)
                    if target.id == "SUPPORTED_EXTENSIONS":
                        return values[target.id] | {".m3u", ".m3u8"}
    raise AssertionError("SUPPORTED_EXTENSIONS was not found")


def registry_entries():
    text = (PROJECT / "installer.iss").read_text(encoding="utf-8")
    entries = []
    in_registry = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            in_registry = line == "[Registry]"
        elif in_registry and line and not line.startswith(";"):
            entry = {}
            for part in line.split("; "):
                key, value = part.split(":", 1)
                value = value.strip()
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1].replace('""', '"')
                entry[key] = value
            entries.append(entry)
    return entries


class WindowsAssociationTests(unittest.TestCase):
    def test_all_supported_media_types_have_open_with_registrations(self):
        entries = registry_entries()
        associations = [e for e in entries if e["Subkey"].endswith("\\OpenWithProgids")]
        extensions = {
            re.fullmatch(r"Software\\Classes\\(\.[^.\\]+)\\OpenWithProgids", e["Subkey"]).group(1)
            for e in associations
        }
        self.assertEqual(extensions, registered_extensions())
        for entry in associations:
            self.assertEqual(entry["Root"], "HKCU")
            self.assertEqual(entry["ValueName"], "KaosTunes.Media")
            self.assertEqual(entry["ValueData"], "")
            self.assertIn("uninsdeletevalue", entry["Flags"].split())
            self.assertNotIn("uninsdeletekey", entry["Flags"].split())

        supported_types = {
            e["ValueName"] for e in entries if e["Subkey"].endswith("\\SupportedTypes")
        }
        self.assertEqual(supported_types, extensions)

    def test_commands_quote_executable_and_file_and_refresh_explorer(self):
        commands = [
            e["ValueData"] for e in registry_entries()
            if e["Subkey"].endswith("\\shell\\open\\command")
        ]
        self.assertEqual(len(commands), 2)
        for command in commands:
            self.assertEqual(command, '"{app}\\KaosTunes.exe" "%1"')
        script = (PROJECT / "installer.iss").read_text(encoding="utf-8")
        self.assertRegex(script, r"(?m)^ChangesAssociations=yes$")

    def test_only_app_owned_keys_are_deleted_and_defaults_are_not_written(self):
        own_keys = {
            "Software\\Classes\\KaosTunes.Media",
            "Software\\Classes\\Applications\\KaosTunes.exe",
        }
        for entry in registry_entries():
            self.assertEqual(entry["Root"], "HKCU")
            self.assertNotIn("UserChoice", entry["Subkey"])
            if "uninsdeletekey" in entry.get("Flags", "").split():
                self.assertIn(entry["Subkey"], own_keys)
            if entry["Subkey"].startswith("Software\\Classes\\."):
                self.assertTrue(entry["Subkey"].endswith("\\OpenWithProgids"))
                self.assertEqual(entry["ValueName"], "KaosTunes.Media")


class LinuxAssociationTests(unittest.TestCase):
    def test_desktop_entry_supports_multiple_files_and_media_playlist_mime_types(self):
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(PROJECT / "kaos-tunes.desktop", encoding="utf-8")
        entry = parser["Desktop Entry"]
        self.assertEqual(entry["Type"], "Application")
        self.assertEqual(entry["Exec"], "/usr/bin/kaos-tunes %F")
        self.assertEqual(entry["Icon"], "plagues-jukebox")
        mime_types = set(entry["MimeType"].strip(";").split(";"))
        expected = {
            ".mp3": "audio/mpeg", ".wav": "audio/vnd.wave",
            ".flac": "audio/flac", ".ogg": "audio/ogg", ".oga": "audio/ogg",
            ".opus": "audio/x-opus+ogg", ".m4a": "audio/mp4",
            ".mp4": "video/mp4", ".aac": "audio/aac", ".wma": "audio/x-ms-wma",
            ".aiff": "audio/x-aiff", ".aif": "audio/x-aiff",
            ".m3u": "audio/x-mpegurl", ".m3u8": "application/vnd.apple.mpegurl",
            ".m4v": "video/x-m4v", ".mkv": "video/x-matroska",
            ".webm": "video/webm", ".mov": "video/quicktime", ".avi": "video/x-msvideo",
            ".wmv": "video/x-ms-wmv", ".mpg": "video/mpeg", ".mpeg": "video/mpeg",
            ".ogv": "video/ogg", ".3gp": "video/3gpp",
        }
        self.assertEqual(set(expected), registered_extensions())
        self.assertTrue(set(expected.values()).issubset(mime_types))
        self.assertNotIn("application/json", mime_types)
        self.assertNotIn("text/plain", mime_types)

    @unittest.skipUnless(shutil.which("desktop-file-validate"), "desktop-file-utils is not installed")
    def test_desktop_entry_passes_platform_validator(self):
        subprocess.run(
            ["desktop-file-validate", str(PROJECT / "kaos-tunes.desktop")],
            check=True, capture_output=True, text=True,
        )

    @unittest.skipUnless(
        shutil.which("dpkg-deb") and shutil.which("desktop-file-validate"),
        "Debian packaging tools are not installed",
    )
    def test_debian_package_contains_launcher_and_refreshes_cache_on_install_remove(self):
        # Build a real .deb with a stub executable so this checks packaging
        # independently of PyInstaller, Qt, and the machine's audio devices.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "desktop"
            root.mkdir()
            shutil.copyfile(PROJECT.parent / "LICENSE", root.parent / "LICENSE")
            for filename in ("build_linux_deb.sh", "kaos-tunes.desktop"):
                shutil.copyfile(PROJECT / filename, root / filename)
            (root / "PlaguesJukebox.png").write_bytes(b"test icon")
            tools = root / "tools"
            tools.mkdir()
            python = tools / "python"
            python.write_text(
                '#!/bin/sh\nset -e\nmkdir -p dist/PlaguesJukebox\n'
                'printf "#!/bin/sh\\nexit 0\\n" > dist/PlaguesJukebox/PlaguesJukebox\n'
                'chmod 755 dist/PlaguesJukebox/PlaguesJukebox\n',
                encoding="utf-8",
            )
            python.chmod(0o755)
            env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ.get("PATH", ""))
            subprocess.run(
                ["bash", str(root / "build_linux_deb.sh")], env=env,
                check=True, capture_output=True, text=True,
            )
            packages = list((root / "dist/linux").glob("*.deb"))
            self.assertEqual(len(packages), 1)
            unpacked, control = root / "unpacked", root / "control"
            subprocess.run(["dpkg-deb", "--extract", str(packages[0]), str(unpacked)], check=True)
            subprocess.run(["dpkg-deb", "--control", str(packages[0]), str(control)], check=True)
            self.assertEqual(
                (unpacked / "usr/share/applications/kaos-tunes.desktop").read_bytes(),
                (PROJECT / "kaos-tunes.desktop").read_bytes(),
            )
            self.assertIn(
                'exec /opt/kaos-tunes/PlaguesJukebox "$@"',
                (unpacked / "usr/bin/kaos-tunes").read_text(encoding="utf-8"),
            )
            self.assertTrue(os.access(unpacked / "opt/kaos-tunes/PlaguesJukebox", os.X_OK))
            self.assertIn("desktop-file-utils", (control / "control").read_text(encoding="utf-8"))
            self.assertFalse(list(unpacked.rglob("mimeapps.list")))

            cache_log = root / "cache-calls"
            cache_tool = tools / "update-desktop-database"
            cache_tool.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$*" >> "$KAOS_CACHE_LOG"\n',
                encoding="utf-8",
            )
            cache_tool.chmod(0o755)
            env["KAOS_CACHE_LOG"] = str(cache_log)
            for script, argument in (
                ("postinst", "configure"), ("postrm", "remove"), ("postrm", "purge")
            ):
                self.assertTrue(os.access(control / script, os.X_OK))
                subprocess.run([str(control / script), argument], env=env, check=True)
            self.assertEqual(
                cache_log.read_text(encoding="utf-8").splitlines(),
                ["-q /usr/share/applications"] * 3,
            )
            subprocess.run([str(control / "postrm"), "upgrade"], env=env, check=True)
            self.assertEqual(len(cache_log.read_text(encoding="utf-8").splitlines()), 3)


if __name__ == "__main__":
    unittest.main()
