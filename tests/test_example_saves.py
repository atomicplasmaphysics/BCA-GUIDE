"""Loads all example saves, lists their output files and parameters and draws all plots"""

import pytest

from conftest import SAVES, TEST_SAVES, SIMULATION_PROGRAMS, addSimulationPage, copySave, pump

from Simulations.SDTrimSP import SimulationInput as SDTrimSPInput, Versions
from Simulations.TRIDYN2022 import SimulationInput as TridynInput


def sdtrimspVersion(name: str) -> str:
    """Returns the version group of SDTrimSP that suits an example save best"""

    if '7.02' in name or '7.05' in name:
        return Versions.V_702
    if '609' in name:
        return Versions.V_609
    if '606' in name:
        return Versions.V_606
    if '601' in name:
        return Versions.V_601
    return Versions.V_700


def sdtrimspFolder(version: str):
    folder_name = {
        Versions.V_601: 'SDTrimSP_6.01',
        Versions.V_606: 'SDTrimSP_6.06',
        Versions.V_609: 'SDTrimSP_6.09',
        Versions.V_700: 'SDTrimSP_7.00',
        Versions.V_702: 'SDTrimSP_7.02',
    }[version]
    return SIMULATION_PROGRAMS / 'SDTrimSP' / folder_name


# the examples of the GUI and the simulations of the tests (not the other simulations of the user in saves)
CASES = [(program, save) for program in ('SDTrimSP', 'TRIDYN') for save in sorted((SAVES / program).glob('example_*')) if save.is_dir()]
CASES += [(program, save) for program in ('SDTrimSP', 'TRIDYN') for save in sorted((TEST_SAVES / program).iterdir()) if save.is_dir()]


@pytest.mark.parametrize('program, save', CASES, ids=lambda value: getattr(value, 'name', value))
def test_example_save(main_window, qapp, tmp_path, errors, program, save):
    save_folder = copySave(save, tmp_path / save.name)

    if program == 'SDTrimSP':
        version = sdtrimspVersion(save.name)
        folder = sdtrimspFolder(version)
        binary = SDTrimSPInput.findBinary(folder) or folder / 'bin' / 'SDTrimSP.exe'
        program_idx = 0
    else:
        version = '2022'
        folder = SIMULATION_PROGRAMS / 'TRIDYN' / 'Tridyn2022'
        binary = TridynInput.findBinary(folder) or folder / 'tridyn2022w.exe'
        program_idx = 1
    if not folder.is_dir():
        pytest.skip(f'{folder} not available')

    sc, page = addSimulationPage(main_window, save.name, program_idx, folder, binary, version, save_folder)
    pump(qapp)

    # output files and their preview
    page.tab_widget.setCurrentIndex(3)
    page.updateOutputFilesList()
    for i in range(page.output_files_list.count()):
        page.output_files_list.setCurrentRow(i)
        pump(qapp, 0.01)

    # output parameters and all plots
    page.tab_widget.setCurrentIndex(4)
    page.updateOutputParametersList(forced=True)
    parameters = page.output_parameters_list
    for i in range(parameters.count()):
        item = parameters.item(i)
        if getattr(item, 'function', None):
            item.function(**item.function_args)
            pump(qapp, 0.15)

    # saving writes the input files into the copied folder
    files = page.saveSettings()
    pump(qapp, 0.3)
    assert not errors, '\n'.join(errors)
    if files is not None:
        for file in files:
            assert (save_folder / file).is_file()
