"""Tests of dialogs, the configuration page, themes and the crystal editor (with stubbed file dialogs)"""

import shutil

import pytest

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QGraphicsDropShadowEffect

from conftest import SAVES, SIMULATION_PROGRAMS, DATA, addSimulationPage, copySave, pump

from GlobalConf import GlobalConf
from Containers.SimulationConfiguration import SimulationConfiguration
from Simulations.SDTrimSP import SimulationInput as SDTrimSPInput, Versions
from Simulations.SimulationsList import SimulationsList


TRIDYN = SIMULATION_PROGRAMS / 'TRIDYN' / 'Tridyn2022'
SDTRIMSP = SIMULATION_PROGRAMS / 'SDTrimSP'


@pytest.fixture
def dialogs(monkeypatch):
    """Stubbed file dialogs: set answers['dir'] and answers['file'] to the paths that are returned"""

    answers = {'dir': '', 'file': ''}
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', staticmethod(lambda *args, **kwargs: answers['dir']))
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', staticmethod(lambda *args, **kwargs: (answers['file'], '')))
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', staticmethod(lambda *args, **kwargs: (answers['file'], '')))
    return answers


def highlighted(widget) -> bool:
    return isinstance(widget.graphicsEffect(), QGraphicsDropShadowEffect)


@pytest.mark.skipif(not TRIDYN.is_dir(), reason='TRIDYN not available')
def test_program_page_dialogs(main_window, qapp, tmp_path, dialogs, errors):
    source = copySave(SAVES / 'TRIDYN' / 'Ar_on_W', tmp_path / 'src')
    (tmp_path / 'target').mkdir()
    sc, page = addSimulationPage(main_window, 't', 1, TRIDYN, TRIDYN / 'tridyn2022w.exe', '2022')

    dialogs.update(file=str(source / 'input.json'), dir=str(tmp_path / 'target'))
    assert page.importSettings()
    assert sc.save_folder == tmp_path / 'target'
    assert (tmp_path / 'target' / 'input.json').is_file()

    page.resetSettings()
    assert sc.save_folder is None

    dialogs['file'] = ''
    main_window.menuOpen()
    assert sc.save_folder is None

    dialogs['file'] = str(source / 'input.json')
    main_window.menuOpen()
    assert sc.save_folder == source.resolve()
    assert not errors, '\n'.join(errors)


def test_configuration_dialogs(main_window, tmp_path, dialogs, errors):
    page = main_window.simulation_configuration_page

    dialogs['file'] = str(tmp_path / 'config.json')
    page.save()
    assert (tmp_path / 'config.json').is_file()

    dialogs['file'] = ''
    page.save()
    page.open()

    dialogs['dir'] = ''
    assert page.selectSaveFolder() is None
    dialogs['dir'] = str(tmp_path)
    assert page.selectSaveFolder() == tmp_path
    assert not errors, '\n'.join(errors)


@pytest.mark.skipif(not (SDTRIMSP / 'SDTrimSP_7.07').is_dir(), reason='SDTrimSP 7.07 not available')
def test_binary_detection_and_version_highlight(main_window, qapp, dialogs, errors):
    page = main_window.simulation_configuration_page
    pump(qapp)
    page.program.setCurrentIndex(0)

    dialogs['dir'] = str(SDTRIMSP / 'SDTrimSP_7.07')
    page.simulation_folder.select_path_loc()
    assert page.simulation_binary.path == SDTrimSPInput.findBinary(SDTRIMSP / 'SDTrimSP_7.07')
    assert page.versions.currentText() == Versions.V_707
    assert not highlighted(page.versions)

    # 7.06 is not listed explicitly, the best suited version (7.02, 7.05) is selected without highlighting
    page.detected_version_name = 'SDTrimSP v7.06'
    page.selectDetectedVersion()
    assert page.versions.currentText() == Versions.V_702
    assert not highlighted(page.versions)

    page.versions.setCurrentIndex(0)
    assert highlighted(page.versions)

    if TRIDYN.is_dir():
        dialogs['dir'] = str(TRIDYN)
        page.simulation_folder.select_path_loc()
        assert highlighted(page.program)
        page.program.setCurrentIndex(1)
        assert not highlighted(page.program)
    assert not errors, '\n'.join(errors)


def test_reorder_configurations(main_window, qapp, errors):
    if not (SDTRIMSP / 'SDTrimSP_7.00').is_dir():
        pytest.skip('SDTrimSP 7.00 not available')
    folder = SDTRIMSP / 'SDTrimSP_7.00'
    for title in 'ABC':
        sc = SimulationConfiguration(title, 0, folder, folder / 'bin' / 'SDTrimSP.exe', Versions.V_700)
        main_window.simulation_configs.append(sc)
    page = main_window.simulation_configuration_page
    page.listConfigView()
    pump(qapp)

    items = page.simulation_configuration_list
    items.insertItem(1, items.takeItem(3))
    page.configListReordered()
    assert [sc.title for sc in main_window.simulation_configs] == ['C', 'A', 'B']
    assert [main_window.tab_simulations.tabText(i) for i in range(1, 4)] == ['C', 'A', 'B']

    # "Add new configuration" always stays on top
    items.insertItem(0, items.takeItem(2))
    page.configListReordered()
    assert items.item(0).text() == page.new_configuration_text
    assert not errors, '\n'.join(errors)


def test_base_save_folder_follows_preferences(tmp_path):
    folder = SDTRIMSP / 'SDTrimSP_7.00'
    if not folder.is_dir():
        pytest.skip('SDTrimSP 7.00 not available')
    settings = {'title': 'X', 'program': 'SDTrimSP', 'folder': str(folder), 'binary': str(folder / 'bin' / 'Windows.SEQ' / 'SDTrimSP.exe'), 'version': Versions.V_700}
    if not (folder / 'bin' / 'Windows.SEQ' / 'SDTrimSP.exe').is_file():
        settings['binary'] = str(SDTrimSPInput.findBinary(folder))

    automatic = GlobalConf.save_path / 'SDTrimSP'
    automatic.mkdir(parents=True, exist_ok=True)
    sc = SimulationConfiguration.load({**settings, 'base_save_folder': str(automatic)})
    assert sc.base_save_folder is None
    assert sc.getBaseSaveFolder() == automatic

    custom = tmp_path / 'custom'
    custom.mkdir()
    sc = SimulationConfiguration.load({**settings, 'base_save_folder': str(custom)})
    assert sc.getBaseSaveFolder() == custom


def test_theme_switch(main_window, qapp):
    """Switching the theme while running updates widgets with palette dependent colors"""

    from matplotlib.colors import to_hex
    from Utility.Layouts import MplCanvas

    from PyQt6.QtGui import QPalette, QColor

    canvas = MplCanvas(main_window)
    canvas.axes.plot([0, 1], [0, 1])
    canvas.axes.set_xlabel('x')

    def check():
        palette = qapp.palette()
        assert to_hex(canvas.fig.get_facecolor()) == palette.color(QPalette.ColorRole.Window).name()
        assert canvas.axes.xaxis.label.get_color() == palette.color(QPalette.ColorRole.WindowText).name()

    # the offscreen platform has no dark theme, so a dark palette is set directly
    light_palette = QPalette(qapp.palette())
    dark_palette = QPalette(qapp.palette())
    dark_palette.setColor(QPalette.ColorRole.Window, QColor('#202020'))
    dark_palette.setColor(QPalette.ColorRole.WindowText, QColor('#ffffff'))
    for palette in (dark_palette, light_palette):
        qapp.setPalette(palette)
        pump(qapp, 0.3)
        check()

    for theme in ('dark', 'light', 'srim'):
        GlobalConf.theme = theme
        main_window.applyTheme()
        pump(qapp, 0.3)
        check()

    assert main_window.window_title == 'BCA-SRIM'
    GlobalConf.theme = 'system'
    main_window.applyTheme()
    assert main_window.window_title == GlobalConf.title
    assert main_window.styleSheet() == ''


@pytest.mark.skipif(not (SDTRIMSP / 'SDTrimSP_7.05').is_dir(), reason='SDTrimSP 7.05 not available')
def test_crystal_editor_table_mode(main_window, qapp, tmp_path, errors):
    # copy of the simulation folder with its own table.crystal
    folder = tmp_path / 'SDTrimSP_7.05'
    shutil.copytree(SDTRIMSP / 'SDTrimSP_7.05' / 'tables', folder / 'tables')
    binary = SDTrimSPInput.findBinary(SDTRIMSP / 'SDTrimSP_7.05') or folder / 'SDTrimSP.exe'

    sc, page = addSimulationPage(main_window, 'cryst', 0, folder, binary, Versions.V_702, copySave(SAVES / 'SDTrimSP' / 'example_01_Ar_on_Au', tmp_path / 'save'))
    pump(qapp)
    page.general_target_settings.layout_crystal_file.checkbox.setChecked(True)
    dialog = page.crystal_editor_dialog
    assert dialog.table_mode

    # Au is not in the table: create it with the dialog logic
    from TableWidgets.CrystalTableDialog import NewCrystalDialog
    from Utility.CrystalImport import ImportedCrystal
    new = NewCrystalDialog(dialog, dialog.table_file, ['Au', 'Ar'])
    new.applyImported(ImportedCrystal('Au_fcc', (4.078, 4.078, 4.078), positions=[(0, 0, 0), (0, .5, .5), (.5, 0, .5), (.5, .5, 0)], elements=['Au'] * 4))
    assert new.validate()
    new.save()
    assert new.created_crystal.name == 'Au_fcc'
    dialog.loadCrystalTable(select='Au_fcc')
    dialog.elementChanged()
    assert dialog.table_crystal_selected.name == 'Au_fcc'
    assert not dialog.undefined_state

    arguments, input_text, layer_text, crystal_text = page.makePreview()
    assert "name_cryst1 = 'Au_fcc'" in input_text
    assert 'miller_ind1' in input_text
    assert crystal_text is None

    # input.json and tri.inp can be loaded again
    files = page.saveSettings()
    assert files is not None
    assert page.loadSettings(sc.save_folder, from_json=False, unsaved_warning=False)
    assert dialog.table_crystal_selected.name == 'Au_fcc'
    assert page.loadSettings(sc.save_folder, from_json=True, unsaved_warning=False)
    assert dialog.table_crystal_selected.name == 'Au_fcc'
    assert not errors, '\n'.join(errors)


LAYERED_EXAMPLE = SDTRIMSP / 'SDTrimSP_7.05' / 'case' / 'Ar_2_Cu_W_layer_crystal'


def loadLayeredCrystalExample(main_window, qapp, tmp_path):
    """Loads the example with two crystals in layers (Cu_fcc and W_bcc) from tri.inp and layer.inp"""

    folder = SDTRIMSP / 'SDTrimSP_7.05'
    binary = SDTrimSPInput.findBinary(folder) or folder / 'SDTrimSP.exe'
    save = tmp_path / 'layered'
    save.mkdir()
    for file in ('tri.inp', 'layer.inp'):
        shutil.copy(LAYERED_EXAMPLE / file, save / file)

    sc, page = addSimulationPage(main_window, 'layered', 0, folder, binary, Versions.V_702)
    pump(qapp)
    assert page.loadSettings(save, from_json=False, unsaved_warning=False)
    pump(qapp)
    return sc, page


@pytest.mark.skipif(not LAYERED_EXAMPLE.is_dir(), reason='layered crystal example not available')
def test_layered_crystals(main_window, qapp, tmp_path, errors):
    sc, page = loadLayeredCrystalExample(main_window, qapp, tmp_path)
    dialog = page.crystal_editor_dialog
    layers = page.target_layers

    assert [crystal['name'] for crystal in dialog.tableCrystalsList()] == ['Cu_fcc', 'W_bcc']
    assert layers.crystal_names == ['Cu_fcc', 'W_bcc']
    assert len(layers.rows) == 8
    assert [cell.value() for cell in layers.rows[0].crystal_cells] == pytest.approx([1, 0])
    assert [cell.value() for cell in layers.rows[1].crystal_cells] == pytest.approx([0, 1])
    assert [cell.value() for cell in layers.rows[0].miller_cells] == pytest.approx([1, 0, 0.1])
    assert not dialog.undefined_state, dialog.table_crystal_validation.text()

    # mixture of both crystals and amorphous material in the first layer
    layers.rows[0].crystal_cells[0].setValue(0.5)
    layers.rows[0].crystal_cells[1].setValue(0.25)

    arguments, input_text, layer_text, crystal_text = page.makePreview()
    assert 'l_crystal2 = .true.' in input_text
    assert "name_cryst2 = 'W_bcc'" in input_text
    assert 'iq0 = -1' in input_text
    assert layer_text is not None and 'Cu_1' in layer_text and 'W_2' in layer_text
    assert all(line.startswith('!') for line in layer_text.splitlines()[:2])

    # saved files can be loaded again
    files = page.saveSettings()
    assert files is not None and 'layer.inp' in files
    for from_json in (False, True):
        assert page.loadSettings(sc.save_folder, from_json=from_json, unsaved_warning=False)
        pump(qapp)
        assert [cell.value() for cell in page.target_layers.rows[0].crystal_cells] == pytest.approx([0.5, 0.25])

    # fractions larger than 1 are not accepted
    page.target_layers.rows[0].crystal_cells[1].setValue(0.75)
    assert page.simulation_class.checkArguments(page.makeArguments(), sc.version)

    # without crystal the columns are removed
    page.general_target_settings.layout_crystal_file.checkbox.setChecked(False)
    pump(qapp)
    assert page.target_layers.crystal_names == []
    assert not errors, '\n'.join(errors)


DISTRIBUTION_EXAMPLE = SDTRIMSP / 'SDTrimSP_7.07' / 'case' / 'He_Ar_Si_distribution'


@pytest.mark.skipif(not DISTRIBUTION_EXAMPLE.is_dir(), reason='distribution example of SDTrimSP 7.07 not available')
def test_distribution_files(main_window, qapp, tmp_path, monkeypatch, errors):
    """The distributions of the example are loaded, edited in the dialog and written again when saving"""

    from Containers.Arguments import ArgumentValues
    import TableWidgets.DistributionEditor as DistributionEditor

    folder = SDTRIMSP / 'SDTrimSP_7.07'
    binary = SDTrimSPInput.findBinary(folder)
    save = tmp_path / 'save'
    shutil.copytree(DISTRIBUTION_EXAMPLE, save)
    sc, page = addSimulationPage(main_window, 'distr', 0, folder, binary, Versions.V_707)
    assert page.loadSettings(save, from_json=False, unsaved_warning=False)
    pump(qapp)

    beam = page.general_beam_settings
    assert not beam.distribution_button.isHidden()
    assert beam.sheath_potential.isHidden()
    assert set(beam.distributions['energy']) == {'He', 'Ar'}
    assert set(beam.distributions['angle']) == {'He', 'Ar'}

    # the dialog changes the distribution of He
    def accept(dialog):
        dialog.energy_tables['He'].setRows([[100., 1.], [300., 2.]])
        dialog.accept()
        return 1
    monkeypatch.setattr(DistributionEditor.DistributionDialog, 'exec', lambda dialog: accept(dialog))
    beam.editDistributions()
    assert beam.distributions['energy']['He'] == [[100., 1.], [300., 2.]]

    # saving keeps the order of the species of the loaded tri.inp (He, Ar, Si) and writes the files with their number
    files = page.saveSettings()
    assert '"He", "Ar", "Si"' in (save / 'tri.inp').read_text()
    assert files and {'energy.inp', 'energy02.inp', 'angle.inp', 'angle02.inp'} <= set(files)
    assert DistributionEditor.readDistributionFile(save / 'energy.inp') == [[100., 1.], [300., 2.]]
    assert (save / 'energy.inp').read_text().startswith('!')

    # with grouped elements the target species are first (Si, He, Ar)
    page.settings_group_layout_settings.layout_group_elements.checkbox.setChecked(True)
    files = page.saveSettings()
    assert '"Si", "He", "Ar"' in (save / 'tri.inp').read_text()
    assert files and {'energy02.inp', 'energy03.inp', 'angle02.inp', 'angle03.inp'} <= set(files)
    assert DistributionEditor.readDistributionFile(save / 'energy02.inp') == [[100., 1.], [300., 2.]]

    # Maxwellian distributions show the sheath potential, constant energies hide the button
    beam.kinetic_energy.setValue(ArgumentValues.KineticEnergy.MAXWELLIAN_ENERGY_DISTRIBUTION, from_entries_save=True)
    pump(qapp)
    assert not beam.sheath_potential.isHidden()
    beam.kinetic_energy.setValue(ArgumentValues.KineticEnergy.FIXED, from_entries_save=True)
    beam.angle.setValue(ArgumentValues.Angle.FIXED, from_entries_save=True)
    pump(qapp)
    assert beam.distribution_button.isHidden()
    assert not errors, '\n'.join(errors)


def test_search_simulations(main_window, qapp, tmp_path, dialogs, errors):
    """The search adds all installations below the selected folder once, with versions and binaries"""

    if not any(SDTRIMSP.glob('SDTrimSP_*')):
        pytest.skip('no SDTrimSP installation available')
    page = main_window.simulation_configuration_page

    dialogs['dir'] = ''
    assert page.searchSimulations() == 0

    dialogs['dir'] = str(SIMULATION_PROGRAMS)
    added = page.searchSimulations()
    assert added == len(main_window.simulation_configs) > 0
    for sc in main_window.simulation_configs:
        assert sc.binary.is_file() and sc.binary.is_relative_to(sc.folder)
        assert sc.version in SimulationsList().simulation_program_versions[sc.program_name]
    titles = [sc.title for sc in main_window.simulation_configs]
    if (SDTRIMSP / 'SDTrimSP_7.07').is_dir():
        sc = main_window.simulation_configs[titles.index('SDTrimSP 7.07')]
        assert sc.version == Versions.V_707
    if (SDTRIMSP / 'SDTrimSP_7.05').is_dir():
        assert main_window.simulation_configs[titles.index('SDTrimSP 7.05')].version == Versions.V_702
    # installations without a binary for this operating system are not added
    assert 'SDTrimSP 6.09' not in titles

    # a second search does not add the same installations again
    assert page.searchSimulations() == 0
    assert len(main_window.simulation_configs) == added
    assert not errors, '\n'.join(errors)


@pytest.mark.skipif(not (SDTRIMSP / 'SDTrimSP_7.07').is_dir(), reason='SDTrimSP 7.07 not available')
def test_composition_table_columns(main_window, qapp, errors):
    """Delete button, index and element stay visible when the composition tables are scrolled horizontally"""

    folder = SDTRIMSP / 'SDTrimSP_7.07'
    sc, page = addSimulationPage(main_window, 'cols', 0, folder, SDTrimSPInput.findBinary(folder), Versions.V_707)
    main_window.resize(900, 800)
    main_window.show()
    main_window.tab_simulations.setCurrentWidget(page)
    page.tab_widget.setCurrentIndex(0)
    pump(qapp)
    for table in (page.table_beam, page.table_target):
        table.addRow()
        pump(qapp)
        labels = [table.horizontalHeaderItem(column).text() for column in range(table.columnCount())]
        assert labels[1:3] == ['#', 'Element']
        # the energies of the elements are next to each other
        energies = [i for i, label in enumerate(labels) if 'energy' in label.lower() and not label.startswith('Kin.')]
        assert energies == list(range(energies[0], energies[0] + len(energies)))

        row = table.rows[-1]
        assert table.frozen.cellWidget(table.rowCount() - 2, 2) is row.selected_element
        assert table.cellWidget(table.rowCount() - 2, 2) is row.selected_element
        bar = table.horizontalScrollBar()
        bar.setValue(bar.maximum())
        pump(qapp)
        assert table.frozen.isVisible() and bar.value() > 0
        assert table.frozen.geometry().width() == sum(table.columnWidth(column) for column in range(3))
        assert row.selected_element.isVisible()

    labels = [page.table_beam.horizontalHeaderItem(column).text() for column in range(page.table_beam.columnCount())]
    assert labels[3:6] == ['Abundance', 'Kin. energy [eV]', 'Angle [°]']
    assert labels[-3:] == ['Azimuth [°]', 'Start depth [Å]', 'Charge']

    # removing a row removes it in both tables
    rows = page.table_beam.rowCount()
    page.table_beam.rows[-1].remove.click()
    pump(qapp)
    assert page.table_beam.rowCount() == page.table_beam.frozen.rowCount() == rows - 1
    assert not errors, '\n'.join(errors)


def test_crystal_preview_not_clipped(qapp):
    """Lines and atoms of the crystal preview are not clipped to the square 3D axes (only the texts were visible outside)"""

    from Utility.Layouts import CrystalPreview
    preview = CrystalPreview(None, show_beam=True, show_basis_vecs=True, show_surface=True, disable_interaction=False)
    assert preview.axes.get_children()
    assert all(not artist.get_clip_on() for artist in preview.axes.get_children())
    preview.updateParams(show_coordinate_system=True)
    assert all(not artist.get_clip_on() for artist in preview.axes.get_children())
