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
from typing import List, Union, TYPE_CHECKING
from enum import Enum, auto
from platform import system
from os import chdir
from sys import exit
from locale import getpreferredencoding
from re import sub
from subprocess import Popen, getstatusoutput

from PyQt6.QtCore import Qt, QUrl, QDir, QFile, QFileInfo, QProcess, QTimer
from PyQt6.QtGui import QIcon, QKeySequence, QDesktopServices
from PyQt6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QTabWidget, QSplitter, QVBoxLayout, QGroupBox,
    QSizePolicy, QPushButton, QListWidget, QAbstractItemView, QProgressBar,
    QMessageBox, QFileDialog, QScrollArea, QApplication
)

from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT

from GlobalConf import GlobalConf
from Styles import Styles

from Utility.Layouts import TabWithToolbar, InputHBoxLayout, SpinBox, VBoxTitleLayout, MplCanvas, ListWidget, FileEditor
from Utility.Indexing import Counter
from Utility.Dialogs import showMessageBox, selectFileDialog
from Utility.Functions import alphanumeric, inFileList, inFileDict
from Utility.ModifyWidget import setWidgetHighlight

from TableWidgets.CompTable import CompRow, CompTable, CompTableTarget
from TableWidgets.TargetTable import TargetLayersTable
from TableWidgets.TargetPreview import TargetPreview
from TableWidgets.CompoundList import CompoundList
from TableWidgets.PeriodicTable import PeriodicTableDialog

from Simulations.Simulations import SimulationsInput, SimulationsOutput

from Containers.SimulationConfiguration import SimulationConfiguration
from Containers.Arguments import SimulationArguments, saveSimulationArguments, loadSimulationArguments
from Containers.GlobalDensity import GlobalDensity

# avoiding circular import, but still get type hinting functionality
if TYPE_CHECKING:
    from MainWindow import MainWindow


class SimulationPage(TabWithToolbar):
    """
    Class for all Simulation Page Classes
    """

    class RunStatus(Enum):
        """
        Possible status for SimulationPage
        """

        READY = auto()
        RUNNING = auto()
        DONE = auto()
        MISSING_PATHS = auto()
        ABORTED = auto()
        ERROR = auto()

    def __init__(self, main_window: MainWindow, simulation_configuration: SimulationConfiguration):
        """
        :param main_window: main window object
        :param simulation_configuration: specific simulation configuration
        """

        super().__init__()

        #
        # VARIABLES
        #

        self.main_window = main_window
        self.simulation_configuration = simulation_configuration

        # instance of simulation specific configuration class in folder 'Simulations'
        self.simulation_class = self.simulation_configuration.program_class()
        if not isinstance(self.simulation_class, SimulationsInput):
            exit('Provided simulation class is not a <SimulationsInput> class')
            # will never be reached, but useful for autocompletion in editor
            self.simulation_class = SimulationsInput()

        # style elements needed in evaluation class
        self.plot_vbox = VBoxTitleLayout(self, 'Outputs & plots', add_stretch=False)
        self.output_plot_view = MplCanvas()

        # instance of simulation specific evaluation class in folder 'Simulations'
        self.evaluation_class = self.simulation_configuration.evaluation_class(
            self.output_plot_view,
            self.simulation_class.element_data,
            self.plot_vbox
        )
        if not isinstance(self.evaluation_class, SimulationsOutput):
            exit('Provided evaluation class is not a <SimulationsOutput> class')
            # will never be reached, but useful for autocompletion in editor
            self.evaluation_class = SimulationsOutput(self.output_plot_view, self.simulation_class.element_data)

        if not self.simulation_configuration.base_save_folder:
            self.simulation_configuration.base_save_folder = f'{GlobalConf.save_path}/{self.simulation_class.SaveFolder}'
        self.run_status = SimulationPage.RunStatus.READY

        # update element data
        if not self.simulation_class.updateElements(self.simulation_configuration.folder, self.simulation_configuration.version) and not GlobalConf.skip_element_info:
            msg_box, _ = showMessageBox(
                self.main_window,
                QMessageBox.Icon.Warning,
                'Warning!',
                f'Unable to load simulation element data for {self.simulation_configuration.version}, using default element data from <b>SDTrimSP v6.01</b>',
                check_box_text='Do not show again'
            )
            if msg_box.checkBox().isChecked():
                GlobalConf.skip_element_info = True

        # general updates for simulation class
        self.simulation_class.update(
            self.simulation_configuration.folder,
            self.simulation_configuration.binary,
            self.simulation_configuration.version
        )

        # Dialog for periodic table
        self.periodic_table_dialog = PeriodicTableDialog(self.main_window)
        self.periodic_table_dialog.setElementData(self.simulation_class.element_data, self.simulation_class.element_data_default)
        self.dialog_source_row = None
        self.global_density = GlobalDensity()
        self.global_density_needed = False
        self.group_elements = self.simulation_class.GroupElements

        # Counter for components
        self.component_count = Counter(maximum=self.simulation_class.MaxComponents)

        # Output files and parameters
        self.previous_scroll_position = 0
        self.last_selected_output_file = ''
        self.selected_output_parameter = None

        # process for running simulation
        self.process = QProcess(self)
        self.process_log = ''
        self.setupProcess()

        #
        # TOOLBAR
        #

        # New
        self.action_new = self.toolbar.addAction(QIcon(':/icons/new.png'), 'New')
        self.action_new.setToolTip('<b>Reset</b> this simulation-tab and the input fields to their default states')
        self.action_new.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_N))
        self.action_new.triggered.connect(lambda: self.resetSettings())

        # Open
        self.action_open = self.toolbar.addAction(QIcon(':/icons/open.png'), 'Open')
        self.action_open.setToolTip('<b>Open</b> an existing simulation input setting')
        self.action_open.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_O))
        self.action_open.triggered.connect(lambda: self.loadSettings())  # self.loadSettings(from_json=False)

        # Import
        self.action_import = self.toolbar.addAction(QIcon(':/icons/convert.png'), 'Convert')
        self.action_import.setToolTip('<b>Convert</b> simulation input setting')
        self.action_import.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_I))
        self.action_import.triggered.connect(lambda: self.importSettings())

        # Save
        self.action_save = self.toolbar.addAction(QIcon(':/icons/save_new.png'), 'Save')
        self.action_save.setToolTip('<b>Save</b> the current settings of this simulation-tab to a simulation-tab input file')
        self.action_save.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_S))
        self.action_save.setEnabled(False)
        self.action_save.triggered.connect(lambda: self.saveSettings())

        # Save as
        self.action_save_as = self.toolbar.addAction(QIcon(':/icons/save_as.png'), 'Save as')
        self.action_save_as.setToolTip('<b>Save</b> the current settings of this simulation-tab under a different name and/or in a different location')
        self.action_save_as.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_S))
        self.action_save_as.setEnabled(False)
        self.action_save_as.triggered.connect(lambda: self.saveSettings(new_folder=True))

        # Separator
        self.toolbar.addSeparator()

        # Preferences
        self.action_preferences = self.toolbar.addAction(QIcon(':/icons/preferences.png'), 'Preferences')
        self.action_preferences.setToolTip('Open the <b>general settings</b> of this simulation configuration')
        self.action_preferences.setShortcut(QKeySequence.StandardKey.Preferences)
        self.action_preferences.triggered.connect(lambda: self.main_window.switchSettingsTab(self.simulation_configuration))

        # Separator
        self.toolbar.addSeparator()

        # Status
        self.pixmap_ok = QIcon(':/icons/okay.png').pixmap(32)
        self.pixmap_warning = QIcon(':/icons/warning.png').pixmap(32)
        self.pixmap_error = QIcon(':/icons/error.png').pixmap(32)
        self.run_status_icon = QLabel('')
        self.toolbar.addWidget(self.run_status_icon)
        self.run_status_text = QLabel('')
        self.toolbar.addWidget(self.run_status_text)

        # Separator
        self.toolbar.addSeparator()

        # Run
        self.action_run = self.toolbar.addAction(QIcon(':/icons/play.png'), 'Run')
        self.action_run.setToolTip('Save the current settings and <b>run the simulation</b> on the input file')
        self.action_run.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_R))
        self.action_run.triggered.connect(lambda: self.runSimulation())

        # Run progress bar
        self.run_progress = QProgressBar(self)
        self.run_progress.setToolTip('The progress of the simulation')
        self.run_progress.setMinimumWidth(50)
        self.run_progress.setMaximumWidth(400)
        self.toolbar.addWidget(self.run_progress)

        # Run abort
        self.action_abort = self.toolbar.addAction(QIcon(':/icons/abort.png'), 'Abort')
        self.action_abort.setToolTip('<b>Abort</b> the currently active simulation')
        self.action_abort.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_P))
        self.action_abort.setEnabled(False)
        self.action_abort.triggered.connect(lambda: self.process.kill())
        self.toolbar.addSeparator()

        # Run detached
        self.action_run_detached = self.toolbar.addAction(QIcon(':/icons/play_detached.png'), 'Run detached')
        self.action_run_detached.setToolTip('Save the current settings and <b>run the simulation</b> on the input file in detached mode.\nThe simulation is run in a separate window, and the GUI can be closed')
        self.action_run_detached.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_R))
        self.action_run_detached.triggered.connect(lambda: self.runSimulation(detached=True))

        # Separator
        self.toolbar.addSeparator()

        # Add empty space
        self.empty_space = QWidget()
        self.empty_space.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(self.empty_space)

        # Name of working directory
        self.toolbar.addWidget(QLabel('<b>Project: </b>'))
        self.working_dir = QLabel('unknown')
        self.toolbar.addWidget(self.working_dir)

        # Open working directory button
        self.open_working_dir = self.toolbar.addAction(QIcon(':/icons/open_workdir.png'), 'Open working directory')
        self.open_working_dir.setToolTip('Open the working directory in the file explorer')
        self.open_working_dir.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.simulation_configuration.save_folder)))

        # Open docs button
        self.action_open_documentation = self.toolbar.addAction(QIcon(':/icons/book.png'), 'Simulation documentation')
        self.action_open_documentation.setShortcut(QKeySequence.StandardKey.HelpContents)
        self.updateDocs()
        self.action_open_documentation.triggered.connect(self.openDocs)

        #
        # TAB WIDGET
        #

        self.tab_widget = QTabWidget(self)
        self.page.addWidget(self.tab_widget)

        #
        # TAB: 'Simulation setup'
        #

        self.settings_tab_splitter = QSplitter(self)
        self.settings_tab_splitter.setChildrenCollapsible(False)
        self.tab_widget.addTab(self.settings_tab_splitter, 'Simulation setup')

        self.composition_splitter = QSplitter(self)
        self.composition_splitter.setOrientation(Qt.Orientation.Vertical)
        self.settings_tab_splitter.addWidget(self.composition_splitter)

        #
        # BEAM SETTINGS
        self.settings_layout_beam = VBoxTitleLayout(self, 'Beam Settings', spacing=2, add_stretch=False)
        self.settings_group_layout_beam = QVBoxLayout()
        self.settings_group_layout_beam.setSpacing(5)
        self.settings_group_layout_beam.setContentsMargins(12, 0, 12, 0)

        # General beam settings
        self.general_beam_settings = self.simulation_class.HlBeamSettings(self.simulation_configuration.version)  # QHBoxLayout()
        self.settings_group_layout_beam.addLayout(self.general_beam_settings)

        # Beam composition title and composition
        self.beam_composition_vbox = VBoxTitleLayout(self, 'Beam composition', add_stretch=True)
        self.settings_group_layout_beam.addLayout(self.beam_composition_vbox)

        self.table_beam = CompTable(
            self,
            comp_count=self.component_count,
            row_fields=self.simulation_class.CompRowBeamSettings.rowFields,
            custom_comp_row=self.simulation_class.CompRowBeamSettings
        )
        self.beam_composition_vbox.addWidget(self.table_beam)

        # Add a parent to the settings layout and add that to the splitter
        self.settings_parent_beam = QWidget(self)
        self.settings_group_beam = QGroupBox(self)
        self.settings_group_beam.setLayout(self.settings_group_layout_beam)
        self.settings_layout_beam.addWidget(self.settings_group_beam)
        self.settings_parent_beam.setLayout(self.settings_layout_beam)
        self.composition_splitter.addWidget(self.settings_parent_beam)

        #
        # TARGET SETTINGS
        self.target_settings_vbox = VBoxTitleLayout(self, 'Target Settings', spacing=2, add_stretch=False)
        self.settings_group_layout_target = QVBoxLayout()
        self.settings_group_layout_target.setSpacing(5)
        self.settings_group_layout_target.setContentsMargins(12, 6, 12, 6)

        # General target settings
        self.general_target_settings = self.simulation_class.HlTargetSettings(self.simulation_configuration.version)  # QHBoxLayout()
        self.settings_group_layout_target.addLayout(self.general_target_settings)

        # Target composition + target layers preview
        self.target_composition_preview = QHBoxLayout()
        self.target_composition_vbox = VBoxTitleLayout(self, 'Target composition', add_stretch=True)
        self.target_composition_preview.addLayout(self.target_composition_vbox)

        self.table_target = CompTableTarget(
            self,
            comp_count=self.component_count,
            row_fields=self.simulation_class.CompRowTargetSettings.rowFields,
            custom_comp_row=self.simulation_class.CompRowTargetSettings
        )
        self.target_composition_vbox.addWidget(self.table_target)

        # Target preview
        self.target_preview_vbox = VBoxTitleLayout(self, 'Preview', add_stretch=50)
        self.target_composition_preview.addLayout(self.target_preview_vbox)
        self.settings_group_layout_target.addLayout(self.target_composition_preview)

        self.target_preview = TargetPreview(self)
        self.target_preview.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.target_preview_vbox.addWidget(self.target_preview)

        # Target layers
        self.target_structure_compounds = QHBoxLayout()
        self.target_structure_vbox = VBoxTitleLayout(self, 'Target structure', add_stretch=True)
        self.target_structure_compounds.addLayout(self.target_structure_vbox)

        self.target_layers = TargetLayersTable(self, 100, 100)
        self.target_structure_vbox.addWidget(self.target_layers)

        # Compounds
        self.compound_list = None
        if self.simulation_class.CompoundList:
            self.target_compound_vbox = VBoxTitleLayout(self, 'Compounds', add_stretch=50)
            self.target_structure_compounds.addLayout(self.target_compound_vbox)

            # Compound holder
            self.compound_list = CompoundList(
                self,
                compounds=self.simulation_class.CompoundList,
                table_beam=self.table_beam,
                table_target=self.table_target
            )
            self.compound_list.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
            self.target_compound_vbox.addWidget(self.compound_list)

        self.settings_group_layout_target.addLayout(self.target_structure_compounds)

        # Add a parent to the settings layout and add that to the splitter
        self.settings_parent_target = QWidget(self)
        self.settings_group_target = QGroupBox(self)
        self.settings_group_target.setLayout(self.settings_group_layout_target)
        self.target_settings_vbox.addWidget(self.settings_group_target)
        self.settings_parent_target.setLayout(self.target_settings_vbox)
        self.composition_splitter.addWidget(self.settings_parent_target)

        #
        # SIMULATION SETTINGS
        self.simulation_settings_vbox = VBoxTitleLayout(self, 'Simulation Settings', add_stretch=False)
        self.settings_group_layout_settings = self.simulation_class.VlSimulationSettings(self.simulation_configuration.version)  # QVBoxLayout()
        self.settings_group_layout_settings.setSpacing(5)

        # Additional settings
        self.additional_settings_vbox = VBoxTitleLayout(self, 'Additional Settings', add_stretch=False)
        self.check_settings_button = QPushButton(QIcon(':/icons/error_check.png'), '', self)
        self.check_settings_button.setMaximumWidth(50)
        self.check_settings_button.setToolTip('Check the settings for validity')
        self.check_settings_button.clicked.connect(lambda: self.checkAdditionalSettings())

        self.additional_settings_vbox.hl.addWidget(self.check_settings_button)
        self.additional_settings_vbox.setContentsMargins(0, 0, 0, 0)
        self.additional_settings = FileEditor(self, readonly=False, highlighting=False)
        self.additional_settings.setMinimumHeight(150)
        self.additional_settings.setPlaceholderText(f'Add additional settings here which will be appended to the input file\n\n{self.simulation_class.ExampleAdditionalSetting}')
        self.additional_settings.setToolTip('Additional lines of settings which are appended to the created input file')
        self.additional_settings.textChanged.connect(lambda: self.checkAdditionalSettings(silent=True))
        self.additional_settings_vbox.addWidget(self.additional_settings)

        self.settings_group_layout_settings.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.settings_group_layout_settings.addLayout(self.additional_settings_vbox)
        self.settings_group_layout_settings.addStretch(1)

        # Add a parent to the settings layout and add that to the splitter
        self.settings_parent_settings = QWidget(self)
        self.settings_scroll_area = QScrollArea(self)
        self.settings_group_settings = QGroupBox(self)
        self.settings_group_settings.setLayout(self.settings_group_layout_settings)
        self.settings_group_settings.setStyleSheet('QGroupBox { background-color: white; }')
        self.settings_scroll_area.setWidgetResizable(True)
        self.settings_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.settings_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.settings_scroll_area.setMinimumWidth(self.settings_group_settings.sizeHint().width() + self.settings_scroll_area.verticalScrollBar().sizeHint().width())
        self.settings_scroll_area.setStyleSheet('QScrollArea { border: none; }')
        self.settings_scroll_area.setWidget(self.settings_group_settings)
        self.simulation_settings_vbox.addWidget(self.settings_scroll_area)
        self.settings_parent_settings.setLayout(self.simulation_settings_vbox)
        self.settings_tab_splitter.addWidget(self.settings_parent_settings)

        #
        # TAB: 'File Preview'
        #

        self.file_preview_tab_splitter = QSplitter()
        self.tab_widget.addTab(self.file_preview_tab_splitter, 'Files preview')

        # Input File / Input Parameters
        self.parent_widget_file_input = QWidget(self)
        self.file_input_vbox = VBoxTitleLayout(self, 'INPUT', add_stretch=False)
        self.input_file_preview = FileEditor(self)
        self.file_input_vbox.addWidget(self.input_file_preview)
        self.parent_widget_file_input.setLayout(self.file_input_vbox)
        self.file_preview_tab_splitter.addWidget(self.parent_widget_file_input)

        # Layer File
        self.parent_widget_file_layer = QWidget(self)
        self.file_layer_vbox = VBoxTitleLayout(self, 'LAYER FILE', add_stretch=False)
        self.layer_file_preview = FileEditor(self)
        self.file_layer_vbox.addWidget(self.layer_file_preview)
        self.parent_widget_file_layer.setLayout(self.file_layer_vbox)
        self.file_preview_tab_splitter.addWidget(self.parent_widget_file_layer)

        #
        # TAB: 'Log files'
        #

        self.simulation_output = FileEditor(self, line_numbering=False, highlighting=False)
        self.simulation_output.setPlaceholderText('The output of the simulation process will be shown here.')
        self.tab_widget.addTab(self.simulation_output, 'Log files')

        #
        # TAB: 'Output files'
        #

        self.output_files_splitter = QSplitter()
        self.tab_widget.addTab(self.output_files_splitter, 'Output files')

        # List of output files
        self.parent_widget_output_list = QWidget(self)
        self.output_list_vbox = VBoxTitleLayout(self, 'List of files', add_stretch=False)
        self.refresh_output_files_button = QPushButton(QIcon(':/icons/refresh.png'), '', self)
        self.refresh_output_files_button.setMaximumWidth(50)
        self.refresh_output_files_button.setToolTip('Refresh the list')
        self.output_list_vbox.hl.addWidget(self.refresh_output_files_button)
        self.open_output_file_button = QPushButton(QIcon(':/icons/open_external.png'), '', self)
        self.open_output_file_button.setMaximumWidth(50)
        self.open_output_file_button.setToolTip('Open the selected file with the standard text editor')
        self.open_output_file_button.setEnabled(False)
        self.output_list_vbox.hl.addWidget(self.open_output_file_button)
        self.output_files_list = QListWidget(self)
        self.output_files_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.output_list_vbox.addWidget(self.output_files_list)
        self.parent_widget_output_list.setLayout(self.output_list_vbox)
        self.output_files_splitter.addWidget(self.parent_widget_output_list)

        # Preview of selected output file
        self.parent_widget_output_preview = QWidget(self)
        self.output_preview_vbox = VBoxTitleLayout(self, 'Output file preview', add_stretch=False)
        self.outputFilePreview = FileEditor(self)
        self.output_preview_vbox.addWidget(self.outputFilePreview)
        self.output_preview_line_count = SpinBox(
            default=100,
            input_range=(-5e3, 5e3),
        )
        self.layout_output_preview_line_count = InputHBoxLayout(
            'Previewed lines:',
            self.output_preview_line_count,
            checkbox=True,
            tooltip='Positive sign will show first lines, negative sign will show last lines. Disable if all lines should be visible'
        )
        self.layout_output_preview_line_count.checkbox.setMaximumWidth(120)
        self.layout_output_preview_line_count.checkbox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.output_preview_line_count.setMaximumWidth(50)
        self.output_preview_line_count.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.output_preview_vbox.hl.addLayout(self.layout_output_preview_line_count)
        self.parent_widget_output_preview.setLayout(self.output_preview_vbox)
        self.output_files_splitter.addWidget(self.parent_widget_output_preview)

        # division between columns
        self.output_files_splitter.setStretchFactor(0, 30)
        self.output_files_splitter.setStretchFactor(1, 70)

        #
        # TAB: 'Simulation results'
        #

        self.simulation_result_splitter = QSplitter()
        self.tab_widget.addTab(self.simulation_result_splitter, 'Simulation results')

        # Available data for plotting
        self.parent_widget_plot_list = QWidget(self)
        self.plot_list_vbox = VBoxTitleLayout(self, 'Available data for plotting', add_stretch=False)
        self.refresh_output_parameters_button = QPushButton(QIcon(':/icons/refresh.png'), '', self)
        self.refresh_output_parameters_button.setMaximumWidth(50)
        self.refresh_output_parameters_button.setToolTip('Refresh the list')
        self.plot_list_vbox.hl.addWidget(self.refresh_output_parameters_button)
        self.save_plot_button = QPushButton(QIcon(':/icons/save.png'), '', self)
        self.save_plot_button.setMaximumWidth(50)
        self.save_plot_button.setToolTip('Save the data of the selected plot')
        self.save_plot_button.clicked.connect(self.savePlot)
        self.plot_list_vbox.hl.addWidget(self.save_plot_button)
        self.output_parameters_list = ListWidget(self)
        self.output_parameters_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.plot_list_vbox.addWidget(self.output_parameters_list)
        self.parent_widget_plot_list.setLayout(self.plot_list_vbox)
        self.simulation_result_splitter.addWidget(self.parent_widget_plot_list)

        # Output and plots
        self.parent_widget_plot = QWidget(self)
        # self.plot_vbox = VBoxTitleLayout(self, 'Outputs & plots', add_stretch=False)  # already defined at the top
        self.plot_vbox.title.setMaximumHeight(20)
        # self.output_plot_view = MplCanvas()  # already set at the top
        self.output_plot_toolbar = NavigationToolbar2QT(self.output_plot_view, self)
        self.plot_vbox.addWidget(self.output_plot_view, stretch=1)
        self.plot_vbox.addWidget(self.output_plot_toolbar)
        self.plot_hbox = self.evaluation_class.HlPlot(self.simulation_configuration.version)
        self.plot_vbox.addLayout(self.plot_hbox)
        self.parent_widget_plot.setLayout(self.plot_vbox)
        self.simulation_result_splitter.addWidget(self.parent_widget_plot)

        # division between columns
        self.simulation_result_splitter.setStretchFactor(0, 40)
        self.simulation_result_splitter.setStretchFactor(1, 60)

        #
        # CONNECT SIGNALS
        #

        # Open periodic table when clicking select-element-button
        self.table_beam.elementClicked.connect(lambda row: self.openPeriodicTableDialog(row, typ='beam'))
        self.table_target.elementClicked.connect(lambda row: self.openPeriodicTableDialog(row, typ='target'))
        # Close periodic table
        self.periodic_table_dialog.finished.connect(self.periodicTableDialogClosed)

        # Update synced parameters for elements which occur both in the beam and the target
        self.table_target.syncableValueChanged.connect(self.table_beam.updateSyncedValue)
        self.table_target.syncableValueChanged.connect(self.table_target.updateSyncedValue)

        # Dis-/Enable certain inputs for elements in the beam also present in the target
        self.table_target.rowRemoved.connect(lambda: self.table_beam.updateSyncedFields(self.table_target.rows))
        self.table_target.rowRemoved.connect(lambda: self.table_target.updateSyncedFields(self.table_target.rows))
        self.table_target.elementChanged.connect(lambda: self.table_beam.updateSyncedFields(self.table_target.rows))
        self.table_target.elementChanged.connect(lambda: self.table_target.updateSyncedFields(self.table_target.rows))
        self.table_beam.elementChanged.connect(lambda: self.table_beam.updateSyncedFields(self.table_target.rows))
        self.table_beam.elementChanged.connect(lambda: self.table_beam.updateAllSyncedValues(self.table_target.rows))

        # Have a column in the target layers table for each element in the target composition table
        self.table_target.rowAdded.connect(self.target_layers.addElementColumn)
        self.table_target.rowRemoved.connect(lambda idx: self.target_layers.removeElementColumn(idx))

        # Update the target preview
        self.table_target.elementChanged.connect(lambda r, element: self.target_layers.renameElementColumn(self.table_target.rows.index(r), element.symbol))
        self.target_layers.layersChanged.connect(self.target_preview.setTargetInfo)
        self.general_target_settings.settingsChanged.connect(lambda dictionary: self.target_layers.setParameters(dictionary))
        self.general_target_settings.emit()

        # redirect emits between all input layouts
        connections = [
            self.general_beam_settings,
            self.table_beam,
            self.general_target_settings,
            self.table_target,
            self.settings_group_layout_settings,
            self.target_layers
        ]

        def updateConnections(dictionary):
            for c in connections:
                c.receive(dictionary)

        for connection in connections:
            connection.settingsChanged.connect(lambda dictionary: updateConnections(dictionary))

        # compounds
        if self.compound_list is not None:
            self.table_beam.elementChanged.connect(lambda: self.compound_list.elementChanged())
            self.table_beam.rowRemoved.connect(lambda: self.compound_list.elementChanged())
            self.table_target.elementChanged.connect(lambda: self.compound_list.elementChanged())
            self.table_target.rowRemoved.connect(lambda: self.compound_list.elementChanged())

        # global density
        self.general_target_settings.settingsChanged.connect(lambda dictionary: self.updateGlobalDensity(dictionary))
        self.target_layers.settingsChanged.connect(lambda dictionary: self.updateGlobalDensity(dictionary))

        # group elements
        self.settings_group_layout_settings.settingsChanged.connect(lambda dictionary: self.updateGroupElements(dictionary))

        # popups
        for connection in connections:
            connection.settingsChanged.connect(lambda dictionary: self.showPopup(dictionary))

        # update 'unsaved changes'
        for connection in connections:
            connection.contentChanged.connect(lambda: self.setEdited(True))
        self.additional_settings.textChanged.connect(lambda: self.setEdited(True))
        if self.compound_list is not None:
            self.compound_list.compoundChanged.connect(lambda: self.setEdited(True))

        # detect tab change
        self.tab_widget.currentChanged.connect(lambda tab: self.tabChange(tab))

        # output file preview
        self.output_files_list.itemSelectionChanged.connect(self.previewSelectedFile)
        self.output_preview_line_count.editingFinished.connect(self.updateOutputFilesList)
        self.layout_output_preview_line_count.checkbox.clicked.connect(self.updateOutputFilesList)
        self.refresh_output_files_button.clicked.connect(self.updateOutputFilesList)
        self.refresh_output_parameters_button.clicked.connect(self.updateOutputParametersList)
        self.open_output_file_button.clicked.connect(self.openSelectedOutputFile)

        # output parameters
        self.evaluation_class.hlChange.connect(self.plot_hbox.receive)
        self.plot_hbox.settingsChanged.connect(self.evaluation_class.receive)

        #
        # TIMERS
        #

        # timer for updates on the running simulation
        self.update_simulation_data = QTimer(self)
        self.update_simulation_data.timeout.connect(self.updateProgress)
        self.update_simulation_data.timeout.connect(self.updateOutputFilesList)
        self.update_simulation_data.timeout.connect(lambda: self.updateOutputParametersList(in_loop=True))

        #
        # STARTUP SETTINGS
        #

        # reset settings
        starting_save_folder = self.simulation_configuration.save_folder
        self.resetSettings()

        # open last settings
        if starting_save_folder:
            self.loadSettings(starting_save_folder)

    def tabChange(self, tab: int):
        """Executed when tabs ara changed"""

        if tab == 1:
            self.makePreview()
        elif tab == 3:
            self.updateOutputFilesList()
        elif tab == 4:
            self.updateOutputParametersList()

    def showPopup(self, value_dict: dict):
        """Shows a popup"""

        if value_dict.get('popup') is None:
            return

        popup_title = value_dict.get('popup_title')
        if popup_title is None:
            return

        popup_text = value_dict.get('popup_text')
        if popup_text is None:
            return

        popup_icon = value_dict.get('popup_icon')
        if popup_icon is None:
            popup_icon = QMessageBox.Icon.Information

        popup_info_message = value_dict.get('popup_info_message')
        if popup_info_message is None:
            popup_info_message = ''

        popup_detailed_message = value_dict.get('popup_detailed_message')
        if popup_detailed_message is None:
            popup_detailed_message = ''

        popup_hide = value_dict.get('popup_hide')
        popup_check_box_text = ''
        if isinstance(popup_hide, str):
            popup_check_box_text = 'Do not show again'

        if GlobalConf.getValue(popup_hide, default_value=True, type=bool) is False:
            return

        msg_box, _ = showMessageBox(
            self,
            popup_icon,
            popup_title,
            popup_text,
            info_message=popup_info_message,
            detailed_message=popup_detailed_message,
            check_box_text=popup_check_box_text
        )
        if msg_box.checkBox() is not None and msg_box.checkBox().isChecked() and isinstance(popup_hide, str):
            GlobalConf.setValue(popup_hide, False)

    def setupProcess(self):
        """Connects all process signals"""

        self.process.started.connect(self.processStarted)
        self.process.readyRead.connect(self.processReadyRead)
        self.process.errorOccurred.connect(self.processError)
        self.process.finished.connect(self.processFinished)

    def openPeriodicTableDialog(self, row: CompRow, typ: str):
        """
        Opens simulation specific periodic table

        :param row: row where select element button was pressed
        :param typ: 'beam' or 'target'
        """

        self.dialog_source_row = row

        existing_elements = []
        if self.group_elements:
            rows = []
            if typ == 'beam':
                rows = self.table_beam.rows
            elif typ == 'target':
                rows = self.table_target.rows

            for row in rows:
                existing_elements.append(row.element)

        self.periodic_table_dialog.openDialog(self.dialog_source_row.element, existing_elements)

    def periodicTableDialogClosed(self, return_element):
        """
        Function called when periodic table is closed. Sets element in row where select element button was pressed

        :param return_element: selected element or 0 if no element was selected
        """

        if return_element > 0:
            self.dialog_source_row.setElement(self.periodic_table_dialog.isotope)

    def updateGlobalDensity(self, value_dict: dict):
        """
        Updates global density if needed

        :param value_dict: dictionary of updated settings
        """

        desired_density = value_dict.get('global_density')
        if desired_density is not None:
            if isinstance(desired_density, float):
                self.global_density_needed = True
                self.global_density.updateDensity(desired_density)
            else:
                if self.global_density_needed:
                    self.table_target.receive({
                        'atomic_global_density': False
                    })
                self.global_density_needed = False

        if not self.global_density_needed:
            return

        abundances = value_dict.get('first_abundances')
        if abundances is not None:
            self.global_density.updateAbundances(abundances)

        args = self.table_target.getArguments()
        if args:
            self.global_density.updateElements([arg.element for arg in args])

        if any([arg.element.symbol != '' for arg in args]):
            self.table_target.receive({
                'atomic_global_density': self.global_density.atomicDensity()
            })

    def updateGroupElements(self, value_dict: dict):
        """
        Updates grouping of elements if needed

        :param value_dict: dictionary of updated settings
        """

        group_elements = value_dict.get('group_elements')
        if isinstance(group_elements, bool):
            self.group_elements = group_elements

    def openDocs(self):
        """Opens documentation pdf-file for simulation"""

        docs_path = self.simulation_class.getDoc(
            self.simulation_configuration.folder,
            self.simulation_configuration.binary,
            self.simulation_configuration.version
        )

        # no documentation available, and no download provided
        if docs_path is False:
            self.updateDocs(disable=True)

        # no documentation available, but download provided
        elif docs_path is True:
            self.simulation_class.downloadDoc(
                self,
                self.simulation_configuration.folder,
                self.simulation_configuration.binary,
                self.simulation_configuration.version
            )

        # try to open documentation
        elif not docs_path or not QFile(docs_path).exists() or not QDesktopServices.openUrl(QUrl.fromUserInput(docs_path)):
            self.updateDocs(disable=True)

    def updateDocs(self, disable: bool = False):
        """
        Updates 'open documentation' docs

        :param disable: if True disables 'open documentation' button
        """

        doc_path = self.simulation_class.getDoc(
            self.simulation_configuration.folder,
            self.simulation_configuration.binary,
            self.simulation_configuration.version,
        )

        if disable or not doc_path:
            self.action_open_documentation.setEnabled(False)
            self.action_open_documentation.setToolTip('No simulation documentation can be found')
        else:
            self.action_open_documentation.setEnabled(True)
            self.action_open_documentation.setToolTip('Open the simulation documentation PDF with the standard PDF viewer')

    def runSimulation(self, detached: bool = False):
        """
        Executes the simulation based on input file (and layer file if provided)

        :param detached: (optional) if simulation should run in a detached window
        """

        # save files
        input_files = self.saveSettings()
        if not input_files:
            return
        input_file = input_files[1]

        # delete all files except input files
        files = []
        for file in QDir(self.simulation_configuration.save_folder).entryInfoList(filters=QDir.Filter.Files):
            file_name = file.fileName()
            if not inFileList(file_name, input_files):
                files.append(file)

        if files and not GlobalConf.skip_delete_info:
            msg_box, result = showMessageBox(
                self,
                QMessageBox.Icon.Information,
                'Attention!',
                'Files in the working directory will be deleted',
                info_message=f'In order to run the simulation, all non-input files in the working directory<br><br>{self.simulation_configuration.save_folder}<br><br>will be deleted automatically.',
                detailed_message='Affected files:\n\n' + '\n'.join([file.fileName() for file in files]),
                standard_buttons=QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                check_box_text='Do not show again'
            )
            if result == QMessageBox.StandardButton.Cancel:
                return
            if msg_box.checkBox().isChecked():
                GlobalConf.skip_delete_info = True

        for file in files:
            QFile(file.filePath()).remove()

        # change working directory
        chdir(self.simulation_configuration.save_folder)

        self.simulation_output.clear()
        self.output_files_list.clear()
        self.output_parameters_list.clear()
        self.evaluation_class.reset()

        qcmd, qpipe, cmd = self.simulation_class.cmd(
            self.simulation_configuration.binary,
            self.simulation_configuration.save_folder,
            input_file,
            self.simulation_configuration.version
        )

        if not detached:
            self.setProcessWidgetsEnabled(False)
            self.run_progress.setValue(0)
            self.update_simulation_data.start(1000)

            # reset process
            self.process = QProcess(self)
            self.setupProcess()

            # pipe in file if needed
            if qpipe:
                self.process.setStandardInputFile(f'{self.simulation_configuration.save_folder}/{input_file}')
            self.process.start(qcmd)

        else:
            if system() == 'Windows':
                cmd = f'start /wait cmd /k "{cmd}"'
                Popen(cmd, shell=True)

            elif system() in ['Linux', 'Darwin']:
                terminal_cmds = [
                    f'gnome-terminal -t {self.simulation_configuration.title} -- bash -c \'{cmd}; exec bash\'',
                    f'xterm -T {self.simulation_configuration.title} -e bash -c \'{cmd}; exec bash\'',
                    f'guake --show --rename-tab={self.simulation_configuration.title} -e \'{cmd}; exec bash\'',
                    f'konsole -p tabtitle="{self.simulation_configuration.title}" -e bash -c \'{cmd}; exec bash\'',
                    f'terminator -T {self.simulation_configuration.title} -e \'{cmd}; exec bash\''
                ]
                checking_cmds = [
                    'command -v ',
                    'type ',
                    'hash '
                ]

                for terminal_cmd in terminal_cmds:
                    # check if command is found
                    if any([getstatusoutput(f'{checking_cmd}{terminal_cmd.split(" ")[0]}')[0] for checking_cmd in checking_cmds]):
                        continue
                    Popen(terminal_cmd, shell=True)
                    break

                else:
                    Popen(cmd, shell=True)

            else:
                self.main_window.writeStatusBar(f'OS {system()} not supported in detached mode')
                return

            self.main_window.writeStatusBar(f'Detached simulation {self.simulation_configuration.title} started')

    def setEdited(self, state: bool = True):
        """Sets edited status"""

        self.action_save.setEnabled(state)
        self.simulation_configuration.unsaved_changes = state
        self.main_window.simChanged(self.simulation_configuration)

    def resetSettings(self):
        """Reset Settings to default"""

        if self.simulation_configuration.running:
            return

        if self.simulation_configuration.unsaved_changes:
            _, result = showMessageBox(
                self,
                QMessageBox.Icon.Information,
                'Attention!',
                'The document has been modified',
                info_message=f'Do you want to save your changes?',
                standard_buttons=QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
            )

            if result == QMessageBox.StandardButton.Cancel:
                return

            elif result == QMessageBox.StandardButton.Save:
                if not self.saveSettings():
                    return

        self.action_save_as.setEnabled(False)
        self.action_save.setEnabled(False)

        # reset save folder
        self.simulation_configuration.save_folder = ''
        self.working_dir.setText('unknown')

        # reset parameter lists
        self.updateOutputFilesList()
        self.updateOutputParametersList()
        self.evaluation_class.clearPlotWindow()

        # reset tables
        self.target_layers.resetTable()
        self.table_beam.resetTable()
        self.table_target.resetTable()

        # add first rows
        self.table_beam.addRow()
        self.table_target.addRow()
        self.target_layers.addRow()
        # somehow the resize of the target layer table does not work, therefore this fix is needed
        QTimer.singleShot(0, self.target_layers.resizeTable)

        # reset other settings
        self.general_beam_settings.reset()
        self.general_target_settings.reset()
        self.settings_group_layout_settings.reset()
        self.additional_settings.setPlainText('')

        # set run status
        self.setRunStatus(SimulationPage.RunStatus.READY)
        self.setEdited(False)

    def loadSettings(self, path: Union[str, bool] = False, from_json: bool = True, unsaved_warning: bool = True) -> bool:
        """Loads settings and returns if it was successful"""

        # check for unsaved changes
        if self.simulation_configuration.unsaved_changes and unsaved_warning:
            _, result = showMessageBox(
                self,
                QMessageBox.Icon.Information,
                'Attention!',
                'The document has been modified',
                info_message=f'Do you want to save your changes?',
                standard_buttons=QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
            )

            if result == QMessageBox.StandardButton.Cancel:
                return False

            elif result == QMessageBox.StandardButton.Save:
                if not self.saveSettings():
                    return False

        # check if provided path should be loaded
        if isinstance(path, str):
            if not QDir().exists(path):
                showMessageBox(
                    self,
                    QMessageBox.Icon.Warning,
                    'Error!',
                    'Invalid file path',
                    f'Input file path "{path}" does not exist'
                )
                return False
            self.simulation_configuration.save_folder = path

        else:
            # create base save folder if it does not exist
            QDir().mkpath(self.simulation_configuration.base_save_folder)

            file = selectFileDialog(
                self,
                False,
                f'Load input file "{self.simulation_class.InputFilename}"',
                self.simulation_configuration.base_save_folder,
                file_filter=f'Input files ({self.simulation_class.InputFilename})'
            )
            folder = QFileInfo(file).canonicalPath()

            if len(folder) == 0:
                self.main_window.writeStatusBar('Loading aborted')
                return False
            self.simulation_configuration.save_folder = folder

        # name of save folder
        save_folder_parts = self.simulation_configuration.save_folder.split('/')
        if save_folder_parts:
            self.working_dir.setText(f'{save_folder_parts[-1]}')

        # update parameter lists
        self.updateOutputFilesList()
        self.updateOutputParametersList()

        # try to get input files
        arguments: Union[bool, str, SimulationArguments] = False
        json_loaded = False
        if from_json:
            arguments = loadSimulationArguments(f'{self.simulation_configuration.save_folder}/input.json')
            if arguments:
                json_loaded = True

        if not arguments:
            load_result = self.simulation_class.loadFiles(
                self.simulation_configuration.save_folder,
                self.simulation_configuration.version
            )
            if isinstance(load_result, tuple):
                arguments, error_list = load_result
                if error_list:
                    showMessageBox(
                        self,
                        QMessageBox.Icon.Information,
                        'Information!',
                        'Problems while loading input file',
                        f'The following problems occurred while trying to load files from "{self.simulation_configuration.save_folder}"',
                        detailed_message='\n'.join(error_list),
                        expand_details=True
                    )
            elif isinstance(load_result, str):
                arguments = load_result
        if not arguments:
            showMessageBox(
                self,
                QMessageBox.Icon.Information,
                'Information!',
                'Input files could not be read',
                'There are either no input files present, or the chosen simulation does not support the present input files. Try to open the input files with the corresponding simulation selected and copy the generated "input.json" file.'
            )
            return False
        if isinstance(arguments, str):
            showMessageBox(
                self,
                QMessageBox.Icon.Information,
                'Information!',
                'Input files could not be read',
                'There are either no input files present, or the chosen simulation does not support the present input files. Try to open the input files with the corresponding simulation selected and copy the generated "input.json" file.'
            )
            return False

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        # reset beam, target and layer tables
        self.target_layers.resetTable()
        self.table_target.resetTable()
        self.table_beam.resetTable()

        load_error = []
        load_error += self.general_beam_settings.loadArguments(arguments)
        load_error += self.general_target_settings.loadArguments(arguments)
        load_error += self.settings_group_layout_settings.loadArguments(arguments)

        # fill simulation with loaded arguments
        element_data = self.simulation_class.element_data

        # fill rows in order
        if json_loaded:
            for _, row in sorted(zip([row.index for row in arguments.beam_rows + arguments.target_rows], arguments.beam_rows + arguments.target_rows)):
                if row in arguments.beam_rows:
                    self.table_beam.setArguments([row], arguments, element_data, False)
                else:
                    self.table_target.setArguments([row], arguments, element_data, False)

            self.table_beam.connectRows()
            self.table_beam.limitColumns()
            self.table_target.connectRows()
            self.table_target.limitColumns()

        else:
            self.table_beam.setArguments(arguments.beam_rows, arguments, element_data)
            self.table_target.setArguments(arguments.target_rows, arguments, element_data)

        self.target_layers.setArguments(arguments.structure)
        # somehow the resize of the target layer table does not work, therefore this fix is needed
        QTimer.singleShot(0, self.target_layers.resizeTable)
        self.additional_settings.setPlainText('\n'.join(arguments.additional))
        if self.compound_list is not None:
            self.compound_list.setCompounds([compound.name_save for compound in arguments.settings.compounds])

        self.makePreview()
        self.setEdited(False)
        self.action_save_as.setEnabled(True)
        self.action_save.setEnabled(True)
        self.evaluation_class.reset()
        self.updateOutputParametersList()
        QApplication.restoreOverrideCursor()
        self.main_window.writeStatusBar('Input files loaded')

    def importSettings(self) -> bool:
        """Imports settings and returns if it was successful"""

        # select import file
        import_file = selectFileDialog(
            self,
            False,
            f'Load input file "input.json"',
            GlobalConf.save_path,
            file_filter=f'Import file (input.json)'
        )

        if import_file is None:
            self.main_window.writeStatusBar('Import aborted')
            return False

        # select folder where imported file should be saved
        QDir().mkpath(self.simulation_configuration.base_save_folder)

        result = None
        folder = ''
        while result != QMessageBox.StandardButton.Yes:
            folder = QFileDialog.getExistingDirectory(
                self,
                'Select the folder where the imported files should be saved',
                self.simulation_configuration.base_save_folder
            )

            if len(folder) == 0:
                self.main_window.writeStatusBar('Import aborted')
                return False

            # check if folder contains no files
            if not any([file_info.isFile() for file_info in QDir(folder).entryInfoList()]):
                break

            _, result = showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                'This folder already contains files',
                info_message=f'Do you want to save the settings in\n"{folder}"?',
                standard_buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

        self.simulation_configuration.save_folder = folder

        # copy input.json file
        save_file_json = f'{self.simulation_configuration.save_folder}/input.json'
        if QFile.exists(save_file_json):
            QFile.remove(save_file_json)
        QFile().copy(import_file, save_file_json)
        self.main_window.writeStatusBar('Import successful')

        # open file
        self.loadSettings(self.simulation_configuration.save_folder)

    def saveSettings(self, new_folder: bool = False) -> Union[List[str], bool]:
        """
        Saves settings and return list of created input files successful or False if not

        :param new_folder: create a new folder
        """

        old_save_folder = self.simulation_configuration.save_folder
        arguments, input_text, layer_text = self.makePreview()

        # file names to input files
        file_name_input = self.simulation_class.nameInputFile(arguments, self.simulation_configuration.version)
        file_name_layer = self.simulation_class.nameLayerFile(arguments, self.simulation_configuration.version)

        # check all compound data has been inserted
        if not self.table_beam.allRowsHaveData() or not self.table_target.allRowsHaveData():
            showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                'All elements must be defined in order to save the input file'
            )
            return False

        # create base save folder if it does not exist
        QDir().mkpath(self.simulation_configuration.base_save_folder)

        # check if save_folder exists if set
        if self.simulation_configuration.save_folder:
            if not QDir(self.simulation_configuration.save_folder).exists():
                self.simulation_configuration.save_folder = ''

        # check if save folder is set and let user set it if it does not exist
        if not self.simulation_configuration.save_folder or new_folder:
            result = None
            folder = ''
            while result != QMessageBox.StandardButton.Yes:
                folder = QFileDialog.getExistingDirectory(
                    self,
                    'Select the folder where the files will be saved',
                    self.simulation_configuration.base_save_folder
                )

                if len(folder) == 0:
                    self.main_window.writeStatusBar('Saving aborted')
                    return False

                # check if folder contains no files
                if not any([file_info.isFile() for file_info in QDir(folder).entryInfoList()]):
                    break

                _, result = showMessageBox(
                    self,
                    QMessageBox.Icon.Warning,
                    'Warning!',
                    'This folder already contains files',
                    info_message=f'Do you want to save the settings in\n"{folder}"?',
                    standard_buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

            self.simulation_configuration.save_folder = folder

        # copy all files into new folder
        if new_folder:
            files_info = QDir(old_save_folder).entryInfoList()
            for file_info in files_info:
                QFile(file_info.canonicalFilePath()).copy(f'{self.simulation_configuration.save_folder}/{file_info.fileName()}')

        # save json simulation output
        saveSimulationArguments(arguments, f'{self.simulation_configuration.save_folder}/input.json')
        filelist = ['input.json', file_name_input]

        # save input and layer input (or remove if not needed)
        path_input = f'{self.simulation_configuration.save_folder}/{file_name_input}'
        path_layer = f'{self.simulation_configuration.save_folder}/{file_name_layer}'
        with open(path_input, 'w') as file:
            file.write(input_text)

        if layer_text is not False:
            with open(path_layer, 'w') as file:
                file.write(layer_text)
            filelist.append(file_name_layer)

        elif QFile(path_layer).exists():
            QFile(path_layer).remove()

        # open file
        if new_folder:
            self.loadSettings(self.simulation_configuration.save_folder, unsaved_warning=False)

        # update wording directory text
        save_folder_parts = self.simulation_configuration.save_folder.split('/')
        self.working_dir.setText(f'{save_folder_parts[-1]}')

        # enable save as option
        self.action_save_as.setEnabled(True)
        self.action_save.setEnabled(False)

        self.setEdited(False)
        self.main_window.writeStatusBar('Saving successful')

        return filelist

    def makePreview(self):
        """
        Makes preview of the input and layer file

        :return: input_file as string, layer_file as string if should be created or False
        """

        arguments = self.makeArguments()
        input_file = self.simulation_class.makeInputFile(arguments, self.simulation_configuration.folder, self.simulation_configuration.version)
        layer_file = self.simulation_class.makeLayerFile(arguments, self.simulation_configuration.folder, self.simulation_configuration.version)
        create_layer_file = True
        if not layer_file:
            layer_file = '(-- FILE WILL NOT BE CREATED --)'
            create_layer_file = False

        self.input_file_preview.setPlainText(input_file)
        self.layer_file_preview.setPlainText(layer_file)

        return arguments, input_file, layer_file if create_layer_file else False

    def makeArguments(self) -> SimulationArguments:
        """Returns <SimulationArguments> container with current parameters"""

        simulation = self.simulation_class.Name

        beam_args = self.general_beam_settings.getArguments()
        beam_rows = self.table_beam.getArguments()
        target_args = self.general_target_settings.getArguments()
        target_rows = self.table_target.getArguments()
        structure = self.target_layers.getArguments()
        settings = self.settings_group_layout_settings.getArguments()
        if self.compound_list is not None:
            settings.compounds = self.compound_list.getCompounds()

        additional = self.additional_settings.toPlainText().split('\n')

        arguments = SimulationArguments(
            simulation=simulation,
            beam_args=beam_args,
            beam_rows=beam_rows,
            target_args=target_args,
            target_rows=target_rows,
            structure=structure,
            settings=settings,
            additional=additional
        )

        return arguments

    def checkAdditionalSettings(self, silent: bool = False):
        """Checks additional settings from the user"""

        additional = self.additional_settings.toPlainText()
        errors = self.simulation_class.checkAdditional(additional, self.simulation_configuration.version)

        setWidgetHighlight(self.additional_settings, bool(errors))

        if not errors:
            if not silent:
                showMessageBox(
                    self,
                    QMessageBox.Icon.Information,
                    'Valid!',
                    'No problems with the additional settings detected.'
                )
            return

        if not silent:
            showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                'Problems with settings detected.',
                info_message='Some settings appear multiple times, or there are unknown or invalid ones.\nNote that multiple occurring settings overwrite previous ones.',
                detailed_message='\n'.join(errors),
                expand_details=True
            )

    def isClosable(self) -> bool:
        """Returns if this simulation page can be closed: no unsaved changes and no simulation running"""

        return not (self.simulation_configuration.running or self.simulation_configuration.unsaved_changes)

    def setRunStatus(self, status: SimulationPage.RunStatus):
        """
        Change run status of simulation page

        :param status: status of page
        """

        self.run_status = status
        # assuming status = SimulationPage.RunStatus.READY
        text = 'Ready!'
        tooltip = 'Everything is set up and ready for the simulation'
        pixmap = self.pixmap_ok
        color_style = Styles.green

        # set running state
        self.simulation_configuration.running = (status == SimulationPage.RunStatus.RUNNING)
        self.main_window.simChanged(self.simulation_configuration)

        if status == SimulationPage.RunStatus.RUNNING:
            text = 'Running...'
            tooltip = 'The simulation is currently running'
        elif status == SimulationPage.RunStatus.DONE:
            text = 'Done!'
            tooltip = 'The simulation has successfully finished'
        elif status == SimulationPage.RunStatus.MISSING_PATHS:
            text = 'Missing paths'
            pixmap = self.pixmap_warning
            color_style = Styles.orange
            tooltip = 'One or more of the following paths are not set up:\n  - folder directory\n  - simulation binary'
        elif status == SimulationPage.RunStatus.ABORTED:
            text = 'Aborted'
            pixmap = self.pixmap_error
            color_style = Styles.red
            tooltip = 'The process was aborted on purpose'
        elif status == SimulationPage.RunStatus.ERROR:
            text = 'ERROR'
            pixmap = self.pixmap_error
            color_style = Styles.red
            tooltip = 'Something went wrong with the simulation\nCheck the "Simulation log" tab for more info'

        self.run_status_text.setText(text)
        self.run_status_icon.setPixmap(pixmap)
        self.run_status_text.setStyleSheet(Styles.status_text_style + color_style)
        self.run_status_text.setToolTip(tooltip)

    def processStarted(self):
        """Called when process of simulation is started"""

        self.process_log = ''
        self.main_window.writeStatusBar(f'{self.simulation_class.Name} Simulation running...', visible_time=0)
        self.setRunStatus(SimulationPage.RunStatus.RUNNING)

    def processReadyRead(self):
        """Called when process has new readable data"""

        process_log = self.process_log = bytes(self.process.readAll()).decode(getpreferredencoding(), 'ignore')
        # Remove trailing newlines
        self.simulation_output.appendPlainText(process_log.rstrip())

    def processError(self, error):
        """Called when process runs into an error"""

        errors = {
            0: 'QProcess::FailedToStart',
            1: 'QProcess::Crashed',
            2: 'QProcess::Timed out',
            3: 'QProcess::WriteError',
            4: 'QProcess::ReadError',
            5: 'QProcess::UnknownError'
        }
        error = errors.get(error)

        self.main_window.writeStatusBar(f'{self.simulation_configuration.program_name} ERROR: {error}')
        self.simulation_output.appendPlainText(f'\n\nAn error occurred: {error}')
        self.setRunStatus(SimulationPage.RunStatus.ERROR)

        self.setProcessWidgetsEnabled(True)
        self.stopSimulationTimer()

    def processFinished(self, exit_code: int, exit_status: int):
        """Called when process has finished"""

        # check if there were errors in log
        log = self.simulation_output.toPlainText()
        if 'stop from subroutine' in log or exit_code == 66:
            exit_status = -1

        if exit_status == QProcess.ExitStatus.NormalExit:
            result = 'finished'
            status = SimulationPage.RunStatus.DONE
        elif exit_status == QProcess.ExitStatus.CrashExit:
            result = 'aborted'
            status = SimulationPage.RunStatus.ABORTED
        else:
            result = f'error with exit code: {exit_code}'
            status = SimulationPage.RunStatus.ERROR

        self.main_window.writeStatusBar(f'{self.simulation_configuration.program_name} simulation {result}')
        self.setRunStatus(status)

        self.setProcessWidgetsEnabled(True)
        self.stopSimulationTimer()

    def setProcessWidgetsEnabled(self, enabled):
        """Enable or disable actions which depend on the state of the process"""

        self.action_new.setEnabled(enabled)
        self.action_open.setEnabled(enabled)
        self.action_import.setEnabled(enabled)
        self.action_save.setEnabled(enabled)
        self.action_save_as.setEnabled(enabled)
        self.action_run.setEnabled(enabled)
        self.action_run_detached.setEnabled(enabled)
        self.action_abort.setEnabled(not enabled)

    def stopSimulationTimer(self):
        """Stops the simulation timer"""

        self.update_simulation_data.stop()
        self.run_progress.setValue(100)
        self.updateOutputFilesList()
        self.updateOutputParametersList(forced=True, in_loop=True)

    def updateProgress(self):
        """Update the progress bar"""

        percent = self.simulation_class.getProgress(
            self.simulation_configuration.save_folder,
            self.process_log,
            self.simulation_configuration.version
        )
        if percent >= 0:
            self.run_progress.setValue(percent)

    def updateOutputFilesList(self):
        """Update list of output files"""

        # Only update if simulation tab is active
        if not self.simulation_configuration.is_active:
            return

        # Only update if the tab is actually visible
        if self.tab_widget.currentIndex() != 3:
            return

        if not self.simulation_configuration.save_folder:
            self.output_files_list.clear()
            return

        # Save the currently selected entry of the output list
        selected_output_file = None
        selected_items = self.output_files_list.selectedItems()
        if selected_items:
            selected_output_file = selected_items[0].text()
            self.previous_scroll_position = self.outputFilePreview.verticalScrollBar().value()

        self.output_files_list.clear()

        # Get files in working directory
        skipped_files = ['input.json']
        skipped_files.extend(self.simulation_class.SkipList)

        for file in QDir(self.simulation_configuration.save_folder).entryInfoList(filters=QDir.Filter.Files):
            file_name = file.fileName()
            if inFileList(file_name, skipped_files):
                continue

            self.output_files_list.addItem(file.fileName())
            item = self.output_files_list.item(self.output_files_list.count() - 1)

            tooltip = inFileDict(file.fileName(), self.simulation_class.OutputTooltips)
            if tooltip is not False:
                item.setToolTip(tooltip[1])

            # Keep the previous selection
            if item.text() == selected_output_file:
                self.output_files_list.setCurrentItem(item)

    def previewSelectedFile(self):
        """Preview the selected file"""

        if self.outputFilePreview.verticalScrollBar().isSliderDown():
            return

        selected_items = self.output_files_list.selectedItems()
        if not selected_items:
            self.open_output_file_button.setEnabled(False)
            self.outputFilePreview.clear()
            return

        file_path = f'{self.simulation_configuration.save_folder}/{selected_items[0].text()}'
        if not QFile(file_path).exists():
            self.outputFilePreview.clear()
            self.main_window.writeStatusBar(f'Failed to preview file "{file_path}"')
            self.open_output_file_button.setEnabled(False)
            self.outputFilePreview.setPlainText('(-- FILE DOES NOT EXIST, PLEASE REFRESH LIST OF FILES --)')
            return

        self.outputFilePreview.updateOffset(0)
        with open(file_path, 'r') as file:
            file_content = file.read()
        line_limit = 0
        if self.layout_output_preview_line_count.checkbox.isChecked():
            line_limit = self.output_preview_line_count.value()

        if not file_content:
            file_content = '(-- EMPTY FILE --)'

        # limit the maximum lines in the preview to the set number
        elif line_limit > 0:
            file_content = file_content.split('\n')
            file_content_length = len(file_content)
            file_content = '\n'.join(file_content[:line_limit])
            if file_content_length > line_limit:
                file_content += '\n\n(-- END OF PREVIEW --)'

        elif line_limit < 0:
            file_content = file_content.split('\n')
            file_content_length = len(file_content)
            file_content_text = ''
            if file_content_length > -line_limit:
                file_content_text = '(-- START OF PREVIEW --)\n\n'
                self.outputFilePreview.updateOffset(file_content_length + line_limit - 2)
            file_content_text += '\n'.join(file_content[line_limit:])
            file_content = file_content_text

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        # self.outputFilePreview.setPlainText(file_content)
        # delete old text and append new text is faster than overwriting with new text
        self.outputFilePreview.setPlainText('')
        self.outputFilePreview.appendPlainText(file_content)
        QApplication.restoreOverrideCursor()

        if self.last_selected_output_file == selected_items[0].text():
            self.outputFilePreview.verticalScrollBar().setValue(self.previous_scroll_position)
        self.last_selected_output_file = selected_items[0].text()
        self.open_output_file_button.setEnabled(True)

    def openSelectedOutputFile(self):
        """Opens the selected output file"""

        file_path = f'{self.simulation_configuration.save_folder}/{self.output_files_list.selectedItems()[0].text()}'
        if not QFile.exists(file_path) or not QDesktopServices.openUrl(QUrl.fromUserInput(file_path)):
            self.main_window.writeStatusBar(f'Failed to open file "{file_path}"')

    def updateOutputParametersList(self, forced: bool = False, in_loop: bool = False):
        """
        Updates the output parameter list

        :param forced: forces update
        :param in_loop: if called during simulation running-loop
        """

        if not forced:
            # Only update if simulation tab is active
            if not self.simulation_configuration.is_active:
                return

            # only update if the tab is actually visible
            if self.tab_widget.currentIndex() != 4:
                return

        # save the currently selected entry of the list
        self.selected_output_parameter = None
        selected_items = self.output_parameters_list.selectedItems()
        if selected_items:
            self.selected_output_parameter = selected_items[0].text()

        # clear parameter list and plot window
        self.output_parameters_list.clear()
        if not QDir().exists(self.simulation_configuration.save_folder):
            return
        self.evaluation_class.listParameters(self.simulation_configuration.save_folder, self.output_parameters_list)

        # only reset plot window if not in loop
        if not in_loop:
            self.evaluation_class.clearPlotWindow()

        # reselect item
        for i in range(self.output_parameters_list.count()):
            if self.output_parameters_list.item(i).text() == self.selected_output_parameter:
                self.output_parameters_list.setCurrentRow(i)
                break

    def savePlot(self):
        """Saves active plot"""

        selected_items = self.output_parameters_list.selectedItems()
        if not selected_items:
            self.main_window.writeStatusBar('No plot selected - aborted')
            return

        title = selected_items[0].text()
        title = sub(r'\(.*?\)', '', title)  # delete brackets
        title = title.strip().replace(' ', '_')  # no spaces
        title = alphanumeric(title)  # only alphanumeric characters
        plot_data = self.evaluation_class.getReturnData()
        if plot_data is None:
            self.main_window.writeStatusBar(f'No plot data provided - aborted')
            return

        file_path = selectFileDialog(self,
                                     True,
                                     'Save plot data as...',
                                     f'{self.simulation_configuration.save_folder}/{title}.txt',
                                     'Text files (*.txt)')
        if file_path is None:
            self.main_window.writeStatusBar('No file selected - aborted')
            return

        with open(file_path, 'w') as file:
            file.write(plot_data)

        self.main_window.writeStatusBar(f'Plot data saved as "{file_path}"')
