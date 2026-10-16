"""Loading of tri.inp and layer.inp of SDTrimSP: the input written by the GUI must describe the same simulation"""

import pytest

from conftest import SIMULATION_PROGRAMS

from Containers.Arguments import ArgumentValues
from Simulations.SDTrimSP import SimulationInput, Versions, speciesList


FOLDER = SIMULATION_PROGRAMS / 'SDTrimSP' / 'SDTrimSP_7.07'
pytestmark = pytest.mark.skipif(not (FOLDER / 'tables').is_dir(), reason='SDTrimSP 7.07 not available')


def load(tmp_path, tri: str, layer: str = '', version: str = Versions.V_707):
    """Loads the input files with SDTrimSP 7.07 and returns (arguments, errors)"""

    (tmp_path / 'tri.inp').write_text(tri)
    if layer:
        (tmp_path / 'layer.inp').write_text(layer)
    simulation = SimulationInput()
    simulation.simulation_folder = FOLDER
    simulation.updateElements(FOLDER, version)
    result = simulation.loadFiles(tmp_path, version)
    assert isinstance(result, tuple), result
    return result


def tri(symbols: str, qubeam: str, qu: str, extra: str = '') -> str:
    return f"""test
&TRI_INP
     ncp = {symbols.count(',') + 1}
     symbol = {symbols}
     nh = 10
     nr_pproj = 10
     qubeam = {qubeam}
     e0 = 1000.0, 0.0, 0.0
     alpha0 = 0.0, 0.0, 0.0
     ttarget = 100.0
     nqx = 10
     qu = {qu}
{extra}
/
"""


def symbols(arguments) -> list:
    group = arguments.settings.get('group_elements')
    return [symbol for symbol, _ in speciesList(arguments, group)]


def test_species_order_is_kept(tmp_path):
    # projectile first (as in most cases of SDTrimSP): not grouped
    arguments, errors = load(tmp_path, tri('"He", "Ni"', '1.0, 0.0', '0.0, 1.0'))
    assert symbols(arguments) == ['He', 'Ni']
    assert arguments.settings.get('group_elements') is False

    # target first: grouped
    arguments, errors = load(tmp_path, tri('"Ni", "He"', '0.0, 1.0', '1.0, 0.0'))
    assert symbols(arguments) == ['Ni', 'He']
    assert arguments.settings.get('group_elements') is True

    # an element in beam and target is only possible with grouped elements
    arguments, errors = load(tmp_path, tri('"Si", "Ar"', '0.5, 0.5', '1.0, 0.0'))
    assert symbols(arguments) == ['Si', 'Ar']
    assert arguments.settings.get('group_elements') is True


def test_default_inelastic_loss_model(tmp_path):
    """Since 6.09 SDTrimSP uses model 4 for H, D, T and model 5 for He if inel0 is not given"""

    arguments, _ = load(tmp_path, tri('"He", "H", "Ni"', '0.5, 0.5, 0.0', '0.0, 0.0, 1.0'))
    models = {row.symbol: row.get('inelastic_loss_model') for row in arguments.beam_rows + arguments.target_rows}
    assert models == {
        'He': ArgumentValues.InelasticLossModel.HELIUM,
        'H': ArgumentValues.InelasticLossModel.HYDROGEN,
        'Ni': ArgumentValues.InelasticLossModel.LINDHARD_SCHARFF_AND_ZIEGLER
    }


def test_number_of_sweeps(tmp_path):
    arguments, _ = load(tmp_path, tri('"Ar", "Si"', '1.0, 0.0', '0.0, 1.0', '     case_alpha = 5\n     number_calc = 9'))
    assert arguments.beam_args.get('sweep') == 9
    assert isinstance(arguments.beam_args.get('sweep'), int)


def test_target_species_from_layer_file(tmp_path):
    """With a layer file (iq0 = -1) qu is not needed"""

    text = tri('"Ar", "Si", "O"', '1.0, 0.0, 0.0', '', '     iq0 = -1').replace('     qu = \n', '')
    layer = """! layers  thickness  qu_2  qu_3
     4  2.0  0.333333  0.666667  SiO2
     6  2.0  1.0       0.0       Si
     0  0    0         0         end
"""
    arguments, errors = load(tmp_path, text, layer)
    assert [row.symbol for row in arguments.beam_rows] == ['Ar']
    assert [row.symbol for row in arguments.target_rows] == ['Si', 'O']
    assert [layer.name for layer in arguments.structure] == ['SiO2', 'Si']
    assert arguments.target_args.thickness == 100.


def test_layers_longer_than_target(tmp_path):
    """SDTrimSP uses the first nqx segments of layer.inp with their thickness (ttarget is not used)"""

    text = tri('"Si", "W"', '1.0, 0.0', '0.0, 1.0', '     iq0 = -1')
    layer = """! layers  thickness  qu_2
     5  10.0  1.0  W
     2  10.0  0.0  Si
   100  10.0  1.0  W
     0  0     0    end
"""
    arguments, errors = load(tmp_path, text, layer)
    # Si is a projectile and forms a layer
    assert [row.symbol for row in arguments.target_rows] == ['Si', 'W']
    assert [(layer.name, layer.segments, layer.thickness) for layer in arguments.structure] == [('W', 5, 50.), ('Si', 2, 20.), ('W', 3, 30.)]
    assert arguments.target_args.thickness == 100.


def test_layers_shorter_than_target(tmp_path):
    """SDTrimSP repeats the segments of layer.inp (starting with the first layer) until nqx segments are reached"""

    text = tri('"Si", "W"', '1.0, 0.0', '0.0, 1.0', '     iq0 = -1')
    layer = """! layers  thickness  qu_2
     3  10.0  1.0  W
     2  5.0   0.0  Si
     0  0     0    end
"""
    arguments, errors = load(tmp_path, text, layer)
    assert [(layer.name, layer.segments, layer.thickness) for layer in arguments.structure] == [
        ('W', 3, 30.), ('Si', 2, 10.), ('W', 3, 30.), ('Si', 2, 10.)
    ]
    assert arguments.target_args.thickness == 80.

    layer = layer.replace('2  5.0', '4  5.0')
    arguments, errors = load(tmp_path, text, layer)
    assert [(layer.name, layer.segments) for layer in arguments.structure] == [('W', 3), ('Si', 4), ('W', 3)]
