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

import sys
from os import path, remove, listdir
from pathlib import Path
from shutil import move, rmtree
from inspect import getfile, currentframe
from platform import system

import PyInstaller.__main__

current_dir = Path(path.dirname(path.abspath(getfile(currentframe()))))
parent_dir = Path(path.dirname(current_dir))
sys.path.insert(0, parent_dir)


import GlobalConf

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

exe_name = f'{GlobalConf.GlobalConf.title}'
system_name = system()
if system_name == 'Windows':
    exe_name += '_windows.exe'
elif system_name == 'Linux':
    exe_name += '_linux'
elif system_name == 'Darwin':
    exe_name += '_mac.app'
else:
    exe_name += f'_{system_name.lower()}.exe'
divider = ';' if system_name == 'Windows' else ':'
pyinstaller_parameters = [
    parent_dir / 'main.py',
    f'--icon={parent_dir / 'icons' / 'tu_logo.ico'}',
    f'--name={exe_name}',
    '--windowed',
    '--clean',
    f'--add-data={parent_dir / 'Simulations' / divider / 'Simulations' / ''}',
    '--onefile',
    f'--distpath={dist_path}',
    f'--workpath={build_path}'
]

pyinstaller_parameters.extend([f'--hidden-import={hidden}' for hidden in hidden_imports])

PyInstaller.__main__.run(pyinstaller_parameters)

if path.exists(dist_path / exe_name):
    move(dist_path / exe_name, parent_dir / exe_name)
    clearFiles()
    print('\n\nSUCCESSFULLY created executable file ')

else:
    print('\n\nERROR creating executable file')
