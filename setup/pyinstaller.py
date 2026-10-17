# A manual for PyInstaller is found here: https://pyinstaller.org/en/stable/
#
# Automatic execution:
#  1) Update Python and all necessary packages, as well as PyInstaller to the latest version
#     Tested version: Python 3.10.7
#      Package      Version
#      ------------ ---------
#      matplotlib   3.6.0
#      numpy        1.23.3
#      pyinstaller  5.4.1
#      PyQt6        6.5.0
#      scipy        1.9.1
#
#  2) Just run this python script and a 'BCA-GUIDE' executable will be generated in the main folder
#     (python setup/pyinstaller.py, requires: pip install pyinstaller)
#
# The executable contains the assets (images in assets/resources.py, manual of the GUI) and the simulation modules
# (Simulations/*.py are loaded by SimulationsList at runtime). The simulation programs are not part of it.

import sys
from os import path, remove, listdir, environ
from subprocess import run, TimeoutExpired
from pathlib import Path
from shutil import move, rmtree
from platform import system

import PyInstaller.__main__

current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

from Utility.GlobalConf import GlobalConf  # noqa: E402 (needs the path of the project)

dist_path = current_dir / 'dist'
build_path = current_dir / 'build'


def clearFiles():
    """ Remove files (build- and dist-directories and any *.spec files) """
    directories = [build_path, dist_path]
    for directory in directories:
        if path.exists(directory):
            rmtree(directory)
    files = listdir(current_dir)
    files = [current_dir / file for file in files if file.endswith('.spec')]
    for file in files:
        remove(file)


clearFiles()

# build app
hidden_imports = [
    'scipy.optimize'
]

exe_name = f'{GlobalConf.title}'
system_name = system()
if system_name == 'Windows':
    exe_name += '_windows.exe'
elif system_name == 'Linux':
    exe_name += '_linux'
elif system_name == 'Darwin':
    exe_name += '_mac.app'
else:
    exe_name += f'_{system_name.lower()}.exe'
# icon of the executable: .icns for macOS, otherwise converted from the png (PyInstaller converts it with Pillow)
icon = parent_dir / 'assets' / ('tu_logo.icns' if system_name == 'Darwin' else 'tu_logo.png')

divider = ';' if system_name == 'Windows' else ':'
pyinstaller_parameters = [
    str(parent_dir / 'main.py'),
    f'--icon={icon}',
    f'--name={exe_name}',
    '--windowed',
    '--clean',
    '--noconfirm',
    f'--paths={parent_dir}',
    # the simulation modules are found by their files and imported at runtime
    f'--add-data={parent_dir / "Simulations"}{divider}Simulations',
    '--collect-submodules=Simulations',
    f'--add-data={parent_dir / "assets" / "BCA-GUIDE_manual.pdf"}{divider}assets',
    '--onefile',
    f'--distpath={dist_path}',
    f'--workpath={build_path}',
    f'--specpath={current_dir}'
]

pyinstaller_parameters.extend([f'--hidden-import={hidden}' for hidden in hidden_imports])

PyInstaller.__main__.run(pyinstaller_parameters)

if path.exists(dist_path / exe_name):
    move(dist_path / exe_name, parent_dir / exe_name)
    clearFiles()
    print(f'\n\nSUCCESSFULLY created executable file {parent_dir / exe_name}')

    # check the executable: it starts (without showing the window), loads the simulation modules and finds its assets
    try:
        result = run([str(parent_dir / exe_name), '--self-test'], env=dict(environ, QT_QPA_PLATFORM='offscreen'), timeout=300)
        print('Self test of the executable ' + ('passed' if result.returncode == 0 else f'FAILED (exit code {result.returncode})'))
    except TimeoutExpired:
        print('Self test of the executable FAILED (no response within 5 minutes, e.g. an error dialog)')
    except OSError as error:
        print(f'Self test of the executable could not be run: {error}')

else:
    print('\n\nERROR creating executable file')
