from __future__ import annotations
from typing import Any, Dict, List, Literal, Union, Optional, Tuple, TYPE_CHECKING
from enum import Enum, auto
from platform import system
from os import chdir
from pathlib import Path
from shutil import copy2
from sys import exit
from locale import getpreferredencoding
from re import sub, findall
from subprocess import Popen, getstatusoutput
import subprocess
import logging


from PyQt6.QtCore import Qt, QUrl, QProcess, QTimer
from PyQt6.QtGui import QKeySequence, QDesktopServices
from PyQt6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QTabWidget, QSplitter, QVBoxLayout, QGroupBox, QSizePolicy, QPushButton,
    QListWidget, QAbstractItemView, QMessageBox, QFileDialog, QScrollArea, QApplication, QComboBox, QStackedWidget,
    QTableWidget, QHeaderView, QToolButton
)


from GlobalConf import GlobalConf
from Styles import Styles

from Utility.Layouts import (
    TabWithToolbar, InputHBoxLayout, SpinBox, VBoxTitleLayout, MplCanvas, ListWidget, FileEditor, TargetPreview, contentButton, StayOpenMenu,
    CrystalPreview, TimeProgressBar, PlotToolbar
)
from Utility.Indexing import Counter
from Utility.Dialogs import showMessageBox, selectFileDialog
from Utility.Functions import alphanumeric, inFileList, inFileDict, pathToStr, lowerProcessPriority
from Utility.ModifyWidget import setWidgetHighlight
from Utility.Icons import getIcon
from Utility.Typing import notNone

from TableWidgets.CompTable import CompRow, CompTable, CompTableTarget
from TableWidgets.TargetTable import TargetLayersTable
from TableWidgets.CompoundList import CompoundList
from TableWidgets.PeriodicTable import PeriodicTableDialog
from TableWidgets.CrystalEditor import CrystalEditorDialog

from Simulations.Simulations import writeInputFiles, SimulationsInput, SimulationsOutput

from Pages.ParameterScan import ParameterScan, SCAN_FILE, LOG_FILE, STATUS_ICONS

from Containers.SimulationConfiguration import SimulationConfiguration
from Containers.Arguments import SimulationArguments, loadSimulationArguments
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
        QUEUED = auto()
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
        self.dialog_source_row: Optional[CompRow] = None
        self.global_density = GlobalDensity()
        self.global_density_needed = False
        self.group_elements = self.simulation_class.GroupElements

        # Counter for components
        self.component_count = Counter(maximum=self.simulation_class.MaxComponents)

        # Output files and parameters
        self.previous_scroll_position = 0
        self.last_selected_output_file = ''
        self.selected_output_parameter: Optional[str] = None

        # process for running simulation
        self.process = QProcess(self)
        self.process_log = ''
        self.setupProcess()

        #
        # TOOLBAR
        #

        # New
        self.action_new = self.toolbar.addAction(getIcon('new'), 'New')
        self.action_new.setToolTip('<b>Reset</b> this simulation-tab and the input fields to their default states')
        self.action_new.setShortcut(QKeySequence('Ctrl+N'))
        self.action_new.triggered.connect(lambda: self.resetSettings())

        # Open
        self.action_open = self.toolbar.addAction(getIcon('open'), 'Open')
        self.action_open.setToolTip('<b>Open</b> an existing simulation input setting')
        self.action_open.setShortcut(QKeySequence('Ctrl+O'))
        self.action_open.triggered.connect(lambda: self.loadSettings())  # self.loadSettings(from_json=False)

        # Import
        self.action_import = self.toolbar.addAction(getIcon('convert'), 'Convert')
        self.action_import.setToolTip('<b>Convert</b> simulation input setting')
        self.action_import.setShortcut(QKeySequence('Ctrl+I'))
        self.action_import.triggered.connect(lambda: self.importSettings())

        # Save
        self.action_save = self.toolbar.addAction(getIcon('save'), 'Save')
        self.action_save.setToolTip('<b>Save</b> the current settings of this simulation-tab to a simulation-tab input file')
        self.action_save.setShortcut(QKeySequence('Ctrl+S'))
        self.action_save.setEnabled(False)
        self.action_save.triggered.connect(lambda: self.saveSettings())

        # Save as
        self.action_save_as = self.toolbar.addAction(getIcon('save_as'), 'Save as')
        self.action_save_as.setToolTip('<b>Save</b> the current settings of this simulation-tab under a different name and/or in a different location')
        self.action_save_as.setShortcut(QKeySequence('Ctrl+Shift+S'))
        self.action_save_as.setEnabled(False)
        self.action_save_as.triggered.connect(lambda: self.saveSettings(new_folder=True))

        # Separator
        self.toolbar.addSeparator()

        # Parameter scan: several values in the input fields, the menu selects other versions
        self.scan = ParameterScan(self)
        self.action_scan = self.toolbar.addAction(getIcon('scan'), 'Parameter scan')
        self.action_scan.setCheckable(True)
        self.action_scan.setToolTip(
            '<b>Parameter scan</b>: simulations in which any number of parameters are varied (all combinations of their values).<br>'
            'The input fields that can be scanned get a mark in their upper left corner: click on it to enter several values '
            '(also as linear or logarithmic range). The simulations are written into subfolders of the folder of this '
            'simulation and described in scan.json.<br>The menu of the button adds other versions of the simulation program, '
            'lists the scanned parameters and resets the scan.'
        )
        self.action_scan.toggled.connect(lambda checked: self.setScanEnabled(checked))
        self.scan_menu = StayOpenMenu(self)
        self.scan_menu.setToolTipsVisible(True)
        self.scan_menu.aboutToShow.connect(self.updateScanMenu)
        self.action_scan.setMenu(self.scan_menu)
        scan_button = self.toolbar.widgetForAction(self.action_scan)
        if isinstance(scan_button, QToolButton):
            scan_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)

        # Separator
        self.toolbar.addSeparator()

        # Preferences
        self.action_preferences = self.toolbar.addAction(getIcon('preferences'), 'Preferences')
        self.action_preferences.setToolTip('Open the <b>general settings</b> of this simulation configuration')
        self.action_preferences.setShortcut(QKeySequence.StandardKey.Preferences)
        self.action_preferences.triggered.connect(lambda: self.main_window.switchSettingsTab(self.simulation_configuration))

        # Separator
        self.toolbar.addSeparator()

        # Status
        self.pixmap_ok = getIcon('okay').pixmap(32)
        self.pixmap_warning = getIcon('warning').pixmap(32)
        self.pixmap_error = getIcon('error').pixmap(32)
        self.run_status_icon = QLabel('')
        self.toolbar.addWidget(self.run_status_icon)
        self.run_status_text = QLabel('')
        self.toolbar.addWidget(self.run_status_text)

        # Separator
        self.toolbar.addSeparator()

        # Run
        self.action_run = self.toolbar.addAction(getIcon('play'), 'Run')
        self.action_run.setToolTip('Save the current settings and <b>run the simulation</b> on the input file')
        self.action_run.setShortcut(QKeySequence('Ctrl+R'))
        self.action_run.triggered.connect(lambda: self.runSimulation())

        # Run progress bar
        self.run_progress = TimeProgressBar(self)
        self.run_progress.setToolTip('The progress of the simulation')
        self.run_progress.setMinimumWidth(50)
        self.run_progress.setMaximumWidth(400)
        self.toolbar.addWidget(self.run_progress)

        # Run abort
        self.action_abort = self.toolbar.addAction(getIcon('abort'), 'Abort')
        self.action_abort.setToolTip('<b>Abort</b> the currently active simulation')
        self.action_abort.setShortcut(QKeySequence('Ctrl+P'))
        self.action_abort.setEnabled(False)
        self.action_abort.triggered.connect(lambda: self.abortSimulation())
        self.toolbar.addSeparator()

        # Run detached
        self.action_run_detached = self.toolbar.addAction(getIcon('play_detached'), 'Run detached')
        self.action_run_detached.setToolTip('Save the current settings and <b>run the simulation</b> on the input file in detached mode.\nThe simulation is run in a separate window, and the GUI can be closed')
        self.action_run_detached.setShortcut(QKeySequence('Ctrl+Shift+R'))
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
        self.open_working_dir = self.toolbar.addAction(getIcon('open_workdir'), 'Open working directory')
        self.open_working_dir.setToolTip('Open the working directory in the file explorer')
        self.open_working_dir.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(pathToStr(self.simulation_configuration.save_folder))))

        # Open docs button
        self.action_open_documentation = self.toolbar.addAction(getIcon('book'), 'Simulation documentation')
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
        if hasattr(self.general_beam_settings, 'projectiles'):
            self.general_beam_settings.projectiles = lambda: [row.symbol for row in self.table_beam.getArguments()]

        # Beam composition title and composition
        self.beam_composition_vbox = VBoxTitleLayout(self, 'Beam composition', add_stretch=True)
        self.settings_group_layout_beam.addLayout(self.beam_composition_vbox)

        self.table_beam: CompTable = CompTable(
            self,
            comp_count=self.component_count,
            row_fields=self.simulation_class.CompRowBeamSettings.rowFields,
            custom_comp_row=self.simulation_class.CompRowBeamSettings,
            version=self.simulation_configuration.version
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
            custom_comp_row=self.simulation_class.CompRowTargetSettings,
            version=self.simulation_configuration.version
        )
        self.target_composition_vbox.addWidget(self.table_target)

        # Target preview
        self.target_preview_vbox = VBoxTitleLayout(self, 'Preview', add_stretch=50)
        self.target_composition_preview.addLayout(self.target_preview_vbox)
        self.settings_group_layout_target.addLayout(self.target_composition_preview)

        self.target_preview_groupbox = QGroupBox(self)
        self.target_preview_vbox.addWidget(self.target_preview_groupbox)

        self.target_preview_groupbox_vbox = QVBoxLayout(self)
        self.target_preview_groupbox_vbox.setContentsMargins(2, 2, 2, 2)
        self.target_preview_groupbox.setLayout(self.target_preview_groupbox_vbox)

        self.target_preview = TargetPreview(self)
        self.target_preview.setToolTip('Preview of target structure')
        self.target_preview.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.target_preview_groupbox_vbox.addWidget(self.target_preview)

        # Target layers
        self.target_structure_compounds = QHBoxLayout()
        self.target_structure_vbox = VBoxTitleLayout(self, 'Target structure', add_stretch=True)
        self.target_structure_compounds.addLayout(self.target_structure_vbox)

        self.target_layers = TargetLayersTable(self, 100, 100)
        self.target_structure_vbox.addWidget(self.target_layers)

        # Compounds
        self.compound_list = None
        if self.simulation_class.CompoundList:
            target_compound_vbox = VBoxTitleLayout(self, 'Compounds', add_stretch=50)
            self.target_structure_compounds.addLayout(target_compound_vbox)

            # Compound holder
            self.compound_list = CompoundList(
                self,
                compounds=self.simulation_class.CompoundList,
                table_beam=self.table_beam,
                table_target=self.table_target
            )
            self.compound_list.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
            target_compound_vbox.addWidget(self.compound_list)

        self.settings_group_layout_target.addLayout(self.target_structure_compounds)

        self.crystal_editor_vbox_widget = QWidget(self)
        self.crystal_editor_vbox_widget.setHidden(True)
        self.target_structure_compounds.addWidget(self.crystal_editor_vbox_widget)

        self.crystal_editor_vbox = VBoxTitleLayout(self, 'Crystal Editor', add_stretch=50)
        self.crystal_editor_vbox.setContentsMargins(0, 0, 0, 0)
        self.crystal_editor_vbox_widget.setLayout(self.crystal_editor_vbox)

        self.crystal_editor_groupbox = QGroupBox(self)
        self.crystal_editor_vbox.addWidget(self.crystal_editor_groupbox)

        self.crystal_editor_groupbox_vbox = QVBoxLayout(self)
        self.crystal_editor_groupbox.setLayout(self.crystal_editor_groupbox_vbox)

        self.crystal_editor_button = QPushButton('Edit Crystal')
        self.crystal_editor_button.setToolTip('Click to change crystal parameters')
        self.crystal_editor_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.crystal_editor_groupbox_vbox.addWidget(self.crystal_editor_button, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.crystal_editor_button.clicked.connect(lambda _: self.openCrystalEditorDialog())

        self.crystal_preview = CrystalPreview(self)
        self.crystal_preview.setToolTip('Preview of crystal structure')
        self.crystal_editor_groupbox_vbox.addWidget(self.crystal_preview)

        #
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

        #
        # Additional settings
        self.additional_settings_vbox = VBoxTitleLayout(self, 'Additional Settings', add_stretch=False)
        self.check_settings_button = contentButton(getIcon('error_check'), 'Check', self)
        self.check_settings_button.setToolTip(
            '<b>Checks the validity</b> of the additional settings for this program version: each line needs the form '
            '"name = value", the variable must be known to the program and its value must have the right type.<br>'
            'Lines with problems are already marked while typing (the problem is the tooltip of the line), the button '
            'lists all problems.'
        )
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

        #
        # Add a parent to the settings layout and add that to the splitter
        self.settings_parent_settings = QWidget(self)
        self.settings_scroll_area = QScrollArea(self)
        self.settings_group_settings = QGroupBox(self)
        self.settings_group_settings.setLayout(self.settings_group_layout_settings)

        self.settings_scroll_area.setWidgetResizable(True)
        self.settings_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.settings_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.settings_scroll_area.setMinimumWidth(self.settings_group_settings.sizeHint().width() + notNone(self.settings_scroll_area.verticalScrollBar()).sizeHint().width())
        self.settings_scroll_area.setStyleSheet('QScrollArea { border: none; }')
        self.settings_scroll_area.setWidget(self.settings_group_settings)

        # transparent background of scroll area; do not set a palette here, since it would not follow theme changes
        notNone(self.settings_scroll_area.viewport()).setAutoFillBackground(False)
        self.settings_group_settings.setAutoFillBackground(False)
        self.simulation_settings_vbox.addWidget(self.settings_scroll_area)
        self.settings_parent_settings.setLayout(self.simulation_settings_vbox)
        self.settings_tab_splitter.addWidget(self.settings_parent_settings)

        #
        # TAB: 'File Preview'
        #

        self.file_preview_tab = QWidget(self)
        self.file_preview_tab_layout = QVBoxLayout(self.file_preview_tab)
        self.file_preview_tab_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_widget.addTab(self.file_preview_tab, 'Files preview')

        # simulation of the parameter scan whose files are shown
        self.preview_selector_widget = QWidget(self)
        preview_selector_layout = QHBoxLayout(self.preview_selector_widget)
        preview_selector_layout.setContentsMargins(6, 4, 6, 0)
        preview_selector_layout.addWidget(QLabel('Simulation of the parameter scan:'))
        self.preview_selector = QComboBox(self)
        self.preview_selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.preview_selector.setToolTip('The files of this simulation of the parameter scan are shown')
        self.preview_selector.currentIndexChanged.connect(lambda _: self.makePreview())
        preview_selector_layout.addWidget(self.preview_selector)
        preview_selector_layout.addStretch(1)
        # only one line high, the file previews get the remaining space
        self.preview_selector_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.preview_selector_widget.setHidden(True)
        self.file_preview_tab_layout.addWidget(self.preview_selector_widget)

        self.file_preview_tab_splitter = QSplitter()
        self.file_preview_tab_layout.addWidget(self.file_preview_tab_splitter, 1)

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

        # Crystal Input File / Input Parameters
        self.parent_widget_file_crystal = QWidget(self)
        self.parent_widget_file_crystal.setHidden(not self.simulation_class.default_values.enable_crystal)
        self.file_crystal_vbox = VBoxTitleLayout(self, 'CRYSTAL FILE', add_stretch=False)
        self.crystal_file_preview = FileEditor(self)
        self.file_crystal_vbox.addWidget(self.crystal_file_preview)
        self.parent_widget_file_crystal.setLayout(self.file_crystal_vbox)
        self.file_preview_tab_splitter.addWidget(self.parent_widget_file_crystal)

        #
        # TAB: 'Run status': output of the simulation, for a parameter scan the state of its simulations
        #

        self.run_status_splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.run_status_splitter.setChildrenCollapsible(False)
        self.tab_widget.addTab(self.run_status_splitter, 'Run status')

        # simulations of the parameter scan with their state, the output of the selected one is shown below
        self.scan_runs = QTableWidget(0, 1, self)
        self.scan_runs.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.scan_runs.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.scan_runs.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.scan_runs.setAlternatingRowColors(True)
        self.scan_runs.setShowGrid(False)
        self.scan_runs.setWordWrap(False)
        self.scan_runs.setToolTip('Simulations of the parameter scan, the output of the selected simulation is shown below')
        scan_runs_header = notNone(self.scan_runs.verticalHeader())
        scan_runs_header.setVisible(False)
        scan_runs_header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        scan_runs_header.setDefaultSectionSize(self.fontMetrics().height() + 4)
        self.scan_runs.itemSelectionChanged.connect(lambda: self.showScanLog())
        self.scan_runs.setHidden(True)
        self.run_status_splitter.addWidget(self.scan_runs)

        self.scan_log = FileEditor(self, line_numbering=False, highlighting=False)
        self.scan_log.setPlaceholderText('Select a simulation of the parameter scan to see its output.')
        self.scan_log.setHidden(True)
        self.run_status_splitter.addWidget(self.scan_log)

        self.simulation_output = FileEditor(self, line_numbering=False, highlighting=False)
        self.simulation_output.setPlaceholderText('The output of the simulation process will be shown here.')
        self.run_status_splitter.addWidget(self.simulation_output)
        self.run_status_splitter.setStretchFactor(0, 40)
        self.run_status_splitter.setStretchFactor(1, 60)

        #
        # TAB: 'Output files'
        #

        self.output_files_splitter = QSplitter()
        self.tab_widget.addTab(self.output_files_splitter, 'Output files')

        # List of output files
        self.parent_widget_output_list = QWidget(self)
        self.output_list_vbox = VBoxTitleLayout(self, 'List of files', add_stretch=False)
        self.refresh_output_files_button = contentButton(getIcon('refresh'), '', self)
        self.refresh_output_files_button.setToolTip('Refresh the list')
        self.output_list_vbox.hl.addWidget(self.refresh_output_files_button)
        self.open_output_file_button = contentButton(getIcon('open_external'), 'Open', self)
        self.open_output_file_button.setToolTip('Open the selected file with the standard text editor')
        self.open_output_file_button.setEnabled(False)
        self.output_list_vbox.hl.addWidget(self.open_output_file_button)
        # folder of the files: the simulation or a simulation of its parameter scan
        self.output_folder_selector = QComboBox(self)
        self.output_folder_selector.setToolTip('The files of this folder are shown: the folder of the simulation or of a simulation of the parameter scan')
        self.output_folder_selector.currentIndexChanged.connect(lambda _: self.updateOutputFilesList())
        self.output_folder_selector.setHidden(True)
        self.output_list_vbox.addWidget(self.output_folder_selector)
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
        self.layout_output_preview_line_count.check.setMaximumWidth(120)
        self.layout_output_preview_line_count.check.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
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

        # results of the simulation or of the parameter scan (comparison of its simulations)
        self.results_stack = QStackedWidget(self)
        self.tab_widget.addTab(self.results_stack, 'Simulation results')
        self.simulation_result_splitter = QSplitter()
        self.results_stack.addWidget(self.simulation_result_splitter)

        # Available data for plotting
        self.parent_widget_plot_list = QWidget(self)
        self.plot_list_vbox = VBoxTitleLayout(self, 'Available data for plotting', add_stretch=False)
        # buttons as wide as their content
        self.refresh_output_parameters_button = contentButton(getIcon('refresh'), '', self)
        self.refresh_output_parameters_button.setToolTip('Refresh the list')
        self.plot_list_vbox.hl.addWidget(self.refresh_output_parameters_button)
        self.save_plot_button = contentButton(getIcon('save'), 'CSV', self)
        self.save_plot_button.setToolTip('Export the data of the selected plot (CSV or tab separated text)')
        self.save_plot_button.clicked.connect(self.savePlot)
        self.plot_list_vbox.hl.addWidget(self.save_plot_button)
        self.compare_button = contentButton(getIcon('compare'), 'Compare', self)
        self.compare_button.setToolTip('Compare the results with other simulations')
        self.compare_button.clicked.connect(lambda: self.main_window.openComparison(self))
        self.plot_list_vbox.hl.addWidget(self.compare_button)
        self.output_parameters_list = ListWidget(self)
        self.output_parameters_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.plot_list_vbox.addWidget(self.output_parameters_list)
        self.parent_widget_plot_list.setLayout(self.plot_list_vbox)
        self.simulation_result_splitter.addWidget(self.parent_widget_plot_list)

        # Output and plots
        self.parent_widget_plot = QWidget(self)
        self.plot_vbox.title.setMaximumHeight(20)
        self.output_plot_toolbar = PlotToolbar(self.output_plot_view, self)
        self.plot_vbox.addWidget(self.output_plot_view, stretch=1)
        self.plot_vbox.addWidget(self.output_plot_toolbar)
        self.plot_hbox = self.evaluation_class.HlPlot(self.simulation_configuration.version)
        self.plot_vbox.addLayout(self.plot_hbox)
        self.parent_widget_plot.setLayout(self.plot_vbox)
        self.simulation_result_splitter.addWidget(self.parent_widget_plot)

        # division between columns
        self.simulation_result_splitter.setStretchFactor(0, 40)
        self.simulation_result_splitter.setStretchFactor(1, 60)

        # crystal editor dialog
        self.crystal_editor_dialog = CrystalEditorDialog(
            self.main_window,
            self.simulation_configuration,
            [row.get('symbol') for row in self.table_target.getArguments()],  # TODO: this should be list of <Element> not strings
            table_target=self.table_target,
            element_data=self.simulation_class.element_data
        )

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
        connections: List[Any] = [
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
            self.table_beam.elementChanged.connect(lambda: notNone(self.compound_list).elementChanged())
            self.table_beam.rowRemoved.connect(lambda: notNone(self.compound_list).elementChanged())
            self.table_target.elementChanged.connect(lambda: notNone(self.compound_list).elementChanged())
            self.table_target.rowRemoved.connect(lambda: notNone(self.compound_list).elementChanged())

        # global density
        self.general_target_settings.settingsChanged.connect(lambda dictionary: self.updateGlobalDensity(dictionary))
        self.general_target_settings.settingsChanged.connect(lambda dictionary: self.updateCrystalView(dictionary))
        self.target_layers.settingsChanged.connect(lambda dictionary: self.updateGlobalDensity(dictionary))

        # group elements
        self.settings_group_layout_settings.settingsChanged.connect(lambda dictionary: self.updateGroupElements(dictionary))

        # popups
        for connection in connections:
            connection.settingsChanged.connect(lambda dictionary: self.showPopup(dictionary))

        # update 'unsaved changes'
        for connection in connections:
            connection.contentChanged.connect(lambda: self.setEdited(True))

        # marks of the input fields of the parameter scan (new elements, layers, ...)
        for connection in connections:
            connection.contentChanged.connect(self.scan.scheduleRefresh)
        for table in (self.table_beam, self.table_target):
            table.rowAdded.connect(lambda _: self.scan.scheduleRefresh())
            table.rowRemoved.connect(lambda _: self.scan.scheduleRefresh())
            table.elementChanged.connect(lambda *_: self.scan.scheduleRefresh())
        self.scan.changed.connect(self.scanChanged)
        self.additional_settings.textChanged.connect(lambda: self.setEdited(True))
        if self.compound_list is not None:
            self.compound_list.compoundChanged.connect(lambda: self.setEdited(True))

        # detect tab change
        self.tab_widget.currentChanged.connect(lambda tab: self.tabChange(tab))

        # output file preview
        self.output_files_list.itemSelectionChanged.connect(self.previewSelectedFile)
        self.output_preview_line_count.editingFinished.connect(self.updateOutputFilesList)
        self.layout_output_preview_line_count.check.clicked.connect(self.updateOutputFilesList)
        self.refresh_output_files_button.clicked.connect(self.updateOutputFilesList)
        self.refresh_output_parameters_button.clicked.connect(self.updateOutputParametersList)
        self.open_output_file_button.clicked.connect(self.openSelectedOutputFile)

        # output parameters
        self.evaluation_class.hlChange.connect(self.plot_hbox.receive)
        self.plot_hbox.settingsChanged.connect(self.evaluation_class.receive)

        # crystal parameters
        self.crystal_editor_dialog.crystalCoordsChanged.connect(lambda crystal_coords: self.crystal_preview.updateParams(crystal_coords=crystal_coords))
        self.crystal_editor_dialog.crystalMillerChanged.connect(lambda miller_ind: self.crystal_preview.updateParams(miller_ind=miller_ind))
        self.crystal_editor_dialog.crystalBasisChanged.connect(lambda basis_vecs: self.crystal_preview.updateParams(basis_vecs=basis_vecs))
        self.crystal_editor_dialog.crystalDefinedChanged.connect(lambda state: setWidgetHighlight(self.crystal_editor_button, state))
        self.table_target.elementChanged.connect(self.crystal_editor_dialog.elementChanged)
        self.crystal_editor_dialog.crystalListChanged.connect(lambda _: self.updateCrystalColumns())

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

        # parameter scan of the last session (the settings of the configuration can differ from scan.json, if not saved)
        if self.simulation_configuration.scan_state:
            self.scan.setState(self.simulation_configuration.scan_state)
        if self.simulation_configuration.scan_enabled:
            self.action_scan.setChecked(True)

    def setScanEnabled(self, enabled: bool):
        """
        Enables or disables the parameter scan: marks and values of the input fields, the simulations of the scan in the
        tabs "Files preview", "Run status" and "Output files" and the results of the scan

        :param enabled: enable the scan
        """

        if not enabled and self.scan.isRunning():
            # a running scan stays enabled (it can be aborted)
            self.action_scan.blockSignals(True)
            self.action_scan.setChecked(True)
            self.action_scan.blockSignals(False)
            self.main_window.writeStatusBar('The parameter scan is running, abort it before the scan is disabled')
            return

        self.scan.setEnabled(enabled)
        self.simulation_configuration.scan_enabled = enabled
        if enabled and self.scan.results is None:
            self.results_stack.addWidget(self.scan.createResults())
        self.results_stack.setCurrentWidget(self.scan.results if enabled else self.simulation_result_splitter)
        self.tab_widget.setTabText(4, 'Parameter scan results' if enabled else 'Simulation results')
        self.action_run_detached.setEnabled(not enabled and self.action_run.isEnabled())
        if enabled:
            self.scan.loadRuns()
        self.updateScanLists()
        self.makePreview()
        if self.run_status == SimulationPage.RunStatus.READY:
            self.setRunStatus(SimulationPage.RunStatus.READY)
        if self.resultsShown():
            if enabled:
                self.scan.refreshResults()
            else:
                self.updateOutputParametersList()

    def scanState(self) -> Tuple[bool, dict]:
        """Returns if the parameter scan is enabled and the settings of the scan"""

        return self.action_scan.isChecked(), self.scan.state()

    def scanChanged(self):
        """The values of the parameter scan have changed"""

        if self.run_status == SimulationPage.RunStatus.READY:
            self.setRunStatus(SimulationPage.RunStatus.READY)
        if self.scan.enabled and self.tab_widget.currentIndex() == 1:
            self.makePreview()

    def updateScanMenu(self):
        """Menu of the scan button: other versions of the simulation program and removing all values"""

        self.scan_menu.clear()
        self.scan_menu.addSection('Versions (other configurations of the program)')
        versions = self.scan.otherVersions()
        for sc in versions:
            action = notNone(self.scan_menu.addAction(f'{sc.title} ({sc.version})'))
            action.setCheckable(True)
            action.setChecked(sc.title in self.scan.versions)
            action.setToolTip('The simulations of the scan are also run with this configuration')
            action.toggled.connect(lambda checked, title=sc.title: self.scan.setVersions(
                [t for t in self.scan.versions if t != title] + ([title] if checked else [])
            ))
        if not versions:
            action = notNone(self.scan_menu.addAction('(no other configuration of this program)'))
            action.setEnabled(False)

        # scanned parameters (also of fields that are currently hidden), a click removes the values of a parameter
        self.scan_menu.addSection('Scanned parameters (click to remove)')
        running = self.scan.isRunning()
        labels = {key: parameter.label for key, parameter in self.scan.safeParameters().items()}
        for key in self.scan.values:
            action = notNone(self.scan_menu.addAction(getIcon('close'), f'{labels.get(key, key)}: {self.scan.valuesText(key)}'))
            action.setToolTip('Removes the values of this parameter (its field has a single value again)')
            action.setEnabled(not running)
            action.triggered.connect(lambda _, key=key: self.scan.setValues(key, None))
        if not self.scan.values:
            action = notNone(self.scan_menu.addAction('(no parameter has several values)'))
            action.setEnabled(False)
        self.scan_menu.addSeparator()
        action_clear = notNone(self.scan_menu.addAction(getIcon('reset'), 'Reset the scan'))
        action_clear.setToolTip('Removes the values of all parameters and the other versions, to start the scan over')
        action_clear.setEnabled(self.scan.hasParameters() and not running)
        action_clear.triggered.connect(lambda: self.scan.clearValues())

    def updateScanLists(self):
        """Shows the simulations of the parameter scan in the tabs (preview, run status and output files)"""

        enabled = self.scan.enabled
        self.preview_selector_widget.setHidden(not enabled)
        self.scan_runs.setHidden(not enabled)
        self.scan_log.setHidden(not enabled)
        self.simulation_output.setHidden(enabled)
        self.output_folder_selector.setHidden(not enabled)

        # output files: folder of the simulation and the folders of the simulations of the scan
        selected = self.output_folder_selector.currentData()
        self.output_folder_selector.blockSignals(True)
        self.output_folder_selector.clear()
        self.output_folder_selector.addItem('Folder of the simulation', None)
        for job in self.scan.jobs:
            self.output_folder_selector.addItem(getIcon(STATUS_ICONS.get(job['status'], 'error')), self.scan.jobText(job), pathToStr(job['folder']))
        index = self.output_folder_selector.findData(selected)
        self.output_folder_selector.setCurrentIndex(max(index, 0))
        self.output_folder_selector.blockSignals(False)
        self.updateOutputFilesList()

    def showScanLog(self, job: Optional[dict] = None, text: Optional[str] = None):
        """
        Shows the output of the selected simulation of the parameter scan

        :param job: (optional) simulation with new output (only shown if it is selected)
        :param text: (optional) new output of the simulation
        """

        rows = notNone(self.scan_runs.selectionModel()).selectedRows()
        if not rows or rows[0].row() >= len(self.scan.jobs):
            if job is None:
                self.scan_log.clear()
            return
        selected = self.scan.jobs[rows[0].row()]
        if job is not None:
            if job is selected and text:
                self.scan_log.appendPlainText(text.rstrip())
            return
        log = selected['log']
        if not log and (selected['folder'] / LOG_FILE).is_file():
            log = (selected['folder'] / LOG_FILE).read_text(encoding='utf-8', errors='replace')
        self.scan_log.setPlainText(log or f'({self.scan.jobText(selected)}: {selected["status"]})')

    def resultsShown(self) -> bool:
        """Returns if the tab of the results is shown"""

        return self.tab_widget.currentIndex() == 4

    def outputFolder(self) -> Optional[Path]:
        """Folder of the output files: the folder of the simulation or the selected simulation of the parameter scan"""

        folder = self.output_folder_selector.currentData() if self.scan.enabled else None
        return Path(folder) if folder else self.simulation_configuration.save_folder

    def abortSimulation(self):
        """Aborts the simulation or the parameter scan"""

        if self.scan.isRunning():
            self.scan.abort()
        else:
            self.process.kill()

    def tabChange(self, tab: int):
        """Executed when tabs ara changed"""

        if tab == 1:
            self.makePreview()
        elif tab == 3:
            self.updateOutputFilesList()
        elif tab == 4:
            if self.scan.enabled:
                self.scan.refreshResults()
            else:
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

        if isinstance(popup_hide, str) and GlobalConf.getValue(popup_hide, default_value=True, type=bool) is False:
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
        # lower priority, so that the GUI stays responsive while many simulations run
        self.process.started.connect(lambda: lowerProcessPriority(self.process.processId()))
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
            rows: List[CompRow] = []
            if typ == 'beam':
                rows = self.table_beam.rows
            elif typ == 'target':
                rows = self.table_target.rows

            for other_row in rows:
                existing_elements.append(other_row.element)

        self.periodic_table_dialog.openDialog(row.element, existing_elements)

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

    def updateCrystalView(self, value_dict: dict):
        """
        Updates crystal view if needed

        :param value_dict: dictionary of updated settings
        """

        crystal_state = value_dict.get('crystal_state')
        if crystal_state is not None:
            self.crystal_editor_vbox_widget.setHidden(not crystal_state)
            self.updateCrystalColumns()

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
        elif not isinstance(docs_path, Path) or not docs_path.is_file() or not QDesktopServices.openUrl(QUrl.fromLocalFile(pathToStr(docs_path))):
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

    def runWarnings(self) -> List[str]:
        """Returns the warnings of the simulation about the current parameters (see SimulationsInput.checkWarnings)"""

        try:
            return self.simulation_class.checkWarnings(self.makeArguments(), self.simulation_configuration.version)
        except Exception as error:
            logging.warning(f'Could not check the parameters for warnings: {error}')
            return []

    def runSimulation(self, detached: bool = False, check_warnings: bool = True, ask_delete: bool = True) -> bool:
        """
        Executes the simulation based on input file (and layer file if provided). Returns True if the simulation was started

        :param detached: (optional) if simulation should run in a detached window
        :param check_warnings: (optional) show the warnings about the parameters before the run (the user decides)
        :param ask_delete: (optional) ask before the files of a previous run are deleted
        """

        # warnings: the simulation might fail, give wrong results or create large files, the user decides
        # (the warnings of a parameter scan are checked for all of its simulations)
        if check_warnings and not (self.scan.enabled and self.scan.hasParameters()):
            warnings = self.runWarnings()
            if warnings:
                _, result = showMessageBox(
                    self,
                    QMessageBox.Icon.Warning,
                    'Warning!',
                    'The simulation might fail, give wrong results or create very large files',
                    info_message='Press "OK" to run the simulation anyway.',
                    detailed_message='\n\n'.join(warnings),
                    standard_buttons=QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                    expand_details=True
                )
                if result == QMessageBox.StandardButton.Cancel:
                    return False

        # save files (asks for the save folder if the simulation has not been saved yet)
        input_files = self.saveSettings()
        if not input_files or not self.simulation_configuration.save_folder:
            return False
        input_file = input_files[1]

        # parameter scan: the simulations are run in subfolders
        if self.scan.enabled and self.scan.hasParameters() and not detached:
            return self.scan.run(check_warnings=check_warnings)

        # delete all files except input files (also the ones that are not written by the GUI, e.g. a0_tdiff.inp) and the
        # description of the parameter scan (its simulations are in subfolders, which are kept)
        files = [
            file for file in self.simulation_configuration.save_folder.iterdir()
            if file.is_file() and file.name not in input_files and file.name != SCAN_FILE
            and not inFileList(file.name, self.simulation_class.KeepFiles)
        ]

        if files and not GlobalConf.skip_delete_info and ask_delete:
            msg_box, result = showMessageBox(
                self,
                QMessageBox.Icon.Information,
                'Attention!',
                'Files in the working directory will be deleted',
                info_message=f'In order to run the simulation, all non-input files in the working directory<br><br>{self.simulation_configuration.save_folder}<br><br>will be deleted automatically.',
                detailed_message='Affected files:\n\n' + '\n'.join(file.name for file in files),
                standard_buttons=QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                check_box_text='Do not show again'
            )
            if result == QMessageBox.StandardButton.Cancel:
                return False
            if msg_box.checkBox().isChecked():
                GlobalConf.skip_delete_info = True

        for file in files:
            file.unlink(missing_ok=True)

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
            self.run_progress.startTiming()
            self.setProgressStatus(0)
            self.update_simulation_data.start(1000)

            # reset process
            self.process = QProcess(self)
            self.setupProcess()

            # pipe in file if needed
            if qpipe:
                self.process.setStandardInputFile(pathToStr(self.simulation_configuration.save_folder / input_file))
            self.process.setProgram(qcmd)
            self.process.start()

        else:
            if system() == 'Windows':
                # pass a single command string, since a list would escape the quotes in cmd with backslashes, which cmd.exe does not understand
                # cmd.exe removes the first and last quote of the command after /k
                title = sub(r'[&|<>^"%]', '', self.simulation_configuration.title)
                Popen(
                    f'cmd /k "title {title} & {cmd}"',
                    creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0),
                    cwd=self.simulation_configuration.save_folder
                )

            elif system() == 'Linux':
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

            elif system() == 'Darwin':
                cmd = f'''
dir='{pathToStr(self.simulation_configuration.save_folder)}'
cmd='{cmd}'
osascript - "$dir" "$cmd" << EOF
    on run argv
        tell application "Terminal"
            set newWindow to do script ""
            activate
            set custom title of newWindow to "{self.simulation_configuration.title}"
            do script ("cd " & quoted form of item 1 of argv) in newWindow
            do script (item 2 of argv) in newWindow
        end tell
    end run
EOF
'''.strip()
                Popen(cmd, shell=True)

            else:
                self.main_window.writeStatusBar(f'OS {system()} not supported in detached mode')
                return False

            self.main_window.writeStatusBar(f'Detached simulation {self.simulation_configuration.title} started')

        return True

    def setEdited(self, state: bool = True):
        """Sets edited status"""

        self.action_save.setEnabled(state)
        self.simulation_configuration.unsaved_changes = state
        self.main_window.simChanged(self.simulation_configuration)

        # changed inputs: the status of the last run no longer applies
        if state and self.run_status in (SimulationPage.RunStatus.DONE, SimulationPage.RunStatus.ABORTED, SimulationPage.RunStatus.ERROR):
            self.setRunStatus(SimulationPage.RunStatus.READY)

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
                info_message='Do you want to save your changes?',
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
        self.simulation_configuration.save_folder = None
        self.working_dir.setText('unknown')

        # no parameter scan
        self.scan.loadFolder(None)

        # reset parameter lists
        self.updateOutputFilesList()
        self.updateOutputParametersList()
        self.evaluation_class.clearPlotWindow()

        # reset tables
        self.target_layers.resetTable()
        self.table_beam.resetTable()
        self.table_target.resetTable()
        self.crystal_editor_dialog.reset()

        # add first rows
        self.table_beam.addRow()
        self.table_target.addRow()
        self.target_layers.addRow()
        self.crystal_editor_dialog.addRow()

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

        # reset file previews
        self.makePreview()

    def loadSettings(self, path: Union[Path, None] = None, from_json: bool = True, unsaved_warning: bool = True) -> bool:
        """Loads settings and returns if it was successful"""

        # check for unsaved changes
        if self.simulation_configuration.unsaved_changes and unsaved_warning:
            _, result = showMessageBox(
                self,
                QMessageBox.Icon.Information,
                'Attention!',
                'The document has been modified',
                info_message='Do you want to save your changes?',
                standard_buttons=QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
            )

            if result == QMessageBox.StandardButton.Cancel:
                return False

            elif result == QMessageBox.StandardButton.Save:
                if not self.saveSettings():
                    return False

        # check if provided path should be loaded
        open_scan = False
        if isinstance(path, Path):
            if not path.exists():
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
            path = self.simulation_configuration.getBaseSaveFolder()
            path.mkdir(parents=True, exist_ok=True)

            file = selectFileDialog(
                self,
                False,
                f'Load input file "{self.simulation_class.InputFilename}" or parameter scan "{SCAN_FILE}"',
                path,
                file_filter=f'Input files or parameter scans ({self.simulation_class.InputFilename} {SCAN_FILE})'
            )
            if file is None:
                self.main_window.writeStatusBar('Loading aborted')
                return False

            self.simulation_configuration.save_folder = file.resolve().parent
            # a parameter scan is opened with its description
            open_scan = file.name == SCAN_FILE

        # name of save folder
        if self.simulation_configuration.save_folder is not None:
            self.working_dir.setText(self.simulation_configuration.save_folder.resolve().name)

        # update parameter lists
        self.updateOutputFilesList()
        self.updateOutputParametersList()

        # try to get input files
        arguments: Union[Literal[False], str, SimulationArguments] = False
        json_loaded = False
        if from_json:
            arguments = loadSimulationArguments(self.simulation_configuration.save_folder / 'input.json')
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
                arguments
            )
            return False

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        # reset beam, target and layer tables
        self.target_layers.resetTable()
        self.table_target.resetTable()
        self.table_beam.resetTable()
        self.crystal_editor_dialog.table_crystal.resetTable()

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
            self.crystal_editor_dialog.table_crystal.connectRows()

        else:
            self.table_beam.setArguments(arguments.beam_rows, arguments, element_data)
            self.table_target.setArguments(arguments.target_rows, arguments, element_data)

        self.target_layers.setArguments(arguments.structure)
        # somehow the resize of the target layer table does not work, therefore this fix is needed
        QTimer.singleShot(0, self.target_layers.resizeTable)
        self.additional_settings.setPlainText('\n'.join(arguments.additional))
        if self.compound_list is not None:
            self.compound_list.setCompounds([compound.name_save for compound in arguments.settings.compounds])

        self.crystal_editor_dialog.elementChanged()
        if arguments.crystal_rows is not None:
            self.crystal_editor_dialog.table_crystal.setArguments(arguments.crystal_rows)
        if self.simulation_class.default_values.enable_crystal:
            load_error += self.crystal_editor_dialog.loadArguments(arguments)

        # parameter scan of the folder (scan.json), a folder without scan is a single simulation
        self.scan.loadFolder(self.simulation_configuration.save_folder)
        if open_scan:
            self.action_scan.setChecked(True)
        elif not (self.simulation_configuration.save_folder / SCAN_FILE).is_file():
            self.action_scan.setChecked(False)

        self.makePreview()
        self.setEdited(False)
        self.action_save_as.setEnabled(True)
        self.action_save.setEnabled(True)
        self.evaluation_class.reset()
        self.updateOutputParametersList()
        QApplication.restoreOverrideCursor()
        self.main_window.writeStatusBar('Parameter scan loaded' if open_scan else 'Input files loaded')

        return True

    def importSettings(self) -> bool:
        """Imports settings and returns if it was successful"""

        # select import file
        import_file = selectFileDialog(
            self,
            False,
            'Load input file "input.json"',
            GlobalConf.save_path,
            file_filter='Import file (input.json)'
        )

        if import_file is None:
            self.main_window.writeStatusBar('Import aborted')
            return False

        # select folder where imported file should be saved
        path = self.simulation_configuration.getBaseSaveFolder()
        path.mkdir(parents=True, exist_ok=True)

        result = None
        folder = path
        while result != QMessageBox.StandardButton.Yes:
            folder_str = QFileDialog.getExistingDirectory(
                self,
                'Select the folder where the imported files should be saved',
                pathToStr(path)
            )

            if len(folder_str) == 0:
                self.main_window.writeStatusBar('Import aborted')
                return False

            folder = Path(folder_str)

            # check if folder contains no files
            if not folder.exists() or not any(file.is_file() for file in folder.iterdir()):
                break

            _, result = showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                'This folder already contains files',
                info_message=f'Do you want to save the settings in\n"{pathToStr(folder)}"?',
                standard_buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

        self.simulation_configuration.save_folder = folder

        # copy input.json file
        save_file_json = folder / 'input.json'
        if import_file.resolve() != save_file_json.resolve():
            copy2(import_file, save_file_json)
        self.main_window.writeStatusBar('Import successful')

        # open file
        self.loadSettings(self.simulation_configuration.save_folder)
        return True

    def saveSettings(self, new_folder: bool = False) -> Optional[List[str]]:
        """
        Saves settings and return list of created input files if successful

        :param new_folder: create a new folder
        """

        old_save_folder = self.simulation_configuration.save_folder
        arguments = self.makeArguments()

        # check all compound data has been inserted
        if not self.table_beam.allRowsHaveData() or not self.table_target.allRowsHaveData():
            showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                'All elements must be defined in order to save the input file'
            )
            return None

        # check combinations of parameters that the simulation does not accept
        problems = self.simulation_class.checkArguments(arguments, self.simulation_configuration.version)
        if problems:
            showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                'The simulation does not accept these parameters',
                detailed_message='\n'.join(problems)
            )
            return None

        # check if crystal is fully defined
        if self.crystal_editor_button.isVisible() and self.crystal_editor_dialog.undefined_state:
            showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                'Crystal must be defined in order to save the input file'
            )
            return None

        # check if save_folder exists if set
        if self.simulation_configuration.save_folder and not self.simulation_configuration.save_folder.is_dir():
                self.simulation_configuration.save_folder = None

        # check if save folder is set and let user set it if it does not exist
        if not self.simulation_configuration.save_folder or new_folder:

            # create base save folder if it does not exist
            path = self.simulation_configuration.getBaseSaveFolder()
            path.mkdir(parents=True, exist_ok=True)

            result = None
            folder = path

            while result != QMessageBox.StandardButton.Yes:
                folder_str = QFileDialog.getExistingDirectory(
                    self,
                    'Select the folder where the files will be saved',
                    pathToStr(path)
                )

                if len(folder_str) == 0:
                    self.main_window.writeStatusBar('Saving aborted')
                    return None

                folder = Path(folder_str)

                # check if folder contains no files
                if not folder.exists() or not any(file.is_file() for file in folder.iterdir()):
                    break

                _, result = showMessageBox(
                    self,
                    QMessageBox.Icon.Warning,
                    'Warning!',
                    'This folder already contains files',
                    info_message=f'Do you want to save the settings in\n"{pathToStr(folder)}"?',
                    standard_buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

            self.simulation_configuration.save_folder = Path(folder)

        # copy all files into new folder
        if new_folder and old_save_folder:
            for file in old_save_folder.iterdir():
                if file.is_file():
                    copy2(file, self.simulation_configuration.save_folder / file.name)

        # save all input files (input.json, input file, layer file, distributions, crystal file)
        filelist = writeInputFiles(
            self.simulation_class,
            arguments,
            self.simulation_configuration.save_folder,
            self.simulation_configuration.folder,
            self.simulation_configuration.version
        )

        # description of the parameter scan
        if self.scan.enabled:
            self.scan.writeDescription()

        # open file (the settings of the parameter scan are kept)
        if new_folder:
            scan_state = self.scan.state()
            self.loadSettings(self.simulation_configuration.save_folder, unsaved_warning=False)
            self.scan.setState(scan_state)

        # update wording directory text
        save_folder_parts = self.simulation_configuration.save_folder.parts
        self.working_dir.setText(f'{save_folder_parts[-1]}')

        # enable save as option
        self.action_save_as.setEnabled(True)
        self.action_save.setEnabled(False)

        self.setEdited(False)
        self.main_window.writeStatusBar('Saving successful')

        return filelist

    def makePreview(self) -> Tuple[SimulationArguments, str, Optional[str], Optional[str]]:
        """
        Makes preview of the input and layer file

        :return: input_file as string, layer_file as string if should be created or None, crystal_file as string if should be created or None
        """

        arguments = self.previewArguments()
        input_file = self.simulation_class.makeInputFile(arguments, self.simulation_configuration.folder, self.simulation_configuration.version)
        layer_file = self.simulation_class.makeLayerFile(arguments, self.simulation_configuration.folder, self.simulation_configuration.version)

        crystal_file = ''
        if self.simulation_class.default_values.enable_crystal:
            crystal_file = self.simulation_class.makeCrystalFile(arguments, self.simulation_configuration.folder, self.simulation_configuration.version)

        create_layer_file = True
        if not layer_file:
            layer_file = '(-- FILE WILL NOT BE CREATED --)'
            create_layer_file = False

        create_crystal_file = True
        if not crystal_file:
            crystal_file = '(-- FILE WILL NOT BE CREATED --)'
            create_crystal_file = False

        self.input_file_preview.setPlainText(input_file)
        self.layer_file_preview.setPlainText(layer_file)
        self.crystal_file_preview.setPlainText(crystal_file)

        return arguments, input_file, layer_file if create_layer_file else None, crystal_file if create_crystal_file else None

    def previewArguments(self) -> SimulationArguments:
        """
        Returns the arguments of the preview: the current parameters or, if the parameter scan is enabled, the parameters of
        the selected simulation of the scan (the list of the simulations is updated)
        """

        if not self.scan.enabled:
            return self.makeArguments()
        try:
            simulations, names = self.scan.plan()
        except Exception as error:
            logging.warning(f'Could not create the simulations of the parameter scan: {error}')
            simulations, names = [], []
        if not names:
            simulations = []
        index = self.preview_selector.currentIndex()
        self.preview_selector.blockSignals(True)
        self.preview_selector.clear()
        for simulation in simulations:
            self.preview_selector.addItem(', '.join(
                f'{name} = {value if isinstance(value, str) else f"{value:g}"}' for name, value in zip(names, simulation['values'])
            ), simulation['label'])
        if not simulations:
            self.preview_selector.addItem('(no values entered: the current parameters)')
        self.preview_selector.setCurrentIndex(min(max(index, 0), self.preview_selector.count() - 1))
        self.preview_selector.blockSignals(False)
        if not simulations:
            return self.makeArguments()
        return self.scan.arguments(simulations[self.preview_selector.currentIndex()]['assignments'])

    def makeArguments(self) -> SimulationArguments:
        """Returns <SimulationArguments> container with current parameters"""

        simulation = self.simulation_class.Name

        beam_args = self.general_beam_settings.getArguments()
        beam_rows = self.table_beam.getArguments()
        target_rows = self.table_target.getArguments()

        structure = self.target_layers.getArguments()
        settings = self.settings_group_layout_settings.getArguments()
        if self.compound_list is not None:
            settings.compounds = self.compound_list.getCompounds()

        additional = self.additional_settings.toPlainText().split('\n')

        crystal_args = self.crystal_editor_dialog.getArguments()
        crystal_rows = self.crystal_editor_dialog.getRowArguments()
        target_args = self.general_target_settings.getArguments(miller_ind=crystal_args.miller_ind)

        arguments = SimulationArguments(
            simulation=simulation,
            beam_args=beam_args,
            beam_rows=beam_rows,
            target_args=target_args,
            target_rows=target_rows,
            structure=structure,
            settings=settings,
            additional=additional,
            crystal_args=crystal_args,
            crystal_rows=crystal_rows
        )

        return arguments

    def checkAdditionalSettings(self, silent: bool = False):
        """Checks additional settings from the user"""

        additional = self.additional_settings.toPlainText()
        errors = self.simulation_class.checkAdditional(additional, self.simulation_configuration.version)

        setWidgetHighlight(self.additional_settings, bool(errors))

        # mark the lines with problems (the message is shown as tooltip of the line)
        marked_lines: Dict[int, str] = {}
        for error in errors:
            match = findall(r'^Line (\d+): (.*)$', error)
            if match:
                line = int(match[0][0]) - 1
                marked_lines[line] = (marked_lines[line] + '\n' if line in marked_lines else '') + match[0][1]
        self.additional_settings.setMarkedLines(marked_lines)

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

        return not (self.simulation_configuration.running or self.simulation_configuration.unsaved_changes or self.scan.isRunning())

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
        elif status == SimulationPage.RunStatus.QUEUED:
            text = 'Queued'
            pixmap = self.pixmap_warning
            color_style = Styles.orange
            tooltip = 'The simulation waits until other simulations have finished ("Run all")'
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
            tooltip = 'Something went wrong with the simulation\nCheck the "Run status" tab for more info'

        # number of simulations of the parameter scan
        if status == SimulationPage.RunStatus.READY and self.scan.enabled and self.scan.hasParameters():
            count = self.scan.count()
            text = f'Ready! ({count} simulation{"s" if count != 1 else ""})'
            tooltip = 'The parameter scan is ready'

        self.run_status_text.setText(text)
        self.run_status_icon.setPixmap(pixmap)
        self.run_status_text.setStyleSheet(Styles.status_text_style + color_style)
        self.run_status_text.setToolTip(tooltip)

    def setProgressStatus(self, progress: int):
        """
        Change progress of simulation page

        :param progress: progress of simulation
        """

        self.simulation_configuration.progress = progress
        self.main_window.simChanged(self.simulation_configuration)

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

        if isinstance(error, int):
            errors = {
                0: 'QProcess::FailedToStart',
                1: 'QProcess::Crashed',
                2: 'QProcess::Timed out',
                3: 'QProcess::WriteError',
                4: 'QProcess::ReadError',
                5: 'QProcess::UnknownError'
            }
            error = errors.get(error, 'unknown error')

        self.main_window.writeStatusBar(f'{self.simulation_configuration.program_name} ERROR: {error}')
        self.simulation_output.appendPlainText(f'\n\nAn error occurred: "{error}" with description: {self.process.errorString()}')
        self.setRunStatus(SimulationPage.RunStatus.ERROR)

        self.setProcessWidgetsEnabled(True)
        self.stopSimulationTimer()

    def processFinished(self, exit_code: int, exit_status: int):
        """Called when process has finished"""

        # check if there were errors (in log, exit code or results)
        log = self.simulation_output.toPlainText()
        problem = None
        if exit_status == QProcess.ExitStatus.NormalExit:
            problem = self.simulation_class.runFailed(self.simulation_configuration.save_folder, log, exit_code, self.simulation_configuration.version)
        if problem is not None:
            exit_status = -1
            self.simulation_output.appendPlainText(f'\n\nThe simulation failed: {problem}')

        if exit_status == QProcess.ExitStatus.NormalExit:
            result = 'finished'
            status = SimulationPage.RunStatus.DONE
        elif exit_status == QProcess.ExitStatus.CrashExit:
            result = 'aborted'
            status = SimulationPage.RunStatus.ABORTED
        else:
            result = f'error with exit code: {exit_code}'
            status = SimulationPage.RunStatus.ERROR
            self.simulation_output.appendPlainText(f'\n\nExit code: "{exit_code}"')

        self.main_window.writeStatusBar(f'{self.simulation_configuration.program_name} simulation {result}')
        self.setRunStatus(status)

        self.setProcessWidgetsEnabled(True)
        self.stopSimulationTimer()

        # next simulations of the queue ("Run all")
        self.main_window.simulationFinished(self)

    def setProcessWidgetsEnabled(self, enabled):
        """Enable or disable actions which depend on the state of the process"""

        self.action_new.setEnabled(enabled)
        self.action_open.setEnabled(enabled)
        self.action_import.setEnabled(enabled)
        self.action_save.setEnabled(enabled)
        self.action_save_as.setEnabled(enabled)
        self.action_run.setEnabled(enabled)
        self.action_run_detached.setEnabled(enabled and not self.scan.enabled)
        self.action_scan.setEnabled(enabled)
        self.action_abort.setEnabled(not enabled)

    def stopSimulationTimer(self):
        """Stops the simulation timer"""

        self.update_simulation_data.stop()
        self.run_progress.stopTiming()
        self.setProgressStatus(100)
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
            self.setProgressStatus(percent)

    def updateOutputFilesList(self):
        """Update list of output files"""

        # Only update if simulation tab is active
        if not self.simulation_configuration.is_active:
            return

        # Only update if the tab is actually visible
        if self.tab_widget.currentIndex() != 3:
            return

        folder = self.outputFolder()
        if not folder or not folder.is_dir():
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

        for file in folder.iterdir():
            if not file.is_file():
                continue

            if inFileList(file.name, skipped_files):
                continue

            self.output_files_list.addItem(file.name)
            item = self.output_files_list.item(self.output_files_list.count() - 1)

            tooltip = inFileDict(file.name, self.simulation_class.OutputTooltips)
            if tooltip is not False:
                item.setToolTip(tooltip[1])

            # Keep the previous selection
            if item.text() == selected_output_file:
                self.output_files_list.setCurrentItem(item)

    def previewSelectedFile(self):
        """Preview the selected file"""

        vertical_scrollbar = self.outputFilePreview.verticalScrollBar()
        if vertical_scrollbar and vertical_scrollbar.isSliderDown():
            return

        selected_items = self.output_files_list.selectedItems()
        if not selected_items:
            self.open_output_file_button.setEnabled(False)
            self.outputFilePreview.clear()
            return

        folder = self.outputFolder()
        if not folder:
            return

        file_path = folder / selected_items[0].text()
        file_content = ''
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
                file_content = file.read()

        except FileNotFoundError:
            logging.info(f'Could not open file "{pathToStr(file_path)}"!')
            self.outputFilePreview.clear()
            self.main_window.writeStatusBar(f'Failed to preview file "{pathToStr(file_path)}"')
            self.open_output_file_button.setEnabled(False)
            self.outputFilePreview.setPlainText('(-- FILE DOES NOT EXIST, PLEASE REFRESH LIST OF FILES --)')
            return

        self.outputFilePreview.updateOffset(0)

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

        folder = self.outputFolder()
        if not folder:
            return

        file_path = folder / self.output_files_list.selectedItems()[0].text()
        if not file_path.is_file() or not QDesktopServices.openUrl(QUrl.fromLocalFile(pathToStr(file_path))):
            self.main_window.writeStatusBar(f'Failed to open file "{pathToStr(file_path)}"')

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
        if not self.simulation_configuration.save_folder or not self.simulation_configuration.save_folder.exists():
            return
        self.evaluation_class.listParameters(self.simulation_configuration.save_folder, self.output_parameters_list)

        # only reset plot window if not in loop
        if not in_loop:
            self.evaluation_class.clearPlotWindow()

        # reselect item
        for i in range(self.output_parameters_list.count()):
            if notNone(self.output_parameters_list.item(i)).text() == self.selected_output_parameter:
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
        if self.evaluation_class.getReturnData() is None:
            self.main_window.writeStatusBar('No plot data provided - aborted')
            return

        file_path = selectFileDialog(
            self,
            True,
            'Save plot data as...',
            self.simulation_configuration.save_folder / f'{title}.csv',
            'CSV files (*.csv);;Text files, tab separated (*.txt)'
        )
        if file_path is None:
            self.main_window.writeStatusBar('No file selected - aborted')
            return

        # CSV files are comma separated, other files tab separated
        plot_data = self.evaluation_class.getReturnData(separator=',' if file_path.suffix.lower() == '.csv' else '\t')
        with open(file_path, 'w', encoding='utf-8', newline='') as file:
            file.write(plot_data)

        self.main_window.writeStatusBar(f'Plot data saved as "{file_path}"')

    def updateCrystalColumns(self):
        """Shows the columns for the crystal fractions in the target structure if crystals from table.crystal are used"""

        names = []
        if self.crystal_editor_dialog.table_mode and not self.crystal_editor_vbox_widget.isHidden():
            names = [crystal['name'] for crystal in self.crystal_editor_dialog.tableCrystalsList()]
        self.target_layers.setCrystals(names)

    def openCrystalEditorDialog(self):
        """
        Opens simulation specific crystal editor
        """

        self.setEdited(True)
        self.crystal_editor_dialog.elementChanged()
        self.crystal_editor_dialog.open()
