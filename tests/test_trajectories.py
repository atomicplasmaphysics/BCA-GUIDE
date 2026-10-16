"""Tests of reading and plotting the trajectories (trajec_all.dat) of SDTrimSP"""

import numpy as np

from conftest import SIMULATION_PROGRAMS, addSimulationPage, pump

from Simulations.SDTrimSP import readTrajectoryFile, readLayers, SimulationInput as SDTrimSPInput, Versions


# format since 6.09: "parent" is the generation of the recoils
TRAJECTORIES_707 = """# SDTrimSP: VERSION 7.07    16.10.2026
SDTrimSP - Tue. Mar 03 14:24:43 2026
           2           1 ! maxnumber history, 1...projectiles + recoil
#   i_traj     ihist     iproj    parent     ncoll   species       ibn  termflag
         0         1         1         0         2         2         3         2
#        k              x              y              z          ptime         energy
         0 -4.3460094E+00  0.0000000E+00  0.0000000E+00  0.0000000E+00  2.0000000E+03
         1  2.4816540E-01  6.8912622E+00  3.9786721E+00  5.0611772E-01  1.7827309E+03
         2 -6.1565169E+00  1.3820732E+01  7.1163318E+00  1.7863705E+00  1.5941894E+03
#   i_traj     ihist     iproj    parent     ncoll   species       ibn  termflag
         1         1         1         1         1         1         2         4
#        k              x              y              z          ptime         energy
         0  1.9949944E+01  3.2091194E+01  1.7544402E+01  0.0000000E+00  1.5741780E+00
         1  2.0201428E+01  3.1521306E+01  1.6931889E+01  7.4664916E+01  0.0000000E+00
#   i_traj     ihist     iproj    parent     ncoll   species       ibn  termflag
         2         1         1         2         1         1         2         5
#        k              x              y              z          ptime         energy
         0  1.0000000E+01  3.0000000E+01  1.0000000E+01  0.0000000E+00  5.0000000E+00
         1 -1.0000000E+00  2.9000000E+01  9.0000000E+00  7.4664916E+01  2.0000000E+00
#   i_traj     ihist     iproj    parent     ncoll   species       ibn  termflag
         3         1         2         0        27         2         2         1
#        k              x              y              z          ptime         energy
         0 -4.3460094E+00  0.0000000E+00  0.0000000E+00  0.0000000E+00  2.0000000E+03
         1  3.0000000E+01  5.0000000E+00  3.0000000E+00  1.0000000E+01  0.0000000E+00
#ende
           2   number history from SDTrimSP
"""

# format until 6.06: no "#", "parent" is the species of the parent
TRAJECTORIES_601 = """SDTrimSP: VERSION 6.01    16.10.2026
SDTrimSP - Tue. Mar 03 14:24:43 2026
           1           1   maxnumber history, 1...projectiles + recoil
    i_traj     ihist     iproj    parent     ncoll   species       ibn  termflag
         0         1         1         0        40         2         2         1
         k              x              y              z          ptime         energy
         0 -4.3460094E+00  0.0000000E+00  0.0000000E+00  0.0000000E+00  2.0000000E+03
         1  7.1498933E-01  8.7659069E+00  0.0000000E+00  5.1582553E+00  1.9537590E+03
    i_traj     ihist     iproj    parent     ncoll   species       ibn  termflag
         1         1         1         2         1         1         2         4
         k              x              y              z          ptime         energy
         0  1.9573137E+01  7.6653962E+00 -1.0448797E+01  4.1154052E+02  1.5943743E+00
         1  1.9357998E+01  6.8319993E+00 -1.0315858E+01  4.8311192E+02  0.0000000E+00
 ende
           1   number history from SDTrimSP
"""

LAYER_INP = """! number of    thick-    target composition 2...ncp    name of layer
! layers       ness      qu_2           qu_3
     2  2.50000E+01    1.00000E+00    0.00000E+00    Cu
     4  1.00000E+01    0.00000E+00    1.00000E+00    W
     0            0              0              0      end
"""


def test_read_trajectories(tmp_path):
    path = tmp_path / 'trajec_all.dat'
    path.write_text(TRAJECTORIES_707)
    trajectories = readTrajectoryFile(path)
    assert len(trajectories) == 4
    assert [trajectory['projectile'] for trajectory in trajectories] == [(1, 1), (1, 1), (1, 1), (1, 2)]
    assert [trajectory['recoil'] for trajectory in trajectories] == [False, True, True, False]
    assert [trajectory['generation'] for trajectory in trajectories] == [0, 1, 2, 0]
    assert [trajectory['species'] for trajectory in trajectories] == [1, 0, 0, 1]
    assert trajectories[0]['points'].shape == (3, 4)
    assert np.allclose(trajectories[1]['points'][1], [20.201428, 31.521306, 16.931889, 0.])

    path.write_text(TRAJECTORIES_601)
    trajectories = readTrajectoryFile(path)
    assert [trajectory['recoil'] for trajectory in trajectories] == [False, True]
    # the generation is unknown until 6.06, all recoils are shown as first generation
    assert [trajectory['generation'] for trajectory in trajectories] == [0, 1]
    assert not trajectories[1]['generation_known']

    assert readTrajectoryFile(tmp_path / 'missing.dat') == []


def test_read_layers(tmp_path):
    (tmp_path / 'tri.inp').write_text('&TRI_INP\n    ttarget = 2000.0\n    nqx = 200\n/\n')
    assert readLayers(tmp_path) == [(0., 2000., 'Target')]
    (tmp_path / 'layer.inp').write_text(LAYER_INP)
    assert readLayers(tmp_path) == [(0., 50., 'Cu'), (50., 90., 'W')]


def test_plot_trajectories(main_window, qapp, tmp_path, errors):
    folder = SIMULATION_PROGRAMS / 'SDTrimSP' / 'SDTrimSP_7.07'
    save = tmp_path / 'save'
    save.mkdir()
    (save / 'trajec_all.dat').write_text(TRAJECTORIES_707)
    (save / 'layer.inp').write_text(LAYER_INP)
    sc, page = addSimulationPage(main_window, 'traj', 0, folder, SDTrimSPInput.findBinary(folder) or folder / 'SDTrimSP.exe', Versions.V_707, save)
    pump(qapp)

    analysis = page.evaluation_class.analysis
    analysis.save_folder = save
    emitted = []
    analysis.hlChange.connect(emitted.append)

    data, settings = analysis.plotTrajectories(number=1)
    calls = [call[1] for call in settings.axes.get_calls()]
    # the first layer (the trajectories end before the second one at 50 A), surface, projectile and two recoil generations
    assert calls.count('axhspan') == 1
    assert calls.count('plot') == 3
    labels = data[1]
    assert 'Generation 2' in labels
    pump(qapp)
    assert {'hide_trajectories': False, 'max_trajectories': 2} in emitted

    _, settings = analysis.plotTrajectories(number=5, recoils=False, layers=False, view='z')
    calls = settings.axes.get_calls()
    assert [call[1] for call in calls].count('axhspan') == 0
    plots = [call for call in calls if call[1] == 'plot']
    # only the projectiles, both in one line separated by nan
    assert len(plots) == 1
    assert np.isnan(plots[0][2][0]).sum() == 2

    # the settings in the plot toolbar change the plot
    page.plot_hbox.receive({'hide_trajectories': False, 'max_trajectories': 2})
    assert page.plot_hbox.trajectory_number.maximum() == 2
    assert not page.plot_hbox.layout_trajectory_number.widgets_list[0].isHidden()
    page.plot_hbox.receive({'hide': True})
    assert page.plot_hbox.trajectory_number.isHidden()
    assert not errors, '\n'.join(errors)
