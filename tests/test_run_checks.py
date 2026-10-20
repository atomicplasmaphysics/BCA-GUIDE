"""
Checks before a run: warnings about the parameters (the user decides), unknown additional settings, miller indices of
layer files, version groups of configurations and the queue of "Run all"
"""


import pytest

from conftest import SIMULATION_PROGRAMS, addSimulationPage, pump

from Containers.CrystalTableFile import layerMillerError, layerMillerSuggestion
from Containers.SimulationConfiguration import SimulationConfiguration
from Simulations.SDTrimSP import SimulationInput, Versions, estimateRange, maxElements, namelistParameters, stoppingTableSymbols


SDTRIMSP = SIMULATION_PROGRAMS / 'SDTrimSP'
FOLDER = SDTRIMSP / 'SDTrimSP_7.07'
pytestmark = pytest.mark.skipif(not (FOLDER / 'tables').is_dir(), reason='SDTrimSP 7.07 not available')


def load(tmp_path, tri: str, version: str = Versions.V_707, folder=FOLDER):
    """Loads tri.inp and returns the arguments"""

    (tmp_path / 'tri.inp').write_text(tri)
    simulation = SimulationInput()
    simulation.simulation_folder = folder
    simulation.updateElements(folder, version)
    result = simulation.loadFiles(tmp_path, version)
    assert isinstance(result, tuple), result
    return simulation, result[0]


def tri(symbols: str, e0: str, inel0: str = '', extra: str = '', ttarget: float = 1000.) -> str:
    return f"""test
&TRI_INP
     ncp = 2
     symbol = {symbols}
     nh = 10
     nr_pproj = 10
     qubeam = 1.0, 0.0
     qumax = 0.0, 1.0
     e0 = {e0}, 0.0
     alpha0 = 0.0, 0.0
     ttarget = {ttarget}
     nqx = 100
     qu = 0.0, 1.0
{f'     inel0 = {inel0}' if inel0 else ''}
{extra}
/
"""


def test_range_estimate():
    # path lengths (upper limits of the projected ranges): 1 keV Ar in Si some nm, 1 MeV He in Si some um
    assert 30 < estimateRange(1000, 18, 39.95, 14, 28.09, 0.04994) < 100
    assert 2e4 < estimateRange(1e6, 2, 4.0, 14, 28.09, 0.04994) < 1e5
    assert estimateRange(0, 18, 39.95, 14, 28.09, 0.04994) == 0


def test_warning_inelastic_model(tmp_path):
    # Lindhard-Scharff (inel0 = 1) is only valid below 25 Z^(4/3) M keV (He: 25 * 2.52 * 4 keV = 252 keV)
    simulation, arguments = load(tmp_path, tri('"He", "Si"', '1e6', '1, 1'))
    warnings = simulation.checkWarnings(arguments, Versions.V_707)
    assert any(warning.startswith('He: the inelastic loss model 1') for warning in warnings), warnings
    # the recoils (Si) can get up to 4 * 4 * 28 / 32^2 * 1 MeV = 0.44 MeV, the limit of Si is 25 * 33.8 * 28 keV = 23.7 MeV
    assert not any(warning.startswith('Si') for warning in warnings)

    simulation, arguments = load(tmp_path, tri('"He", "Si"', '1e4', '1, 1'))
    assert simulation.checkWarnings(arguments, Versions.V_707) == []
    # LZ7 is valid at all energies
    simulation, arguments = load(tmp_path, tri('"He", "Si"', '1e6', '7, 7'))
    assert simulation.checkWarnings(arguments, Versions.V_707) == []


def test_warning_transmission_700(tmp_path):
    folder = SDTRIMSP / 'SDTrimSP_7.00'
    if not (folder / 'tables').is_dir():
        pytest.skip('SDTrimSP 7.00 not available')
    simulation, arguments = load(tmp_path, tri('"Ar", "Si"', '1e6', '', ttarget=500.), Versions.V_700, folder)
    warnings = simulation.checkWarnings(arguments, Versions.V_700)
    assert any('invalid case for flag' in warning for warning in warnings), warnings
    # newer versions handle transmitted projectiles
    simulation, arguments = load(tmp_path, tri('"Ar", "Si"', '1e6', '', ttarget=500.))
    assert not any('invalid case for flag' in warning for warning in simulation.checkWarnings(arguments, Versions.V_707))
    # a thick target
    simulation, arguments = load(tmp_path, tri('"Ar", "Si"', '1e3', '', ttarget=500.), Versions.V_700, folder)
    assert simulation.checkWarnings(arguments, Versions.V_700) == []


def test_warning_max_elements(tmp_path):
    # SDTrimSP 6.01 is compiled for 3 elements (ncpm = 3 in src/param.F90), 4 elements stop it while reading tri.inp
    installation = tmp_path / 'installation'
    (installation / 'src').mkdir(parents=True)
    (installation / 'src' / 'param.F90').write_text('module param\n   integer, parameter :: ncpm = 1   ! elements\nend module\n')
    assert maxElements(installation) == 1
    assert maxElements(tmp_path / 'missing') is None and maxElements(None) is None
    if (FOLDER / 'src').is_dir():
        assert (maxElements(FOLDER) or 0) >= 2

    simulation, arguments = load(tmp_path, tri('"Ar", "Si"', '1e3'))
    assert not any('ncpm' in warning for warning in simulation.checkWarnings(arguments, Versions.V_707))
    simulation.simulation_folder = installation
    warnings = simulation.checkWarnings(arguments, Versions.V_707)
    assert any('2 elements' in warning and 'at most 1' in warning for warning in warnings), warnings


def test_warning_stopping_table(tmp_path):
    # inel0 = 4 (H, D, T) reads tables/table3 for all species, SDTrimSP 7.01 has no C_a there (here: no Cu)
    installation = tmp_path / 'installation'
    (installation / 'tables').mkdir(parents=True)
    (installation / 'tables' / 'table3').write_text('table3\nc symbol  a1  a2\nH      1  1.262  1.44\nSi    14  2.1  3.2\n')
    assert stoppingTableSymbols(installation, 'table3') == {'H', 'Si'}
    assert stoppingTableSymbols(installation, 'table4') is None

    simulation, arguments = load(tmp_path, tri('"H", "Si"', '1e4', '4, 7'))
    simulation.simulation_folder = installation
    assert not any('table3' in warning for warning in simulation.checkWarnings(arguments, Versions.V_707))
    simulation, arguments = load(tmp_path, tri('"H", "Cu"', '1e4', '4, 7'))
    simulation.simulation_folder = installation
    warnings = simulation.checkWarnings(arguments, Versions.V_707)
    assert any('tables/table3, Cu is missing' in warning for warning in warnings), warnings
    # without inel0 = 4 the table is not read
    simulation, arguments = load(tmp_path, tri('"H", "Cu"', '1e4', '7, 7'))
    simulation.simulation_folder = installation
    assert not any('table3' in warning for warning in simulation.checkWarnings(arguments, Versions.V_707))
    # the automatic model of SDTrimSP (inel0 not given or -1) is 4 for H
    for inel0 in ('', '-1, 7'):
        simulation, arguments = load(tmp_path, tri('"H", "Cu"', '1e4', inel0))
        simulation.simulation_folder = installation
        warnings = simulation.checkWarnings(arguments, Versions.V_707)
        assert any('tables/table3, Cu is missing' in warning for warning in warnings), (inel0, warnings)


def test_warning_large_files(tmp_path):
    simulation, arguments = load(tmp_path, tri('"Ar", "Si"', '1e5', '', '     ltraj_p = .true.\n     ltraj_r = .true.\n     numb_hist = 1000'))
    warnings = simulation.checkWarnings(arguments, Versions.V_707)
    assert any('trajec_' in warning for warning in warnings), warnings


def test_additional_settings_of_version(tmp_path):
    # the namelist of the source code: beta0 since 7.00, tbsp_binary since 7.07
    names_601 = namelistParameters(SDTRIMSP / 'SDTrimSP_6.01')
    names_707 = namelistParameters(FOLDER)
    if names_601 is not None:
        assert 'beta0' not in names_601 and 'ttarget' in names_601
    assert {'beta0', 'tbsp_binary', 'l_crystal1', 'name_cryst1', 'ttarget'} <= names_707

    simulation = SimulationInput()
    simulation.simulation_folder = FOLDER
    errors = simulation.checkAdditional('beta0 = 10.0\nnot_a_parameter = 1\n! comment\nk_start = 0', Versions.V_707)
    assert len(errors) == 1 and errors[0].startswith('Line 2: Unknown variable "not_a_parameter"')
    if names_601 is not None:
        simulation.simulation_folder = SDTRIMSP / 'SDTrimSP_6.01'
        errors = simulation.checkAdditional('beta0 = 10.0', Versions.V_601)
        assert len(errors) == 1 and 'SDTrimSP 6.01 does not read it' in errors[0]


def test_unknown_settings_are_marked(main_window, qapp, tmp_path, errors):
    sc, page = addSimulationPage(main_window, 'marks', 0, FOLDER, SimulationInput.findBinary(FOLDER) or FOLDER / 'SDTrimSP.exe', Versions.V_707, tmp_path)
    pump(qapp)
    page.additional_settings.setPlainText('k_start = 0\nunknown = 1')
    pump(qapp)
    assert list(page.additional_settings.marked_lines) == [1]
    assert 'unknown' in page.additional_settings.marked_lines[1]
    page.additional_settings.setPlainText('k_start = 0')
    pump(qapp)
    assert page.additional_settings.marked_lines == {}
    assert not errors, '\n'.join(errors)


def test_layer_miller_index():
    assert layerMillerError([1, 0, 0]) is None
    assert layerMillerError([2, 1, 1]) is None
    assert layerMillerError([0, 0, 1]) is not None
    assert layerMillerError([1, 2, 0]) is not None
    assert layerMillerError([1, -1, 0]) is not None
    assert layerMillerSuggestion([0, 0, 1]) == [1, 0, 0]
    assert layerMillerSuggestion([1, 1, 2]) == [2, 1, 1]


def configuration(folder, version: str) -> dict:
    binary = SimulationInput.findBinary(folder)
    return {'title': 'test', 'program': 'SDTrimSP', 'folder': str(folder), 'binary': str(binary), 'version': version,
            'base_save_folder': '', 'save_folder': ''}


def test_version_groups_of_configurations():
    # old version group "6.01, 6.06" is replaced by the version found in the folder
    folder = SDTRIMSP / 'SDTrimSP_6.06'
    if SimulationInput.findBinary(folder) is not None:
        sc = SimulationConfiguration.load(configuration(folder, '6.01, 6.06'))
        assert sc.version == Versions.V_606
        assert sc.detected_version is None

    # a different (but existing) version group is kept, the found version is remembered for a question to the user
    sc = SimulationConfiguration.load(configuration(FOLDER, Versions.V_702))
    assert sc.version == Versions.V_702
    assert sc.detected_version == Versions.V_707
    sc = SimulationConfiguration.load(configuration(FOLDER, Versions.V_707))
    assert sc.detected_version is None

    # empty save folders do not crash
    assert sc.save_folder is None and sc.base_save_folder is None


class StubProgress:
    def __init__(self):
        self.progress = 0
        self.elapsed_timer_final = 0

    def value(self):
        return self.progress

    @property
    def elapsed_timer(self):
        stub = self

        class Timer:
            def elapsed(self):
                return 1000 * max(stub.progress, 1)
        return Timer()


class StubPage:
    """Simulation page that only records the runs"""

    def __init__(self, title: str, started: list):
        from Pages.ProgramPage import SimulationPage
        self.simulation_configuration = type('SC', (), {'title': title, 'running': False, 'save_folder': None, 'tab_widget': self})()
        self.run_status = SimulationPage.RunStatus.READY
        self.run_progress = StubProgress()
        self.started = started

    def runWarnings(self):
        return ['energy too high'] if self.simulation_configuration.title == 'b' else []

    def setRunStatus(self, status):
        self.run_status = status

    def runSimulation(self, detached=False, check_warnings=True, ask_delete=True):
        assert not check_warnings and not ask_delete
        self.started.append(self.simulation_configuration.title)
        self.simulation_configuration.running = True
        return True


def test_run_all_queue(main_window, qapp, monkeypatch):
    from Utility.GlobalConf import GlobalConf
    from Pages.ProgramPage import SimulationPage
    monkeypatch.setattr(GlobalConf, 'max_parallel_runs', 2)
    monkeypatch.setattr(GlobalConf, 'skip_delete_info', True)
    started = []
    pages = [StubPage(title, started) for title in 'abcde']

    main_window.runSimulations([page.simulation_configuration for page in pages])
    # at most 2 at the same time, the others are queued
    assert started == ['a', 'b']
    assert [page.run_status for page in pages[2:]] == [SimulationPage.RunStatus.QUEUED] * 3
    assert 'Run all: 0 of 5 finished, 2 running, 3 waiting' in main_window.statusBar().currentMessage()

    pages[0].run_progress.progress = 50
    assert main_window.runAllRemainingTime() is not None

    main_window.simulationFinished(pages[1])
    assert started == ['a', 'b', 'c']
    main_window.setMaxParallelRuns(3)
    assert started == ['a', 'b', 'c', 'd']

    # abort: the waiting simulation is not started
    main_window.menuAbort()
    assert pages[4].run_status == SimulationPage.RunStatus.READY
    for page in (pages[0], pages[2], pages[3]):
        main_window.simulationFinished(page)
    assert started == ['a', 'b', 'c', 'd']
    assert 'finished' in main_window.statusBar().currentMessage()


def test_polycrystal_only_without_layers():
    """(0 0 0) means a polycrystal, SDTrimSP supports it only without layer.inp (iq0 = 0)"""

    error = layerMillerError([0, 0, 0])
    assert error is not None and 'polycrystal' in error and 'one layer' in error
