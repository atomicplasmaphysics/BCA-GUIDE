"""Tests of the plots of the simulation results: every plot of the examples can be drawn and exported"""


import numpy as np
import pytest

from conftest import ROOT, SIMULATION_PROGRAMS, addSimulationPage, copySave, pump

from Simulations.SDTrimSP import (
    SimulationInput as SDTrimSPInput, Versions, readEnergyDistribution, readEnergyDepthMatrix, readEnergyAngleMatrix,
    matrixSpecies, numbersOfLine
)
from Simulations.TRIDYN2022 import SimulationInput as TridynInput


EXAMPLES = ROOT / 'saves' / 'SDTrimSP'
TRIDYN_EXAMPLES = ROOT / 'saves' / 'TRIDYN'
TRIDYN_FOLDER = SIMULATION_PROGRAMS / 'TRIDYN' / 'Tridyn2022'


def waitForPlot(qapp, page, timeout: float = 30):
    """Waits until the analysis of the plot is finished"""

    evaluation = page.evaluation_class
    pump(qapp, timeout, until=lambda: evaluation.waiting is None and not evaluation.analyse_queue)
    pump(qapp, 0.05)


def plotItems(page):
    """Returns the items of the list of plots that show a plot"""

    items = page.output_parameters_list
    return [items.item(i) for i in range(items.count()) if getattr(items.item(i), 'function', None) is not None]


def showAllPlots(qapp, page) -> dict:
    """Shows all plots of the list and returns {text of item: exported data or None}"""

    page.tab_widget.setCurrentIndex(4)
    page.updateOutputParametersList(forced=True)
    pump(qapp)
    exports = {}
    for item in plotItems(page):
        page.evaluation_class.analysis.data = None
        page.output_parameters_list.setCurrentItem(item)
        waitForPlot(qapp, page)
        exports[item.text().strip()] = page.evaluation_class.getReturnData(separator=',')
    return exports


CASES = [('SDTrimSP', path.name) for path in sorted(EXAMPLES.glob('example_*')) if (path / 'output.dat').is_file()]
CASES += [('TRIDYN', path.name) for path in sorted(TRIDYN_EXAMPLES.glob('example_*')) if any(path.glob('*_out.dat'))]


@pytest.mark.parametrize('program, example', CASES)
def test_all_plots_of_examples(main_window, qapp, tmp_path, errors, program, example):
    if program == 'SDTrimSP':
        folder = SIMULATION_PROGRAMS / 'SDTrimSP' / 'SDTrimSP_7.07'
        save = copySave(EXAMPLES / example, tmp_path / example)
        sc, page = addSimulationPage(main_window, example, 0, folder, SDTrimSPInput.findBinary(folder) or folder / 'SDTrimSP.exe', Versions.V_707, save)
    else:
        if not TRIDYN_FOLDER.is_dir():
            pytest.skip('TRIDYN 2022 not available')
        save = copySave(TRIDYN_EXAMPLES / example, tmp_path / example)
        sc, page = addSimulationPage(main_window, example, 1, TRIDYN_FOLDER, TridynInput.findBinary(TRIDYN_FOLDER) or TRIDYN_FOLDER / 'tridyn.exe', '2022', save)
    pump(qapp)

    exports = showAllPlots(qapp, page)
    assert exports, 'no plots listed'
    assert not errors, '\n'.join(errors)

    # most plots have data, the ones without data are e.g. sputtered projectiles
    with_data = [text for text, data in exports.items() if data is not None]
    assert len(with_data) >= len(exports) / 2, exports.keys()
    for text in with_data:
        lines = exports[text].splitlines()
        assert len(lines) >= 2, text
        # CSV: same number of columns in each line
        assert len({len(line.split(',')) for line in lines[1:]}) == 1, text


@pytest.mark.skipif(not (EXAMPLES / 'example_01_Ar_on_Au' / 'E_distr_all.dat').is_file(), reason='example without energy distribution')
def test_energy_distribution(main_window, qapp, tmp_path, errors):
    folder = SIMULATION_PROGRAMS / 'SDTrimSP' / 'SDTrimSP_7.07'
    save = copySave(EXAMPLES / 'example_01_Ar_on_Au', tmp_path / 'example')

    # stopped energy + electronic + nuclear loss = deposited energy
    parts = [readEnergyDistribution(save / f'E_distr_{kind}.dat') for kind in ('all', 'stop', 'inel', 'nucl')]
    assert all(part is not None for part in parts)
    assert parts[0]['values'].shape == (40, 40, 40)
    assert np.sum(parts[0]['values']) == pytest.approx(sum(np.sum(part['values']) for part in parts[1:]), rel=1e-3)

    sc, page = addSimulationPage(main_window, 'distribution', 0, folder, SDTrimSPInput.findBinary(folder) or folder / 'SDTrimSP.exe', Versions.V_707, save)
    pump(qapp)
    page.tab_widget.setCurrentIndex(4)
    page.updateOutputParametersList(forced=True)
    pump(qapp)
    item = next(item for item in plotItems(page) if item.text().strip().startswith('Deposited energy'))
    page.output_parameters_list.setCurrentItem(item)
    waitForPlot(qapp, page)

    hl = page.plot_hbox
    assert not hl.energy_distribution_view.isHidden()
    assert hl.trajectory_number.isHidden()
    data, labels = page.evaluation_class.analysis.data
    assert labels == ['Depth x [Å]', 'Lateral position y [Å]', 'Energy [eV/Å²/projectile]']
    assert len(data[0]) == 40 * 40

    # depth profile: summed over the lateral directions, the integral is the deposited energy per projectile
    hl.energy_distribution_view.setCurrentIndex(3)
    waitForPlot(qapp, page)
    data, labels = page.evaluation_class.analysis.data
    assert labels[0] == 'Depth x [Å]' and len(data[0]) == 40
    assert np.sum(data[1]) * 2.5 == pytest.approx(np.sum(parts[0]['values']) * 2.5 ** 3, rel=1e-6)

    for view in range(3):
        hl.energy_distribution_view.setCurrentIndex(view)
        hl.energy_distribution_log.checkbox.setChecked(view == 1)
        waitForPlot(qapp, page)
        assert page.evaluation_class.analysis.data is not None

    # other plots hide the settings
    item = next(item for item in plotItems(page) if item.text().strip() == 'Implantation depth')
    page.output_parameters_list.setCurrentItem(item)
    waitForPlot(qapp, page)
    assert hl.energy_distribution_view.isHidden()
    assert not errors, '\n'.join(errors)


ENERGY_DEPTH_MATRIX = """# SDTrimSP: VERSION 7.07    16.10.2026
title
           1          40         100    number species of particle , NH, NR
   4000.00000000000        nproj
  MAX. PENETRATION DEPTH BACKSCATTERED PROJECILES, COMPONENT( 1): Ar
#  DIMENSION:   lin.energy        depth    log_energ
                       3           2           0
 ENERGY [eV]   MAXIMUM PENETRATION DEPTH [A] (center layer)
  0.0000E+00  0.5000E+01  0.1500E+02
  0.2000E+02          12          14          26
  0.4000E+02          20          10          30
  0.6000E+02           8           7          15
  0.0000E+00          40          31          71
"""

ENERGY_ANGLE_MATRIX = """# SDTrimSP: VERSION 7.07    16.10.2026
title
#   number species ,  ihist,    NR,    lmatout_cos_angle
           1          40         100           0
# BACKSCATTERED PROJECTILE,   COMPONENT( 1): Ar
# DIMENSION: lin.energy azim.angle polar-angle  nrproj (ANGLE:degree)
           2           2           3   0.100000000000E+03
# ENERGY [eV] lin
  0.1000E+02  0.2000E+02
# AZIMUTHAL ANGLE [ DEGREE ]
  0.1800E+03  0.3600E+03
# POLAR ANGLE [ DEGREE ]
  0.3000E+02  0.6000E+02  0.9000E+02
    30.0   60.0   90.0
       1      2      3
       4      5      6
    30.0   60.0   90.0
       0      0      1
       0      1      0
# BACKSCATTERED PROJECTILE,   COMPONENT( 1): Ar
# DIMENSION: log.energy azim.angle polar-angle nrproj (ANGLE:degree)
           2           2           3   0.100000000000E+03
"""


def test_matrix_readers(tmp_path):
    # numbers without blank in between (negative values in E_distr_*.dat)
    assert numbersOfLine(' 0.24525E-04-0.10110E-04  1.0D+01') == pytest.approx([0.24525e-4, -0.10110e-4, 10.])
    assert numbersOfLine(' intervals x (dimension: ni+1)') == []

    path = tmp_path / 'mpe_ex_p.dat'
    path.write_text(ENERGY_DEPTH_MATRIX)
    matrices = readEnergyDepthMatrix(path)
    assert len(matrices) == 1
    assert matrices[0]['species'] == 'Ar'
    assert matrices[0]['projectiles'] == 4000
    assert list(matrices[0]['depths']) == [5, 15]
    assert matrices[0]['counts'].tolist() == [[12, 14], [20, 10], [8, 7]]

    path = tmp_path / 'meagb_p.dat'
    path.write_text(ENERGY_ANGLE_MATRIX)
    assert matrixSpecies(path) == ['Ar']
    matrices = readEnergyAngleMatrix(path)
    assert len(matrices) == 1
    assert list(matrices[0]['energies']) == [10, 20]
    assert list(matrices[0]['polar']) == [30, 60, 90]
    # summed over the azimuthal angle
    assert matrices[0]['counts'].tolist() == [[5, 7, 9], [0, 1, 1]]
    assert matrices[0]['projectiles'] == 100


def test_depth_intervals_and_colors():
    from Simulations.SDTrimSP import SimulationAnalysis
    from Utility.Styles import PALETTE, paletteHex, paletteRgb, Palette

    # one depth interval (nqx = 1) starts at the surface
    assert list(SimulationAnalysis.depthIntervals(np.array([[0.5], [5.]]))) == [1., 10.]
    assert list(SimulationAnalysis.depthIntervals(np.array([[5., 15., 25.]]))) == [10.]

    # the 12 colors of the palette, then lightened versions
    assert sorted(paletteHex(i).upper() for i in range(12)) == sorted(PALETTE)
    assert all(c >= d for c, d in zip(paletteRgb(12), paletteRgb(0)))
    assert Palette()[100] == paletteRgb(100)


def test_failing_plot_does_not_crash(main_window, qapp, tmp_path, errors):
    """An exception in a plot shows the error in the plot and is logged (PyQt6 would terminate the application)"""

    folder = SIMULATION_PROGRAMS / 'SDTrimSP' / 'SDTrimSP_7.07'
    save = copySave(EXAMPLES / 'example_01_Ar_on_Au', tmp_path / 'example')
    (save / 'depth_proj.dat').write_text('broken\n')
    sc, page = addSimulationPage(main_window, 'broken', 0, folder, SDTrimSPInput.findBinary(folder) or folder / 'SDTrimSP.exe', Versions.V_707, save)
    pump(qapp)
    analysis = page.evaluation_class.analysis
    analysis.save_folder = save
    analysis.plotImplantationDepth = lambda: 1 / 0
    page.evaluation_class.analyse('plotImplantationDepth')
    waitForPlot(qapp, page)
    assert any('ZeroDivisionError' in error for error in errors)
    errors.clear()
