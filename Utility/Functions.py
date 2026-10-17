from typing import Any, Iterable, List, Union, Tuple, Optional
from datetime import datetime
from platform import system
from pathlib import Path
from re import sub, findall
import logging

import numpy as np

from Utility.Styles import paletteQColor



def limitSum(objects: list, maximum: float):
    """
    Limits the sum of the values held by the object.value() method to the given maximum.
    The last object's field fills up to the maximum, if possible, and is also disabled.

    :param objects: objects of which the sum should be used for limiting
    :param maximum: maximum sum
    """

    len_objects = len(objects)
    if not len_objects:
        return

    # int for integer spin boxes
    total: float = 0
    for obj in objects[:-1]:
        obj.setEnabled(True)
        new_total = total + obj.value()
        if new_total > maximum:
            obj.setValue(maximum - total)
            total = maximum
        else:
            total = new_total

    if len_objects > 1:
        objects[-1].setValue(maximum - total)
        objects[-1].setEnabled(False)
    else:
        objects[0].setValue(maximum)
        objects[0].setEnabled(False)


def normalizeList(numbers: List[float], total: int = 1, digits: int = 5) -> List[float]:
    """
    Normalizes list numbers to sum of total

    :param numbers: list to be normalized
    :param total: (optional) value to be normalized to
    :param digits: (optional) max number of output digits

    :return: normalized list
    """

    if not numbers:
        return numbers
    total_init = sum(numbers)
    if not total_init:
        return [total / len(numbers)] * len(numbers)
    numbers_rounded = [round(total * num / total_init, digits) for num in numbers]
    if len(numbers_rounded) == 1:
        return numbers_rounded
    numbers_return = numbers_rounded[:-1]
    numbers_return.append(round(total - sum(numbers_return), digits))
    return numbers_return


def dateStr(fmt: str = '%a. %b %d %H:%M:%S %Y') -> str:
    """
    Returns date as string

    :param fmt: (optional) format specification

    :return: string of date
    """

    return datetime.now().strftime(fmt)


def alphanumeric(string: str) -> str:
    """
    Returns string with all non-alphanumeric characters deleted

    :param string: input string

    :return: cleaned string
    """

    return sub(r'[^0-9a-zA-Z_]+', '', string)


def roundToStr(number: float) -> str:
    """
    Round number to string

    :param number: number to be rounded

    :return: string representation
    """

    if number >= 1.e-3:
        return f'{number:.3f}'
    return f'{number:.2e}'


def fileName(file: Union[str, Path]) -> str:
    """
    Returns the name of a file. Path objects are reduced to their final component, strings are returned unchanged

    :param file: filename or Path object

    :return: name of file
    """

    if isinstance(file, Path):
        return file.name
    return file


def fileMatches(file: Union[str, Path], match_file: Union[str, Path]) -> bool:
    """
    Returns True if file matches the match_file, otherwise False. Also supports wildcards (*) in match_file.
    Path objects are compared by their name only

    e.g.:
        fileMatches('test.txt', 'test.txt') -> True
        fileMatches('test.txt', 'te*.txt') -> True
        fileMatches('test.txt', '*st.txt') -> True
        fileMatches('test.txt', 'test.*') -> True
        fileMatches(Path('folder/test.txt'), 'test.*') -> True

    :param file: filename or Path to be checked against
    :param match_file: filename or Path that should match

    :return: if match_file matches file
    """

    file = fileName(file)
    match_file = fileName(match_file)

    # no wildcard (*)
    if '*' not in match_file:
        return file == match_file

    # wildcard (*)
    split_file = file.split('.')
    prefix_file = '.'.join(split_file[0:-1])
    suffix_file = split_file[-1]

    split_match_file = match_file.split('.')
    prefix_match_file = '.'.join(split_match_file[0:-1]).replace('*', '.*')
    suffix_match_file = split_match_file[-1].replace('*', '.*')

    prefix_match = False
    prefix_find = findall(prefix_match_file, prefix_file)
    if prefix_find and prefix_file == prefix_find[0]:
        prefix_match = True
    if not prefix_match:
        return False

    suffix_match = False
    suffix_find = findall(suffix_match_file, suffix_file)
    if suffix_find and suffix_file == suffix_find[0]:
        suffix_match = True
    if not suffix_match:
        return False

    return True


def inFileList(file: Union[str, Path], files_list: Iterable[Union[str, Path]]) -> bool:
    """
    Returns True if file is in files_list, otherwise False. Also supports wildcards (*) in file_list

    e.g.:
        inFileList('test.txt', ['test.txt', ...]) -> True
        inFileList('test.txt', ['t*.txt', ...]) -> True
        inFileList('test.txt', ['test.*', ...]) -> True

    :param file: filename or Path to be checked against
    :param files_list: iterable of filenames or Paths that should match

    :return: if any element of files_list matches file
    """

    for check_file in files_list:
        if fileMatches(file, check_file):
            return True
    return False


def inFileDict(file: Union[str, Path], files_dict: dict) -> Union[Tuple[Union[str, Path], Any], bool]:
    """
    Returns key-value-pair if file is in files_dict(key), otherwise False. Also supports wildcards (*) in files_dict

    e.g.:
        inFileDict('test.txt', {'test.txt': 'xxx', ...}) -> ('test.txt', 'xxx')
        inFileDict('test.txt', {'t*.txt': 'xxx', ...}) -> ('t*.txt', 'xxx')
        inFileDict('test.txt', {'test.*': 'xxx', ...}) -> ('test.*', 'xxx')

    :param file: filename or Path to be checked against
    :param files_dict: dictionary with keys (filenames or Paths) acting as list that should match

    :return: (key, value) of corresponding entry in files_dict
             or False
    """
    for key, value in files_dict.items():
        if fileMatches(file, key):
            return key, value
    return False


def getFileNameFromFileList(file: Union[str, Path], files_list: Iterable[Union[str, Path]]) -> str:
    """
    Returns name of first file in files_list that matches file. File supports wildcards (*).
    files_list can also be a generator of Paths, e.g. folder.iterdir()

    e.g.:
        getFileNameFromFileList('test.txt', ['test.txt', ...]) -> 'test.txt'
        getFileNameFromFileList('test2.txt', ['test.txt', ...]) -> ''
        getFileNameFromFileList('t*.txt', ['test.txt', ...]) -> 'test.txt'
        getFileNameFromFileList('test.*', [Path('folder/test.txt'), ...]) -> 'test.txt'

    :param file: filename to be matched
    :param files_list: iterable of filenames or Paths to be matched against

    :return: name of matching file in files_list
             or ''
    """

    for check_file in files_list:
        if fileMatches(check_file, file):
            return fileName(check_file)
    return ''


def getFilesNameFromFileList(file: Union[str, Path], files_list: Iterable[Union[str, Path]]) -> List[str]:
    """
    Returns names of all files in files_list that match file. File supports wildcards (*).
    files_list can also be a generator of Paths, e.g. folder.iterdir()

    e.g.:
        getFilesNameFromFileList('test*.txt', ['test1.txt', 'test2.txt' ...]) -> ['test1.txt', 'test2.txt']

    :param file: filename to be matched
    :param files_list: iterable of filenames or Paths to be matched against

    :return: list of names from files_list that fulfill the match
    """

    matches = []
    for check_file in files_list:
        if fileMatches(check_file, file):
            matches.append(fileName(check_file))
    return matches


def fileToNpArray(filename: Path, skip_header: int = 0, skip_footer: int = 0, usecols: Optional[Tuple[int, ...]] = None, colum_required: Optional[int] = None) -> np.ndarray:
    """
    Use this function instead of numpy genfromtxt, since it is very slow. Reads file as numpy array.

    :param filename: name of file
    :param skip_header: (optional) number of lines skipped at beginning
    :param skip_footer: (optional) number of lines skipped at end
    :param usecols: (optional) index of used columns
    :param colum_required: (optional) number of required columns; used if columns are divided into multiple lines

    :return: numpy.array
    """

    with open(filename, 'r', encoding='utf-8', errors='replace') as file:
        for _ in range(skip_header):
            file.readline()
        lines = file.readlines()

    # columns might spread over multiple lines
    if colum_required is not None:
        line_count = 0
        colum_count = 0

        for line in lines:
            line_count += 1
            colum_count += len(line.split())
            if colum_count > colum_required:
                break

        if line_count > 1:
            lines = [' '.join(lines[i:i+line_count]) for i in range(0, len(lines), line_count)]

    data = np.array([[float(var) for var in line.split()] for line in lines[:len(lines) - skip_footer]])
    if usecols is None:
        return data

    if len(data.shape) == 2 and data.shape[1] >= len(usecols):
        data = data[:, list(usecols)]
    return data


class SafeInt(int):
    """
    Integer class that first converts to float before converting to int
    """

    def __new__(cls, value=0):
        return super().__new__(cls, float(value))


def intSafe(string: str, fallback: int = 0, log_warning: bool = False) -> int:
    """
    Tries to convert the string to an integer and returns it, if it fails, it will return the fallback value

    :param string: string to be converted
    :param fallback: (optional) fallback value
    :param log_warning: (optional) enable logging of warnings
    """

    try:
        return int(float(string))
    except ValueError:
        if log_warning:
            logging.warning(f'Could not convert "{string}" to int, using {fallback} instead.')
        return fallback


def floatSafe(string: str, fallback: float = 0, log_warning: bool = False) -> float:

    """
    Tries to convert the string to a float and returns it, if it fails, it will return the fallback value

    :param string: string to be converted
    :param fallback: (optional) fallback value
    :param log_warning: (optional) enable logging of warnings
    """

    try:
        return float(string)
    except ValueError:
        if log_warning:
            logging.warning(f'Could not convert "{string}" to float, using {fallback} instead.')
        return fallback


def splitSafe(string: str, seperator: Optional[str] = None, length: int = -1) -> Union[list, bool]:
    """
    Splits a string on a seperator. The resulting list should be of a specific length, otherwise False is returned

    :param string: string to be split
    :param seperator: string for splitting
    :param length: needed length
    """

    result = string.split(seperator)
    if length == -1 or length == len(result):
        return result
    return False


def getUniqueColor(index: int, length: int):
    """
    Generates unique color based on index and total length of requested colors

    :param index: index of color
    :param length: length of requested colors
    :return: unique <QColor> per index
    """

    return paletteQColor(index, 127)


def getPeriodicCoords(coord: np.ndarray, bounds: Tuple[float, float] = (0, 1), tol: float = 1e-8):
    """
    Generates 3D coordinates including periodic images for boundary points

    :param coord: coordinate to check
    :param bounds: (optional) boundaries in all directions
    :param tol: (optional) tolerance to boundaries
    :return: coordinates including periodic images from initial coord
    """

    bounds_len = bounds[1] - bounds[0]

    shifts = []
    coords = []
    for c in coord:
        if abs(c - bounds[0]) < tol:
            shifts.append([c, c + bounds_len])
        elif abs(c - bounds[1]) < tol:
            shifts.append([c, c - bounds_len])
        else:
            shifts.append([c])

    for x in shifts[0]:
        for y in shifts[1]:
            for z in shifts[2]:
                coords.append((x, y, z))

    return np.array(coords)


def setDictIfNotExists(dictionary: dict, key, value):
    """
    Sets value to key-entry of dictionary

    :param dictionary: dictionary
    :param key: key object
    :param value: value object
    """

    if key not in dictionary.keys():
        dictionary[key] = value


def readlines(file, *args, comments: Union[str, List[str], None] = None, strip_lines: bool = True, **kwargs) -> List[str]:
    """
    Reads lines from a text file and excludes lines that start with given comments

    :param file: filepath
    :param comments: comment(s) to be excluded
    :param strip_lines: strip lines
    :return: list of lines
    """

    if comments is None:
        comments = []
    elif isinstance(comments, str):
        comments = [comments]

    exclude_empty = False
    if '' in comments:
        exclude_empty = True
        comments.remove('')

    lines = []
    with open(file, *args, **kwargs) as f:
        for line in f.readlines():
            if strip_lines:
                line = line.strip()
            if any(line.startswith(comment) for comment in comments):
                continue
            if exclude_empty and not line:
                continue
            lines.append(line)

    return lines

def isNativeExecutable(file: Path) -> bool:
    """
    Returns True if file is an executable binary for the current operating system.
    The check is based on the file header, since the file extension is not reliable (e.g. linux binaries named *.exe)

    :param file: path to file
    """

    magic_numbers = {
        'Windows': (b'MZ',),
        'Linux': (b'\x7fELF',),
        'Darwin': (b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe', b'\xca\xfe\xba\xbe', b'\xfe\xed\xfa\xcf'),
    }.get(system(), ())

    # on Windows, libraries (*.dll) have the same header as executables
    if system() == 'Windows' and file.suffix.lower() != '.exe':
        return False

    try:
        if not file.is_file():
            return False
        with open(file, 'rb') as f:
            header = f.read(4)
    except OSError:
        return False

    return any(header.startswith(magic) for magic in magic_numbers)


def findExecutables(folder: Path, max_depth: int = 3, skip_folders: Iterable[str] = ()) -> List[Path]:
    """
    Returns all executable binaries for the current operating system in folder and its subfolders

    :param folder: folder to search in
    :param max_depth: (optional) maximum depth of subfolders
    :param skip_folders: (optional) names of folders that are not searched (case-insensitive)
    """

    skip = {name.lower() for name in skip_folders}
    executables = []

    def search(current: Path, depth: int):
        try:
            entries = sorted(current.iterdir())
        except OSError:
            return
        for entry in entries:
            if entry.is_dir():
                if depth < max_depth and entry.name.lower() not in skip:
                    search(entry, depth + 1)
            elif isNativeExecutable(entry):
                executables.append(entry)

    if folder is not None and folder.is_dir():
        search(folder, 0)
    return executables


def pathToStr(path: Path | None) -> str:
    """
    Returns a stringified path

    :param path: Path object or None
    :return: stringified path or empty string
    """

    if isinstance(path, Path):
        return str(path)
    return ''


def bestVersion(versions: List[str], version_name: str) -> Tuple[int, bool]:
    """
    Returns the index of the selectable version that suits the detected version best and if it matches exactly.
    If the detected version is not listed, the highest listed version below it is used (or the lowest listed version)

    :param versions: selectable versions, e.g. ['6.01', '7.00, 7.01', '7.07']
    :param version_name: detected version name, e.g. 'SDTrimSP v7.05'

    :return: (index or -1 if no version number is found, exact match)
    """

    version_numbers = findall(r'\d+(?:\.\d+)?', version_name)
    if not version_numbers:
        return -1, False
    detected = version_numbers[0]

    candidates = []
    for i, entry in enumerate(versions):
        for version in entry.split(','):
            version = version.strip()
            if version == detected:
                return i, True
            try:
                candidates.append((float(version), i))
            except ValueError:
                pass

    if not candidates:
        return -1, False

    detected_value = float(detected)
    lower = [candidate for candidate in candidates if candidate[0] <= detected_value]
    if lower:
        return max(lower)[1], False
    return min(candidates)[1], False


def lowerProcessPriority(pid: int):
    """
    Lowers the priority of a process (below normal), so that the GUI stays responsive while many simulations run

    :param pid: id of the process
    """

    if pid <= 0:
        return
    try:
        if system() == 'Windows':
            import ctypes
            kernel32 = getattr(ctypes, 'windll').kernel32
            # PROCESS_SET_INFORMATION | PROCESS_QUERY_INFORMATION
            handle = kernel32.OpenProcess(0x0200 | 0x0400, False, pid)
            if handle:
                # BELOW_NORMAL_PRIORITY_CLASS
                kernel32.SetPriorityClass(handle, 0x4000)
                kernel32.CloseHandle(handle)
        else:
            import os
            getattr(os, 'setpriority')(getattr(os, 'PRIO_PROCESS'), pid, 10)
    except (OSError, AttributeError) as error:
        logging.debug(f'Could not lower the priority of process {pid}: {error}')
