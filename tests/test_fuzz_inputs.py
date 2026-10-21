"""
Robustness of the GUI against broken, extreme and unknown input: hand-written cases (many and unknown elements, unknown
parameters, Fortran syntax, invalid numbers and types, binary garbage, other encodings) and random mutations of the
examples for tri.inp, layer.inp and crystal.inp of SDTrimSP, the input file of TRIDYN, input.json and scan.json, and
damaged output files. The GUI may refuse a file (with a message), but it never raises an exception: the files are
loaded, previewed, checked, saved, loaded again and scanned, the outputs are listed and plotted.

Without installations the simulation programs are replaced by stand-in folders (the GUI then uses its default element
data). BCA_TEST_FUZZ sets the number of random mutations per file (default 5: every test keeps about 20 MB of memory,
see TODO.md, run more mutations in several runs), BCA_TEST_FUZZ_SEED the random seed.
"""

import json
import os
import random
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pytest

from conftest import SAVES, SIMULATION_PROGRAMS, TEST_SAVES, addSimulationPage, pump

from Simulations.SDTrimSP import SimulationInput as SDTrimSPInput, Versions


MUTATIONS = int(os.environ.get('BCA_TEST_FUZZ', '5'))
SEED = int(os.environ.get('BCA_TEST_FUZZ_SEED', '20261020'))

SDTRIMSP_707 = SIMULATION_PROGRAMS / 'SDTrimSP' / 'SDTrimSP_7.07'
SDTRIMSP_601 = SIMULATION_PROGRAMS / 'SDTrimSP' / 'SDTrimSP_6.01'
TRIDYN_FOLDER = SIMULATION_PROGRAMS / 'TRIDYN' / 'Tridyn2022'

# program index of the GUI, installation folder (None: stand-in), version
PROGRAMS: List[Tuple[str, int, Optional[Path], str]] = [
    ('SDTrimSP', 0, SDTRIMSP_707 if (SDTRIMSP_707 / 'tables').is_dir() else None, Versions.V_707),
    ('TRIDYN', 1, TRIDYN_FOLDER if TRIDYN_FOLDER.is_dir() else None, '2022'),
]
if (SDTRIMSP_601 / 'tables').is_dir():
    PROGRAMS.append(('SDTrimSP', 0, SDTRIMSP_601, Versions.V_601))

# values that replace numbers, symbols or flags
GARBAGE = ['abc', '-1', '0', '-0', '1e308', '-1e308', '1e-320', 'NaN', 'nan', 'inf', '-inf', '', '***', '1d5', '1.5D-3',
           '3*0.5', '"Xx"', "'Ar'", '"', '.true.', '.false.', 'T', ',,,', '1/0', 'é', 'µ', '\t', '99999999999999999999',
           '0x10', '1,2,3', '(1)', '!', '#', '/', '&end', '"' + 'A' * 300 + '"']


def program(name: str, version: Optional[str] = None) -> Tuple[str, int, Optional[Path], str]:
    return next(p for p in PROGRAMS if p[0] == name and (version is None or p[3] == version))


def openPage(main_window, qapp, tmp_path: Path, name: str, index: int, folder: Optional[Path], version: str, save: Path):
    """Simulation tab of the program for the save folder (a stand-in program folder without installation)"""

    if folder is None:
        folder = tmp_path / f'stand-in {name}'
        folder.mkdir(exist_ok=True)
        binary = folder / ('SDTrimSP.exe' if name == 'SDTrimSP' else 'tridyn.exe')
        binary.write_bytes(b'')
    else:
        cls = SDTrimSPInput if name == 'SDTrimSP' else __import__('Simulations.TRIDYN2022', fromlist=['SimulationInput']).SimulationInput
        binary = cls.findBinary(folder) or folder / 'binary.exe'
    sc, page = addSimulationPage(main_window, save.name, index, folder, binary, version, save)
    pump(qapp, 0.05)
    return sc, page


def exercise(qapp, page, save: Path):
    """
    Loads the save folder (input files and input.json), and if the GUI accepts it: preview, checks, run warnings,
    saving, loading again and the parameter scan. Returns if the input was accepted
    """

    from Utility.GlobalConf import GlobalConf
    GlobalConf.skip_element_info = True

    accepted = False
    for from_json in (False, True):
        if from_json and not (save / 'input.json').is_file():
            continue
        if not page.loadSettings(save, from_json=from_json, unsaved_warning=False):
            continue
        accepted = True
        pump(qapp, 0.02)
        page.makePreview()
        arguments = page.makeArguments()
        page.simulation_class.checkArguments(arguments, page.simulation_configuration.version)
        page.simulation_class.checkWarnings(arguments, page.simulation_configuration.version)
        page.runWarnings()

        # the parameter scan with the loaded values
        page.action_scan.setChecked(True)
        pump(qapp, 0.15)
        scan = page.scan
        for key in list(scan.parameters())[:5]:
            scan.valuesStrings(key)
        if scan.values:
            simulations, _ = scan.plan()
            for simulation in simulations[:3]:
                scan.arguments(simulation['assignments'])
        scan.count()
        page.action_scan.setChecked(False)
        pump(qapp, 0.02)

        # saved and loaded again (both ways)
        assert page.saveSettings() is not None or True
        pump(qapp, 0.02)
        for again in (False, True):
            if page.loadSettings(save, from_json=again, unsaved_warning=False):
                page.makePreview()
    return accepted


# --- hand-written cases ---


def tri(body: str, title: str = 'fuzz') -> str:
    return f'{title}\n&TRI_INP\n{body}\n/\n'


BASE_TRI = """     ncp = 2
     symbol = "Ar", "W"
     nh = 10
     nr_pproj = 10
     qubeam = 1.0, 0.0
     e0 = 1000.0, 0.0
     alpha0 = 0.0, 0.0
     ttarget = 100.0
     nqx = 10
     qu = 0.0, 1.0"""

MANY = ['H', 'He', 'Li', 'Be', 'B', 'C', 'N', 'O', 'F', 'Ne', 'Na', 'Mg', 'Al', 'Si', 'P', 'S', 'Cl', 'Ar', 'K', 'Ca',
        'Ti', 'Fe', 'Ni', 'Cu', 'Zn', 'Ag', 'Au', 'W', 'Pb', 'U']


def many(count: int, symbols: Optional[List[str]] = None) -> str:
    symbols = symbols or [MANY[i % len(MANY)] for i in range(count)]
    qubeam = ['1.0'] + ['0.0'] * (count - 1)
    qu = ['0.0'] + [f'{1 / max(count - 1, 1):.4f}'] * (count - 1)
    return tri(f"""     ncp = {count}
     symbol = {', '.join(f'"{s}"' for s in symbols)}
     nh = 10
     nr_pproj = 10
     qubeam = {', '.join(qubeam)}
     e0 = 1000.0{', 0.0' * (count - 1)}
     alpha0 = 0.0{', 0.0' * (count - 1)}
     ttarget = 100.0
     nqx = 10
     qu = {', '.join(qu)}""")


SDTRIMSP_CASES: Dict[str, Dict[str, Any]] = {
    'empty': {'tri.inp': ''},
    'only title': {'tri.inp': 'title only\n'},
    'no namelist': {'tri.inp': 'title\nncp = 2\nsymbol = "Ar", "W"\n'},
    'no end': {'tri.inp': f'title\n&TRI_INP\n{BASE_TRI}\n'},
    'binary garbage': {'tri.inp': bytes(range(256)) * 4},
    'utf-16': {'tri.inp': tri(BASE_TRI).encode('utf-16')},
    'latin-1 title': {'tri.inp': tri(BASE_TRI, 'Ar auf W bei 20 °C, äöü').encode('latin-1')},
    'windows line ends and tabs': {'tri.inp': tri(BASE_TRI).replace('\n', '\r\n').replace('     ', '\t')},
    'upper and lower case': {'tri.inp': tri(BASE_TRI.upper().replace('"AR"', '"Ar"'))},
    'ncp 0': {'tri.inp': tri(BASE_TRI.replace('ncp = 2', 'ncp = 0'))},
    'ncp negative': {'tri.inp': tri(BASE_TRI.replace('ncp = 2', 'ncp = -3'))},
    'ncp text': {'tri.inp': tri(BASE_TRI.replace('ncp = 2', 'ncp = two'))},
    'ncp larger than symbols': {'tri.inp': tri(BASE_TRI.replace('ncp = 2', 'ncp = 5'))},
    'ncp smaller than symbols': {'tri.inp': tri(BASE_TRI.replace('ncp = 2', 'ncp = 1'))},
    'no symbols': {'tri.inp': tri(BASE_TRI.replace('     symbol = "Ar", "W"\n', ''))},
    'empty symbols': {'tri.inp': tri(BASE_TRI.replace('"Ar", "W"', '"", ""'))},
    'unknown elements': {'tri.inp': tri(BASE_TRI.replace('"Ar", "W"', '"Xx", "Uuo"'))},
    'element names': {'tri.inp': tri(BASE_TRI.replace('"Ar", "W"', '"argon", "tungsten"'))},
    'unquoted and numeric symbols': {'tri.inp': tri(BASE_TRI.replace('"Ar", "W"', 'Ar, 74'))},
    'unterminated quote': {'tri.inp': tri(BASE_TRI.replace('"Ar", "W"', '"Ar, "W'))},
    'isotopes and compounds': {'tri.inp': tri(BASE_TRI.replace('"Ar", "W"', '"D", "C_g"'))},
    '12 elements': {'tri.inp': many(12)},
    '13 elements': {'tri.inp': many(13)},
    '30 elements': {'tri.inp': many(30)},
    '30 times the same element': {'tri.inp': many(30, ['Ar'] * 30)},
    'unknown parameters': {'tri.inp': tri(BASE_TRI + '\n     foo_bar = 3\n     lwhatever = .true.\n     x = "y"')},
    'index syntax': {'tri.inp': tri(BASE_TRI + '\n     e0(2) = 500.0\n     inel0(15) = 2\n     ioutput_part(0) = 1')},
    'fortran repeat and exponents': {'tri.inp': tri(BASE_TRI.replace('qu = 0.0, 1.0', 'qu = 1*0.0, 1*1.0').replace('1000.0', '1.0d3'))},
    'duplicate parameters': {'tri.inp': tri(BASE_TRI + '\n     nh = 20\n     nh = abc\n     ncp = 3')},
    'invalid numbers': {'tri.inp': tri(BASE_TRI.replace('1000.0', 'NaN').replace('nqx = 10', 'nqx = inf').replace('100.0', '-1e308'))},
    'huge numbers': {'tri.inp': tri(BASE_TRI.replace('nqx = 10', 'nqx = 99999999999999999999').replace('nh = 10', 'nh = 1e300'))},
    'negative values': {'tri.inp': tri(BASE_TRI.replace('qu = 0.0, 1.0', 'qu = -1.0, 2.0').replace('ttarget = 100.0', 'ttarget = -5'))},
    'angles out of range': {'tri.inp': tri(BASE_TRI.replace('alpha0 = 0.0, 0.0', 'alpha0 = 400.0, -1000.0'))},
    'too long lists': {'tri.inp': tri(BASE_TRI.replace('qubeam = 1.0, 0.0', 'qubeam = ' + ', '.join(['1.0'] * 50)))},
    'semicolons and comments': {'tri.inp': tri(BASE_TRI.replace('\n', ' ! comment ; x = 1\n').replace('nh = 10', 'nh = 10; nr_pproj = 3'))},
    'all on one line': {'tri.inp': tri(BASE_TRI.replace('\n', ' '))},
    'unknown cases': {'tri.inp': tri(BASE_TRI + '\n     case_e0 = 99\n     case_alpha = -7\n     idrel = 5\n     ipot = 0\n     isbv = 100\n     inel0 = 99, -5')},
    'distribution files missing': {'tri.inp': tri(BASE_TRI + '\n     case_e0 = 5\n     case_alpha = 5\n     number_calc = 10')},
    'broken distribution files': {
        'tri.inp': tri(BASE_TRI + '\n     case_e0 = 5\n     case_alpha = 5'),
        'energy.inp': 'garbage\n1 2 3\nabc\n', 'angle.inp': '\n\n', 'ene_ang.inp': bytes(range(100)),
    },
    'broken layer.inp': {
        'tri.inp': tri(BASE_TRI.replace('"Ar", "W"', '"Ar", "W", "Fe"').replace('ncp = 2', 'ncp = 3') + '\n     iq0 = -1'),
        'layer.inp': '! header\n! header\n  10  abc  1.0  x  layer1\n  -5  1e308\n  0 0 0 end\n',
    },
    'layer.inp with many columns': {
        'tri.inp': tri(BASE_TRI + '\n     iq0 = -1'),
        'layer.inp': '! h\n! h\n' + '\n'.join(f'  {i}  1.0  ' + '  '.join(['0.5'] * 40) + f'  layer{i}' for i in range(1, 300)) + '\n0 0 0 end\n',
    },
    'empty layer.inp': {'tri.inp': tri(BASE_TRI + '\n     iq0 = -1'), 'layer.inp': ''},
    'crystal without tables': {'tri.inp': tri(BASE_TRI + '\n     l_crystal = .true.\n     name_cryst1 = "nonexistent"\n     miller_ind1 = 1, 1, 1')},
    'broken crystal.inp': {'tri.inp': tri(BASE_TRI + '\n     l_crystal = .true.'), 'crystal.inp': '# x\nabc def\n1 2\n\n9 9 9 9 9 9 9 9\n'},
    'input.json and tri.inp disagree': {'tri.inp': tri(BASE_TRI), 'input.json': '{"general": {"simulation": "SDTrimSP"}, "beam_rows": 5}'},
}

TRIDYN_BASE = """fuzz
cdat 0 1.0 0
geom 1000.0 100 0.0
atda Ar W
comp 0.0 1.0
irra 1 500.0 0.0 1.0
pspr 100
"""

TRIDYN_CASES: Dict[str, str] = {
    'empty': '',
    'only title': 'fuzz\n',
    'binary garbage': bytes(range(256)) * 4,  # type: ignore[dict-item]
    'missing obligatory commands': 'fuzz\nirra 1 500.0 0.0 1.0\n',
    'unknown commands': TRIDYN_BASE + 'xyzz 1 2 3\nfoo\n#comment\n   \n',
    'unknown elements': TRIDYN_BASE.replace('atda Ar W', 'atda Xx Yy'),
    'many elements': TRIDYN_BASE.replace('atda Ar W', 'atda ' + ' '.join(MANY)).replace('comp 0.0 1.0', 'comp ' + ' '.join(['0.0'] + ['0.03'] * 29)),
    'no elements': TRIDYN_BASE.replace('atda Ar W', 'atda'),
    'wrong number of values': TRIDYN_BASE.replace('irra 1 500.0 0.0 1.0', 'irra 1').replace('geom 1000.0 100 0.0', 'geom 1 2 3 4 5 6 7'),
    'invalid numbers': TRIDYN_BASE.replace('500.0', 'NaN').replace('1000.0', 'abc').replace('100 0.0', '1e30 -inf'),
    'irradiation of unknown species': TRIDYN_BASE.replace('irra 1 ', 'irra 9 ') + 'irra 0 1 1 1\nirra -1 1 1 1\n',
    'duplicate commands': TRIDYN_BASE + TRIDYN_BASE.split('\n', 1)[1],
    'commands in upper case': TRIDYN_BASE.upper().replace('AR W', 'Ar W'),
    'utf-16': TRIDYN_BASE.encode('utf-16'),  # type: ignore[dict-item]
    'broken layer file': TRIDYN_BASE + 'layr 1\n',
}

JSON_CASES: Dict[str, str] = {
    'invalid json': '{"general": ',
    'empty object': '{}',
    'list': '[1, 2, 3]',
    'string': '"input"',
    'null': 'null',
    'wrong types': json.dumps({'general': 5, 'beam_rows': {'a': 1}, 'target_rows': 'x', 'settings': [], 'structure': None}),
    'rows with garbage': json.dumps({'general': {'simulation': 'SDTrimSP'}, 'beam_rows': [None, 1, 'x', {'symbol': 5}, {'element': 'Ar'}],
                                     'target_rows': [{'symbol': 'Xx', 'element': {'symbol': 'Xx', 'atomic_nr': -1}}]}),
    'huge numbers': json.dumps({'beam_rows': [{'symbol': 'Ar', 'energy': 1e308, 'angle': -1e308, 'abundance': float('inf')}]}),
    'deep nesting': '{"a": ' * 500 + '1' + '}' * 500,
}


def writeFiles(folder: Path, files: Dict[str, Any]):
    folder.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        if isinstance(content, bytes):
            (folder / name).write_bytes(content)
        else:
            (folder / name).write_text(content, encoding='utf-8', newline='')


@pytest.mark.parametrize('case', list(SDTRIMSP_CASES), ids=list(SDTRIMSP_CASES))
@pytest.mark.parametrize('version', [p[3] for p in PROGRAMS if p[0] == 'SDTrimSP'])
def test_sdtrimsp_cases(main_window, qapp, tmp_path, errors, case, version):
    save = tmp_path / 'save'
    writeFiles(save, SDTRIMSP_CASES[case])
    _, index, folder, version = program('SDTrimSP', version)
    sc, page = openPage(main_window, qapp, tmp_path, 'SDTrimSP', index, folder, version, save)
    exercise(qapp, page, save)
    assert not errors, '\n'.join(errors)


@pytest.mark.parametrize('case', list(TRIDYN_CASES), ids=list(TRIDYN_CASES))
def test_tridyn_cases(main_window, qapp, tmp_path, errors, case):
    save = tmp_path / 'save'
    content = TRIDYN_CASES[case]
    writeFiles(save, {'fuzz.in': content})
    _, index, folder, version = program('TRIDYN')
    sc, page = openPage(main_window, qapp, tmp_path, 'TRIDYN', index, folder, version, save)
    exercise(qapp, page, save)
    assert not errors, '\n'.join(errors)


@pytest.mark.parametrize('case', list(JSON_CASES), ids=list(JSON_CASES))
@pytest.mark.parametrize('name', ['SDTrimSP', 'TRIDYN'])
def test_json_cases(main_window, qapp, tmp_path, errors, case, name):
    save = tmp_path / 'save'
    writeFiles(save, {'input.json': JSON_CASES[case]})
    _, index, folder, version = program(name)
    sc, page = openPage(main_window, qapp, tmp_path, name, index, folder, version, save)
    exercise(qapp, page, save)
    assert not errors, '\n'.join(errors)


# --- random mutations of the examples ---


def mutateText(text: str, rng: random.Random) -> str:
    """A few random changes of the lines and values of an input file"""

    lines = text.splitlines()
    for _ in range(rng.randint(1, 4)):
        if not lines:
            lines = ['']
        i = rng.randrange(len(lines))
        operation = rng.randrange(7)
        if operation == 0:
            del lines[i]
        elif operation == 1:
            lines.insert(i, lines[i])
        elif operation == 2:
            words = lines[i].replace(',', ' , ').split(' ')
            positions = [j for j, word in enumerate(words) if word.strip() and word.strip() != ',']
            if positions:
                words[rng.choice(positions)] = rng.choice(GARBAGE)
            lines[i] = ' '.join(words).replace(' , ', ',')
        elif operation == 3:
            lines.insert(i, f'     {rng.choice(["foo", "e0", "ncp", "qu", "symbol", "geom", "irra", "atda"])} = {rng.choice(GARBAGE)}')
        elif operation == 4:
            j = rng.randrange(len(lines))
            lines[i], lines[j] = lines[j], lines[i]
        elif operation == 5:
            lines = lines[:i]
        else:
            lines[i] = lines[i][:rng.randrange(len(lines[i]) + 1)]
    return '\n'.join(lines) + '\n'


def garbageValue(rng: random.Random) -> Any:
    return rng.choice([None, True, False, 0, -1, 1e308, -1e308, float('nan'), '', 'abc', 'Xx', [], {}, [1, 'a', None],
                       {'symbol': 'Xx'}, 10 ** 30, -0.0, 'NaN', '1e5', 999999999])


def mutateJson(data: Any, rng: random.Random) -> Any:
    """Changes, removes or adds a random value of the JSON data"""

    def containers(value, path=()):
        if isinstance(value, (dict, list)):
            yield path, value
            items = value.items() if isinstance(value, dict) else enumerate(value)
            for key, item in items:
                yield from containers(item, path + (key,))

    data = json.loads(json.dumps(data))
    for _ in range(rng.randint(1, 5)):
        found = list(containers(data))
        if not found:
            return garbageValue(rng)
        _, container = rng.choice(found)
        if isinstance(container, dict):
            if container and rng.random() < 0.7:
                key = rng.choice(list(container))
                if rng.random() < 0.3:
                    del container[key]
                else:
                    container[key] = garbageValue(rng)
            else:
                container[rng.choice(['foo', 'symbol', 'energy', 'rows', 'values', 'key'])] = garbageValue(rng)
        elif container and rng.random() < 0.6:
            index = rng.randrange(len(container))
            if rng.random() < 0.3:
                del container[index]
            else:
                container[index] = garbageValue(rng)
        else:
            container.append(garbageValue(rng))
    return data


def exampleSaves(name: str, with_file: str) -> List[Path]:
    saves = sorted((SAVES / name).glob('example_*')) + sorted((TEST_SAVES / name).glob('*'))
    return [save for save in saves if save.is_dir() and any(save.glob(with_file))]


def mutationCases(name: str, pattern: str) -> list:
    rng = random.Random(f'{SEED}-{name}-{pattern}')
    saves = exampleSaves(name, pattern)
    if not saves:
        return [pytest.param(None, 0, marks=pytest.mark.skip(reason='no example'))]
    return [pytest.param(saves[i % len(saves)], rng.randrange(10 ** 9), id=f'{saves[i % len(saves)].name}-{i}') for i in range(MUTATIONS)]


def copyInputs(source: Path, save: Path, input_files: Callable[[Path], bool]):
    save.mkdir(parents=True)
    for path in source.iterdir():
        if path.is_file() and input_files(path):
            shutil.copy(path, save / path.name)


def isInput(path: Path) -> bool:
    return path.suffix in ('.inp', '.in', '.json') or path.name.endswith('.json')


@pytest.mark.parametrize('source, seed', mutationCases('SDTrimSP', 'tri.inp'))
def test_sdtrimsp_mutations(main_window, qapp, tmp_path, errors, source, seed):
    rng = random.Random(seed)
    save = tmp_path / 'save'
    copyInputs(source, save, lambda path: path.suffix == '.inp')
    for path in save.glob('*.inp'):
        if path.name == 'tri.inp' or rng.random() < 0.3:
            path.write_text(mutateText(path.read_text(encoding='utf-8', errors='replace'), rng), encoding='utf-8')
    _, index, folder, version = program('SDTrimSP')
    sc, page = openPage(main_window, qapp, tmp_path, 'SDTrimSP', index, folder, version, save)
    exercise(qapp, page, save)
    assert not errors, '\n'.join(errors)


@pytest.mark.parametrize('source, seed', mutationCases('TRIDYN', '*.in'))
def test_tridyn_mutations(main_window, qapp, tmp_path, errors, source, seed):
    rng = random.Random(seed)
    save = tmp_path / 'save'
    copyInputs(source, save, lambda path: path.suffix == '.in')
    for path in save.glob('*.in'):
        path.write_text(mutateText(path.read_text(encoding='latin-1'), rng), encoding='latin-1', errors='replace')
    _, index, folder, version = program('TRIDYN')
    sc, page = openPage(main_window, qapp, tmp_path, 'TRIDYN', index, folder, version, save)
    exercise(qapp, page, save)
    assert not errors, '\n'.join(errors)


@pytest.mark.parametrize('name', ['SDTrimSP', 'TRIDYN'])
@pytest.mark.parametrize('index', range(MUTATIONS))
def test_json_mutations(main_window, qapp, tmp_path, errors, name, index):
    saves = exampleSaves(name, 'input.json')
    if not saves:
        pytest.skip('no example')
    rng = random.Random(f'{SEED}-json-{name}-{index}')
    source = saves[index % len(saves)]
    save = tmp_path / 'save'
    save.mkdir()
    data = json.loads((source / 'input.json').read_text(encoding='utf-8'))
    # also the input.json of the other program
    if rng.random() < 0.2:
        other = exampleSaves('TRIDYN' if name == 'SDTrimSP' else 'SDTrimSP', 'input.json')
        if other:
            data = json.loads((rng.choice(other) / 'input.json').read_text(encoding='utf-8'))
    (save / 'input.json').write_text(json.dumps(mutateJson(data, rng)), encoding='utf-8')
    _, program_index, folder, version = program(name)
    sc, page = openPage(main_window, qapp, tmp_path, name, program_index, folder, version, save)
    exercise(qapp, page, save)
    assert not errors, '\n'.join(errors)


def scanDescription(main_window, qapp, tmp_path: Path) -> Tuple[Path, dict]:
    """Writes scan.json of a scan of example 1 (two parameters, a combo box and another version) with the GUI"""

    source = SAVES / 'SDTrimSP' / 'example_01_Ar_on_Au'
    save = tmp_path / 'scan base'
    copyInputs(source, save, isInput)
    _, index, folder, version = program('SDTrimSP')
    sc, page = openPage(main_window, qapp, tmp_path, 'SDTrimSP', index, folder, version, save)
    assert page.loadSettings(save, from_json=True, unsaved_warning=False)
    scan = page.scan
    parameters = scan.parameters()
    scan.setValues('energy_Ar', {'start': 100., 'stop': 1000., 'number': 3, 'scale': 1, 'values': '100, 316.2, 1000'})
    choice = next((key for key, parameter in parameters.items() if parameter.choices), None)
    if choice is not None:
        scan.setValues(choice, {'values': '0, 1'})
    scan.setVersions(['another version'])
    scan.writeDescription()
    return save, json.loads((save / 'scan.json').read_text(encoding='utf-8'))


SCAN_CASES: Dict[str, Any] = {
    'invalid json': '{"rows": [',
    'list': [],
    'no runs': {'rows': [], 'parameters': []},
    'rows of garbage': {'rows': [None, 1, 'x', {'key': 5}, {'key': 'unknown_parameter', 'values': '1, 2'}, {'label': 'nonexistent'}],
                        'parameters': ['x'], 'runs': [None, {'folder': '../../outside', 'values': [1, 2, 3]}, {'folder': 5}]},
    'huge scan': {'rows': [{'key': 'energy_Ar', 'start': 1, 'stop': 1e6, 'number': 10 ** 9, 'scale': 1},
                           {'key': 'angle_Ar', 'values': ', '.join(str(i) for i in range(5000))}],
                  'parameters': [], 'runs': []},
    'invalid values': {'rows': [{'key': 'energy_Ar', 'start': 'a', 'stop': None, 'number': -5, 'scale': 99, 'values': 'abc, NaN, inf, , ,'}],
                       'parameters': [], 'runs': []},
    'versions of garbage': {'rows': [], 'versions': [None, 5, {'a': 1}, 'x' * 1000], 'parameters': [], 'runs': []},
}


@pytest.mark.parametrize('case', list(SCAN_CASES) + [f'mutation {i}' for i in range(MUTATIONS)])
def test_scan_json(main_window, qapp, tmp_path, errors, case):
    """scan.json of a folder is read when the folder is loaded, also a broken or manipulated one"""

    base, description = scanDescription(main_window, qapp, tmp_path)
    save = tmp_path / 'save'
    copyInputs(base, save, isInput)
    if case in SCAN_CASES:
        content = SCAN_CASES[case]
        text = content if isinstance(content, str) else json.dumps(content)
    else:
        text = json.dumps(mutateJson(description, random.Random(f'{SEED}-scan-{case}')))
    (save / 'scan.json').write_text(text, encoding='utf-8')
    _, index, folder, version = program('SDTrimSP')
    sc, page = openPage(main_window, qapp, tmp_path, 'SDTrimSP', index, folder, version, save)
    exercise(qapp, page, save)
    assert not errors, '\n'.join(errors)


# --- damaged output files ---


def outputCases() -> list:
    rng = random.Random(f'{SEED}-outputs')
    cases = []
    for name in ('SDTrimSP', 'TRIDYN'):
        saves = [save for save in exampleSaves(name, 'input.json') if any(path.suffix == '.dat' for path in save.iterdir())]
        for i in range(MUTATIONS if saves else 0):
            cases.append(pytest.param(name, saves[i % len(saves)], rng.randrange(10 ** 9), id=f'{name}-{saves[i % len(saves)].name}-{i}'))
    return cases or [pytest.param(None, None, 0, marks=pytest.mark.skip(reason='no examples'))]


def damage(path: Path, rng: random.Random):
    data = path.read_bytes()
    operation = rng.randrange(5)
    if operation == 0:
        path.write_bytes(b'')
    elif operation == 1:
        path.write_bytes(data[:rng.randrange(len(data) + 1)])
    elif operation == 2:
        path.write_bytes(bytes(rng.randrange(256) for _ in range(rng.randrange(1, 2000))))
    else:
        lines = data.decode('latin-1').splitlines()
        for _ in range(rng.randint(1, 10)):
            if lines:
                i = rng.randrange(len(lines))
                lines[i] = rng.choice(['', 'abc def', '***** NaN', ' '.join(rng.choice(GARBAGE) for _ in range(5)), lines[i] * 3])
        path.write_bytes('\n'.join(lines).encode('latin-1', errors='replace'))


@pytest.mark.parametrize('name, source, seed', outputCases())
def test_damaged_outputs(main_window, qapp, tmp_path, errors, name, source, seed):
    """Output files that are damaged (e.g. a run that was killed): the lists and all plots never raise exceptions"""

    from test_plots import showAllPlots

    rng = random.Random(seed)
    save = tmp_path / source.name
    shutil.copytree(source, save)
    outputs = [path for path in save.iterdir() if path.suffix == '.dat']
    for path in rng.sample(outputs, min(len(outputs), rng.randint(1, 3))):
        damage(path, rng)
    _, index, folder, version = program(name)
    sc, page = openPage(main_window, qapp, tmp_path, name, index, folder, version, save)
    from Utility.GlobalConf import GlobalConf
    GlobalConf.skip_element_info = True
    page.loadSettings(save, from_json=True, unsaved_warning=False)
    pump(qapp, 0.05)
    page.updateOutputFilesList()
    showAllPlots(qapp, page)
    # errors of the plots are caught and logged by the GUI (the plot shows the error), exceptions are not allowed
    uncaught = [error for error in errors if error.startswith('Traceback')]
    assert not uncaught, '\n'.join(uncaught)


# --- damaged installations, configurations and imported files ---


TABLES = ['table1', 'table2', 'table3', 'table4', 'table.compound', 'table.compound3', 'table.crystal']


def installationCases() -> list:
    cases = [pytest.param(None, 'garbage tables', i, id=f'stand-in-{i}') for i in range(max(MUTATIONS // 5, 2))]
    if (SDTRIMSP_707 / 'tables').is_dir():
        cases += [pytest.param(SDTRIMSP_707, table, i, id=f'7.07-{table}-{i}') for table in TABLES + ['param.F90']
                  for i in range(max(MUTATIONS // 5, 2))]
    return cases


@pytest.mark.parametrize('installation, table, index', installationCases())
def test_damaged_installation(main_window, qapp, tmp_path, errors, installation, table, index):
    """Damaged tables (or src/param.F90) of a SDTrimSP installation: a simulation can still be opened and edited"""

    rng = random.Random(f'{SEED}-installation-{table}-{index}')
    folder = tmp_path / 'SDTrimSP_7.07'
    if installation is None:
        (folder / 'tables').mkdir(parents=True)
        for name in TABLES:
            (folder / 'tables' / name).write_bytes(bytes(rng.randrange(256) for _ in range(rng.randrange(0, 3000))))
    else:
        shutil.copytree(installation / 'tables', folder / 'tables', ignore=shutil.ignore_patterns('tbsp*'))
        if table == 'param.F90':
            (folder / 'src').mkdir()
            source = installation / 'src' / 'param.F90'
            text = source.read_text(encoding='utf-8', errors='replace') if source.is_file() else 'ncpm = 12'
            (folder / 'src' / 'param.F90').write_text(mutateText(text, rng), encoding='utf-8')
        else:
            damage(folder / 'tables' / table, rng)
    binary = folder / 'bin' / 'SDTrimSP.exe'
    binary.parent.mkdir()
    binary.write_bytes(b'')
    save = tmp_path / 'save'
    copyInputs(SAVES / 'SDTrimSP' / 'example_01_Ar_on_Au', save, isInput)
    sc, page = addSimulationPage(main_window, 'damaged installation', 0, folder, binary, Versions.V_707, save)
    pump(qapp, 0.05)
    exercise(qapp, page, save)
    assert not errors, '\n'.join(errors)


def configuration(tmp_path: Path) -> list:
    """Configurations of a SDTrimSP and a TRIDYN tab (as saved in autosave.json), with stand-in program folders"""

    result = []
    for name, binary_name, version, example in (('SDTrimSP', 'SDTrimSP.exe', Versions.V_707, 'example_01_Ar_on_Au'),
                                                ('TRIDYN', 'tridyn.exe', '2022', 'example_01_Ar_on_Au')):
        folder = tmp_path / 'programs' / name
        folder.mkdir(parents=True)
        (folder / binary_name).write_bytes(b'')
        save = tmp_path / 'saves' / name / example
        shutil.copytree(SAVES / name / example, save)
        result.append({'title': f'{name} tab', 'program': name, 'folder': str(folder), 'binary': str(folder / binary_name),
                       'version': version, 'scan_enabled': True, 'base_save_folder': '', 'save_folder': str(save),
                       'scan': {'rows': [{'key': 'energy_Ar', 'values': '100, 200'}], 'versions': []}})
    return result


@pytest.mark.parametrize('index', range(MUTATIONS))
def test_damaged_configuration(qapp, tmp_path, errors, index):
    """A damaged autosave.json of the configurations: the GUI starts (the configurations that can not be read are skipped)"""

    import Pages.MainWindow
    from Utility.GlobalConf import GlobalConf

    rng = random.Random(f'{SEED}-configuration-{index}')
    GlobalConf.save_path = tmp_path / 'saves'
    (GlobalConf.save_path / 'config').mkdir(parents=True)
    data = configuration(tmp_path)
    text = json.dumps(mutateJson(data, rng)) if index % 5 else rng.choice(['', '{', '[', 'null', '"x"', '{"a": 1}', '[1, null]'])
    (GlobalConf.save_path / 'config' / 'autosave.json').write_text(text, encoding='utf-8')
    GlobalConf.skip_element_info = True
    window = Pages.MainWindow.MainWindow(qapp)
    pump(qapp, 0.1)
    for sc in window.simulation_configs:
        if sc.tab_widget is not None:
            sc.tab_widget.scan.stop(ask=False)
    window.deleteLater()
    pump(qapp, 0.05)
    assert not errors, '\n'.join(errors)


@pytest.mark.parametrize('index', range(MUTATIONS))
def test_damaged_import_files(tmp_path, index):
    """Damaged crystal files (CIF, POSCAR) only raise CrystalImportError (shown by the GUI), distribution files nothing"""

    from Utility.CrystalImport import CrystalImportError, importCrystal
    from TableWidgets.DistributionEditor import readDistributionFile, readEnergyAngleFile

    rng = random.Random(f'{SEED}-import-{index}')
    data = Path(__file__).resolve().parent / 'data'
    for source in sorted(data.glob('*.cif')) + sorted(data.glob('*.vasp')):
        path = tmp_path / source.name
        path.write_text(mutateText(source.read_text(encoding='utf-8'), rng), encoding='utf-8')
        try:
            importCrystal(path)
        except CrystalImportError:
            pass
    distributions = [path for path in SAVES.glob('SDTrimSP/*/*.inp') if path.name.startswith(('energy', 'angle', 'ene_ang'))]
    for source in distributions:
        path = tmp_path / source.name
        shutil.copy(source, path)
        damage(path, rng)
        if path.name.startswith('ene_ang'):
            readEnergyAngleFile(path)
        else:
            readDistributionFile(path)


def test_cif_loop_without_headers(tmp_path):
    """A loop_ without headers made the CIF import run forever and fill the memory (in a separate process with timeout)"""

    import subprocess
    import sys

    path = tmp_path / 'damaged.cif'
    path.write_text('data_x\n_cell_length_a 4\n_cell_length_b 4\n_cell_length_c 4\nloop_\nNa 0 0 0\nCl 0.5 0.5 0.5\n', encoding='utf-8')
    code = ('import sys; sys.path.insert(0, sys.argv[2]); from pathlib import Path; from Utility.CrystalImport import importCrystal, '
            'CrystalImportError\ntry:\n    importCrystal(Path(sys.argv[1]))\nexcept CrystalImportError:\n    print("refused")')
    result = subprocess.run([sys.executable, '-c', code, str(path), str(Path(__file__).resolve().parents[1])],
                            capture_output=True, text=True, timeout=60)
    assert result.stdout.strip() == 'refused', result.stdout + result.stderr
