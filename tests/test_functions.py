import os
import sys
from pathlib import Path

import pytest

from Utility.Functions import (
    fileMatches, inFileList, inFileDict, getFileNameFromFileList, getFilesNameFromFileList, pathToStr, fileName,
    ensureExecutable
)


def test_file_matches_str_and_path():
    assert fileMatches('test.txt', 'test.txt')
    assert fileMatches('test.txt', 'te*.txt')
    assert fileMatches('test.txt', '*st.txt')
    assert fileMatches('test.txt', 'test.*')
    assert fileMatches(Path('folder/test.txt'), 'test.*')
    assert fileMatches('test.txt', Path('test.txt'))
    assert not fileMatches('test.txt', 'other.txt')
    assert not fileMatches('test.txt', '*.dat')


def test_file_lists_with_paths():
    files = [Path('x/abc_out.dat'), Path('x/abc_pr001.dat'), 'abc_pr002.dat', Path('x/b.txt')]
    assert getFileNameFromFileList('*_out.dat', files) == 'abc_out.dat'
    assert getFileNameFromFileList('missing.dat', iter(files)) == ''
    assert getFilesNameFromFileList('*_pr*.dat', files) == ['abc_pr001.dat', 'abc_pr002.dat']
    assert inFileList('input.json', ['tri.inp', 'input.json'])
    assert inFileDict(Path('x/tri.inp'), {'tri.inp': 'tooltip'}) == ('tri.inp', 'tooltip')
    assert inFileDict('none', {'tri.inp': 'tooltip'}) is False


def test_iterdir(tmp_path):
    for name in ['run_out.dat', 'run_indat.dat', 'other.txt']:
        (tmp_path / name).write_text('')
    assert getFileNameFromFileList('*_indat.dat', tmp_path.iterdir()) == 'run_indat.dat'


def test_path_helpers():
    assert pathToStr(None) == ''
    assert pathToStr(Path('a') / 'b') == str(Path('a') / 'b')
    assert fileName(Path('a/b.txt')) == 'b.txt'
    assert fileName('b.txt') == 'b.txt'


@pytest.mark.skipif(sys.platform == 'win32', reason='no executable flag on Windows')
def test_ensure_executable(tmp_path):
    """Binaries without executable flag (e.g. unpacked from an archive) are made executable before a run"""

    binary = tmp_path / 'SDTrimSP.exe'
    binary.write_bytes(b'\x7fELF')
    binary.chmod(0o640)
    assert not os.access(binary, os.X_OK)
    assert ensureExecutable(binary)
    assert os.access(binary, os.X_OK) and binary.stat().st_mode & 0o777 == 0o750
    assert ensureExecutable(binary)
    assert not ensureExecutable(tmp_path / 'missing') and not ensureExecutable(None)
