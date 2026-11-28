"""Build a shared Windows x64 standalone payload, portable zip, and installer."""
import argparse
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'src' / 'airport_canvas'
BUILD = ROOT / 'build'
DIST = BUILD / 'gui.dist'
RELEASE = ROOT / 'release'
VERSION = '1.3'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iscc', help='Path to Inno Setup ISCC.exe')
    parser.add_argument('--portable-only', action='store_true')
    args = parser.parse_args()
    if os.name != 'nt' or struct.calcsize('P') != 8:
        parser.error('Use 64-bit Python on Windows to build this release.')
    iscc = args.iscc or shutil.which('ISCC')
    if not iscc:
        default = Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Inno Setup 6' / 'ISCC.exe'
        if default.is_file():
            iscc = str(default)
    if not args.portable_only and not iscc:
        parser.error('Install Inno Setup 6 or pass --iscc. Use --portable-only for ZIP only.')
    config = json.loads((SOURCE / 'RELEASE_MANIFEST.json').read_text(encoding='utf8'))
    assets = [name for name in config['files']
              if Path(name).suffix.lower() in {'.acp', '.csv', '.ico', '.png', '.qm', '.ttf'}]
    assets += ['USER_GUIDE.md', 'SOFTWARE_OVERVIEW.md', 'CHANGELOG.md', 'QUICK_START.md', 'QUICK_START_EN.md', 'FEATURES.md', 'FEATURES_EN.md', 'VERSION.json', 'LICENSE.md']
    command = [sys.executable, '-m', 'nuitka', '--mode=standalone', '--enable-plugin=pyside6',
               '--msvc=latest', '--windows-console-mode=disable', '--windows-icon-from-ico=AirportCanvas.ico',
               '--product-name=Airport Canvas', '--company-name=刃下狼血', f'--product-version={VERSION}.0.0',
               '--output-filename=AirportCanvas.exe', f'--output-dir={BUILD}',
               f'--report={BUILD / "nuitka-report.xml"}']
    command.extend(f'--include-module={name}' for name in config['dynamic_imports'])
    command.extend(f'--include-data-files={name}={name}' for name in assets)
    command.append(f'--include-data-files={ROOT / "COPYING"}=COPYING')
    command.append('gui.py')
    BUILD.mkdir(exist_ok=True)
    subprocess.run(command, cwd=SOURCE, check=True)
    if not (DIST / 'AirportCanvas.exe').is_file():
        raise SystemExit(f'Build did not produce {DIST / "AirportCanvas.exe"}')
    RELEASE.mkdir(exist_ok=True)
    shutil.make_archive(str(RELEASE / f'AirportCanvas_{VERSION}_Windows_x64_Portable'),
                        'zip', root_dir=DIST)
    if not args.portable_only:
        subprocess.run([iscc, str(ROOT / 'AirportCanvas.iss')], cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
