"""Loading and writing of TRIDYN input files: the GUI must write the same simulation as the loaded input"""

from zipfile import ZipFile

import pytest

from conftest import SIMULATION_PROGRAMS, addSimulationPage, pump

from Simulations.TRIDYN2022 import SimulationInput as TridynInput


FOLDER = SIMULATION_PROGRAMS / 'TRIDYN' / 'Tridyn2022'
SAMPLES = FOLDER / 'TRIDYN2022_sample.ZIP'
pytestmark = pytest.mark.skipif(not SAMPLES.is_file(), reason='samples of TRIDYN 2022 not available')


def loadSample(main_window, qapp, tmp_path, sample: str):
    with ZipFile(SAMPLES) as archive:
        for name in archive.namelist():
            if name.startswith(sample) and name.endswith(('.in', '.lay')):
                (tmp_path / name).write_bytes(archive.read(name))
    sc, page = addSimulationPage(main_window, sample, 1, FOLDER, TridynInput.findBinary(FOLDER) or FOLDER / 'tridyn.exe', '2022', tmp_path)
    pump(qapp)
    assert page.loadSettings(tmp_path, from_json=False, unsaved_warning=False)
    pump(qapp)
    return page


def test_element_in_beam_and_target(main_window, qapp, tmp_path, errors):
    """Si is a projectile (thermal Si) and in the target: one species, the indices of the other options are kept"""

    page = loadSample(main_window, qapp, tmp_path, 'SiO_NeSi22')
    _, text, layer, _ = page.makePreview()
    lines = text.splitlines()
    assert 'atda Ne Si O' in lines
    assert 'irra 2 20.0 0.0 0.8' in lines
    assert 'exst 3 0.6667 -1 0' in lines
    assert 'angd 2 2 30. 1. 0.' in lines
    # the layer file has a column for each species
    original = [line.split()[:3] for line in (tmp_path / 'SiO_NeSi22.lay').read_text().splitlines() if line.strip()]
    written = [line.split()[:3] for line in layer.splitlines() if line.strip()]
    assert [[float(v) for v in values] for values in written] == [[float(v) for v in values] for values in original]
    assert not errors, '\n'.join(errors)


def test_defaults_of_tridyn_are_kept(main_window, qapp, tmp_path, errors):
    """Without "thrd" and "pspr" TRIDYN uses all threads and the default precision, the output lists are kept"""

    page = loadSample(main_window, qapp, tmp_path, 'SiO_NeSi23')
    _, text, _, _ = page.makePreview()
    lines = text.splitlines()
    assert 'thrd 0' in lines
    assert 'prec 0.0001' in lines and not any(line.startswith('pspr') for line in lines)
    assert '°' in lines[0]
    outi = next(line for line in lines if line.startswith('outi')).split()[1:]
    outl = next(line for line in lines if line.startswith('outl')).split()[1:]
    assert {'ardn', 'spyl'} <= set(outi)
    assert {'rang', 'sput'} <= set(outl)
    assert 'mixg' in lines
    assert not errors, '\n'.join(errors)
