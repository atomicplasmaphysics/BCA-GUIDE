"""Tests of dialogs, the configuration page, themes and the crystal editor (with stubbed file dialogs)"""

import shutil

import pytest

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QGraphicsDropShadowEffect

from conftest import SAVES, SIMULATION_PROGRAMS, DATA, addSimulationPage, copySave, pump

from GlobalConf import GlobalConf
from Containers.SimulationConfiguration import SimulationConfiguration
from Simulations.SDTrimSP import SimulationInput as SDTrimSPInput, Versions


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
    # 7.07 is not listed explicitly, the best suited version is selected without highlighting
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

    sc, page = addSimulationPage(main_window, 'cryst', 0, folder, binary, Versions.V_702, copySave(SAVES / 'SDTrimSP' / 'Ar_on_Au_7.05', tmp_path / 'save'))
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
