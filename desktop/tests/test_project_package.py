import hashlib
import re
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class ProjectPackageTests(unittest.TestCase):
    def test_release_version_is_consistent(self):
        player = (PROJECT / "playTunes.py").read_text(encoding="utf-8")
        setup = (PROJECT / "setup.py").read_text(encoding="utf-8")
        version_info = (PROJECT / "version_info.txt").read_text(encoding="utf-8")
        readme = (PROJECT / "README.md").read_text(encoding="utf-8")
        self.assertIn('APP_VERSION = "2.3.1"', player)
        self.assertIn('version="2.3.1"', setup)
        self.assertIn("filevers=(2, 3, 1, 0)", version_info)
        self.assertIn("# Kaos Tunes 2.3.1", readme)

    def test_bundled_fpcalc_matches_verified_release_binary(self):
        fpcalc = PROJECT / "vendor" / "fpcalc" / "fpcalc.exe"
        digest = hashlib.sha256(fpcalc.read_bytes()).hexdigest()
        self.assertEqual(
            digest,
            "00dcc56d911f2dea84737aa9dc8e2d118c9eb7a037d815d1ed001d8593e8fbee",
        )

    def test_build_script_pins_download_archive_hash(self):
        script = (PROJECT / "prepare_dependencies.ps1").read_text(encoding="utf-8")
        expected = re.search(r'\$ExpectedSha256 = "([0-9a-f]+)"', script)
        self.assertIsNotNone(expected)
        self.assertEqual(
            expected.group(1),
            "735d6182b38e9f364b84ce6f4ccd682c75e2851de89735711d6b762d12b92a4e",
        )

    def test_windows_build_collects_runtime_licenses(self):
        build_script = (PROJECT / "build_windows.bat").read_text(encoding="utf-8")
        collector = (PROJECT / "collect_licenses.py").read_text(encoding="utf-8")
        self.assertIn("collect_licenses.py", build_script)
        for distribution in ("PyQt6", "PyQt6-Qt6", "PyQt6-sip", "mutagen", "PyInstaller"):
            self.assertIn(f'"{distribution}"', collector)


if __name__ == "__main__":
    unittest.main()
