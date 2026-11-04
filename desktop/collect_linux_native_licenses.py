"""Collect distro copyright notices for system binaries bundled by PyInstaller."""
import ast
from pathlib import Path
import shutil
import subprocess
import sys


def source_paths(value):
    if isinstance(value, (list, tuple)):
        for child in value:
            yield from source_paths(child)
    elif isinstance(value, str) and value.startswith(('/usr/lib/', '/lib/')) and '.so' in value:
        yield value


def main():
    toc = Path(sys.argv[1])
    if not toc.is_file():
        candidates = list(Path('build').glob('*/Analysis-00.toc'))
        if len(candidates) != 1:
            raise SystemExit('Cannot identify the current PyInstaller analysis for license collection')
        toc = candidates[0]
    destination = Path(sys.argv[2]) / 'system'
    destination.mkdir(parents=True, exist_ok=True)
    packages = set()
    for source in set(source_paths(ast.literal_eval(toc.read_text()))):
        for candidate in {source, str(Path(source).resolve())}:
            result = subprocess.run(['dpkg-query', '-S', candidate], capture_output=True, text=True)
            if result.returncode == 0:
                packages.update(line.split(': ', 1)[0].split(':', 1)[0] for line in result.stdout.splitlines())
    for package in sorted(packages):
        source = Path('/usr/share/doc') / package / 'copyright'
        if not source.is_file():
            raise SystemExit('Missing distribution copyright file for ' + package)
        folder = destination / package
        folder.mkdir(exist_ok=True)
        shutil.copy2(source, folder / 'copyright')
    (destination / 'packages.txt').write_text('\n'.join(sorted(packages)) + '\n')
    print('Collected native copyright notices for', len(packages), 'packages')


if __name__ == '__main__':
    main()
