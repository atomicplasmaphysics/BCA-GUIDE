"""
Loads simulation data that was created with  python -m pytest --simulations --simulation-data DIR  and checks that all
outputs can be shown and plotted in the GUI, without running the simulations again.

Usage:  python -m pytest tests/test_simulation_data.py --simulation-data DIR
"""

import json
from pathlib import Path

import pytest

from conftest import SIMULATION_PROGRAMS, addSimulationPage, pump

from test_simulation_runs import checkOutputs


def pytest_generate_tests(metafunc):
    if 'data_folder' not in metafunc.fixturenames:
        return
    data_dir = metafunc.config.getoption('--simulation-data')
    folders = []
    if data_dir and Path(data_dir).is_dir():
        folders = sorted(meta.parent for meta in Path(data_dir).glob('*/bca_test.json'))
    if folders:
        metafunc.parametrize('data_folder', folders, ids=[folder.name for folder in folders])
    else:
        metafunc.parametrize('data_folder', [pytest.param(None, marks=pytest.mark.skip(reason='no simulation data, use --simulation-data DIR'))])


def test_simulation_data(main_window, qapp, errors, data_folder):
    meta = json.loads((data_folder / 'bca_test.json').read_text(encoding='utf-8'))
    if meta['program'] == 'SDTrimSP' and not any(data_folder.glob('output*.dat')):
        pytest.skip('the simulation of this folder failed (no output*.dat)')
    program_idx = 0 if meta['program'] == 'SDTrimSP' else 1
    folder = SIMULATION_PROGRAMS / meta['program'] / meta['simulation_folder']
    if not folder.is_dir():
        pytest.skip(f'{folder} not available')

    from Simulations.SimulationsList import SimulationsList
    binary = SimulationsList().simulation_program_list[program_idx].findBinary(folder) or folder / 'binary'

    sc, page = addSimulationPage(main_window, data_folder.name, program_idx, folder, binary, meta['version'], data_folder)
    pump(qapp)
    assert checkOutputs(qapp, page, errors) > 0
