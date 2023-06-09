# BCA-GUIDE - a graphical user interface for bca simulations to simulate sputtering, ion implantation and the
# dynamic effects of ion irradiation
#
# Copyright(C) 2022, Alexander Redl, Paul S.Szabo, David Weichselbaum, Herbert Biber, Christian Cupak, Andreas Mutzke,
# Wolfhard Möller, Richard A.Wilhelm, Friedrich Aumayr
#
# This program implements libraries of the Qt framework (https://www.qt.io/).
#
# This program is free software: you can redistribute it and / or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either version 3 of the License, or any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with this program. If not, see
# https://www.gnu.org/licenses/.


from __future__ import annotations
from typing import Optional, TYPE_CHECKING
from platform import system
from json import dump, load
from json.decoder import JSONDecodeError

from PyQt6.QtCore import Qt, QTimer, QDir, QFileInfo
from PyQt6.QtGui import QIcon, QKeySequence, QPixmap
from PyQt6.QtWidgets import (
    QSplitter, QWidget, QPushButton, QListWidget, QLabel, QListWidgetItem,
    QVBoxLayout, QGroupBox, QHBoxLayout, QMessageBox, QFileDialog, QSizePolicy
)

from GlobalConf import GlobalConf
from Styles import Styles

from Utility.Layouts import TabWithToolbar, VBoxTitleLayout, InputHBoxLayout, LineEdit, FilePath, ComboBox
from Utility.Dialogs import showMessageBox, selectFileDialog

from Pages.ProgramPage import SimulationPage

from Containers.SimulationConfiguration import SimulationConfiguration

from Simulations.SimulationsList import SimulationsList

# avoiding circular import, but still get type hinting functionality
if TYPE_CHECKING:
    from MainWindow import MainWindow


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

        #
        # VARIABLES
        #

        self.selected_configuration: Optional[SimulationConfiguration] = None
        self.new_configuration_text = 'Add new configuration'

        #
        # TOOLBAR
        #

        # New
        self.action_new = self.toolbar.addAction(QIcon(':/icons/new.png'), 'New')
        self.action_new.setToolTip('Reset all configured Simulations')
        self.action_new.setShortcut(QKeySequence.StandardKey.New)
        self.action_new.triggered.connect(lambda: self.clearAll())

        # Open
        self.action_open = self.toolbar.addAction(QIcon(':/icons/open.png'), 'Open')
        self.action_open.setToolTip('Open saved simulation configurations')
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.action_open.triggered.connect(lambda: self.open())

        # Save
        self.action_save = self.toolbar.addAction(QIcon(':/icons/save.png'), 'Save')
        self.action_save.setToolTip('Save all listed simulation configurations')
        self.action_save.setShortcut(QKeySequence.StandardKey.Save)
        self.action_save.triggered.connect(lambda: self.save())

        # Add empty space
        self.empty_space = QWidget()
        self.empty_space.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(self.empty_space)

        # Run
        self.action_run = self.toolbar.addAction(QIcon(':/icons/play.png'), 'Run')
        self.action_run.setToolTip('Run the selected simulation(s)')
        self.action_run.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_R))
        self.action_run.triggered.connect(lambda: self.runSelected())

        # Run detached
        self.action_run_detached = self.toolbar.addAction(QIcon(':/icons/play_detached.png'), 'Run detached')
        self.action_run_detached.setToolTip('Run the selected simulation(s) in detached mode.\nThe simulation(s) is(are) run in a separate window, and the GUI can be closed')
        self.action_run_detached.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_R))
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

        self.simulation_configuration_vbox = VBoxTitleLayout(self, 'Simulation Configuration', add_stretch=False)
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
        self.simulation_configuration_group.addLayout(self.layout_versions)

        # Simulation path
        self.simulation_folder = FilePath(
            placeholder='Select the main folder of the simulation',
            function=lambda: self.selectSimFolder(
                simulation=self.program_names[self.program.currentIndex()]
            ),
            parent=self
        )
        self.layout_simulation_folder = InputHBoxLayout(
            'Simulation folder:',
            self.simulation_folder,
            tooltip='Path of the root folder of the simulation which contains all the content of the simulation program',
            split=split
        )
        self.simulation_folder.path.textChanged.connect(self.unsavedConfigView)
        self.simulation_configuration_group.addLayout(self.layout_simulation_folder)

        # Simulation binary path
        self.simulation_binary = FilePath(
            placeholder='Select simulation binary',
            function=lambda: self.selectSimBinary(
                simulation=self.program_names[self.program.currentIndex()]
            ),

            parent=self
        )
        self.layout_simulation_binary = InputHBoxLayout(
            'Simulation binary:',
            self.simulation_binary,
            tooltip='Path to the executable file of the simulation',
            split=split
        )
        self.simulation_binary.path.textChanged.connect(self.unsavedConfigView)
        self.simulation_configuration_group.addLayout(self.layout_simulation_binary)

        # Base save folder path
        self.base_save_folder = FilePath(
            placeholder='Select the main save folder for the simulation',
            function=lambda: self.selectSaveFolder(
                simulation=self.program_names[self.program.currentIndex()]
            ),
            parent=self
        )
        self.layout_base_save_folder = InputHBoxLayout(
            'Save folder (optional):',
            self.base_save_folder,
            tooltip='Path of the root folder for saves of this simulation. If left empty the folder will be chosen automatically',
            split=split
        )
        self.base_save_folder.path.textChanged.connect(self.unsavedConfigView)
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
        self.simulation_configuration_list_label = QLabel('Click to edit configuration')
        self.simulation_configuration_list_label.setMaximumHeight(20)
        self.simulation_configuration_list_group.addWidget(self.simulation_configuration_list_label, Qt.AlignmentFlag.AlignLeft)

        # List of simulations
        self.simulation_configuration_list = QListWidget()
        self.simulation_configuration_list.setStyleSheet(Styles.list_style)
        self.simulation_configuration_list_group.addWidget(self.simulation_configuration_list)
        self.simulation_configuration_list.currentItemChanged.connect(lambda list_item: self.loadConfigView(list_item))

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
        self.copy_delete_hbox.addWidget(self.clone)
        self.clone.clicked.connect(lambda: self.cloneConfigView())
        self.clone.setDisabled(True)

        self.delete = QPushButton('Delete configuration')
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

        :pram show_warning: if warning should be shown
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

        if default:
            save_file = f'{GlobalConf.save_path}/config/autosave.json'

        else:
            save_file = f'{GlobalConf.save_path}/config/config.json'

            save_file = selectFileDialog(
                self,
                False,
                'Load configuration file',
                save_file,
                file_filter='Configuration Files (*.json)'
            )
            folder = QFileInfo(save_file).canonicalPath()
            if save_file is None or not len(folder):
                self.main_window.writeStatusBar('Loading configuration file aborted')
                return

        if not self.clearAll(show_warning=False):
            return

        try:
            with open(save_file, 'r') as conf_file:
                data = load(conf_file)
        except (FileNotFoundError, JSONDecodeError):
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

        self.clearConfigView()
        self.listConfigView()

        self.main_window.writeStatusBar('Loading configuration file successful')

    def save(self, autosave: bool = False, no_config: bool = False):
        """
        Saves configuration file

        :param autosave: if True, an autosave file will be generated
        :param no_config: if True, only programs without config will be saved
        """

        QDir().mkpath(f'{GlobalConf.save_path}/config')

        if autosave:
            save_file = f'{GlobalConf.save_path}/config/autosave.json'

        else:
            save_file = f'{GlobalConf.save_path}/config/config.json'
            save_file = selectFileDialog(
                self,
                True,
                'Save configuration file',
                save_file,
                file_filter='Configuration Files (*.json)'
            )
            folder = QFileInfo(save_file).canonicalPath()
            if len(folder) == 0:
                self.main_window.writeStatusBar('Saving configuration file aborted')
                return

        config = [sc.save(no_config=no_config) for sc in self.main_window.simulation_configs]

        with open(save_file, 'w') as config_file:
            dump(config, config_file, indent=4)

        self.main_window.writeStatusBar('Saving configuration file successful')

    def listConfigView(self):
        """List configuration from self.mainWindow.simConfigs dictionary"""

        self.simulation_configuration_list.clear()
        self.simulation_configuration_list.addItem(self.new_configuration_text)
        for sc in self.main_window.simulation_configs:
            item = QListWidgetItem(sc.title)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.simulation_configuration_list.addItem(item)
        self.main_window.updateTabs()
        self.simulation_configuration_list.setCurrentRow(0)

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
            self.simulation_folder.path.setText(self.selected_configuration.folder)
            self.simulation_binary.path.setText(self.selected_configuration.binary)
            self.base_save_folder.path.setText(self.selected_configuration.base_save_folder)
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
            if not self.selected_configuration.tab_widget.isClosable():
                warning_text = f'"{self.selected_configuration.title}" '
                if self.selected_configuration.running:
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
        folder = self.simulation_folder.path.text()
        binary = self.simulation_binary.path.text()
        base_save_folder = self.base_save_folder.path.text()
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
                if self.simulation_configuration_list.item(i).text() == title:
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
        self.simulation_folder.path.setText('')
        self.simulation_binary.path.setText('')
        self.saveFolderChanged()
        self.detected_simulation.setText('<b>unknown</b>')
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
                    self.description_logo.setPixmap(
                        QPixmap(logo).scaled(200, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    )
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

    def selectSimFolder(self, show_warning_window: bool = False, simulation: str = 'Simulation') -> Optional[str]:
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
        start_dir = self.selected_configuration.folder if self.selected_configuration is not None else QDir.currentPath()
        folder_dir = QFileDialog.getExistingDirectory(self, f'Select the main "{simulation}" folder', start_dir)
        if len(folder_dir) == 0:
            self.main_window.writeStatusBar(f'{simulation} folder selection aborted')
            return None

        self.tryParseSimVersion()
        self.main_window.writeStatusBar(f'{simulation} folder successfully located')
        return folder_dir

    def selectSimBinary(self, show_warning_window: bool = False, simulation: str = 'Simulation') -> Optional[str]:
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
        elif self.simulation_binary.path.text():
            start_dir = self.simulation_binary.path.text()
        elif self.simulation_folder.path.text():
            start_dir = self.simulation_folder.path.text()
        else:
            start_dir = QDir.currentPath()
        allowed_filetypes = ''
        if system() == 'Windows':
            allowed_filetypes = 'Executable File (*.exe)'
        file_path = selectFileDialog(self, False, f'Select the "{simulation}" binary', start_dir, allowed_filetypes)
        if file_path is None:
            self.main_window.writeStatusBar(f'{simulation} binary selection aborted')
            return None
        self.tryParseSimVersion()
        self.main_window.writeStatusBar(f'{simulation} binary successfully located')
        return file_path

    def selectSaveFolder(self, simulation: str = 'Simulation') -> Optional[str]:
        """
        Opens select dialog for save folder path and returns selected path
        """

        # Starting directory
        start_dir = self.base_save_folder.path.text()
        if not start_dir:
            start_dir = GlobalConf.save_path
        if not start_dir:
            start_dir = QDir.currentPath()

        folder_dir = QFileDialog.getExistingDirectory(self, f'Select the "{simulation}" save folder', start_dir)
        if len(folder_dir) == 0:
            self.main_window.writeStatusBar('Save folder selection aborted')
            return None
        self.main_window.writeStatusBar('Save folder successfully located')
        return folder_dir

    def saveFolderChanged(self):
        """
        Update save folder if other simulation is selected
        """

        default_save_folder = SimulationsList().simulation_program_list[self.program.currentIndex()].SaveFolder
        self.base_save_folder.path.setText(f'{GlobalConf.save_path}/{default_save_folder}')

    def tryParseSimVersion(self):
        """Try to get Simulation name and version"""

        folder = self.simulation_folder.path.text()
        binary = self.simulation_binary.path.text()
        simulation_programs = SimulationsList().simulation_program_list
        version = 'unknown'
        self.detected_program = 0

        for i, simulation_program in enumerate(simulation_programs):
            curr_version = simulation_program.getVersionName(folder, binary)
            if curr_version:
                version = curr_version
                self.detected_program = i
                break

        self.detected_simulation.setText(f'<b>{version}</b>')

    def runSelected(self, detached=False):
        """
        Runs the selected configurations

        :param detached: (optional) if configurations should be run in detached mode
        """

        one_checked = False
        for i in range(self.simulation_configuration_list.count()):
            if self.simulation_configuration_list.item(i).checkState():
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

        for i in range(self.simulation_configuration_list.count()):
            if self.simulation_configuration_list.item(i).checkState() and (i - 1) in range(len(self.main_window.simulation_configs)):
                self.main_window.simulation_configs[i - 1].tab_widget.runSimulation(detached=detached)
