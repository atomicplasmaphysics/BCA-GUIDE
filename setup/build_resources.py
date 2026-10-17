"""
Builds assets/resources.py from assets/resources.qrc

pyside6-rcc is used, since PyQt6 does not provide a resource compiler anymore.
The generated file is changed to import QtCore from PyQt6, so that PySide6 is not needed to run the GUI.

Usage: python setup/build_resources.py
Requires: pip install pyside6
"""

from pathlib import Path
from shutil import which
from subprocess import run
import sys


def main():
    root = Path(__file__).resolve().parent.parent
    qrc_file = root / 'assets' / 'resources.qrc'
    py_file = root / 'assets' / 'resources.py'

    rcc = which('pyside6-rcc') or which('pyside6-rcc', path=str(Path(sys.executable).parent))
    if rcc is None:
        sys.exit('pyside6-rcc not found, install it with "pip install pyside6"')

    run([rcc, '-o', str(py_file), str(qrc_file)], check=True, cwd=qrc_file.parent)

    content = py_file.read_text(encoding='utf-8')
    if 'from PySide6 import QtCore' not in content:
        sys.exit('Unexpected output of pyside6-rcc, could not replace import of PySide6')
    py_file.write_text(content.replace('from PySide6 import QtCore', 'from PyQt6 import QtCore'), encoding='utf-8')

    print(f'Created "{py_file}" ({py_file.stat().st_size / 1e6:.2f} MB)')


if __name__ == '__main__':
    main()
