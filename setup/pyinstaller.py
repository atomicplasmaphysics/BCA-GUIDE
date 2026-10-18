# A manual for PyInstaller is found here: https://pyinstaller.org/en/stable/
#
# Builds the GUI as program that runs without Python (python setup/pyinstaller.py, requires: pip install -r requirements-dev.txt)
#
#   python setup/pyinstaller.py              folder BCA-GUIDE_<system> in the main folder with the program
#                                            (BCA-GUIDE.exe / BCA-GUIDE, on macOS BCA-GUIDE.app) and its libraries
#   python setup/pyinstaller.py --archive    also packs the folder for the download (BCA-GUIDE_windows.zip,
#                                            BCA-GUIDE_linux.tar.gz, BCA-GUIDE_mac.zip), used by .github/workflows/release.yml
#   python setup/pyinstaller.py --onefile    single file BCA-GUIDE_<system>(.exe) instead of the folder: unpacks itself
#                                            into a temporary folder at every start (about 4 s slower start, same size)
#
# The program contains the assets (images in assets/resources.py, manual of the GUI) and the simulation modules
# (Simulations/*.py are loaded by SimulationsList at runtime). The simulation programs are not part of it.
# After building, the program is started once with --self-test (without showing the window): it checks that the
# simulation modules, the images and the manual are found. The exit code is 1 if building or the self test failed.

import sys
from argparse import ArgumentParser
from os import environ
from subprocess import run, TimeoutExpired
from pathlib import Path
from shutil import move, rmtree, make_archive
from platform import system

import PyInstaller.__main__

current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

from Utility.GlobalConf import GlobalConf  # noqa: E402 (needs the path of the project)

dist_path = current_dir / 'dist'
build_path = current_dir / 'build'

SYSTEM_NAMES = {'Windows': 'windows', 'Linux': 'linux', 'Darwin': 'mac'}


def clearFiles():
    """Removes the build and dist folders and the *.spec files"""

    for directory in (build_path, dist_path):
        if directory.exists():
            rmtree(directory)
    for file in current_dir.glob('*.spec'):
        file.unlink()


def selfTest(executable: Path) -> bool:
    """Starts the program with --self-test, returns if the test passed"""

    try:
        result = run([str(executable), '--self-test'], env=dict(environ, QT_QPA_PLATFORM='offscreen'), timeout=300)
    except TimeoutExpired:
        print('Self test of the executable FAILED (no response within 5 minutes, e.g. an error dialog)')
        return False
    except OSError as error:
        print(f'Self test of the executable could not be run: {error}')
        return False
    print('Self test of the executable ' + ('passed' if result.returncode == 0 else f'FAILED (exit code {result.returncode})'))
    return result.returncode == 0


def archive(folder: Path, system_name: str) -> Path:
    """Packs the folder of the program for the download (macOS: ditto keeps the links of the app bundle)"""

    base = parent_dir / folder.name
    if system_name == 'Darwin':
        target = base.with_suffix('.zip')
        run(['ditto', '-c', '-k', '--keepParent', str(folder), str(target)], check=True)
        return target
    # tar.gz keeps the executable permission on Linux
    return Path(make_archive(str(base), 'gztar' if system_name == 'Linux' else 'zip', folder.parent, folder.name))


def main() -> int:
    parser = ArgumentParser(description='Builds the GUI as program that runs without Python')
    parser.add_argument('--onefile', action='store_true', help='single file instead of a folder (slower start)')
    parser.add_argument('--archive', action='store_true', help='pack the folder for the download (zip or tar.gz)')
    args = parser.parse_args()

    system_name = system()
    suffix = SYSTEM_NAMES.get(system_name, system_name.lower())
    # icon of the executable: .icns for macOS, otherwise converted from the png (PyInstaller converts it with Pillow)
    icon = parent_dir / 'assets' / ('tu_logo.icns' if system_name == 'Darwin' else 'tu_logo.png')
    divider = ';' if system_name == 'Windows' else ':'

    if args.onefile:
        name = f'{GlobalConf.title}_{suffix}' + {'Windows': '.exe', 'Darwin': '.app'}.get(system_name, '')
    else:
        name = GlobalConf.title

    clearFiles()
    PyInstaller.__main__.run([
        str(parent_dir / 'main.py'),
        f'--icon={icon}',
        f'--name={name}',
        '--windowed',
        '--clean',
        '--noconfirm',
        f'--paths={parent_dir}',
        # the simulation modules are found by their files and imported at runtime
        f'--add-data={parent_dir / "Simulations"}{divider}Simulations',
        '--collect-submodules=Simulations',
        f'--add-data={parent_dir / "BCA-GUIDE_manual.pdf"}{divider}.',
        '--hidden-import=scipy.optimize',
        '--onefile' if args.onefile else '--onedir',
        f'--distpath={dist_path}',
        f'--workpath={build_path}',
        f'--specpath={current_dir}'
    ])

    if args.onefile:
        built = dist_path / name
        result = parent_dir / name
        executable = result
    else:
        # macOS: the app bundle, otherwise the folder with the executable and the folder _internal of the libraries
        built = dist_path / f'{name}.app' if system_name == 'Darwin' else dist_path / name
        result = parent_dir / f'{GlobalConf.title}_{suffix}'
        executable = (result / built.name / 'Contents' / 'MacOS' / name if system_name == 'Darwin'
                      else result / (f'{name}.exe' if system_name == 'Windows' else name))

    if not built.exists():
        print('\n\nERROR creating executable')
        return 1
    if result.exists():
        rmtree(result) if result.is_dir() else result.unlink()
    if args.onefile or system_name != 'Darwin':
        move(str(built), str(result))
    else:
        result.mkdir()
        move(str(built), str(result / built.name))
    clearFiles()
    print(f'\n\nSUCCESSFULLY created {result}')

    if not selfTest(executable):
        return 1
    if args.archive:
        print(f'Archive for the download: {archive(result, system_name)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
