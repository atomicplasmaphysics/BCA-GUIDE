"""Input files of the distributions of energies and angles of SDTrimSP (energy.inp, angle.inp, ene_ang.inp)"""

from pathlib import Path

import pytest

from Containers.Arguments import ArgumentValues, GeneralArguments, GeneralBeamArguments, GeneralTargetArguments, RowArguments
from Simulations.SDTrimSP import Versions, SimulationInput, distributionFileNames
from TableWidgets.DistributionEditor import (
    readDistributionFile, writeDistributionFile, readEnergyAngleFile, writeEnergyAngleFile, DistributionDialog
)

EXAMPLES = Path(__file__).resolve().parents[1] / 'Simulation Programs' / 'SDTrimSP'


class Arguments:
    """Minimal <SimulationArguments>: beam He and Ar, target Si"""

    def __init__(self, case_e0=ArgumentValues.KineticEnergy.FIXED, case_alpha=ArgumentValues.Angle.FIXED, distributions=None, group=True):
        self.settings = GeneralArguments(title='', mode=None, fluence=1, group_elements=group)
        self.beam_rows = [
            RowArguments(index=1, symbol='He', element=None, abundance=0.2, max_atomic_fraction=1, energy=1, angle=0),
            RowArguments(index=2, symbol='Ar', element=None, abundance=0.8, max_atomic_fraction=1, energy=1, angle=0)
        ]
        self.target_rows = [RowArguments(index=3, symbol='Si', element=None, abundance=1, max_atomic_fraction=1)]
        self.beam_args = GeneralBeamArguments(kinetic_energy_mode=case_e0, angle_mode=case_alpha, distributions=distributions or {})
        self.target_args = GeneralTargetArguments(thickness=100, segments=10)
        self.crystal_args = None
        self.structure = []


def test_distribution_file_roundtrip(tmp_path):
    rows = [[50., 5.], [200., 10.], [300., 15.5]]
    path = tmp_path / 'energy.inp'
    path.write_text(writeDistributionFile(rows, 'E [eV] distribution [-/dE]'))
    assert readDistributionFile(path) == rows


def test_energy_angle_file_roundtrip(tmp_path):
    data = {'angle': [10., 30., 10.], 'energy': [100., 200., 100.], 'matrix': [[1., 2., 3.], [4., 0., 0.5]]}
    path = tmp_path / 'ene_ang.inp'
    path.write_text(writeEnergyAngleFile(data))
    assert readEnergyAngleFile(path) == data


@pytest.mark.skipif(not (EXAMPLES / 'SDTrimSP_7.07' / 'case' / 'He_Ar_Si_distribution').is_dir(), reason='example of SDTrimSP 7.07 not available')
def test_read_examples():
    folder = EXAMPLES / 'SDTrimSP_7.07' / 'case' / 'He_Ar_Si_distribution'
    assert readDistributionFile(folder / 'energy.inp') == [[50., 5.], [200., 10.], [300., 15.], [400., 17.5]]
    assert readDistributionFile(folder / 'angle02.inp') == [[10., 10.], [20., 20.], [40., 35.]]
    data = readEnergyAngleFile(folder / 'ene_ang.inp')
    assert data['angle'] == [10., 80., 10.] and data['energy'] == [10., 140., 10.]
    assert len(data['matrix']) == 13 and all(len(row) == 9 for row in data['matrix'])


def test_file_names_per_version():
    energy = ArgumentValues.KineticEnergy.FILE
    angle = ArgumentValues.Angle.FILE
    # species order of the input file with grouped elements: target (Si), then the other projectiles (He, Ar)
    arguments = Arguments(energy, angle)
    names = distributionFileNames(arguments, Versions.V_707, True)
    assert names['energy'] == [('He', 'energy02.inp'), ('Ar', 'energy03.inp')]
    assert names['angle'] == [('He', 'angle02.inp'), ('Ar', 'angle03.inp')]
    # 7.02 reads only angle.inp, it is written additionally for the first projectile
    assert distributionFileNames(arguments, Versions.V_702, True)['angle'][-1] == ('He', 'angle.inp')
    names = distributionFileNames(arguments, Versions.V_601, True)
    assert names['energy'] == [('He', 'energy.inp'), ('Ar', 'energy2.inp')]
    assert names['angle'] == [('all', 'angle.inp')]
    names = distributionFileNames(Arguments(ArgumentValues.KineticEnergy.FILE_ENERGY_ANGLE, ArgumentValues.Angle.FILE_ENERGY_ANGLE), Versions.V_700, True)
    assert names == {'energy': [], 'angle': [], 'energy_angle': [('all', 'ene_ang.inp')]}


def test_make_and_check_files():
    simulation = SimulationInput()
    energy = ArgumentValues.KineticEnergy.FILE
    angle = ArgumentValues.Angle.FILE

    # missing distributions are reported
    assert len(simulation.checkArguments(Arguments(energy, angle), Versions.V_707)) == 4

    distributions = {'energy': {'Ar': [[100., 1.]], 'He': [[50., 1.]]}, 'angle': {'Ar': [[10., 1.]], 'He': [[20., 1.]], 'all': [[30., 1.]]}}
    arguments = Arguments(energy, angle, distributions)
    assert not simulation.checkArguments(arguments, Versions.V_707)
    assert sorted(simulation.makeDistributionFiles(arguments, Versions.V_707)) == ['angle02.inp', 'angle03.inp', 'energy02.inp', 'energy03.inp']
    assert sorted(simulation.makeDistributionFiles(arguments, Versions.V_609)) == ['angle.inp', 'energy.inp', 'energy2.inp']
    assert not simulation.makeDistributionFiles(Arguments(distributions=distributions), Versions.V_707)


def test_dialog(qapp):
    dialog = DistributionDialog(None, ['He', 'Ar'], {'energy': {'Ar': [[10., 1.], [20., 2.]]}}, True, True, True, angle_per_projectile=False)
    assert dialog.tabs.count() == 4  # energy He, energy Ar, angle (all), energy and angle
    dialog.energy_tables['He'].addRow(500., 3.)
    result = dialog.distributionData()
    assert result['energy']['Ar'] == [[10., 1.], [20., 2.]]
    assert result['energy']['He'][-1] == [500., 3.]
    assert 'all' in result['angle']
    assert result['energy_angle']['matrix']

    # decreasing upper bounds and an empty matrix are not accepted
    dialog.energy_tables['Ar'].setRows([[20., 1.], [10., 1.]])
    dialog.accept()
    assert 'upper bounds must increase' in dialog.problems.text()
    assert 'at least one positive value' in dialog.problems.text()
    dialog.deleteLater()


def test_energy_angle_legacy_format(tmp_path):
    """until SDTrimSP 7.02 two numbers precede the matrix instead of the header"""

    data = {'angle': [10., 30., 10.], 'energy': [100., 200., 100.], 'matrix': [[1., 2., 3.], [4., 0., 0.5]]}
    text = writeEnergyAngleFile(data, legacy=True)
    assert not text.startswith('!')
    path = tmp_path / 'ene_ang.inp'
    path.write_text(text)
    assert readEnergyAngleFile(path) == data


def test_energy_angle_file_support():
    simulation = SimulationInput()
    assert simulation.supportsEnergyAngleFile(Versions.V_601)
    assert not simulation.supportsEnergyAngleFile(Versions.V_700)
    assert simulation.supportsEnergyAngleFile(Versions.V_707)
    for name, supported in (('SDTrimSP_7.02', False), ('SDTrimSP_7.05', True)):
        if (EXAMPLES / name).is_dir():
            simulation.simulation_folder = EXAMPLES / name
            assert simulation.supportsEnergyAngleFile(Versions.V_702) == supported


def test_legacy_format_per_version():
    simulation = SimulationInput()
    assert simulation.legacyEnergyAngleFormat(Versions.V_601)
    assert simulation.legacyEnergyAngleFormat(Versions.V_700)
    assert not simulation.legacyEnergyAngleFormat(Versions.V_707)
    for name, legacy in (('SDTrimSP_7.02', True), ('SDTrimSP_7.05', False)):
        folder = EXAMPLES / name
        if folder.is_dir():
            simulation.simulation_folder = folder
            assert simulation.legacyEnergyAngleFormat(Versions.V_702) == legacy
