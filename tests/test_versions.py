"""Consistency of the version specific options of SDTrimSP with the documentation of each version"""

import pytest

from Containers.Arguments import ArgumentValues
from Simulations.SDTrimSP import Versions, DefaultValues, DictLookup, VlSimulationSettings, CompRowBeamSettings


@pytest.mark.parametrize('version', Versions.ORDER)
def test_defaults_are_valid(version):
    defaults = DefaultValues(version)
    lookup = DictLookup(version)
    assert defaults.isbv in lookup.isbv.values()
    assert defaults.inel0 in lookup.inel0.values()
    assert defaults.ipot in lookup.ipot.values()
    assert defaults.iintegral in lookup.iintegral.values()


def test_version_order():
    assert Versions.atLeast(Versions.V_702, Versions.V_609)
    assert not Versions.atLeast(Versions.V_601, Versions.V_609)
    assert not Versions.atLeast('unknown', Versions.V_601)


@pytest.mark.parametrize('version, isbv', [
    (Versions.V_601, {1, 2, 3, 4, 5, 6, 7}),
    (Versions.V_606, {1, 2, 3, 4, 5, 6, 7}),
    (Versions.V_609, {1, 2, 3, 4, 6, 8}),  # 5 and 7 do not work since 6.09
    (Versions.V_700, {1, 2, 3, 4, 6, 8}),
    (Versions.V_702, {1, 2, 3, 4, 6, 8}),
    (Versions.V_707, {1, 2, 3, 4, 6, 8}),
])
def test_surface_binding_models(version, isbv):
    assert set(DictLookup(version).isbv.values()) == isbv


@pytest.mark.parametrize('version, inel0', [
    (Versions.V_601, {1, 2, 3, 4, 5, 6, 7}),
    (Versions.V_606, {1, 2, 3, 4, 5, 6, 7}),
    (Versions.V_609, {-1, 1, 2, 3, 4, 5, 6, 7}),  # -1: chosen by SDTrimSP for each element since 6.09
    (Versions.V_700, {-1, 1, 2, 3, 4, 5, 6, 7, 8}),  # tabulated stopping power since 7.00
    (Versions.V_702, {-1, 1, 2, 3, 4, 5, 6, 7, 8}),
    (Versions.V_707, {-1, 1, 2, 3, 4, 5, 6, 7, 8}),
])
def test_inelastic_loss_models(version, inel0):
    assert set(DictLookup(version).inel0.values()) == inel0


@pytest.mark.parametrize('version', Versions.ORDER)
def test_gui_entries_match_lookup(qapp, version):
    """Every selectable entry in the GUI must be written as a valid value, and the number shown must be the value"""

    lookup = DictLookup(version)

    settings = VlSimulationSettings(version)
    for i, entry in enumerate(settings.surface_binding_model_entries_save):
        if entry == -1:
            continue
        assert entry in lookup.isbv, f'{entry} can be selected, but is not valid for {version}'
        assert lookup.isbv[entry] == i + 1, f'{entry} is shown as {i + 1}, but written as {lookup.isbv[entry]}'

    row = CompRowBeamSettings(CompRowBeamSettings.rowFields, version=version)
    for i, entry in enumerate(row.inelastic_loss_model_entries_save):
        assert entry in lookup.inel0, f'{entry} can be selected, but is not valid for {version}'
        text = row.inelastic_loss_model.itemText(i)
        number = lookup.inel0[entry]
        assert text.startswith('auto') if number == -1 else text.startswith(f'{number}: '), f'{entry} is shown as "{text}", but written as {number}'
    # the default is the automatic model of SDTrimSP since 6.09
    automatic = ArgumentValues.InelasticLossModel.AUTOMATIC
    assert (row.inelastic_loss_model.getValue(save=True) == automatic) == Versions.atLeast(version, Versions.V_609)
    assert row.inelastic_loss_model.getDefaultSave() == (automatic if Versions.atLeast(version, Versions.V_609) else
                                                         next(k for k, v in lookup.inel0.items() if v == DefaultValues(version).inel0))


@pytest.mark.parametrize('version, crystal, table', [
    (Versions.V_601, False, False),
    (Versions.V_609, False, False),
    (Versions.V_700, True, False),
    (Versions.V_702, True, True),
    (Versions.V_707, True, True),
])
def test_crystal_support(version, crystal, table):
    defaults = DefaultValues(version)
    assert defaults.enable_crystal == crystal
    assert defaults.crystal_table == table


def test_tabulated_model_exists():
    assert ArgumentValues.InelasticLossModel.TABULATED in DictLookup(Versions.V_700).inel0


@pytest.mark.parametrize('version, selection', [(Versions.V_702, False), (Versions.V_707, True)])
def test_tbsp_file_selection(qapp, version, selection):
    """Since 7.07 the file of the tabulated stopping power is selected (tbsp_binary, tbsp_ascii), the GUI always uses the
    binary file (both files contain the same data), so the selection is not shown"""

    settings = VlSimulationSettings(version)
    assert settings.tbsp_format is None
    assert DefaultValues(version).tbsp_file_selection == selection


def test_run_failed(tmp_path):
    """SDTrimSP sometimes terminates with exit code 0 after an error"""

    from Simulations.SDTrimSP import SimulationInput
    simulation = SimulationInput()
    assert simulation.runFailed(tmp_path, 'ERROR: invalid case for flag...code terminates now...', 0, Versions.V_700)
    assert simulation.runFailed(tmp_path, 'stop from subroutine energy_init', 0, Versions.V_707)
    assert simulation.runFailed(tmp_path, '', 170, Versions.V_601)
    assert simulation.runFailed(tmp_path, '', 0, Versions.V_707)  # no output.dat
    (tmp_path / 'output.001.dat').write_text('')
    assert simulation.runFailed(tmp_path, 'end', 0, Versions.V_707) is None


def test_check_arguments():
    """inel0 = 2 or 3 is only allowed for the KrC potential"""

    from Containers.Arguments import ArgumentValues, GeneralArguments, RowArguments, GeneralTargetArguments, GeneralBeamArguments
    from Simulations.SDTrimSP import SimulationInput

    class Arguments:
        def __init__(self, ipot, inel0):
            self.settings = GeneralArguments(title='', mode=None, fluence=1, interaction_potential=ipot)
            row = RowArguments(index=1, symbol='Ar', element=None, abundance=1, max_atomic_fraction=1, energy=1, angle=0, inelastic_loss_model=inel0)
            self.beam_rows = [row]
            self.target_rows = []
            self.target_args = GeneralTargetArguments(thickness=100, segments=10)
            self.crystal_args = None
            self.structure = []
            self.beam_args = GeneralBeamArguments()

    simulation = SimulationInput()
    model = ArgumentValues.InelasticLossModel
    potential = ArgumentValues.InteractionPotential
    assert not simulation.checkArguments(Arguments(potential.KRC, model.LINDHARD_SCHARFF_AND_OEN_ROBINSON), Versions.V_707)
    assert simulation.checkArguments(Arguments(potential.ZBL, model.LINDHARD_SCHARFF_AND_OEN_ROBINSON), Versions.V_707)
    assert not simulation.checkArguments(Arguments(potential.ZBL, model.LINDHARD_SCHARFF), Versions.V_707)
