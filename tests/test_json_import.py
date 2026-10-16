"""
Loading of the GUI files input.json: the same simulation as loading the input files of the simulation program, and
input.json of other versions and of the other simulation program (TRIDYN <-> SDTrimSP) can be loaded without errors and
only parameters are written that the version reads
"""

import shutil
from re import findall, IGNORECASE, MULTILINE

import pytest

from conftest import SAVES, SIMULATION_PROGRAMS, addSimulationPage, pump

from Simulations.SDTrimSP import SimulationInput as SDTrimSPInput, Versions, namelistParameters
from Simulations.TRIDYN2022 import SimulationInput as TridynInput
from Pages.ConfigurationPage import bestVersion


def sdtrimspInstallations():
    """(folder, version) of all SDTrimSP installations with tables (no binary needed)"""

    installations = []
    for folder in sorted((SIMULATION_PROGRAMS / 'SDTrimSP').glob('SDTrimSP_*')):
        version_name = SDTrimSPInput.getVersionName(folder, None)
        index, exact = bestVersion(SDTrimSPInput.Versions, version_name) if version_name else (-1, False)
        if (folder / 'tables').is_dir() and index >= 0 and exact:
            installations.append((folder, SDTrimSPInput.Versions[index]))
    return installations


TRIDYN_FOLDER = SIMULATION_PROGRAMS / 'TRIDYN' / 'Tridyn2022'
TARGETS = [('SDTrimSP', folder, version) for folder, version in sdtrimspInstallations()]
if TRIDYN_FOLDER.is_dir():
    TARGETS.append(('TRIDYN', TRIDYN_FOLDER, '2022'))

SOURCES = sorted(path.parent for path in (SAVES / 'SDTrimSP').glob('*/input.json') if path.parent.name.startswith(('example_', 'Ar_on_W', 'H_Ar')))
SOURCES += sorted(path.parent for path in (SAVES / 'TRIDYN').glob('*/input.json'))


def addPage(main_window, program: str, folder, version: str, save):
    cls = SDTrimSPInput if program == 'SDTrimSP' else TridynInput
    return addSimulationPage(main_window, save.name, 0 if program == 'SDTrimSP' else 1, folder, cls.findBinary(folder) or folder / 'binary.exe', version, save)


def speciesInput(text: str) -> tuple:
    """
    Returns the input of tri.inp independent of the order of the species: ({symbol: (values of the lists)}, other lines).
    Old versions of the GUI wrote input.json without the setting "group_elements", the order of the species can differ
    """

    lists = {}
    other = []
    for line in text.splitlines():
        match = findall(r'^\s*([a-z_0-9]+)\s*=\s*(.*)$', line, flags=IGNORECASE)
        if match and ',' in match[0][1]:
            lists[match[0][0]] = [value.strip() for value in match[0][1].split(',')]
        else:
            other.append(line)
    symbols = lists.pop('symbol', [])
    species = {symbol: tuple(values[i] if i < len(values) else '' for _, values in sorted(lists.items())) for i, symbol in enumerate(symbols)}
    return species, other


def writtenParameters(program: str, text: str) -> set:
    """Returns the names of the parameters of an input file"""

    if program == 'SDTrimSP':
        names = findall(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:\([^)]*\))?\s*=', text, flags=MULTILINE)
        return {name.lower() for name in names}
    return {line.split()[0].lower() for line in text.splitlines()[1:] if line.strip() and not line.startswith('#')}


@pytest.mark.parametrize('save', [save for save in SOURCES if (save / 'tri.inp').is_file()], ids=lambda save: save.name)
def test_tri_inp_and_json_give_the_same_input(main_window, qapp, tmp_path, errors, save):
    """input.json and tri.inp written by the GUI describe the same simulation"""

    folder = SIMULATION_PROGRAMS / 'SDTrimSP' / 'SDTrimSP_7.07'
    if not (folder / 'tables').is_dir():
        pytest.skip('SDTrimSP 7.07 not available')
    copy = tmp_path / save.name
    copy.mkdir()
    for path in save.iterdir():
        if path.is_file() and (path.suffix in ('.inp', '.json')):
            shutil.copy(path, copy / path.name)

    sc, page = addPage(main_window, 'SDTrimSP', folder, Versions.V_707, copy)
    pump(qapp)
    texts = []
    for from_json in (False, True):
        assert page.loadSettings(copy, from_json=from_json, unsaved_warning=False)
        pump(qapp)
        _, input_text, layer_text, crystal_text = page.makePreview()
        texts.append((speciesInput(input_text), layer_text, crystal_text))
    assert texts[0][0] == texts[1][0]
    # layer files have the columns in the order of the species
    if not (texts[0][1] and texts[0][1] != texts[1][1]):
        assert texts[0][1:] == texts[1][1:]
    assert not errors, '\n'.join(errors)


@pytest.mark.parametrize('program, folder, version', TARGETS, ids=[f'{program}-{version}' for program, _, version in TARGETS])
@pytest.mark.parametrize('save', SOURCES, ids=lambda save: f'{save.parent.name}-{save.name}')
def test_load_json_in_other_versions(main_window, qapp, tmp_path, errors, save, program, folder, version):
    copy = tmp_path / save.name
    copy.mkdir()
    shutil.copy(save / 'input.json', copy / 'input.json')

    sc, page = addPage(main_window, program, folder, version, copy)
    pump(qapp)
    assert page.loadSettings(copy, from_json=True, unsaved_warning=False)
    pump(qapp)
    arguments, input_text, layer_text, crystal_text = page.makePreview()
    assert input_text

    # only parameters that the version reads
    written = writtenParameters(program, input_text)
    if program == 'SDTrimSP':
        known = namelistParameters(folder)
        if known is None:
            pytest.skip('parameters of this version unknown')
    else:
        known = set(TridynInput.InputParameters)
    unknown = written - known
    assert not unknown, f'parameters that {program} {version} does not read: {sorted(unknown)}'

    # the problems are reported, but loading never crashes
    page.simulation_class.checkArguments(arguments, version)
    page.simulation_class.checkWarnings(arguments, version)
    assert not errors, '\n'.join(errors)
