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
    # points: x, y, z, energy, absolute time
    assert trajectories[0]['points'].shape == (3, 5)
    assert np.allclose(trajectories[1]['points'][1, :4], [20.201428, 31.521306, 16.931889, 0.])

    # the time of the recoils starts at 0 since 6.09, it is shifted by the time of the nearest point of the previous generation
    assert np.allclose(trajectories[1]['points'][:, 4], [1.7863705, 1.7863705 + 74.664916])
    assert np.allclose(trajectories[2]['points'][:, 4], [76.4512865, 76.4512865 + 74.664916])

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

    data, settings = analysis.plotTrajectories(projectile=1)
    calls = [call[1] for call in settings.axes.get_calls()]
    # the first layer (the trajectories end before the second one at 50 A), surface, one line per species and generation
    assert calls.count('axhspan') == 1
    assert calls.count('plot') == 3
    # colorbar of the recoil generations
    assert len(settings.colorbars) == 1 and settings.colorbars[0][1]['label'] == 'Recoil generation'
    legend = next(call for call in settings.axes.get_calls() if call[1] == 'legend')
    assert [handle.get_label() for handle in legend[3]['handles']] == ['Species 2 projectile', 'Species 1 recoils', 'Cu']
    columns, labels = data
    assert labels[:4] == ['Trajectory', 'Generation', 'Species', 'Recoil']
    assert all(len(column) == 7 for column in columns)
    pump(qapp)
    assert {'hide_trajectories': False, 'max_trajectories': 2} in emitted

    # only the second projectile, without recoils and layers
    data, settings = analysis.plotTrajectories(projectile=2, recoils=False, layers=False, view='z')
    calls = settings.axes.get_calls()
    assert [call[1] for call in calls].count('axhspan') == 0
    assert [call[1] for call in calls].count('plot') == 1
    assert not settings.colorbars
    assert all(len(column) == 2 for column in data[0])

    # both lateral directions, top view and 3D
    _, settings = analysis.plotTrajectories(view='both')
    assert len(settings.extra_axes) == 1 and settings.colorbars[0][2] == 1
    _, settings = analysis.plotTrajectories(view='top')
    assert [call[1] for call in settings.axes.get_calls()].count('axhspan') == 0
    _, settings = analysis.plotTrajectories(view='3d', color='energy')
    assert settings.fig.get_calls()[0][3] == {'projection': '3d'}
    assert [call[1] for call in settings.axes.get_calls()].count('add_collection3d') >= 1
    assert settings.colorbars[0][1]['label'] == 'Energy [eV]'

    # animation: at the start only the beginning of the projectile is shown, at the end everything
    data, settings = analysis.plotTrajectories(time_fraction=0.)
    assert len(data[0][0]) == 2
    data, settings = analysis.plotTrajectories(time_fraction=0.5)
    assert 0 < len(data[0][0]) < 7
    assert any(call[1] == 'scatter' for call in settings.axes.get_calls())

    # all plots can be drawn
    for view in ('y', 'z', 'both', 'top', '3d'):
        for color in ('species', 'energy', 'time'):
            _, settings = analysis.plotTrajectories(view=view, color=color, time_fraction=0.7)
            settings.apply(page.output_plot_view)

    # the settings in the plot toolbar change the plot
    page.plot_hbox.receive({'hide_trajectories': False, 'max_trajectories': 2})
    assert page.plot_hbox.trajectory_number.maximum() == 2
    assert not page.plot_hbox.layout_trajectory_number.widgets_list[0].isHidden()
    page.plot_hbox.trajectory_view.setCurrentIndex(4)
    page.plot_hbox.trajectory_time.setValue(100)
    assert page.evaluation_class.trajectory_args['view'] == '3d'
    assert page.evaluation_class.trajectory_args['time_fraction'] == 0.5
    page.plot_hbox.trajectory_play.setChecked(True)
    pump(qapp, 0.5)
    page.plot_hbox.trajectory_play.setChecked(False)
    assert page.plot_hbox.trajectory_time.value() > 100
    page.plot_hbox.receive({'hide': True})
    assert page.plot_hbox.trajectory_number.isHidden()

    # animation as GIF, saved in the background (the GUI stays usable)
    evaluation = page.evaluation_class
    path = evaluation.saveTrajectoryAnimation(page.plot_hbox.trajectoryArguments(animation=False), path=tmp_path / 'cascade.gif', frames=5)
    export = evaluation.animation_export
    assert path is not None and export is not None
    progress, finished = [], []
    export.progress.connect(lambda frame, number: progress.append((frame, number)))
    export.finished.connect(lambda saved, error: finished.append((saved, error)))
    # a second export waits until the first one is finished
    if export.isRunning():
        assert evaluation.saveTrajectoryAnimation(page.plot_hbox.trajectoryArguments(animation=False), path=tmp_path / 'second.gif') is None
    export.wait(60)
    pump(qapp, 0.2)
    assert finished == [(str(path), '')]
    assert not progress or progress[-1] == (6, 6)
    from PIL import Image
    with Image.open(path) as image:
        assert image.n_frames == 6
    assert 'Animation saved as' in main_window.statusBar().currentMessage()

    # 3D view
    path_3d = evaluation.saveTrajectoryAnimation(dict(page.plot_hbox.trajectoryArguments(animation=False), view='3d'), path=tmp_path / 'cascade_3d.gif', frames=3)
    assert path_3d is not None and evaluation.animation_export is not None
    evaluation.animation_export.wait(60)
    pump(qapp, 0.2)
    with Image.open(path_3d) as image:
        assert image.n_frames == 4
    assert not errors, '\n'.join(errors)
