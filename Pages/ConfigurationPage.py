from __future__ import annotations
from typing import Optional, Tuple, List, TYPE_CHECKING
from platform import system
from pathlib import Path
from re import findall
from json import dump, load
from json.decoder import JSONDecodeError
import logging

from PyQt6.QtCore import Qt, QTimer, QDir
from PyQt6.QtGui import QKeySequence, QPixmap
from PyQt6.QtWidgets import (
    QSplitter, QWidget, QPushButton, QListWidget, QLabel, QListWidgetItem,
    QVBoxLayout, QGroupBox, QHBoxLayout, QMessageBox, QFileDialog, QSizePolicy, QAbstractItemView, QApplication
)

from Utility.GlobalConf import GlobalConf
from Utility.Styles import Styles

from Utility.Layouts import TabWithToolbar, VBoxTitleLayout, InputHBoxLayout, LineEdit, FilePath, ComboBox
from Utility.Dialogs import showMessageBox, selectFileDialog
from Utility.Functions import pathToStr, bestVersion
from Utility.ModifyWidget import setWidgetHighlight
from Utility.Icons import getIcon
from Utility.Typing import notNone

from Pages.ProgramPage import SimulationPage

from Containers.SimulationConfiguration import SimulationConfiguration

from Simulations.SimulationsList import SimulationsList

# avoiding circular import, but still get type hinting functionality
if TYPE_CHECKING:
    from Pages.MainWindow import MainWindow


# folders that are not searched for installed simulations
SEARCH_SKIP_FOLDERS = {'__pycache__', 'node_modules', 'site-packages', '$recycle.bin', 'system volume information', 'windows', 'appdata'}


def searchInstallations(base_folder: Path, max_depth: int = 6) -> Tuple[List[dict], List[str]]:
    """
    Searches base_folder and its subfolders for installed simulation programs.
    A folder is an installation if a simulation program detects its version there and finds a binary for this
    operating system. Subfolders of an installation are not searched.

    :param base_folder: folder to search in
    :param max_depth: (optional) maximum depth of subfolders

    :return: (list of {'program': index, 'name': program name, 'version': selectable version, 'version_name': detected version,
              'folder': folder, 'binary': binary}, list of skipped installations with reasons)
    """

    simulation_list = SimulationsList()
    found = []
    skipped = []

    def detect(folder: Path) -> bool:
        """Returns True if folder is (a not usable) installation"""

        for index, program in enumerate(simulation_list.simulation_program_list):
            version_name = program.getVersionName(folder, None)
            if not version_name:
                continue
            versions = simulation_list.simulation_program_versions.get(program.Name) or []
            version_index, exact = bestVersion(versions, version_name)
            numbers = findall(r'\d+(?:\.\d+)?', version_name)
            supported = version_index >= 0 and (exact or not numbers or float(numbers[0]) >= min(
                float(version.strip()) for entry in versions for version in entry.split(',')
            ))
            if not supported:
                skipped.append(f'{version_name} in "{pathToStr(folder)}": version is not supported')
                return True
            binary = program.findBinary(folder)
            if binary is None:
                skipped.append(f'{version_name} in "{pathToStr(folder)}": no binary for this operating system found')
                return True
            found.append({
                'program': index,
                'name': program.Name,
                'version': versions[version_index] if versions else 'All',
                'version_name': version_name,
                'folder': folder,
                'binary': binary
            })
            return True
        return False

    def search(folder: Path, depth: int):
        if detect(folder) or depth >= max_depth:
            return
        try:
            subfolders = sorted(entry for entry in folder.iterdir() if entry.is_dir())
        except OSError:
            return
        for subfolder in subfolders:
            if subfolder.name.startswith('.') or subfolder.name.lower() in SEARCH_SKIP_FOLDERS:
                continue
            search(subfolder, depth + 1)

    if base_folder.is_dir():
        search(base_folder, 0)
    return found, skipped


class ConfigurationPage(TabWithToolbar):
    """
    Page for configuring the basic simulation parameters
    """

    def __init__(self, main_window: MainWindow):
        """
        :param main_window: main Window object
        """

        super().__init__()
        self.main_window = main_window
        self.detected_program = 0
        self.detected_version_name = ''

        #
        # VARIABLES
        #

        self.selected_configuration: Optional[SimulationConfiguration] = None
        self.new_configuration_text = 'Add new configuration'

        #
        # TOOLBAR
        #

        # New
        self.action_new = notNone(self.toolbar.addAction(getIcon('new'), 'New'))
        self.action_new.setToolTip('Reset all configured Simulations')
        self.action_new.setShortcut(QKeySequence.StandardKey.New)
        self.action_new.triggered.connect(lambda: self.clearAll())

        # Open
        self.action_open = notNone(self.toolbar.addAction(getIcon('open'), 'Open'))
        self.action_open.setToolTip('Open saved simulation configurations')
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.action_open.triggered.connect(lambda: self.open())

        # Save
        self.action_save = notNone(self.toolbar.addAction(getIcon('save'), 'Save'))
        self.action_save.setToolTip('Save all listed simulation configurations')
        self.action_save.setShortcut(QKeySequence.StandardKey.Save)
        self.action_save.triggered.connect(lambda: self.save())

        # Search
        self.action_search = notNone(self.toolbar.addAction(getIcon('search'), 'Search'))
        self.action_search.setToolTip('Search a folder and all its subfolders for installed simulations\nand add them as configurations')
        self.action_search.triggered.connect(lambda: self.searchSimulations())

        # Add empty space
        self.empty_space = QWidget()
        self.empty_space.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(self.empty_space)

        # Run
        self.action_run = notNone(self.toolbar.addAction(getIcon('play'), 'Run'))
        self.action_run.setToolTip('Run the selected simulation(s)')
        self.action_run.setShortcut(QKeySequence('Ctrl+R'))
        self.action_run.triggered.connect(lambda: self.runSelected())

        # Run detached
        self.action_run_detached = notNone(self.toolbar.addAction(getIcon('play_detached'), 'Run detached'))
        self.action_run_detached.setToolTip('Run the selected simulation(s) in detached mode.\nThe simulation(s) is(are) run in a separate window, and the GUI can be closed')
        self.action_run_detached.setShortcut(QKeySequence('Ctrl+Shift+R'))
        self.action_run_detached.triggered.connect(lambda: self.runSelected(detached=True))

        #
        # SPLITTER
        #

        self.splitter = QSplitter()
        self.splitter.setChildrenCollapsible(False)
        self.page.addWidget(self.splitter)

        #
        # SIMULATION CONFIGURATION
        #

        self.simulation_configuration_vbox = VBoxTitleLayout(self, 'Manual Simulation Configuration', add_stretch=False)
        self.simulation_configuration_group = QVBoxLayout()
        self.simulation_configuration_group.setSpacing(5)

        # Split for label and input field
        split = 20

        # Configuration title
        self.title = LineEdit(
            placeholder='Choose a title...',
            max_length=25,
            parent=self
        )
        self.layout_title = InputHBoxLayout(
            'Configuration title:',
            self.title,
            tooltip='Name of your configuration',
            split=split
        )
        self.title.textChanged.connect(self.unsavedConfigView)
        self.simulation_configuration_group.addLayout(self.layout_title)

        # Simulation program
        self.program_tooltips = SimulationsList().simulation_program_description
        self.program_names = SimulationsList().simulation_program_names
        self.program = ComboBox(
            entries=self.program_names,
            tooltips=self.program_tooltips,
            parent=self
        )
        self.layout_program = InputHBoxLayout(
            'Simulation program:',
            self.program,
            tooltip='Program used for the simulation',
            split=split
        )
        self.program.currentIndexChanged.connect(self.getDescription)
        self.program.currentIndexChanged.connect(self.getVersions)
        self.program.currentIndexChanged.connect(self.unsavedConfigView)
        self.program.currentIndexChanged.connect(self.saveFolderChanged)
        self.program.currentIndexChanged.connect(lambda _: self.updateVersionHighlight())
        self.simulation_configuration_group.addLayout(self.layout_program)

        # Simulation version
        self.versions = ComboBox(
            entries=['All'],
            parent=self
        )
        self.layout_versions = InputHBoxLayout(
            'Simulation versions:',
            self.versions,
            tooltip='Program version used for the simulation',
            split=split
        )
        self.layout_versions.setEnabled(False)
        self.versions.currentIndexChanged.connect(self.unsavedConfigView)
        self.versions.currentIndexChanged.connect(lambda _: self.updateVersionHighlight())
        self.simulation_configuration_group.addLayout(self.layout_versions)

        # Simulation path
        self.simulation_folder = FilePath(
            placeholder='Select the main folder of the simulation',
            function_loc=lambda: self.selectSimFolder(
                simulation=self.program_names[self.program.currentIndex()]
            ),
            icon_loc=getIcon('open'),
            parent=self
        )
        self.layout_simulation_folder = InputHBoxLayout(
            'Simulation folder:',
            self.simulation_folder,
            tooltip='Path of the root folder of the simulation which contains all the content of the simulation program',
            split=split
        )
        self.simulation_folder.path_display.textChanged.connect(self.unsavedConfigView)
        self.simulation_configuration_group.addLayout(self.layout_simulation_folder)

        # Simulation binary path
        self.simulation_binary = FilePath(
            placeholder='Select simulation binary',
            function_loc=lambda: self.selectSimBinary(
                simulation=self.program_names[self.program.currentIndex()]
            ),
            icon_loc=getIcon('open'),
            parent=self
        )
        self.layout_simulation_binary = InputHBoxLayout(
            'Simulation binary:',
            self.simulation_binary,
            tooltip='Path to the executable file of the simulation',
            split=split
        )
        self.simulation_binary.path_display.textChanged.connect(self.unsavedConfigView)
        self.simulation_configuration_group.addLayout(self.layout_simulation_binary)

        # Base save folder path
        self.base_save_folder = FilePath(
            placeholder='Automatic',
            function_loc=lambda: self.selectSaveFolder(
                simulation=self.program_names[self.program.currentIndex()]
            ),
            icon_loc=getIcon('open'),
            clearable=True,
            parent=self
        )
        self.layout_base_save_folder = InputHBoxLayout(
            'Save folder (optional):',
            self.base_save_folder,
            tooltip='Path of the root folder for saves of this simulation. If left empty, the default save folder from the preferences is used',
            split=split
        )
        self.base_save_folder.path_display.textChanged.connect(self.unsavedConfigView)
        self.simulation_configuration_group.addLayout(self.layout_base_save_folder)

        # Simulation detected version
        self.detected_simulation = QLabel('unknown', self)
        self.layout_detected_simulation = InputHBoxLayout(
            'Detected simulation:',
            self.detected_simulation,
            tooltip='Used simulation (+version), extracted from the simulation folder. If simulation can not be identified, the detected simulation is "unknown"',
            split=split
        )
        self.simulation_configuration_group.addLayout(self.layout_detected_simulation)

        # Simulation
        self.simulation_description_hbox = QHBoxLayout()
        self.simulation_description_hbox.addWidget(QLabel('Simulation description:', self), split, alignment=Qt.AlignmentFlag.AlignTop)
        self.description_hbox = QHBoxLayout()
        self.description_logo = QLabel('', self)
        self.description_logo.hide()
        self.description_hbox.addWidget(self.description_logo, alignment=Qt.AlignmentFlag.AlignTop)
        self.description_label = QLabel('no description', self)
        self.description_hbox.addWidget(self.description_label, alignment=Qt.AlignmentFlag.AlignTop)
        self.simulation_description_hbox.addLayout(self.description_hbox, 100 - split)
        self.simulation_configuration_group.addLayout(self.simulation_description_hbox)

        # Save button
        self.save_hbox = QHBoxLayout()
        self.save_hbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.simulation_configuration_group.addSpacing(30)
        self.simulation_configuration_group.addLayout(self.save_hbox)

        self.save_hbox.addStretch(1)
        self.save_configuration_button_text = 'Save configuration'
        self.save_configuration_button = QPushButton(self.save_configuration_button_text)
        self.save_hbox.addWidget(self.save_configuration_button, 4)
        self.save_configuration_button.clicked.connect(lambda: self.saveConfigView())
        self.save_hbox.addStretch(1)

        self.saveFolderChanged()

        # Stretch to bottom
        self.simulation_configuration_group.addStretch(1)
        self.simulation_configuration_group.setAlignment(Qt.AlignmentFlag.AlignRight)

        # Add a parent to the simConfL and add that to the splitter (=self)
        self.settings_parent = QWidget(self)
        self.settings_group = QGroupBox(self)
        self.settings_group.setLayout(self.simulation_configuration_group)
        self.simulation_configuration_vbox.addWidget(self.settings_group)
        self.settings_parent.setLayout(self.simulation_configuration_vbox)
        self.splitter.addWidget(self.settings_parent)

        #
        # LIST OF SIMULATION CONFIGURATIONS
        #

        self.simulation_configuration_list_vbox = VBoxTitleLayout(self, 'List of Simulation Configurations', add_stretch=False)
        self.simulation_configuration_list_group = QVBoxLayout()

        # Information
        self.simulation_configuration_list_label = QLabel('Click to edit configuration, drag to reorder')
        self.simulation_configuration_list_label.setMaximumHeight(20)
        self.simulation_configuration_list_group.addWidget(self.simulation_configuration_list_label, Qt.AlignmentFlag.AlignLeft)

        # List of simulations
        self.simulation_configuration_list = QListWidget()
        self.simulation_configuration_list.setStyleSheet(Styles.list_style)
        self.simulation_configuration_list_group.addWidget(self.simulation_configuration_list)
        self.simulation_configuration_list.currentItemChanged.connect(lambda list_item: self.loadConfigView(list_item))
        self.simulation_configuration_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.simulation_configuration_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        notNone(self.simulation_configuration_list.model()).rowsMoved.connect(lambda *_: QTimer.singleShot(0, self.configListReordered))

        # List configurations
        self.simulation_configuration_list.addItem(self.new_configuration_text)
        QTimer.singleShot(0, self.listConfigView)

        # Stretch to bottom
        self.simulation_configuration_list_group.setAlignment(Qt.AlignmentFlag.AlignRight)

        # Copy and delete Buttons
        self.copy_delete_hbox = QHBoxLayout()
        self.simulation_configuration_list_group.addLayout(self.copy_delete_hbox)

        self.copy = QPushButton('Copy configuration')
        # Copy button not needed
        # self.copy_delete_hbox.addWidget(self.copy)
        self.copy.clicked.connect(lambda: self.copyConfigView())
        self.copy.setDisabled(True)

        self.clone = QPushButton('Clone configuration')
        self.clone.setToolTip('Clone the currently selected simulation')
        self.copy_delete_hbox.addWidget(self.clone)
        self.clone.clicked.connect(lambda: self.cloneConfigView())
        self.clone.setDisabled(True)

        self.delete = QPushButton('Delete configuration')
        self.delete.setToolTip('Delete the currently selected simulation')
        self.copy_delete_hbox.addWidget(self.delete)
        self.delete.clicked.connect(lambda: self.deleteConfigView())
        self.delete.setDisabled(True)

        # Add a parent to the simulationConfigurationListLayout and add that to the splitter (=self)
        self.settings_list_parent = QWidget(self)
        self.settings_list_group = QGroupBox(self)
        self.settings_list_group.setLayout(self.simulation_configuration_list_group)
        self.simulation_configuration_list_vbox.addWidget(self.settings_list_group)
        self.settings_list_parent.setLayout(self.simulation_configuration_list_vbox)
        self.splitter.addWidget(self.settings_list_parent)

        # Division between columns
        self.splitter.setStretchFactor(0, 60)
        self.splitter.setStretchFactor(1, 40)

        # clear everything on startup
        self.clearConfigView()

    def checkClosableAll(self, dialog: bool = True) -> bool:
        """
        Check if all simulation tabs are closeable

        :param dialog: if dialog should be shown
        """

        non_closeable = []
        for sc in self.main_window.simulation_configs:
            if sc.tab_widget is not None:
                if not sc.tab_widget.isClosable():
                    text = f'» {sc.title}'
                    if sc.running:
                        text += ' (running)'
                    elif sc.tab_widget.scan.isRunning():
                        text += ' (parameter scan running)'
                    elif sc.unsaved_changes:
                        text += ' (unsaved changes)'
                    non_closeable.append(text)

        if not dialog:
            return bool(non_closeable)

        if non_closeable:
            _, result = showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                'At least one simulation is currently not closeable. It is either running (⧖) or has unsaved changes (*)',
                info_message='Continue anyways?',
                detailed_message='\n'.join(non_closeable),
                standard_buttons=QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Abort
            )
            if result == QMessageBox.StandardButton.Abort:
                return False
        return True

    def clearAll(self, show_warning: bool = True) -> bool:
        """
        Clears all configurations

        :param show_warning: if warning should be shown
        """

        if not self.main_window.simulation_configs:
            return True

        if not self.checkClosableAll():
            return False

        if show_warning:
            _, result = showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                'All listed simulation configurations will be cleared an list of simulation configurations will be reset.',
                standard_buttons=QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
            )

            if result == QMessageBox.StandardButton.Cancel:
                return False

        self.main_window.simulation_configs = []
        self.clearConfigView()
        self.listConfigView()
        return True

    def open(self, default: bool = False):
        """
        Opens configuration file

        :param default: if True, then load autosave
        """

        save_file: Optional[Path]
        if default:
            save_file = GlobalConf.save_path / 'config' / 'autosave.json'

        else:
            save_file = GlobalConf.save_path / 'config' / 'config.json'

            save_file = selectFileDialog(
                self,
                False,
                'Load configuration file',
                save_file,
                file_filter='Configuration Files (*.json)'
            )
            if save_file is None:
                self.main_window.writeStatusBar('Loading configuration file aborted')
                return

        if not self.clearAll(show_warning=False):
            return

        try:
            with open(save_file, 'r', encoding='utf-8', errors='replace') as conf_file:
                data = load(conf_file)
        except (FileNotFoundError, JSONDecodeError):
            logging.info(f'Could not open file "{save_file}"!')
            return

        scs = [SimulationConfiguration.load(d) for d in data]

        error_msg = ''
        for i, sc in enumerate(scs):
            if sc is False:
                error_msg += f'Error while loading simulation-program "{data[i].get("program")}" with simulation-title "{data[i].get("title")}"\n'
            else:
                self.main_window.simulation_configs.append(sc)

        if error_msg:
            showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                'Errors occurred while loading configuration. Effected configurations will not be loaded.',
                detailed_message=error_msg
            )

        # configurations whose version group differs from the version detected in their folder
        mismatches = [sc for sc in self.main_window.simulation_configs if getattr(sc, 'detected_version', None)]
        if mismatches:
            _, result = showMessageBox(
                self,
                QMessageBox.Icon.Question,
                'Version mismatch',
                'The version of some configurations differs from the version found in their folder.',
                info_message='The input files are written for the version of the configuration, so the simulation might fail or '
                             'use different parameters.\nDo you want to use the found versions?',
                detailed_message='\n'.join(f'"{sc.title}": version {sc.version}, found {sc.detected_version}' for sc in mismatches),
                standard_buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                expand_details=True
            )
            if result == QMessageBox.StandardButton.Yes:
                for sc in mismatches:
                    if sc.detected_version is not None:
                        sc.version = sc.detected_version
                self.save(autosave=True, no_config=not GlobalConf.keep_configurations_info)
            for sc in mismatches:
                sc.detected_version = None

        self.clearConfigView()
        self.listConfigView()
        self.main_window.writeStatusBar('Loading configuration file successful')

    def searchSimulations(self, base_folder: Optional[Path] = None) -> int:
        """
        Searches a folder (selected in a dialog) and its subfolders for installed simulations and adds them as configurations.
        Installations that are already configured are skipped.

        :param base_folder: (optional) folder to search in, otherwise a dialog is opened

        :return: number of added configurations
        """

        if base_folder is None:
            folder = QFileDialog.getExistingDirectory(self, 'Select the folder which contains the simulation programs', pathToStr(Path(QDir.currentPath())))
            if not folder:
                self.main_window.writeStatusBar('Search for simulations aborted')
                return 0
            base_folder = Path(folder)

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            found, skipped = searchInstallations(base_folder)
        finally:
            QApplication.restoreOverrideCursor()

        configured = {sc.folder.resolve() for sc in self.main_window.simulation_configs if sc.folder is not None}
        titles = {sc.title for sc in self.main_window.simulation_configs}
        added = []
        for installation in found:
            folder = installation['folder']
            if folder.resolve() in configured:
                skipped.append(f'{installation["version_name"]} in "{pathToStr(folder)}": already configured')
                continue
            numbers = findall(r'\d+(?:\.\d+)?', installation['version_name'])
            title = f'{installation["name"]} {numbers[0]}' if numbers else installation['name']
            unique_title, i = title, 2
            while unique_title in titles:
                unique_title = f'{title} ({i})'
                i += 1
            titles.add(unique_title)
            self.main_window.simulation_configs.append(SimulationConfiguration(
                unique_title, installation['program'], folder, installation['binary'], installation['version']
            ))
            added.append(f'{unique_title}: "{pathToStr(installation["binary"])}" (version {installation["version"]})')

        if added:
            self.save(autosave=True, no_config=not GlobalConf.keep_configurations_info)
            self.clearConfigView()
            self.listConfigView()

        details = []
        if added:
            details += ['Added:'] + added
        if skipped:
            details += ([''] if added else []) + ['Not added:'] + skipped
        showMessageBox(
            self,
            QMessageBox.Icon.Information if added else QMessageBox.Icon.Warning,
            'Search for simulations',
            f'{len(added)} simulation{"" if len(added) == 1 else "s"} added from "{pathToStr(base_folder)}"',
            detailed_message='\n'.join(details) if details else '',
            expand_details=True
        )
        self.main_window.writeStatusBar(f'{len(added)} simulation configuration{"" if len(added) == 1 else "s"} added')
        return len(added)

    def save(self, autosave: bool = False, no_config: bool = False):
        """
        Saves configuration file

        :param autosave: if True, an autosave file will be generated
        :param no_config: if True, only programs without config will be saved
        """

        config_path = GlobalConf.save_path / 'config'
        config_path.mkdir(parents=True, exist_ok=True)

        save_file: Optional[Path]
        if autosave:
            save_file = config_path / 'autosave.json'

        else:
            save_file = config_path / 'config.json'
            save_file = selectFileDialog(
                self,
                True,
                'Save configuration file',
                save_file,
                file_filter='Configuration Files (*.json)'
            )
            if save_file is None:
                self.main_window.writeStatusBar('Saving configuration file aborted')
                return

        config = [sc.save(no_config=no_config) for sc in self.main_window.simulation_configs]

        with open(save_file, 'w', encoding='utf-8') as config_file:
            dump(config, config_file, indent=4)

        self.main_window.writeStatusBar('Saving configuration file successful')

    def listConfigView(self):
        """List configuration from self.mainWindow.simConfigs dictionary"""
        self.simulation_configuration_list.clear()
        new_item = QListWidgetItem(self.new_configuration_text)
        new_item.setFlags(new_item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled & ~Qt.ItemFlag.ItemIsDropEnabled)
        self.simulation_configuration_list.addItem(new_item)
        for sc in self.main_window.simulation_configs:
            item = QListWidgetItem(sc.title)
            item.setFlags((item.flags() | Qt.ItemFlag.ItemIsDragEnabled) & ~Qt.ItemFlag.ItemIsDropEnabled)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip('Selecting simulations allows for simultaneous running. Drag to reorder')
            self.simulation_configuration_list.addItem(item)

        self.main_window.updateTabs()
        self.simulation_configuration_list.setCurrentRow(0)

    def configListReordered(self):
        """Applies the order of the configuration list (changed by drag and drop) to the configurations and tabs"""

        # the "Add new configuration" entry always stays on top
        for i in range(self.simulation_configuration_list.count()):
            if notNone(self.simulation_configuration_list.item(i)).text() == self.new_configuration_text:
                if i != 0:
                    self.simulation_configuration_list.insertItem(0, self.simulation_configuration_list.takeItem(i))
                break

        titles = [notNone(self.simulation_configuration_list.item(i)).text() for i in range(1, self.simulation_configuration_list.count())]
        configs_by_title = {sc.title: sc for sc in self.main_window.simulation_configs}
        if sorted(titles) != sorted(configs_by_title.keys()):
            return

        self.main_window.simulation_configs[:] = [configs_by_title[title] for title in titles]
        self.main_window.updateTabs()
        self.save(autosave=True, no_config=not GlobalConf.keep_configurations_info)

    def selectConfigView(self, list_name: str):
        """
        Selects list_name in config view

        :param list_name: name of configuration in simulation_configuration_list
        """

        items = self.simulation_configuration_list.findItems(list_name, Qt.MatchFlag.MatchExactly)
        if not items:
            self.simulation_configuration_list.setCurrentRow(0)
        else:
            self.simulation_configuration_list.setCurrentItem(items[0])
            self.loadConfigView(items[0])

    def loadConfigView(self, list_item):
        """
        Load configuration from self.mainWindow.simConfigs dictionary into configuration editor

        :param list_item: selected item in list
        """

        if list_item is None:
            return

        conf_name = list_item.text()
        self.title.setFocus()

        # If 'Add new configuration' is pressed
        if conf_name == self.new_configuration_text:
            self.clearConfigView()
            self.selected_configuration = None
            self.layout_program.setEnabled(True)
            self.layout_versions.setEnabled(True)
            self.copy.setDisabled(True)
            self.clone.setDisabled(True)
            self.delete.setDisabled(True)
            return

        else:
            self.copy.setDisabled(False)
            self.clone.setDisabled(False)
            self.delete.setDisabled(False)

        # Try to get SimulationConfiguration
        for sc in self.main_window.simulation_configs:
            if sc.title == conf_name:
                self.selected_configuration = sc
                break

        # Extract variables
        if self.selected_configuration is not None:
            self.title.setText(self.selected_configuration.title)
            self.program.setCurrentIndex(self.selected_configuration.program)
            self.simulation_folder.setPath(self.selected_configuration.folder, ssh=False)
            self.simulation_binary.setPath(self.selected_configuration.binary, ssh=False)
            self.base_save_folder.setPath(self.selected_configuration.base_save_folder, ssh=False)
            self.getVersions()
            self.versions.setCurrentText(self.selected_configuration.version)
            # self.detected_simulation.setText(f'<b>{self.selected_configuration.version}</b>')
            self.description_label.setText(self.selected_configuration.program_description.strip())
            self.save_configuration_button.setText(self.save_configuration_button_text)
            if self.selected_configuration.program_logo:
                self.description_logo.setPixmap(
                    QPixmap(self.selected_configuration.program_logo).scaled(200, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                )
                self.description_logo.show()
            else:
                self.description_logo.hide()
            self.tryParseSimVersion()
        self.layout_program.setEnabled(False)
        self.layout_versions.setEnabled(False)

    def unsavedConfigView(self):
        """Called when the current settings ara changed"""

        self.save_configuration_button.setText(f'{self.save_configuration_button_text} (Unsaved changes)')

    def saveConfigView(self, simulation_check: bool = True):
        """
        Save configuration from self.mainWindow.simConfigs dictionary

        :param simulation_check: if simulation should be checked
        """

        if self.selected_configuration is not None:
            if not notNone(self.selected_configuration.tab_widget).isClosable():
                warning_text = f'"{self.selected_configuration.title}" '
                scan = notNone(self.selected_configuration.tab_widget).scan
                if scan.isRunning():
                    warning_text += 'runs a parameter scan. Please wait until the scan finishes to edit the configuration.'
                elif self.selected_configuration.running:
                    warning_text += 'is running (⧖). Please wait until simulation finishes to edit the configuration.'
                else:
                    warning_text += 'has unsaved changes (*). Please save unsaved changes to edit the configuration.'
                showMessageBox(
                    self,
                    QMessageBox.Icon.Warning,
                    'Warning!',
                    warning_text
                )
                return

        title = self.title.text()
        program = self.program.currentIndex()
        folder = self.simulation_folder.path
        binary = self.simulation_binary.path
        base_save_folder = self.base_save_folder.path
        self.tryParseSimVersion()
        version = self.versions.itemText(self.versions.currentIndex())
        version_detected = self.detected_simulation.text()
        version_detected = version_detected.replace('<b>', '').replace('</b>', '')

        if not title:
            showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                '"Configuration title" can not be empty'
            )

        elif not folder:
            showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                'Path to "Simulation folder" can not be empty'
            )

        elif not binary:
            showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                'Path to "Simulation bolder" can not be empty'
            )

        elif title in [sc.title for sc in self.main_window.simulation_configs] and self.selected_configuration is None:
            showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                '"Configuration title" already exists, choose a different'
            )

        else:
            if not GlobalConf.no_autodetect_version and self.program.getValue() != self.detected_program and simulation_check:
                msg_box, result = showMessageBox(
                    self.main_window,
                    QMessageBox.Icon.Warning,
                    'Warning!',
                    f'Other simulation "<b>{version_detected}</b>" detected, than the selected "<b>{self.program.getValue(text=True)}</b>"',
                    check_box_text='Do not show again',
                    standard_buttons=QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Abort
                )
                if msg_box.checkBox().isChecked():
                    GlobalConf.no_autodetect_version = True
                if result == QMessageBox.StandardButton.Abort:
                    return False

            if self.selected_configuration is None:
                sc = SimulationConfiguration(title, program, folder, binary, version, base_save_folder)
                self.main_window.simulation_configs.append(sc)
            else:
                self.selected_configuration.edit(title, folder, binary, version, base_save_folder)

            # update data for new folder/binary
            if self.selected_configuration is not None and isinstance(self.selected_configuration.tab_widget, SimulationPage):
                self.selected_configuration.tab_widget.simulation_class.update(folder, binary, version)
                self.selected_configuration.tab_widget.simulation_class.updateElements(folder, version)
                self.selected_configuration.tab_widget.periodic_table_dialog.setElementData(
                    self.selected_configuration.tab_widget.simulation_class.element_data,
                    self.selected_configuration.tab_widget.simulation_class.element_data_default
                )

            self.save(autosave=True, no_config=not GlobalConf.keep_configurations_info)

            self.main_window.writeStatusBar('Configuration saved!')

            self.listConfigView()

            # highlight saved item in configuration list
            j = 0
            for i in range(self.simulation_configuration_list.count()):
                if notNone(self.simulation_configuration_list.item(i)).text() == title:
                    j = i
                    break
            self.simulation_configuration_list.setCurrentRow(j)

            self.save_configuration_button.setText(self.save_configuration_button_text)

    def deleteConfigView(self):
        """Delete configuration from self.mainWindow.simConfigs dictionary and reset configuration editor"""

        if self.selected_configuration is not None:
            # check if it is closeable
            if self.selected_configuration.tab_widget is not None:
                if not self.selected_configuration.tab_widget.isClosable():
                    showMessageBox(
                        self,
                        QMessageBox.Icon.Warning,
                        'Warning!',
                        f'"{self.selected_configuration.title}" is currently not closeable. It is either running (⧖) or has unsaved changes (*)'
                    )
                    return
            self.main_window.simulation_configs.remove(self.selected_configuration)
        self.selected_configuration = None
        self.layout_program.setEnabled(True)
        self.layout_versions.setEnabled(True)
        self.save(autosave=True, no_config=not GlobalConf.keep_configurations_info)
        self.clearConfigView()
        self.listConfigView()

    def copyConfigView(self):
        """Copy current configuration"""

        if self.selected_configuration is not None:
            self.title.setText(f'{self.title.text()} - Copy')
            self.selected_configuration = None
            self.layout_program.setEnabled(True)
            self.layout_versions.setEnabled(True)

    def cloneConfigView(self):
        """Clones current configuration"""

        if self.selected_configuration is None:
            return
        self.title.setText(f'{self.title.text()} - Clone')
        self.selected_configuration = None
        self.saveConfigView(simulation_check=False)

    def clearConfigView(self):
        """Reset configuration editor"""

        self.title.setText('')
        self.program.setCurrentIndex(0)
        self.simulation_folder.setPath(None, ssh=False)
        self.simulation_binary.setPath(None, ssh=False)
        self.saveFolderChanged()
        self.detected_simulation.setText('<b>unknown</b>')
        self.detected_version_name = ''
        self.updateVersionHighlight()
        self.description_logo.hide()
        self.description_label.setText('no description')
        self.save_configuration_button.setText(self.save_configuration_button_text)
        self.getVersions()
        self.getDescription()

    def getDescription(self):
        """Tries to load description from simulation class"""

        sim_list = SimulationsList()
        selected = self.program.getValue(text=True)
        for name, desc, logo in zip(sim_list.simulation_program_names, sim_list.simulation_program_description, sim_list.simulation_program_logo):
            if name == selected:
                self.description_label.setText(desc.strip())
                if logo:
                    self.description_logo.setPixmap(QPixmap(logo).scaled(200, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    self.description_logo.show()
                else:
                    self.description_logo.hide()
                break

    def getVersions(self):
        """Gets list of possible versions of a simulation"""

        selected = self.program.getValue(text=True)
        version_list = SimulationsList().simulation_program_versions.get(selected)

        if not isinstance(version_list, list) or not version_list:
            self.versions.clear()
            self.versions.addItem('All')
            self.layout_versions.setEnabled(False)

        else:
            self.versions.clear()
            for version in version_list:
                self.versions.addItem(version)
            self.layout_versions.setEnabled(True)
            self.versions.setCurrentIndex(len(version_list) - 1)

    def selectSimFolder(self, show_warning_window: bool = False, simulation: str = 'Simulation') -> Optional[Path]:
        """
        Opens select dialog for simulation path and returns selected path

        :param show_warning_window: display message box that warns if something is not set
        :param simulation: name of Simulations
        """

        if show_warning_window:
            showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning',
                f'Missing {simulation} folder location',
                f'The main {simulation} folder, has not yet been defined.\nYou can do that either in the preferences or using the window which opens after pressing "OK".'
            )

        # Starting directory
        if self.selected_configuration is not None:
            start_dir = self.selected_configuration.folder
        elif self.simulation_folder.path:
            start_dir = self.simulation_folder.path
        else:
            start_dir = Path(QDir.currentPath())

        folder_dir = QFileDialog.getExistingDirectory(self, f'Select the main "{simulation}" folder', pathToStr(start_dir))
        if len(folder_dir) == 0:
            self.main_window.writeStatusBar(f'{simulation} folder selection aborted')
            return None
        folder_dir = Path(folder_dir)

        # a previously selected binary outside of the new folder is ignored for the detection
        binary = self.simulation_binary.path
        binary_in_folder = binary is not None and binary.is_relative_to(folder_dir)
        self.tryParseSimVersion(folder=folder_dir, binary=binary if binary_in_folder else None, ignore_binary=not binary_in_folder)

        # automatically select the binary if no binary inside the selected folder is chosen yet
        if not binary_in_folder:
            program_idx = self.detected_program if self.detected_version_name else self.program.currentIndex()
            found_binary = SimulationsList().simulation_program_list[program_idx].findBinary(folder_dir)
            if found_binary is not None:
                self.simulation_binary.setPath(found_binary, ssh=False)
                self.tryParseSimVersion(folder=folder_dir, binary=found_binary)
                self.selectDetectedVersion()
                self.main_window.writeStatusBar(f'{simulation} folder successfully located, binary "{found_binary.name}" selected automatically')
                return folder_dir

            # the previous binary belongs to another folder
            if binary is not None:
                self.simulation_binary.setPath(None, ssh=False)
                self.tryParseSimVersion(folder=folder_dir, ignore_binary=True)
                self.selectDetectedVersion()
                self.main_window.writeStatusBar(f'{simulation} folder successfully located, but no binary was found. Please select the binary')
                return folder_dir

        self.selectDetectedVersion()
        self.main_window.writeStatusBar(f'{simulation} folder successfully located')
        return folder_dir

    def selectSimBinary(self, show_warning_window: bool = False, simulation: str = 'Simulation') -> Optional[Path]:
        """
        Select dialog for simulation binary

        :param show_warning_window: display message box that warns if something is not set
        :param simulation: name of Simulations
        """

        if show_warning_window:
            showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning',
                f'Missing {simulation} binary location',
                f'The {simulation} binary has not yet been defined.\nYou can do that either in the preferences or using the window which opens after pressing "OK".'
            )
        # Starting directory
        if self.selected_configuration is not None:
            start_dir = self.selected_configuration.binary
        elif self.simulation_binary.path:
            start_dir = self.simulation_binary.path
        elif self.simulation_folder.path:
            start_dir = self.simulation_folder.path
        else:
            start_dir = Path(QDir.currentPath())

        allowed_filetypes = ''
        if system() == 'Windows':
            allowed_filetypes = 'Executable File (*.exe)'

        file_path = selectFileDialog(self, False, f'Select the "{simulation}" binary', start_dir, allowed_filetypes)
        if file_path is None:
            self.main_window.writeStatusBar(f'{simulation} binary selection aborted')
            return None

        file_path = Path(file_path)
        self.tryParseSimVersion(binary=file_path)
        self.selectDetectedVersion()
        self.main_window.writeStatusBar(f'{simulation} binary successfully located')
        return file_path

    def selectSaveFolder(self, simulation: str = 'Simulation') -> Optional[Path]:
        """
        Opens select dialog for save folder path and returns selected path
        """

        # Starting directory
        start_dir = self.base_save_folder.path
        if start_dir is None or not start_dir.is_dir():
            start_dir = self.defaultSaveFolder()
        if not start_dir.is_dir():
            start_dir = GlobalConf.save_path

        folder_dir = QFileDialog.getExistingDirectory(self, f'Select the "{simulation}" save folder', pathToStr(start_dir))
        if len(folder_dir) == 0:
            self.main_window.writeStatusBar('Save folder selection aborted')
            return None
        self.main_window.writeStatusBar('Save folder successfully located')
        return Path(folder_dir)

    def saveFolderChanged(self):
        """
        Update save folder if other simulation is selected
        """

        self.base_save_folder.setPath(None, ssh=False)
        self.updateSaveFolderPlaceholder()

    def updateSaveFolderPlaceholder(self):
        """Shows the automatically used save folder as placeholder of the save folder field"""

        self.base_save_folder.path_display.setPlaceholderText(f'Automatic: {pathToStr(self.defaultSaveFolder())}')

    def defaultSaveFolder(self) -> Path:
        """Returns the default save folder of the selected simulation program, which depends on the preferences"""

        return GlobalConf.save_path / SimulationsList().simulation_program_list[self.program.currentIndex()].SaveFolder

    def tryParseSimVersion(self, folder: Optional[Path] = None, binary: Optional[Path] = None, ignore_binary: bool = False):
        """
        Try to get Simulation name and version

        :param folder: (optional) folder of simulation, otherwise the selected folder is used
        :param binary: (optional) binary of simulation, otherwise the selected binary is used
        :param ignore_binary: (optional) do not use the selected binary if no binary is provided
        """

        if folder is None:
            folder = self.simulation_folder.path
        if binary is None and not ignore_binary:
            binary = self.simulation_binary.path
        simulation_programs = SimulationsList().simulation_program_list
        version = 'unknown'
        self.detected_program = 0
        self.detected_version_name = ''

        for i, simulation_program in enumerate(simulation_programs):
            curr_version = simulation_program.getVersionName(folder, binary)
            if curr_version:
                version = curr_version
                self.detected_program = i
                self.detected_version_name = curr_version
                break

        self.detected_simulation.setText(f'<b>{version}</b>')
        self.updateVersionHighlight()

    def detectedVersionIndex(self) -> Tuple[int, bool]:
        """
        Returns the index of the selectable version that suits the detected version best and if it matches exactly.
        If the detected version is not listed, the highest listed version below it is used (or the lowest listed version)

        :return: (index or -1 if nothing is detected, exact match)
        """

        if not self.detected_version_name or self.detected_program != self.program.currentIndex():
            return -1, False

        return bestVersion([self.versions.itemText(i) for i in range(self.versions.count())], self.detected_version_name)

    def selectDetectedVersion(self):
        """Selects the version that suits the detected version best, if there is one"""

        index, _ = self.detectedVersionIndex()
        if index >= 0:
            self.versions.setCurrentIndex(index)
        self.updateVersionHighlight()

    def updateVersionHighlight(self):
        """Highlights the selected program and version if they do not coincide with the detected simulation"""

        if not hasattr(self, 'detected_simulation'):
            return

        program_mismatch = bool(self.detected_version_name) and self.detected_program != self.program.currentIndex()
        setWidgetHighlight(self.program, program_mismatch)
        self.program.setToolTip(
            f'Detected simulation "{self.detected_version_name}" does not belong to the selected program' if program_mismatch else ''
        )

        index, exact = self.detectedVersionIndex()
        version_mismatch = index >= 0 and self.versions.currentIndex() != index
        setWidgetHighlight(self.versions, version_mismatch)
        if version_mismatch:
            self.versions.setToolTip(f'Detected simulation "{self.detected_version_name}" suits "{self.versions.itemText(index)}" better than the selected version')
        elif index >= 0 and not exact:
            self.versions.setToolTip(f'Detected simulation "{self.detected_version_name}" is not listed explicitly, the closest supported version is selected')
        else:
            self.versions.setToolTip('')

    def runSelected(self, detached=False):
        """
        Runs the selected configurations

        :param detached: (optional) if configurations should be run in detached mode
        """

        one_checked = False
        for i in range(self.simulation_configuration_list.count()):
            if notNone(self.simulation_configuration_list.item(i)).checkState() == Qt.CheckState.Checked:
                one_checked = True
                break
        if not one_checked:
            return

        non_closeable = []
        for sc in self.main_window.simulation_configs:
            if sc.tab_widget is not None:
                if sc.running:
                    non_closeable.append(f'» "{sc.title}" is running')

        if non_closeable:
            _, result = showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                'At least one simulation is currently running (⧖). Please wait until the simulation has finished',
                detailed_message='\n'.join(non_closeable),
                standard_buttons=QMessageBox.StandardButton.Ok
            )
            return

        configurations = []
        for i in range(self.simulation_configuration_list.count()):
            if notNone(self.simulation_configuration_list.item(i)).checkState() == Qt.CheckState.Checked and (i - 1) in range(len(self.main_window.simulation_configs)):
                configurations.append(self.main_window.simulation_configs[i - 1])
        self.main_window.runSimulations(configurations, detached=detached)
