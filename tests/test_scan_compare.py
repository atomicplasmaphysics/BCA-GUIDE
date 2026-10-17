"""Parameter scans of a simulation tab and the comparison of several simulations"""

import csv

import numpy as np

import pytest

from conftest import SAVES, SIMULATION_PROGRAMS, addSimulationPage, copySave, pump

from Simulations.SDTrimSP import SimulationInput, SimulationAnalysis, Versions

from Utility.Typing import notNone


FOLDER = SIMULATION_PROGRAMS / 'SDTrimSP' / 'SDTrimSP_7.07'
EXAMPLES = SAVES / 'SDTrimSP'
pytestmark = pytest.mark.skipif(not (FOLDER / 'tables').is_dir() or not (EXAMPLES / 'example_01_Ar_on_Au').is_dir(),
                                reason='SDTrimSP 7.07 or the examples not available')


def examplePage(main_window, qapp, tmp_path, example: str = 'example_01_Ar_on_Au'):
    save = copySave(EXAMPLES / example, tmp_path / example)
    sc, page = addSimulationPage(main_window, example, 0, FOLDER, SimulationInput.findBinary(FOLDER) or FOLDER / 'SDTrimSP.exe', Versions.V_707, save)
    pump(qapp)
    return sc, page


def test_summary_of_examples(qapp):
    simulation = SimulationInput()
    simulation.updateElements(FOLDER, Versions.V_707)
    analysis = SimulationAnalysis(simulation.element_data)
    assert analysis.loadFolder(EXAMPLES / 'example_01_Ar_on_Au')
    summary = analysis.summary()
    assert summary['Sputter yield [atoms/ion]']['Au'] > 0
    assert 0 < summary['Reflection coefficient']['Ar'] < 1
    assert summary['Mean implantation depth [Å]']['Ar'] > 0

    # dynamic: values at the end of the fluence
    assert analysis.loadFolder(EXAMPLES / 'example_02_D_on_W_dynamic')
    summary = analysis.summary()
    assert summary['Fluence [10^20 ions/m²]']['total'] > 0
    assert 'W' in summary['Sputter yield [atoms/ion]']

    assert not analysis.loadFolder(EXAMPLES)


def test_compare_dialog(main_window, qapp, tmp_path, monkeypatch, errors):
    from Pages.CompareDialog import CompareDialog
    import Pages.CompareDialog as compare_module

    sc, page = examplePage(main_window, qapp, tmp_path)
    folders = [EXAMPLES / 'example_06_Ar_on_W_crystal', EXAMPLES / 'example_07_Ar_on_W_amorphous', EXAMPLES / 'example_01_Ar_on_Au', EXAMPLES]
    dialog = CompareDialog(main_window, type(page.evaluation_class.analysis), page.simulation_class.element_data, folders)
    pump(qapp)
    # the folder without output is skipped
    assert [entry['label'] for entry in dialog.entries] == ['example_06_Ar_on_W_crystal', 'example_07_Ar_on_W_amorphous', 'example_01_Ar_on_Au']
    assert 'No output found' in dialog.status.text()
    assert dialog.table.rowCount() == 3

    # summary: bars of the simulations (no numbers for the x axis)
    dialog.select('summary', 'Sputter yield [atoms/ion]')
    pump(qapp)
    labels, columns = dialog.data
    assert labels[0] == 'Simulation' and len(columns[0]) == 3
    assert 'Sputter yield [atoms/ion] (W)' in labels and 'Sputter yield [atoms/ion] (Au)' in labels

    # the same plot of all simulations
    dialog.select('plot', 'plotImplantationDepth')
    pump(qapp)
    labels, columns = dialog.data
    assert any(label.startswith('example_06_Ar_on_W_crystal: ') for label in labels)
    assert any(label.startswith('example_01_Ar_on_Au: ') for label in labels)
    for function in type(page.evaluation_class.analysis).ComparablePlots:
        dialog.select('plot', function)
        pump(qapp, 0.05)

    # only checked simulations are compared
    from PyQt6.QtCore import Qt
    dialog.list.item(2).setCheckState(Qt.CheckState.Unchecked)
    dialog.select('plot', 'plotImplantationDepth')
    pump(qapp)
    assert not any(label.startswith('example_01_Ar_on_Au: ') for label in dialog.data[0])

    # export
    path = tmp_path / 'comparison.csv'
    monkeypatch.setattr(compare_module, 'selectFileDialog', lambda *args, **kwargs: path)
    dialog.exportData()
    with open(path, encoding='utf-8') as file:
        rows = list(csv.reader(file))
    assert rows[0] == dialog.data[0]

    # numbers in folder names as x axis
    dialog.removeSelected()
    dialog.list.setCurrentRow(0)
    dialog.removeSelected()
    assert len(dialog.entries) == 2
    assert not errors, '\n'.join(errors)


def test_range_values():
    from Pages.ParameterScanPage import rangeValues, formatRangeValue

    assert rangeValues(0, 80, 5) == pytest.approx([0, 20, 40, 60, 80])
    assert rangeValues(10, 1000, 3, 1) == pytest.approx([10, 100, 1000])
    # ranges from 0 (e.g. angles) are shifted: dense at the start or at the end, but not linear
    dense_start = rangeValues(0, 80, 5, 1)
    dense_end = rangeValues(0, 80, 5, 2)
    assert dense_start[0] == 0 and dense_start[-1] == 80 and dense_start[1] < 20
    assert dense_end[0] == 0 and dense_end[-1] == 80 and dense_end[-2] > 60
    assert dense_end == pytest.approx(80 - dense_start[::-1])
    assert formatRangeValue(632.4555) == '632.5' and formatRangeValue(20000.) == '20000' and formatRangeValue(0.5) == '0.5'


def test_parameter_scan_input_files(main_window, qapp, tmp_path, errors):
    from Pages.ParameterScanPage import scanParameters
    from Pages.CompareDialog import readScanFile

    sc, page = examplePage(main_window, qapp, tmp_path)
    main_window.tab_simulations.setCurrentWidget(page)
    # the scan is shown in the tabs of the simulation (checkbox in the toolbar)
    assert page.scan_page is None and not page.scan_checkbox.isChecked()
    main_window.openParameterScan()
    dialog = page.scan_page
    assert dialog is not None and page.scan_checkbox.isChecked() and page.tab_widget.currentWidget() is dialog
    assert page.tab_widget.isTabVisible(page.tab_widget.indexOf(dialog.results))
    # default folder of the scan: in the folder of the simulation
    assert dialog.folder.text() == str(sc.save_folder / 'scan_energy_Ar')
    row = dialog.rows[0]
    texts = [row.parameter.itemText(i) for i in range(row.parameter.count())]
    assert texts[:2] == ['Energy of Ar [eV]', 'Angle of incidence of Ar [°]']
    for text in ('Surface binding energy of Au [eV]', 'Displacement energy of Au [eV]', 'Cutoff energy of Ar [eV]',
                 'Bulk binding energy of Au [eV]', 'Atomic fraction of Au in the target (first layer)', 'Target thickness [Å]',
                 'Number of histories (nh)', 'Projectiles per history (nr_pproj)'):
        assert text in texts

    # energy: logarithmic range around the current value
    assert row.scanValues() == pytest.approx([200, 632.456, 2000, 6324.56, 20000], rel=1e-3)
    row.values.setText('500, 1000')

    # second parameter: surface binding energy of Au, all combinations
    second = dialog.addParameterRow('sbe_Au')
    second.values.setText('3, 4')
    assert dialog.count.text() == '4 simulations'
    dialog.folder.setText(str(tmp_path / 'scan'))
    jobs = dialog.prepareJobs()
    assert [job['folder'].name for job in jobs] == ['energy_Ar_500__sbe_Au_3', 'energy_Ar_500__sbe_Au_4',
                                                    'energy_Ar_1000__sbe_Au_3', 'energy_Ar_1000__sbe_Au_4']
    text = (jobs[1]['folder'] / 'tri.inp').read_text(encoding='utf-8')
    assert 'e0 = 500.0, 0.0' in text and 'e_surfb = ' in text and '4.0' in text.split('e_surfb = ')[1].split('\n')[0]
    scan = readScanFile(tmp_path / 'scan')
    assert scan['energy_Ar_1000__sbe_Au_4'] == {'Energy of Ar [eV]': 1000., 'Surface binding energy of Au [eV]': 4.}

    # at most 5 parameters
    for _ in range(5):
        dialog.addParameterRow()
    assert len(dialog.rows) == 5 and not dialog.button_add.isEnabled()

    # values of the parameters
    parameters = {parameter.key: parameter for parameter in scanParameters(page.makeArguments(), 'SDTrimSP')}
    arguments = page.makeArguments()
    parameters['thickness'].apply(arguments, 500.)
    assert arguments.target_args.thickness == 500.
    assert sum(layer.thickness for layer in arguments.structure) == pytest.approx(500.)
    parameters['histories'].apply(arguments, 7)
    assert arguments.settings.get('histories') == 7
    parameters['ecut_Ar'].apply(arguments, 2.5)
    assert arguments.beam_rows[0].get('cutoff_energy') == 2.5

    # the tabs of the scan are hidden (the scan does not run)
    page.scan_checkbox.setChecked(False)
    assert not page.tab_widget.isTabVisible(page.tab_widget.indexOf(dialog))
    assert not errors, '\n'.join(errors)


def test_parameter_scan_state(main_window, qapp, tmp_path, errors):
    """The scan is stored in the configuration (restart of the GUI) and can be opened from its folder"""

    from Containers.SimulationConfiguration import SimulationConfiguration
    from Pages.ParameterScanPage import readScanDescription

    sc, page = examplePage(main_window, qapp, tmp_path)
    page.openParameterScan()
    scan_page = page.scan_page
    scan_page.rows[0].values.setText('500, 1000')
    second = scan_page.addParameterRow('angle_Ar')
    second.scale.setCurrentIndex(2)
    second.values.setText('0, 60')
    scan_page.folder.setText(str(tmp_path / 'scan'))
    jobs = scan_page.prepareJobs()
    assert len(jobs) == 4
    # a finished simulation of the scan (the output of an example)
    for file in (EXAMPLES / 'example_01_Ar_on_Au').iterdir():
        if file.is_file():
            (jobs[0]['folder'] / file.name).write_bytes(file.read_bytes())

    # configuration: enabled tabs and the settings of the scan
    saved = sc.save()
    assert saved['scan_enabled'] is True and saved['scan']['folder'] == str(tmp_path / 'scan')
    assert [row['key'] for row in saved['scan']['rows']] == ['energy_Ar', 'angle_Ar']
    loaded = SimulationConfiguration.load(saved)
    assert loaded and loaded.scan_enabled and loaded.scan_state == saved['scan']

    # after a restart the tab shows the scan again
    from Pages.ProgramPage import SimulationPage
    main_window.simulation_configs.append(loaded)
    restored = loaded.tab_widget = main_window.addSimulationTab(SimulationPage(main_window, loaded), 'restored')
    pump(qapp)
    assert restored.scan_checkbox.isChecked() and restored.scan_page is not None
    assert [row.key() for row in restored.scan_page.rows] == ['energy_Ar', 'angle_Ar'] and len(restored.scan_page.jobs) == 4

    # scan.json contains the settings of the scan
    description = readScanDescription(tmp_path / 'scan')
    assert description is not None and description['rows'][1]['scale'] == 2 and description['rows'][1]['values'] == '0, 60'

    # another tab opens the scan from its folder: parameters, state of the simulations and results
    sc2, page2 = examplePage(main_window, qapp, tmp_path, 'example_07_Ar_on_W_amorphous')
    page2.openParameterScan()
    assert page2.scan_page.openScan(tmp_path / 'scan')
    assert [row.key() for row in page2.scan_page.rows] == ['energy_Ar', 'angle_Ar']
    assert page2.scan_page.rows[1].values.text() == '0, 60' and page2.scan_page.rows[1].scale.currentIndex() == 2
    assert [job['status'] for job in page2.scan_page.jobs] == ['finished', 'not run', 'not run', 'not run']
    assert page2.tab_widget.currentWidget() is page2.scan_page.results
    pump(qapp)
    assert len(page2.scan_page.results.entries) == 1
    assert page2.scan_page.results.entries[0]['parameters'] == {'Energy of Ar [eV]': 500., 'Angle of incidence of Ar [°]': 0.}

    # scans of older versions only contain the labels of the parameters
    (tmp_path / 'old_scan').mkdir()
    (tmp_path / 'old_scan' / 'scan.json').write_text(
        '{"parameters": ["Energy of Ar [eV]"], "runs": [{"folder": "e_100", "values": [100.0]}, {"folder": "e_200", "values": [200.0]}]}',
        encoding='utf-8'
    )
    assert page2.scan_page.openScan(tmp_path / 'old_scan')
    assert [row.key() for row in page2.scan_page.rows] == ['energy_Ar'] and page2.scan_page.rows[0].values.text() == '100, 200'
    assert not errors, '\n'.join(errors)


def test_compare_parameters(main_window, qapp, tmp_path, errors):
    """Lines over a parameter and 2D maps over two parameters of a scan"""

    from Pages.CompareDialog import CompareDialog, ALL_VALUES

    sc, page = examplePage(main_window, qapp, tmp_path)
    folders = [EXAMPLES / 'example_06_Ar_on_W_crystal', EXAMPLES / 'example_07_Ar_on_W_amorphous', EXAMPLES / 'example_01_Ar_on_Au']
    parameters = [{'a': 1., 'b': 10.}, {'a': 2., 'b': 10.}, {'a': 1., 'b': 20.}]
    dialog = CompareDialog(main_window, type(page.evaluation_class.analysis), page.simulation_class.element_data, folders, parameters=parameters)
    pump(qapp)
    dialog.select('summary', 'Reflection coefficient')
    assert dialog.x_parameter.currentText() == 'a'
    assert dialog.filters['b'].currentText() == ALL_VALUES
    labels, columns = dialog.data
    # one line per value of b
    assert len(labels) == 4
    dialog.plot_type.setCurrentIndex(1)
    pump(qapp)
    dialog.y_parameter.setCurrentIndex(dialog.y_parameter.findText('b'))
    pump(qapp)
    labels, columns = dialog.data
    assert labels == ['a', 'b', 'Reflection coefficient (Ar)'] and len(columns[2]) == 4
    assert np.isnan(columns[2]).sum() == 1
    assert not errors, '\n'.join(errors)


@pytest.mark.simulation
def test_parameter_scan_run(main_window, qapp, tmp_path, errors):
    sc, page = examplePage(main_window, qapp, tmp_path)
    page.settings_group_layout_settings.histories_total.setValue(4)
    page.openParameterScan()
    dialog = page.scan_page
    assert dialog is not None
    dialog.rows[0].values.setText('500, 2000')
    dialog.run()
    # the simulation tab can not be closed while the scan runs
    assert dialog.isRunning() and not page.isClosable()
    assert 'Parameter scan ⧖' in page.tab_widget.tabText(page.tab_widget.indexOf(dialog))
    assert pump(qapp, 300, until=lambda: not dialog.running and not dialog.queue)
    assert [job['status'] for job in dialog.jobs] == ['finished', 'finished']
    assert all(job['folder'].parent == sc.save_folder / 'scan_energy_Ar' for job in dialog.jobs)
    assert dialog.button_results.isEnabled() and not dialog.isRunning()
    dialog.button_results.click()
    pump(qapp)
    assert page.tab_widget.currentWidget() is dialog.results
    yields = [entry['summary']['Sputter yield [atoms/ion]']['Au'] for entry in dialog.results.entries]
    assert yields[0] < yields[1]
    assert dialog.runs.rowCount() == 2 and notNone(dialog.runs.item(0, 0)).text() == 'finished'
    # running the simulation itself keeps the folder of the scan
    page.saveSettings()
    assert (sc.save_folder / 'scan_energy_Ar' / 'scan.json').is_file()
    assert not errors, '\n'.join(errors)
