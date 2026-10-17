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
    from Pages.ParameterScan import rangeValues, formatRangeValue, parseValues

    assert rangeValues(0, 80, 5) == pytest.approx([0, 20, 40, 60, 80])
    assert rangeValues(10, 1000, 3, 1) == pytest.approx([10, 100, 1000])
    # ranges from 0 (e.g. angles) are shifted: dense at the start or at the end, but not linear
    dense_start = rangeValues(0, 80, 5, 1)
    dense_end = rangeValues(0, 80, 5, 2)
    assert dense_start[0] == 0 and dense_start[-1] == 80 and dense_start[1] < 20
    assert dense_end[0] == 0 and dense_end[-1] == 80 and dense_end[-2] > 60
    assert dense_end == pytest.approx(80 - dense_start[::-1])
    assert formatRangeValue(632.4555) == '632.5' and formatRangeValue(20000.) == '20000' and formatRangeValue(0.5) == '0.5'
    assert parseValues('1, 2.6; x, 2') == [1., 2.6, 2.] and parseValues('1, 2.6, 3', integer=True) == [1, 3]


def test_parameter_scan_fields(main_window, qapp, tmp_path, errors):
    """Several values in the input fields of the tab: marks, popup, preview and the simulations of the scan"""

    from Pages.ParameterScan import ScanFieldOverlay
    from Pages.CompareDialog import readScanFile

    sc, page = examplePage(main_window, qapp, tmp_path)
    main_window.tab_simulations.setCurrentWidget(page)
    energy = page.table_beam.rows[0].kinetic_energy
    assert not energy.findChildren(ScanFieldOverlay)
    assert page.tab_widget.tabText(2) == 'Run status' and page.tab_widget.tabText(4) == 'Simulation results'

    # the scan marks the fields that can be scanned
    page.action_scan.setChecked(True)
    pump(qapp)
    assert page.tab_widget.tabText(4) == 'Parameter scan results'
    overlay = energy.findChild(ScanFieldOverlay)
    assert overlay is not None and overlay.key == 'energy_Ar' and not overlay.isHidden() and overlay.width() == ScanFieldOverlay.SIZE
    settings = page.settings_group_layout_settings
    assert notNone(settings.fluence.findChild(ScanFieldOverlay)).key == 'fluence'
    assert notNone(settings.histories_total.findChild(ScanFieldOverlay)).key == 'histories'
    assert notNone(page.target_layers.rows[0].element_cells[0].findChild(ScanFieldOverlay)).key == 'fraction_Au'
    parameters = page.scan.parameters()
    for key in ('sbe_Au', 'ed_Au', 'ecut_Ar', 'ebulk_Au', 'thickness', 'projectiles'):
        assert parameters[key].widgets, key
    # further numeric simulation settings are set in their field
    generic = [parameter for parameter in parameters.values() if parameter.apply is None]
    assert generic and all(parameter.widgets for parameter in generic)

    # popup below the field: logarithmic range around the current value
    page.scan.editValues('energy_Ar', energy)
    editor = page.scan.editor
    assert editor is not None and editor.isVisible()
    assert [float(value) for value in editor.values.text().split(',')] == pytest.approx([200, 632.5, 2000, 6325, 20000])
    editor.values.setText('500, 1000')
    editor.close()
    pump(qapp)
    assert page.scan.valuesText('energy_Ar') == '500, 1000' and overlay.width() == energy.width()
    assert 'Values of the parameter scan: 500, 1000' in overlay.toolTip()
    # the field keeps its value
    assert energy.value() == 2000

    # second parameter: surface binding energy of Au in the target table, all combinations
    sbe = page.table_target.rows[0].surface_binding_energy
    page.scan.editValues('sbe_Au', sbe)
    notNone(page.scan.editor).values.setText('3, 4')
    notNone(page.scan.editor).close()
    assert page.scan.count() == 4 and page.run_status_text.text() == 'Ready! (4 simulations)'
    assert sc.unsaved_changes

    # preview of the files of each simulation of the scan
    page.tab_widget.setCurrentIndex(1)
    pump(qapp)
    assert not page.preview_selector_widget.isHidden() and page.preview_selector.count() == 4
    page.preview_selector.setCurrentIndex(1)
    text = page.input_file_preview.toPlainText()
    assert 'e0 = 500.0, 0.0' in text and '4.0' in text.split('e_surfb = ')[1].split('\n')[0]

    # the simulations are written into subfolders of the folder of the simulation
    jobs = page.scan.prepareJobs()
    assert jobs is not None
    assert [job['folder'].name for job in jobs] == ['energy_Ar_500__sbe_Au_3', 'energy_Ar_500__sbe_Au_4',
                                                    'energy_Ar_1000__sbe_Au_3', 'energy_Ar_1000__sbe_Au_4']
    assert all(job['folder'].parent == sc.save_folder for job in jobs)
    text = (jobs[1]['folder'] / 'tri.inp').read_text(encoding='utf-8')
    assert 'e0 = 500.0, 0.0' in text and '4.0' in text.split('e_surfb = ')[1].split('\n')[0]
    scan = readScanFile(sc.save_folder)
    assert scan is not None and scan['energy_Ar_1000__sbe_Au_4'] == {'Energy of Ar [eV]': 1000., 'Surface binding energy of Au [eV]': 4.}

    # a setting that is set in its field: the field keeps its value
    parameter = generic[0]
    widget = parameter.widgets[0]
    value = widget.value()
    arguments = page.scan.arguments([(parameter, value + 3)])
    assert widget.value() == value and vars(arguments.settings) != vars(page.makeArguments().settings)

    # any number of parameters
    for key in ('angle_Ar', 'ed_Au', 'mass_Au', 'ck_Au'):
        assert page.scan.setValues(key, {'values': '1, 2'})

    # values of the parameters
    arguments = page.makeArguments()
    parameters['thickness'].apply(arguments, 500.)
    assert arguments.target_args.thickness == 500.
    assert sum(layer.thickness for layer in arguments.structure) == pytest.approx(500.)
    parameters['histories'].apply(arguments, 7)
    assert arguments.settings.get('histories') == 7
    parameters['ecut_Ar'].apply(arguments, 2.5)
    assert arguments.beam_rows[0].get('cutoff_energy') == 2.5

    # the menu of the scan button lists the scanned parameters (a click removes one), "Reset the scan" removes all values
    page.scan.setValues('angle_Ar', {'values': '0, 30'})
    page.updateScanMenu()
    angle = next(action for action in page.scan_menu.actions() if action.text().startswith('Angle of incidence of Ar'))
    assert angle.text().endswith(': 0, 30')
    angle.trigger()
    assert 'angle_Ar' not in page.scan.values and 'energy_Ar' in page.scan.values
    page.updateScanMenu()
    reset = next(action for action in page.scan_menu.actions() if action.text() == 'Reset the scan')
    assert reset.isEnabled()
    reset.trigger()
    assert not page.scan.values and not page.scan.hasParameters()
    page.scan.setValues('energy_Ar', {'values': '500, 1000'})

    # the selector of the simulation in the files preview is only one line high, the previews get the remaining space
    from PyQt6.QtWidgets import QSizePolicy
    assert page.preview_selector_widget.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed
    layout = page.file_preview_tab_layout
    assert layout.stretch(layout.indexOf(page.file_preview_tab_splitter)) == 1

    # without the scan the fields are shown as usual
    page.scan.setValues('energy_Ar', None)
    assert page.scan.valuesText('energy_Ar') == '' and overlay.width() == ScanFieldOverlay.SIZE
    page.action_scan.setChecked(False)
    assert overlay.isHidden() and page.preview_selector_widget.isHidden() and page.tab_widget.tabText(4) == 'Simulation results'
    assert not errors, '\n'.join(errors)


def test_parameter_scan_state(main_window, qapp, tmp_path, monkeypatch, errors):
    """The scan is stored in the configuration (restart of the GUI) and in scan.json, which opens the scan again"""

    import Pages.ProgramPage as program_page
    from Containers.SimulationConfiguration import SimulationConfiguration
    from Pages.ParameterScan import readScanDescription

    sc, page = examplePage(main_window, qapp, tmp_path)
    page.action_scan.setChecked(True)
    page.scan.setValues('energy_Ar', {'start': 500., 'stop': 1000., 'number': 2, 'scale': 0, 'values': '500, 1000'})
    page.scan.setValues('angle_Ar', {'start': 0., 'stop': 60., 'number': 2, 'scale': 2, 'values': '0, 60'})
    jobs = page.scan.prepareJobs()
    assert jobs is not None and len(jobs) == 4
    # a finished simulation of the scan (the output of an example, the input files of the scan are kept)
    for file in (EXAMPLES / 'example_01_Ar_on_Au').iterdir():
        if file.is_file() and file.name != 'input.json' and file.suffix != '.inp':
            (jobs[0]['folder'] / file.name).write_bytes(file.read_bytes())

    # configuration: enabled scan and its settings
    saved = sc.save()
    assert saved['scan_enabled'] is True
    assert [row['key'] for row in saved['scan']['rows']] == ['energy_Ar', 'angle_Ar']
    loaded = SimulationConfiguration.load(saved)
    assert loaded and loaded.scan_enabled and loaded.scan_state == saved['scan']

    # after a restart the tab shows the scan again
    from Pages.ProgramPage import SimulationPage
    main_window.simulation_configs.append(loaded)
    restored = loaded.tab_widget = main_window.addSimulationTab(SimulationPage(main_window, loaded), 'restored')
    pump(qapp)
    assert restored.action_scan.isChecked() and list(restored.scan.values) == ['energy_Ar', 'angle_Ar']
    assert [job['status'] for job in restored.scan.jobs] == ['finished', 'not run', 'not run', 'not run']

    # scan.json contains the settings of the scan
    description = readScanDescription(sc.save_folder)
    assert description is not None and description['rows'][1]['scale'] == 2 and description['rows'][1]['values'] == '0, 60'

    # another tab opens the scan with its scan.json: parameters, state of the simulations and results
    sc2, page2 = examplePage(main_window, qapp, tmp_path, 'example_07_Ar_on_W_amorphous')
    monkeypatch.setattr(program_page, 'selectFileDialog', lambda *args, **kwargs: sc.save_folder / 'scan.json')
    assert page2.loadSettings(unsaved_warning=False)
    assert page2.action_scan.isChecked() and sc2.save_folder == sc.save_folder
    assert list(page2.scan.values) == ['energy_Ar', 'angle_Ar'] and page2.scan.values['angle_Ar']['scale'] == 2
    assert [job['status'] for job in page2.scan.jobs] == ['finished', 'not run', 'not run', 'not run']
    page2.tab_widget.setCurrentIndex(4)
    pump(qapp)
    assert page2.results_stack.currentWidget() is page2.scan.results
    assert len(notNone(page2.scan.results).entries) == 1
    assert notNone(page2.scan.results).entries[0]['parameters'] == {'Energy of Ar [eV]': 500., 'Angle of incidence of Ar [°]': 0.}

    # run status: the simulations of the scan with their state and output
    page2.tab_widget.setCurrentIndex(2)
    assert page2.scan_runs.rowCount() == 4 and notNone(page2.scan_runs.item(1, 0)).text() == 'not run'
    page2.scan_runs.selectRow(1)
    assert 'not run' in page2.scan_log.toPlainText()

    # output files of a simulation of the scan
    page2.tab_widget.setCurrentIndex(3)
    page2.output_folder_selector.setCurrentIndex(1)
    pump(qapp)
    assert page2.outputFolder() == jobs[0]['folder']
    assert 'output.dat' in [notNone(page2.output_files_list.item(i)).text() for i in range(page2.output_files_list.count())]

    # a simulation of the scan is a simulation on its own
    assert page2.loadSettings(jobs[0]['folder'], unsaved_warning=False)
    assert not page2.action_scan.isChecked() and not page2.scan.values and page2.tab_widget.tabText(4) == 'Simulation results'
    assert page2.table_beam.rows[0].kinetic_energy.value() == 500.

    # scans of older versions only contain the labels of the parameters
    (tmp_path / 'old_scan').mkdir()
    (tmp_path / 'old_scan' / 'scan.json').write_text(
        '{"parameters": ["Energy of Ar [eV]"], "runs": [{"folder": "e_100", "values": [100.0]}, {"folder": "e_200", "values": [200.0]}]}',
        encoding='utf-8'
    )
    page2.scan.setState(notNone(readScanDescription(tmp_path / 'old_scan')))
    assert list(page2.scan.values) == ['energy_Ar'] and page2.scan.valuesText('energy_Ar') == '100, 200'
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
def test_parameter_scan_run(main_window, qapp, tmp_path, monkeypatch, errors):
    from GlobalConf import GlobalConf
    from Pages.ProgramPage import SimulationPage

    sc, page = examplePage(main_window, qapp, tmp_path)
    page.settings_group_layout_settings.histories_total.setValue(4)
    page.action_scan.setChecked(True)
    page.scan.setValues('energy_Ar', {'values': '500, 2000'})
    # the limit of simultaneous simulations includes the simulations of the scans
    monkeypatch.setattr(GlobalConf, 'max_parallel_runs', 1)
    assert page.runSimulation(check_warnings=False, ask_delete=False)
    scan = page.scan
    assert scan.isRunning() and not page.isClosable() and len(scan.running) == 1 and main_window.freeRunSlots() == 0
    assert page.run_status_text.text().startswith('Scan ') and page.action_abort.isEnabled()
    assert pump(qapp, 300, until=lambda: not scan.isRunning())
    assert [job['status'] for job in scan.jobs] == ['finished', 'finished']
    assert all(job['folder'].parent == sc.save_folder for job in scan.jobs)
    assert page.run_status == SimulationPage.RunStatus.DONE and page.isClosable()
    page.tab_widget.setCurrentIndex(4)
    pump(qapp)
    yields = [entry['summary']['Sputter yield [atoms/ion]']['Au'] for entry in notNone(scan.results).entries]
    assert yields[0] < yields[1]
    assert page.scan_runs.rowCount() == 2 and notNone(page.scan_runs.item(0, 0)).text() == 'finished'
    # running the simulation itself keeps the simulations of the scan
    page.action_scan.setChecked(False)
    assert page.runSimulation(check_warnings=False, ask_delete=False)
    assert pump(qapp, 300, until=lambda: page.run_status == SimulationPage.RunStatus.DONE)
    assert (sc.save_folder / 'scan.json').is_file() and all((job['folder'] / 'output.dat').is_file() for job in scan.jobs)
    # a changed input: the status of the last run is replaced by "Ready!"
    page.settings_group_layout_settings.histories_total.setValue(5)
    assert page.run_status == SimulationPage.RunStatus.READY and page.run_status_text.text() == 'Ready!'
    assert not errors, '\n'.join(errors)
