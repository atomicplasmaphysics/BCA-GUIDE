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
    (Versions.V_609, {1, 2, 3, 4, 6, 8}),  # 5 and 7 do not work since 6.09
    (Versions.V_700, {1, 2, 3, 4, 6, 8}),
    (Versions.V_702, {1, 2, 3, 4, 6, 8}),
])
def test_surface_binding_models(version, isbv):
    assert set(DictLookup(version).isbv.values()) == isbv


@pytest.mark.parametrize('version, inel0', [
    (Versions.V_601, {1, 2, 3, 4, 5, 6, 7}),
    (Versions.V_609, {1, 2, 3, 4, 5, 6, 7}),
    (Versions.V_700, {1, 2, 3, 4, 5, 6, 7, 8}),  # tabulated stopping power since 7.00
    (Versions.V_702, {1, 2, 3, 4, 5, 6, 7, 8}),
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
    for entry in row.inelastic_loss_model_entries_save:
        assert entry in lookup.inel0, f'{entry} can be selected, but is not valid for {version}'


@pytest.mark.parametrize('version, crystal, table', [
    (Versions.V_601, False, False),
    (Versions.V_609, False, False),
    (Versions.V_700, True, False),
    (Versions.V_702, True, True),
])
def test_crystal_support(version, crystal, table):
    defaults = DefaultValues(version)
    assert defaults.enable_crystal == crystal
    assert defaults.crystal_table == table


def test_tabulated_model_exists():
    assert ArgumentValues.InelasticLossModel.TABULATED in DictLookup(Versions.V_700).inel0
