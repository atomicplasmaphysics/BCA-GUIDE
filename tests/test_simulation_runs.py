"""
Runs simulations with every simulation program found in "Simulation Programs" and checks that all outputs can be shown
and plotted in the GUI. The runs cover many input modes and parameters (energies from 10 eV to 1 GeV, angles, sweeps,
distributions, potentials, integration methods, surface binding models, dynamic mode, output options, crystals, ...).

Only executed with:  python -m pytest --simulations
The simulations run in parallel (pytest-xdist, see pytest.ini), e.g. with 20 processes:  python -m pytest --simulations -n 20

With --simulation-data DIR the simulation folders are kept in DIR, test_simulation_data.py checks them later in the GUI
without running the simulations again.

Environment variables for longer runs:
  BCA_TEST_PROJECTILES  number of projectiles (default 1000)
  BCA_TEST_SEED         random seed of SDTrimSP (irand) if the variant does not set it
  BCA_TEST_TIMEOUT      timeout per simulation in seconds (default 900)
  BCA_TEST_ALL_VARIANTS 1: all variants for all versions (default: all variants only for the newest version)
"""

import copy
import json
import os
import shutil
from pathlib import Path
from re import findall
from typing import Optional

import pytest

from PyQt6.QtCore import QProcess

from conftest import SAVES, TEST_SAVES, SIMULATION_PROGRAMS, addSimulationPage, pump

from Containers.CrystalTableFile import CrystalTableFile, TableCrystal
from Pages.ProgramPage import SimulationPage
from Simulations.SDTrimSP import SimulationInput as SDTrimSPInput, DefaultValues, CrystalTableLimits
from Simulations.TRIDYN2022 import SimulationInput as TridynInput


TIMEOUT = int(os.environ.get('BCA_TEST_TIMEOUT', 900))  # seconds per simulation
PROJECTILES = int(os.environ.get('BCA_TEST_PROJECTILES', 1000))
SEED = int(os.environ['BCA_TEST_SEED']) if os.environ.get('BCA_TEST_SEED') else None
ALL_VARIANTS = os.environ.get('BCA_TEST_ALL_VARIANTS') == '1'
PROJECTILES_PER_HISTORY = 100  # SDTrimSP: projectiles = histories * projectiles per history

AU_FCC = [(0., 0., 0.), (0., 0.5, 0.5), (0.5, 0., 0.5), (0.5, 0.5, 0.)]
AU_LATTICE_CONSTANT = 4.078

# example inputs (input.json) that are varied
BASES = {
    'Ar_Au': SAVES / 'SDTrimSP' / 'example_01_Ar_on_Au',  # Ar on Au, 2 keV, 60 degree
    'Ar_W': TEST_SAVES / 'SDTrimSP' / 'Ar_on_W',  # Ar on W
    'H_Ar_FeW': TEST_SAVES / 'SDTrimSP' / 'H_Ar_on_Fe_W_60deg',  # two projectiles, two layers
}

# distributions of energies and angles for the file modes (energy.inp, angle.inp, ene_ang.inp), keyed by projectile
ENERGY_DISTRIBUTION = [[200., 1.], [800., 3.], [1500., 1.]]
ANGLE_DISTRIBUTION = [[20., 1.], [45., 2.], [70., 0.5]]
DISTRIBUTIONS = {
    'energy': {'H': ENERGY_DISTRIBUTION, 'Ar': [[500., 2.], [2000., 1.]]},
    'angle': {'all': ANGLE_DISTRIBUTION, 'H': ANGLE_DISTRIBUTION, 'Ar': [[10., 1.], [60., 1.]]},
    'energy_angle': {
        'angle': [10., 70., 20.],
        'energy': [100., 400., 100.],
        'matrix': [[1., 2., 1., 0.], [2., 3., 1., 0.5], [1., 1., 1., 0.], [0.5, 0., 0., 0.]]
    }
}

LINDHARD_SCHARFF = {'beam.optional.inelastic_loss_model': 'LINDHARD_SCHARFF', 'target.optional.inelastic_loss_model': 'LINDHARD_SCHARFF'}

# variants of the input: dot separated paths in input.json -> value, 'beam.' and 'target.' set the value in all beam or target rows
VARIANTS = {
    'default': {},
    'dynamic': {'settings.mode': 'DYNAMIC', 'settings.fluence': 0.5},
    'no_recoils': {'settings.mode': 'STATIC_NO_RECOIL'},
    'energy_10eV': {'beam.energy': 10.},
    'energy_1MeV': {'beam.energy': 1e6},
    'energy_1GeV': {'beam.energy': 1e9, '_projectiles': 100},
    'normal_incidence': {'beam.angle': 0.},
    'grazing_89deg': {'beam.angle': 89.},
    # the energy distribution in the target (example 1) crashes SDTrimSP in sweeps
    'energy_sweep': {'beam_arguments.kinetic_energy_mode': 'SWEEP', 'beam_arguments.optional.sweep': 3, 'beam.energy': 500.,
                     'settings.optional.energy_distribution': False},
    'angle_sweep': {'beam_arguments.angle_mode': 'SWEEP', 'beam_arguments.optional.sweep': 3, 'beam.angle': 30.,
                    'settings.optional.energy_distribution': False},
    'random_angles': {'beam_arguments.angle_mode': 'RANDOM_DISTRIBUTION'},
    'cos_angles': {'beam_arguments.angle_mode': 'COS_DISTRIBUTION_1'},
    'maxwell_velocity': {'beam_arguments.kinetic_energy_mode': 'MAXWELLIAN_VELOCITY_DISTRIBUTION', 'beam.energy': 50.,
                         'beam_arguments.optional.sheath_potential': 150., 'beam.optional.charge': 1.},
    'maxwell_energy': {'beam_arguments.kinetic_energy_mode': 'MAXWELLIAN_ENERGY_DISTRIBUTION', 'beam.energy': 50.,
                       'beam_arguments.optional.sheath_potential': 150., 'beam.optional.charge': 1.},
    'energy_file': {'beam_arguments.kinetic_energy_mode': 'FILE', 'beam_arguments.optional.distributions': DISTRIBUTIONS},
    'angle_file': {'beam_arguments.angle_mode': 'FILE', 'beam_arguments.optional.distributions': DISTRIBUTIONS},
    'energy_angle_file': {'beam_arguments.kinetic_energy_mode': 'FILE_ENERGY_ANGLE', 'beam_arguments.angle_mode': 'FILE_ENERGY_ANGLE',
                          'beam_arguments.optional.distributions': DISTRIBUTIONS},
    'extra_parameters': {
        'beam.optional.azimuth': 30., 'beam.optional.start_depth': -2., 'beam.optional.inelastic_correction': 1.1,
        'beam.optional.cutoff_energy': 1.5, 'target.optional.cutoff_energy': 2., 'target.optional.bulk_binding_energy': 0.5,
        'settings.optional.trajectories_projectiles': True, 'settings.optional.trajectories_recoils': True,
        'settings.optional.trajectories_number': 5, 'settings.optional.energy_distribution': True,
        'settings.optional.distribution_grid': [20, 20, 20, 5.0], 'settings.optional.random_seed': 4242,
        'settings.optional.inelastic_outside': True
    },
    # inelastic loss models 2 and 3 are only allowed for the KrC potential
    'moliere_magic': {'settings.optional.interaction_potential': 'MOLIERE', 'settings.optional.integration_method': 'MAGIC', **LINDHARD_SCHARFF},
    'zbl_gauss_mehler': {'settings.optional.interaction_potential': 'ZBL', 'settings.optional.integration_method': 'GAUSS_MEHLER', **LINDHARD_SCHARFF},
    'nakagawa_yamamura': {'settings.optional.interaction_potential': 'NAKAGAWA_YAMAMURA', **LINDHARD_SCHARFF},
    'surface_binding_1': {'settings.optional.surface_binding_model': 'ELEMENT_SPECIFIC'},
    'surface_binding_3': {'settings.optional.surface_binding_model': 'ELEMENT_PAIRS'},
    'inelastic_lindhard_scharff': LINDHARD_SCHARFF,
    'all_outputs': {'settings.optional.log_reflected': True, 'settings.optional.log_sputtered': True, 'settings.optional.log_matrix': True},
}

# reduced set of variants for older versions
CORE_VARIANTS = ['default', 'dynamic', 'energy_1GeV', 'energy_sweep', 'all_outputs', 'extra_parameters', 'maxwell_energy',
                 'energy_file', 'angle_file', 'energy_angle_file']

# known problems of the simulation programs (not of the GUI): (folder name, base, variant) -> reason, None matches all
KNOWN_PROBLEMS = {
    ('SDTrimSP_7.00', None, 'energy_1GeV'): 'SDTrimSP 7.00 terminates with "ERROR: invalid case for flag" if projectiles leave the target at the bottom',
    ('SDTrimSP_7.01', None, 'energy_1GeV'): 'SDTrimSP 7.01 terminates with "ERROR: invalid case for flag" if projectiles leave the target at the bottom',
    ('SDTrimSP_7.00', None, 'energy_1MeV'): 'SDTrimSP 7.00 terminates with "ERROR: invalid case for flag" if projectiles leave the target at the bottom',
    ('SDTrimSP_7.01', None, 'energy_1MeV'): 'SDTrimSP 7.01 terminates with "ERROR: invalid case for flag" if projectiles leave the target at the bottom',
    ('SDTrimSP_6.06', 'H_Ar_FeW', None): 'SDTrimSP 6.06 (Windows binary) crashes with a stack overflow (exit code 170) for this target with two layers',
    ('SDTrimSP_6.06', None, 'all_outputs'): 'SDTrimSP 6.06 (Windows binary) crashes with a stack overflow (exit code 170) when matrices are written',
    ('SDTrimSP_7.00', None, 'all_outputs'): 'SDTrimSP 7.00 (Windows binary) crashes with a stack overflow (exit code 170) when matrices are written',
    ('SDTrimSP_6.06', 'Ar_Au', 'dynamic'): 'SDTrimSP 6.06 stops ("DEPTH INTERVAL COMPLETELY DEPLETED", "DECREASE FLC OR INCREASE NH") or '
                                           'crashes, the few projectiles of the test deplete the surface interval of Au at 60 degree',
}

# known problems where the simulation does not terminate (not run, they would block a process until the timeout)
KNOWN_HANGS = {
    ('SDTrimSP_6.06', None, 'extra_parameters'): 'SDTrimSP 6.06 enlarges the memory of recoil trajectories (ltraj_r) until the size overflows and does not finish',
    ('SDTrimSP_7.00', None, 'extra_parameters'): 'SDTrimSP 7.00 enlarges the memory of trajectories (ltraj_p/r) to more than 20 GB and does not finish',
}


def knownProblem(folder_name: str, base: str, variant: str) -> Optional[str]:
    """Returns the reason if a combination is known to fail because of the simulation program"""

    for (problem_folder, problem_base, problem_variant), reason in {**KNOWN_PROBLEMS, **KNOWN_HANGS}.items():
        if problem_folder in (None, folder_name) and problem_base in (None, base) and problem_variant in (None, variant):
            return reason
    return None


def bestVersion(version_name: str, versions: list) -> str:
    """Returns the listed version that suits the detected version best (highest listed version below it)"""

    detected = float(findall(r'\d+(?:\.\d+)?', version_name)[0])
    candidates = []
    for listed in versions:
        for number in listed.split(','):
            candidates.append((float(number), listed))
    lower = [candidate for candidate in candidates if candidate[0] <= detected + 1e-9]
    return max(lower)[1] if lower else min(candidates)[1]


def sdtrimspInstallations():
    """Returns (folder, binary, version) of all SDTrimSP installations with a binary for this operating system"""

    installations = []
    for folder in sorted((SIMULATION_PROGRAMS / 'SDTrimSP').glob('SDTrimSP_*')):
        binary = SDTrimSPInput.findBinary(folder)
        version_name = SDTrimSPInput.getVersionName(folder, binary)
        if binary is not None and version_name:
            installations.append((folder, binary, bestVersion(version_name, SDTrimSPInput.Versions)))
    return installations


INSTALLATIONS = sdtrimspInstallations()
NEWEST = INSTALLATIONS[-1][0].name if INSTALLATIONS else None


def supportsEnergyAngleFile(folder: Path, version: str) -> bool:
    """Returns True if the installation implements case_e0 = 6"""

    simulation = SDTrimSPInput()
    simulation.simulation_folder = folder
    return simulation.supportsEnergyAngleFile(version)


def sdtrimspCases():
    """All combinations of installation, example input and variant"""

    cases = []
    for folder, binary, version in INSTALLATIONS:
        variants = VARIANTS if (folder.name == NEWEST or ALL_VARIANTS) else CORE_VARIANTS
        for base in BASES:
            for variant in variants:
                reason = knownProblem(folder.name, base, variant)
                marks = [pytest.mark.xfail(reason=reason, strict=False, run=reason not in KNOWN_HANGS.values())] if reason else []
                if variant == 'energy_angle_file' and not supportsEnergyAngleFile(folder, version):
                    marks = [pytest.mark.skip(reason='case_e0 = 6 (ene_ang.inp) is not implemented in this version')]
                cases.append(pytest.param(folder, version, base, variant, id=f'{folder.name}-{base}-{variant}', marks=marks))
    return cases


def crystalCases():
    """Crystals for all versions that support them, layered crystals for versions with table.crystal"""

    cases = []
    for folder, binary, version in INSTALLATIONS:
        defaults = DefaultValues(version)
        if defaults.enable_crystal:
            cases.append(pytest.param(folder, version, 'crystal', id=f'{folder.name}-crystal'))
        if defaults.crystal_table and (folder / 'case' / 'Ar_2_Cu_W_layer_crystal').is_dir():
            cases.append(pytest.param(folder, version, 'layered_crystals', id=f'{folder.name}-layered_crystals'))
    return cases


def setValue(data: dict, path: str, value):
    """Sets a value in input.json data, 'beam.' and 'target.' set the value in all beam or target rows"""

    keys = path.split('.')
    if keys[0] in ('beam', 'target'):
        targets = data[f'{keys[0]}_rows']
        keys = keys[1:]
    else:
        targets = [data]
    for target in targets:
        for key in keys[:-1]:
            target = target.setdefault(key, {})
        target[keys[-1]] = value


def prepareInput(source: Path, save_folder: Path, variant: Optional[dict] = None):
    """Copies only input.json of an example (the GUI creates all other input files), applies the variant and reduces the number of projectiles"""

    variant = dict(variant or {})
    projectiles = variant.pop('_projectiles', PROJECTILES)

    save_folder.mkdir(parents=True)
    data = json.loads((source / 'input.json').read_text(encoding='utf-8'))
    for path, value in variant.items():
        setValue(data, path, copy.deepcopy(value))

    optional = data.setdefault('settings', {}).setdefault('optional', {})
    if 'histories' in optional:
        # SDTrimSP
        optional['projectiles'] = min(PROJECTILES_PER_HISTORY, projectiles)
        optional['histories'] = max(1, projectiles // optional['projectiles'])
        optional['histories_between_out'] = max(1, optional['histories'] // 100)
        if SEED is not None and 'random_seed' not in optional:
            optional['random_seed'] = SEED
    elif 'projectiles' in optional:
        # TRIDYN
        optional['projectiles'] = projectiles
    (save_folder / 'input.json').write_text(json.dumps(data, indent=4), encoding='utf-8')


@pytest.fixture
def run_folder(request, tmp_path):
    """Folder of the simulation run: in --simulation-data DIR (kept) or temporary"""

    data_dir = request.config.getoption('--simulation-data')
    if not data_dir:
        return tmp_path / 'run'
    name = request.node.callspec.id if hasattr(request.node, 'callspec') else request.node.name
    folder = Path(data_dir).resolve() / name
    shutil.rmtree(folder, ignore_errors=True)
    folder.parent.mkdir(parents=True, exist_ok=True)
    return folder


def writeMeta(folder: Path, program: str, simulation_folder: Path, version: str):
    """Stores which simulation created the data (used by test_simulation_data.py)"""

    (folder / 'bca_test.json').write_text(json.dumps({
        'program': program,
        'simulation_folder': simulation_folder.name,
        'version': version
    }, indent=4), encoding='utf-8')


def runAndCheckOutputs(qapp, page, sc, errors, after_start=None):
    """
    Runs the simulation of the page and shows all outputs

    :param after_start: (optional) function that is called after the simulation started (files in the folder can be written then)
    """

    page.runSimulation()
    if after_start is not None:
        after_start()
    assert pump(qapp, 10, until=lambda: page.process.state() != QProcess.ProcessState.NotRunning or not sc.running), 'simulation did not start'
    finished = pump(qapp, TIMEOUT, until=lambda: page.process.state() == QProcess.ProcessState.NotRunning and not sc.running)
    log = page.simulation_output.toPlainText()
    if not finished:
        page.process.kill()
    assert finished, f'simulation did not finish within {TIMEOUT} s\n{log[-2000:]}'
    pump(qapp, 0.5)
    assert page.run_status == SimulationPage.RunStatus.DONE, f'simulation failed:\n{log[-3000:]}'
    return checkOutputs(qapp, page, errors)


def checkOutputs(qapp, page, errors) -> int:
    """Shows all output files and draws all plots, returns the number of plots"""

    page.tab_widget.setCurrentIndex(3)
    page.updateOutputFilesList()
    assert page.output_files_list.count() > 0
    for i in range(page.output_files_list.count()):
        page.output_files_list.setCurrentRow(i)
        pump(qapp, 0.01)

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


@pytest.mark.simulation
@pytest.mark.parametrize('folder, version, base, variant', sdtrimspCases())
def test_sdtrimsp(main_window, qapp, run_folder, tmp_path, monkeypatch, errors, folder, version, base, variant):
    monkeypatch.chdir(tmp_path)
    binary = SDTrimSPInput.findBinary(folder)

    prepareInput(BASES[base], run_folder, VARIANTS[variant])

    sc, page = addSimulationPage(main_window, folder.name, 0, folder, binary, version)
    pump(qapp)
    assert page.loadSettings(run_folder, unsaved_warning=False)

    # the meta data is written after the start of the simulation, since all files except the input files are deleted
    plots = runAndCheckOutputs(qapp, page, sc, errors, lambda: writeMeta(run_folder, 'SDTrimSP', folder, version))
    assert plots > 0


@pytest.mark.simulation
@pytest.mark.parametrize('folder, version, case', crystalCases())
def test_sdtrimsp_crystal(main_window, qapp, run_folder, tmp_path, monkeypatch, errors, folder, version, case):
    monkeypatch.chdir(tmp_path)
    binary = SDTrimSPInput.findBinary(folder)
    defaults = DefaultValues(version)

    simulation_folder = folder
    if defaults.crystal_table:
        # own copy of the tables with Au in table.crystal (the tables of the installation are not changed)
        simulation_folder = tmp_path / folder.name
        shutil.copytree(folder / 'tables', simulation_folder / 'tables')
        table = CrystalTableFile(simulation_folder / 'tables' / 'table.crystal', CrystalTableLimits(version))
        if table.crystal('Au_fcc') is None:
            table.addCrystal(TableCrystal('Au_fcc', AU_LATTICE_CONSTANT, AU_LATTICE_CONSTANT, AU_LATTICE_CONSTANT, 4 / AU_LATTICE_CONSTANT ** 3, elements=['Au'] * 4), AU_FCC)

    sc, page = addSimulationPage(main_window, folder.name, 0, simulation_folder, binary, version)
    pump(qapp)

    if case == 'layered_crystals':
        # example with two crystals in layers (Cu_fcc and W_bcc), loaded from tri.inp and layer.inp
        run_folder.mkdir(parents=True)
        for file in ('tri.inp', 'layer.inp'):
            shutil.copy(folder / 'case' / 'Ar_2_Cu_W_layer_crystal' / file, run_folder / file)
        assert page.loadSettings(run_folder, from_json=False, unsaved_warning=False)
        dialog = page.crystal_editor_dialog
        assert len(dialog.tableCrystalsList()) == 2
        # mixture of both crystals and amorphous material in the first layer
        page.target_layers.rows[0].crystal_cells[0].setValue(0.5)
        page.target_layers.rows[0].crystal_cells[1].setValue(0.25)
    else:
        prepareInput(BASES['Ar_Au'], run_folder)
        assert page.loadSettings(run_folder, unsaved_warning=False)
        page.general_target_settings.layout_crystal_file.checkbox.setChecked(True)
        dialog = page.crystal_editor_dialog
        dialog.elementChanged()
        if dialog.table_mode:
            dialog.loadCrystalTable(select='Au_fcc')
        else:
            dialog.setFccParameter()
            dialog.lattice_constant.setValue(AU_LATTICE_CONSTANT)
        dialog.elementChanged()

    assert not dialog.undefined_state, dialog.table_crystal_validation.text() if dialog.table_mode else ''

    plots = runAndCheckOutputs(qapp, page, sc, errors, lambda: writeMeta(run_folder, 'SDTrimSP', folder, version))
    assert plots > 0


@pytest.mark.simulation
@pytest.mark.skipif(not (SIMULATION_PROGRAMS / 'TRIDYN' / 'Tridyn2022').is_dir(), reason='TRIDYN 2022 not available')
def test_tridyn(main_window, qapp, run_folder, tmp_path, monkeypatch, errors):
    monkeypatch.chdir(tmp_path)
    folder = SIMULATION_PROGRAMS / 'TRIDYN' / 'Tridyn2022'
    binary = TridynInput.findBinary(folder)
    if binary is None:
        pytest.skip('no TRIDYN binary for this operating system')

    prepareInput(TEST_SAVES / 'TRIDYN' / 'Ar_on_W', run_folder)

    sc, page = addSimulationPage(main_window, 'TRIDYN', 1, folder, binary, '2022')
    pump(qapp)
    assert page.loadSettings(run_folder, unsaved_warning=False)

    plots = runAndCheckOutputs(qapp, page, sc, errors, lambda: writeMeta(run_folder, 'TRIDYN', folder, '2022'))
    assert plots > 0
