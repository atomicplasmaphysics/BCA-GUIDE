"""
Runs the test cases that come with SDTrimSP (folder "case") directly with their SDTrimSP version and through the GUI
(the GUI loads the input files of the case, writes its own input files and runs the simulation) and compares the
results. With the same input and the same random seed both runs must give identical results.

Only executed with:  python -m pytest tests/test_case_comparison.py --simulations
With --simulation-data DIR (or --test-dir=DIR) both runs are kept in DIR/cases/<version>-<case>/{native,gui}.

Environment variables:
  BCA_TEST_CASE_PROJECTILES  cases with more projectiles (histories * projectiles per history) are skipped (default 20000)
  BCA_TEST_TIMEOUT           timeout per simulation in seconds (default 900)
"""

import os
import shutil
import subprocess
from pathlib import Path
from re import findall, sub, IGNORECASE, MULTILINE
from typing import Dict, List, Optional, Tuple

import pytest

from conftest import addSimulationPage, pump
from Utility.Functions import inFileList
from test_simulation_runs import INSTALLATIONS, TIMEOUT, runAndCheckOutputs


CASE_PROJECTILES = int(os.environ.get('BCA_TEST_CASE_PROJECTILES', 20000))

# input files of the cases (all other files of a case folder are removed before the runs)
INPUT_FILES = ['*.inp', '*.data']

# files that contain only times or are not results
IGNORED_FILES = {'time.dat', 'time_run.dat', 'ausdat.dat'}

# lines with dates, times, run times or paths differ between the runs
IGNORED_LINE = r'(\d\d:\d\d:\d\d|\d\d\.\d\d\.\d{4}|\btime\b|cpu|\bsec\b|tableinp|version|sdtrimsp -|[a-z]:\\)'

# known differences that are not caused by the GUI: (folder name or None, case or None) -> reason
INEL0_606 = ('SDTrimSP 6.06 supports the inelastic loss model 7 (LZ7, also its default), the GUI treats 6.06 like 6.01 '
             '(version group "6.01, 6.06") and writes model 3 instead, see TODO.md')
KNOWN_DIFFERENCES: Dict[Tuple[Optional[str], Optional[str]], str] = {
    (None, 'Ar_2_Cu_W_layer_crystal'): 'qu of tri.inp (0, 1, 0) is not the composition of the layers, the GUI writes the mean composition '
                                      'of the layers; SDTrimSP uses qu with a layer file only to estimate the dynamic depth (TTDYN)',
    (None, 'Ar_3_Cu_NaCl_W_layer_crystal'): 'layer.inp covers 19 of 20 segments, SDTrimSP fills the last segment with the first layer, '
                                           'the GUI extends the last layer',
}


def triValue(text: str, name: str) -> Optional[str]:
    """Returns the (first) value of a parameter in tri.inp or None"""

    for line in text.splitlines():
        line = line.split('!')[0]
        match = findall(rf'^\s*{name}\s*=\s*([^,\s]+)', line, flags=IGNORECASE)
        if match:
            return match[0]
    return None


def caseProjectiles(case: Path) -> int:
    """
    Returns the number of projectiles of a case (histories * projectiles per history) as measure of the effort.
    Crystals take about 100 times longer than amorphous targets, so their projectiles count 100 times
    """

    text = (case / 'tri.inp').read_text(encoding='utf-8', errors='replace')
    try:
        projectiles = int(float(triValue(text, 'nh') or 0)) * int(float(triValue(text, 'nr_pproj') or 10))
    except ValueError:
        return 0
    if (triValue(text, 'l_crystal') or '').lower().strip('.') in ('true', 't'):
        projectiles *= 100
    return projectiles


def comparisonCases():
    """All test cases of all installations with at most CASE_PROJECTILES projectiles"""

    cases = []
    for folder, binary, version in INSTALLATIONS:
        for case in sorted((folder / 'case').glob('*/tri.inp')):
            case = case.parent
            projectiles = caseProjectiles(case)
            marks = []
            if not projectiles or projectiles > CASE_PROJECTILES:
                marks = [pytest.mark.skip(reason=f'{projectiles} projectiles (more than BCA_TEST_CASE_PROJECTILES={CASE_PROJECTILES})')]
            text = (case / 'tri.inp').read_text(encoding='utf-8', errors='replace')
            inel0 = findall(r'^\s*inel0\s*=([^!\n]*)', text, flags=IGNORECASE | MULTILINE)
            if folder.name == 'SDTrimSP_6.06' and (not inel0 or '7' in inel0[0].replace(',', ' ').split()):
                marks = marks or [pytest.mark.xfail(reason=INEL0_606, strict=False)]
            for (problem_folder, problem_case), reason in KNOWN_DIFFERENCES.items():
                if problem_folder in (None, folder.name) and problem_case in (None, case.name):
                    marks = marks or [pytest.mark.xfail(reason=reason, strict=False)]
            cases.append(pytest.param(folder, binary, version, case, id=f'{folder.name}-{case.name}', marks=marks))
    return cases


def withTables(text: str, tables: Path) -> str:
    """Sets the path of the tables (the default "../../tables" only works inside the case folder)"""

    text = sub(r'^\s*tableinp\s*=.*$', '', text, flags=IGNORECASE | MULTILINE)
    lines = text.rstrip().splitlines()
    end = max(i for i, line in enumerate(lines) if line.strip().startswith('/'))
    lines.insert(end, f'    tableinp = "{tables}"')
    return '\n'.join(lines) + '\n'


def resultLines(path: Path) -> List[str]:
    """Lines of a result file without the lines that depend on the run (dates, times, paths), whitespace normalized"""

    lines = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if findall(IGNORED_LINE, line, flags=IGNORECASE):
            continue
        line = ' '.join(line.split())
        if line:
            lines.append(line)
    return lines


def compareResults(native: Path, gui: Path) -> List[str]:
    """Returns the differences of the result files of both runs"""

    differences = []
    native_files = {path.name for path in native.glob('*.dat')} - IGNORED_FILES
    gui_files = {path.name for path in gui.glob('*.dat')} - IGNORED_FILES
    for name in sorted(native_files ^ gui_files):
        differences.append(f'{name}: only in the {"native" if name in native_files else "GUI"} run')
    for name in sorted(native_files & gui_files):
        native_lines, gui_lines = resultLines(native / name), resultLines(gui / name)
        if native_lines == gui_lines:
            continue
        for i, (native_line, gui_line) in enumerate(zip(native_lines, gui_lines)):
            if native_line != gui_line:
                differences.append(f'{name} (line {i + 1}):\n  native: {native_line[:150]}\n  GUI:    {gui_line[:150]}')
                break
        else:
            differences.append(f'{name}: {len(native_lines)} lines in the native run, {len(gui_lines)} lines in the GUI run')
    return differences


@pytest.fixture
def case_folder(request, tmp_path) -> Path:
    """Folder for both runs: in --simulation-data DIR/cases (kept) or temporary"""

    data_dir = request.config.getoption('--simulation-data')
    if not data_dir:
        return tmp_path
    folder = Path(data_dir).resolve() / 'cases' / request.node.callspec.id
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    return folder


@pytest.mark.simulation
@pytest.mark.parametrize('folder, binary, version, case', comparisonCases())
def test_case_native_and_gui(main_window, qapp, case_folder, tmp_path, monkeypatch, errors, folder, binary, version, case):
    monkeypatch.chdir(tmp_path)
    native = case_folder / 'native'
    gui = case_folder / 'gui'
    shutil.copytree(case, native)
    shutil.copytree(case, gui)
    # only the input files are used: some cases contain results (SDTrimSP appends to some of them, e.g. yield_lattice_uvt.dat),
    # binaries and run scripts of the cluster
    for path in list(native.iterdir()) + list(gui.iterdir()):
        if path.is_file() and not inFileList(path.name, INPUT_FILES):
            path.unlink()

    # native run: only the path of the tables is added to tri.inp
    tri = native / 'tri.inp'
    tri.write_text(withTables(tri.read_text(encoding='utf-8', errors='replace'), folder / 'tables'), encoding='utf-8')
    try:
        result = subprocess.run([str(binary)], cwd=native, capture_output=True, text=True, errors='replace', timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        pytest.fail(f'the native run did not finish within {TIMEOUT} s')
    (native / 'native_log.txt').write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode != 0 or not any(native.glob('output*.dat')):
        pytest.skip(f'the case fails without the GUI (exit code {result.returncode}): {(result.stdout + result.stderr)[-300:]}')

    # GUI run: the GUI loads the input files of the case and writes its own
    sc, page = addSimulationPage(main_window, case.name, 0, folder, binary, version)
    pump(qapp)
    assert page.loadSettings(gui, from_json=False, unsaved_warning=False)
    pump(qapp)
    assert runAndCheckOutputs(qapp, page, sc, errors) > 0

    differences = compareResults(native, gui)
    assert not differences, 'the results of the native and the GUI run differ:\n' + '\n'.join(differences)
