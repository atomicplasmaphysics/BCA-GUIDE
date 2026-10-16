"""Parameter scans of a simulation tab and the comparison of several simulations"""

import csv

import pytest

from conftest import SAVES, SIMULATION_PROGRAMS, addSimulationPage, copySave, pump

from Simulations.SDTrimSP import SimulationInput, SimulationAnalysis, Versions


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


def test_parameter_scan_input_files(main_window, qapp, tmp_path, errors):
    from Pages.ParameterScanDialog import ParameterScanDialog

    sc, page = examplePage(main_window, qapp, tmp_path)
    dialog = ParameterScanDialog(page)
    texts = [dialog.parameter.itemText(i) for i in range(dialog.parameter.count())]
    assert texts[:2] == ['Energy of Ar [eV]', 'Angle of incidence of Ar [°]']
    assert 'Target thickness [Å]' in texts and 'Number of histories' in texts

    # energy: logarithmic range around the current value
    assert dialog.scanValues() == pytest.approx([200, 632.456, 2000, 6324.56, 20000], rel=1e-5)
    dialog.values.setText('500, 1000')
    dialog.folder.setText(str(tmp_path / 'scan'))
    jobs = dialog.prepareJobs()
    assert [job['folder'].name for job in jobs] == ['energy_500', 'energy_1000']
    for job, energy in zip(jobs, ('500.0', '1000.0')):
        text = (job['folder'] / 'tri.inp').read_text(encoding='utf-8')
        assert f'e0 = {energy}, 0.0' in text
        assert (job['folder'] / 'input.json').is_file()

    # angle and thickness (the layers keep their relative thickness)
    dialog.parameter.setCurrentIndex(texts.index('Angle of incidence of Ar [°]'))
    assert dialog.scanValues() == pytest.approx([0, 10, 20, 30, 40, 50, 60, 70, 80])
    arguments = page.makeArguments()
    ParameterScanDialog.applyValue(arguments, 'thickness', None, 500.)
    assert arguments.target_args.thickness == 500.
    assert sum(layer.thickness for layer in arguments.structure) == pytest.approx(500.)
    ParameterScanDialog.applyValue(arguments, 'histories', None, 7)
    assert arguments.settings.get('histories') == 7
    assert not errors, '\n'.join(errors)


@pytest.mark.simulation
def test_parameter_scan_run(main_window, qapp, tmp_path, errors):
    from Pages.ParameterScanDialog import ParameterScanDialog

    sc, page = examplePage(main_window, qapp, tmp_path)
    page.settings_group_layout_settings.histories_total.setValue(4)
    dialog = ParameterScanDialog(page)
    dialog.values.setText('500, 2000')
    dialog.folder.setText(str(tmp_path / 'scan'))
    dialog.run()
    assert pump(qapp, 300, until=lambda: not dialog.running and not dialog.queue)
    assert [job['status'] for job in dialog.jobs] == ['finished', 'finished']
    assert dialog.button_compare.isEnabled()
    dialog.openComparison()
    comparison = dialog.compare_dialog
    assert comparison is not None
    yields = [entry['summary']['Sputter yield [atoms/ion]']['Au'] for entry in comparison.entries]
    assert yields[0] < yields[1]
    comparison.close()
    dialog.close()
    assert not errors, '\n'.join(errors)
