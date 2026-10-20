"""
Input files of colleagues (tests/test-inputs/*.inp, tri.inp of SDTrimSP 7.07) with all SDTrimSP installations: the GUI
loads them without errors, writes them again with the same values and, with --simulations, runs them and shows all
outputs. The runs use fewer projectiles (nh, nr_pproj), set BCA_TEST_INPUT_FULL=1 to run the inputs unchanged.
"""

import os
import shutil
from pathlib import Path
from re import IGNORECASE, MULTILINE, S, findall, finditer, sub
from typing import Dict, List

import pytest

from conftest import addSimulationPage, pump
from Simulations.SDTrimSP import SimulationInput, maxElements
from test_simulation_runs import INSTALLATIONS, run_folder, runAndCheckOutputs, writeMeta  # noqa: F401 (fixture)


INPUTS = sorted((Path(__file__).resolve().parent / 'test-inputs').glob('*.inp'))
FULL = os.environ.get('BCA_TEST_INPUT_FULL') == '1'
# reduced runs: histories and projectiles per history (the output steps idout are reduced to the histories)
HISTORIES = 20
PROJECTILES_PER_HISTORY = 10

# parameters of the GUI that are not compared: the path of the tables is the one of the installation
NOT_COMPARED = {'tableinp'}


def namelist(text: str) -> Dict[str, list]:
    """
    Values of the namelist TRI_INP: lower case name (with index, e.g. "ioutput_part(2)") -> list of values (floats,
    booleans or strings without quotes)
    """

    body = text.split('\n', 1)[1] if '\n' in text else ''
    body = sub(r'[!#].*', '', body)
    body = sub(r'&tri_inp', '', body, flags=IGNORECASE)
    body = body[:body.rfind('/')] if '/' in body else body
    name = r'[A-Za-z_][A-Za-z0-9_]*(?:\(\s*\d+\s*\))?'
    values: Dict[str, list] = {}
    for match in finditer(rf'({name})\s*=\s*(.*?)(?=\s+{name}\s*=|\Z)', body, S):
        key = match.group(1).lower().replace(' ', '')
        if key == 'text':
            continue
        parsed: list = []
        for value in findall(r'"[^"]*"|\'[^\']*\'|[^,\s]+', match.group(2)):
            value = value.strip('"\'').strip()
            low = value.lower()
            if low in ('.true.', 'true', '.t.', 't'):
                parsed.append(True)
            elif low in ('.false.', 'false', '.f.', 'f'):
                parsed.append(False)
            else:
                try:
                    parsed.append(float(low.replace('d', 'e')))
                except ValueError:
                    parsed.append(value.lower())
        values[key] = parsed
    return values


def sameValue(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) <= 1e-6 * max(1., abs(a), abs(b))
    return a == b


def differences(original: str, written: str) -> List[str]:
    """Parameters of the original tri.inp that are missing or have other values in the written one"""

    old, new = namelist(original), namelist(written)
    result = []
    for key, values in old.items():
        if key in NOT_COMPARED:
            continue
        if key not in new:
            result.append(f'{key} = {values} is missing')
        # lists shorter than ncp are filled up with defaults by SDTrimSP and the GUI
        elif len(new[key]) < len(values) or not all(sameValue(a, b) for a, b in zip(values, new[key])):
            result.append(f'{key}: {values} -> {new[key]}')
    return result


def elements(text: str) -> int:
    return int(namelist(text).get('ncp', [0])[0])


def reduced(text: str) -> str:
    """Input with fewer projectiles"""

    if FULL:
        return text
    for name, value in (('nh', HISTORIES), ('nr_pproj', PROJECTILES_PER_HISTORY), ('idout', HISTORIES)):
        text = sub(rf'^(\s*{name}\s*=\s*)[^,!\s]+', rf'\g<1>{value}', text, flags=IGNORECASE | MULTILINE)
    return text


def inputCases(simulation: bool):
    cases = []
    for folder, binary, version in INSTALLATIONS:
        max_elements = maxElements(folder)
        for path in INPUTS:
            marks = [pytest.mark.simulation] if simulation else []
            ncp = elements(path.read_text(encoding='utf-8', errors='replace'))
            if simulation and max_elements is not None and ncp > max_elements:
                # the GUI warns before the run (checkWarnings)
                marks.append(pytest.mark.skip(reason=f'{ncp} elements, the installation is compiled for at most {max_elements} (ncpm)'))
            cases.append(pytest.param(folder, binary, version, path, id=f'{folder.name}-{path.stem}', marks=marks))
    if not cases:
        cases.append(pytest.param(None, None, None, None, marks=pytest.mark.skip(reason='no SDTrimSP installation or no inputs')))
    return cases


def loadAndSave(main_window, qapp, folder: Path, binary: Path, version: str, save_folder: Path):
    """Loads tri.inp of save_folder in a new tab and saves it again, returns (page, configuration, errors of loading)"""

    simulation = SimulationInput()
    simulation.simulation_folder = folder
    simulation.updateElements(folder, version)
    result = simulation.loadFiles(save_folder, version)
    assert isinstance(result, tuple), result

    sc, page = addSimulationPage(main_window, save_folder.name, 0, folder, binary, version, save_folder)
    pump(qapp)
    assert page.loadSettings(save_folder, from_json=False, unsaved_warning=False)
    pump(qapp)
    assert page.saveSettings()
    return page, sc, result[1]


@pytest.mark.parametrize('folder, binary, version, path', inputCases(simulation=False))
def test_input_round_trip(main_window, qapp, tmp_path, errors, folder, binary, version, path):
    """The GUI loads the input without errors and writes it again with the same values"""

    original = path.read_text(encoding='utf-8', errors='replace')
    (tmp_path / 'tri.inp').write_text(original, encoding='utf-8')
    page, sc, load_errors = loadAndSave(main_window, qapp, folder, binary, version, tmp_path)
    assert not load_errors
    assert not errors
    max_elements = maxElements(folder)
    if max_elements is not None and elements(original) > max_elements:
        # the tables only take ncpm elements, the others are not loaded (the GUI shows them)
        assert elements((tmp_path / 'tri.inp').read_text(encoding='utf-8')) <= max_elements
        return
    written = (tmp_path / 'tri.inp').read_text(encoding='utf-8')
    assert not differences(original, written), '\n'.join(differences(original, written))
    # the written input is loaded again with the same values
    page, sc, load_errors = loadAndSave(main_window, qapp, folder, binary, version, tmp_path)
    assert not load_errors and (tmp_path / 'tri.inp').read_text(encoding='utf-8') == written


@pytest.mark.parametrize('folder, binary, version, path', inputCases(simulation=True))
def test_input_simulation(main_window, qapp, run_folder, tmp_path, monkeypatch, errors, folder, binary, version, path):  # noqa: F811
    """The GUI runs the input (with fewer projectiles) and shows all outputs"""

    monkeypatch.chdir(tmp_path)
    run_folder.mkdir(parents=True, exist_ok=True)
    original = reduced(path.read_text(encoding='utf-8', errors='replace'))
    (run_folder / 'tri.inp').write_text(original, encoding='utf-8')
    page, sc, load_errors = loadAndSave(main_window, qapp, folder, binary, version, run_folder)
    assert not load_errors
    assert not differences(original, (run_folder / 'tri.inp').read_text(encoding='utf-8'))
    # combinations that the installation can not run (e.g. elements missing in tables/table3), the GUI warns before the run
    stops = [warning for warning in page.runWarnings() if 'SDTrimSP stops' in warning]
    if stops:
        pytest.skip(f'the GUI warns: {stops[0]}')
    assert runAndCheckOutputs(qapp, page, sc, errors, lambda: writeMeta(run_folder, 'SDTrimSP', folder, version)) > 0
    shutil.copy(path, run_folder / f'original_{path.name}')
