from pathlib import Path

from Utility.Functions import (
    fileMatches, inFileList, inFileDict, getFileNameFromFileList, getFilesNameFromFileList, pathToStr, fileName
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
