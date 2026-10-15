"""
Runs a short example simulation (Ar, 2 keV, 60 degree on Au, 1000 projectiles) with every simulation program found in
"Simulation Programs" (with and without crystal, if supported) and checks that all outputs can be shown in the GUI.

Only executed with: python -m pytest tests --simulations
"""

import json
import shutil
from pathlib import Path
from re import findall

import pytest

from PyQt6.QtCore import QProcess

from conftest import ROOT, SAVES, SIMULATION_PROGRAMS, addSimulationPage, pump

from Containers.CrystalTableFile import CrystalTableFile, TableCrystal
from Pages.ProgramPage import SimulationPage
from Simulations.SDTrimSP import SimulationInput as SDTrimSPInput, DefaultValues, Versions
from Simulations.TRIDYN2022 import SimulationInput as TridynInput


TIMEOUT = 600  # seconds per simulation
PROJECTILES = 1000
PROJECTILES_PER_HISTORY = 100  # SDTrimSP: projectiles = histories * projectiles per history

AU_FCC = [(0., 0., 0.), (0., 0.5, 0.5), (0.5, 0., 0.5), (0.5, 0.5, 0.)]
AU_LATTICE_CONSTANT = 4.078


def bestVersion(version_name: str, versions: list) -> str:
    """Returns the listed version that suits the detected version best (highest listed version below it)"""

    detected = float(findall(r'\d+(?:\.\d+)?', version_name)[0])
    candidates = []
    for listed in versions:
        for number in listed.split(','):
            candidates.append((float(number), listed))
    lower = [candidate for candidate in candidates if candidate[0] <= detected + 1e-9]
    return max(lower)[1] if lower else min(candidates)[1]


def sdtrimspCases():
    cases = []
    for folder in sorted((SIMULATION_PROGRAMS / 'SDTrimSP').glob('SDTrimSP_*')):
        binary = SDTrimSPInput.findBinary(folder)
        version_name = SDTrimSPInput.getVersionName(folder, binary)
        if binary is None or not version_name:
            cases.append(pytest.param(folder, None, False, marks=pytest.mark.skip(reason=f'no binary for this operating system in {folder.name}'), id=folder.name))
            continue
        version = bestVersion(version_name, SDTrimSPInput.Versions)
        cases.append(pytest.param(folder, version, False, id=f'{folder.name}'))
        if DefaultValues(version).enable_crystal:
            cases.append(pytest.param(folder, version, True, id=f'{folder.name}-crystal'))
    return cases


def runAndCheckOutputs(qapp, page, sc, errors):
    """Runs the simulation of the page and shows all outputs"""

    page.runSimulation()
    assert pump(qapp, 5, until=lambda: page.process.state() != QProcess.ProcessState.NotRunning or not sc.running), 'simulation did not start'
    finished = pump(qapp, TIMEOUT, until=lambda: page.process.state() == QProcess.ProcessState.NotRunning and not sc.running)
    log = page.simulation_output.toPlainText()
    if not finished:
        page.process.kill()
    assert finished, f'simulation did not finish within {TIMEOUT} s\n{log[-2000:]}'
    pump(qapp, 0.5)
    assert page.run_status == SimulationPage.RunStatus.DONE, f'simulation failed:\n{log[-3000:]}'

    # output files and their preview
    page.tab_widget.setCurrentIndex(3)
    page.updateOutputFilesList()
    assert page.output_files_list.count() > 0
    for i in range(page.output_files_list.count()):
        page.output_files_list.setCurrentRow(i)
        pump(qapp, 0.01)

    # output parameters and all plots
    page.tab_widget.setCurrentIndex(4)
    page.updateOutputParametersList(forced=True)
    parameters = page.output_parameters_list
    plots = 0
    for i in range(parameters.count()):
        item = parameters.item(i)
        if getattr(item, 'function', None):
            item.function(**item.function_args)
            pump(qapp, 0.2)
            plots += 1

    pump(qapp, 1)
    assert not errors, '\n'.join(errors)
    return plots


def prepareInput(source: Path, save_folder: Path):
    """Copies only input.json of an example (the GUI creates all other input files) and reduces the number of projectiles"""

    save_folder.mkdir(parents=True)
    data = json.loads((source / 'input.json').read_text(encoding='utf-8'))
    optional = data.get('settings', {}).get('optional', {})
    if 'histories' in optional:
        # SDTrimSP
        optional['histories'] = PROJECTILES // PROJECTILES_PER_HISTORY
        optional['projectiles'] = PROJECTILES_PER_HISTORY
        optional['histories_between_out'] = 1
    elif 'projectiles' in optional:
        # TRIDYN
        optional['projectiles'] = PROJECTILES
    (save_folder / 'input.json').write_text(json.dumps(data, indent=4), encoding='utf-8')


@pytest.mark.simulation
@pytest.mark.parametrize('folder, version, crystal', sdtrimspCases())
def test_sdtrimsp(main_window, qapp, tmp_path, monkeypatch, errors, folder, version, crystal):
    monkeypatch.chdir(tmp_path)
    binary = SDTrimSPInput.findBinary(folder)

    simulation_folder = folder
    if crystal and DefaultValues(version).crystal_table:
        # own copy of the tables with Au in table.crystal (the tables of the installation are not changed)
        simulation_folder = tmp_path / folder.name
        shutil.copytree(folder / 'tables', simulation_folder / 'tables')
        table = CrystalTableFile(simulation_folder / 'tables' / 'table.crystal')
        if table.crystal('Au_fcc') is None:
            table.addCrystal(TableCrystal('Au_fcc', AU_LATTICE_CONSTANT, AU_LATTICE_CONSTANT, AU_LATTICE_CONSTANT, 4 / AU_LATTICE_CONSTANT ** 3, elements=['Au'] * 4), AU_FCC)

    save_folder = tmp_path / 'save'
    prepareInput(SAVES / 'SDTrimSP' / 'Ar_on_Au_7.00', save_folder)

    sc, page = addSimulationPage(main_window, folder.name, 0, simulation_folder, binary, version)
    pump(qapp)
    assert page.loadSettings(save_folder, unsaved_warning=False)

    checkbox = page.general_target_settings.layout_crystal_file
    if checkbox is not None and checkbox.checkbox is not None:
        checkbox.checkbox.setChecked(crystal)

    if crystal:
        dialog = page.crystal_editor_dialog
        dialog.elementChanged()
        if dialog.table_mode:
            dialog.loadCrystalTable(select='Au_fcc')
        else:
            dialog.setFccParameter()
            dialog.lattice_constant.setValue(AU_LATTICE_CONSTANT)
        dialog.elementChanged()
        assert not dialog.undefined_state

    plots = runAndCheckOutputs(qapp, page, sc, errors)
    assert plots > 0


@pytest.mark.simulation
@pytest.mark.skipif(not (SIMULATION_PROGRAMS / 'TRIDYN' / 'Tridyn2022').is_dir(), reason='TRIDYN 2022 not available')
def test_tridyn(main_window, qapp, tmp_path, monkeypatch, errors):
    monkeypatch.chdir(tmp_path)
    folder = SIMULATION_PROGRAMS / 'TRIDYN' / 'Tridyn2022'
    binary = TridynInput.findBinary(folder)
    if binary is None:
        pytest.skip('no TRIDYN binary for this operating system')

    save_folder = tmp_path / 'save'
    prepareInput(SAVES / 'TRIDYN' / 'Ar_on_W', save_folder)

    sc, page = addSimulationPage(main_window, 'TRIDYN', 1, folder, binary, '2022')
    pump(qapp)
    assert page.loadSettings(save_folder, unsaved_warning=False)

    plots = runAndCheckOutputs(qapp, page, sc, errors)
    assert plots > 0
