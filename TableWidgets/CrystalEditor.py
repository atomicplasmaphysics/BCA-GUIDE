# TODO: this is not a very general class for different simulation codes, but rather only SDTrimSP...
#   we should create a base class and nest simulation code specific layouts into this at some point

from typing import List, Optional
from pathlib import Path


from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QGroupBox, QSizePolicy, QPushButton, QComboBox, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QLayout
)

import numpy as np


from TableWidgets.CompTable import CompTable
from TableWidgets.CrystalTable import CrystalTable

from Utility.Layouts import (
    InputHBoxLayout, InputHBoxLayouts, VBoxTitleLayout, DoubleSpinBox, SpinBox, SpinBoxRange,
    CrystalPreview, NoMessageToolbar
)
from Utility.Functions import getPeriodicCoords
from Utility.ModifyWidget import setWidgetHighlight
from Utility.Icons import getIcon

from Containers.SimulationConfiguration import SimulationConfiguration
from Containers.Element import Element, Elements
from Containers.Arguments import GeneralCrystalArguments, SimulationArguments, CrystalRowArguments
from Containers.Crystal import MillerIndex, BasisVector, Coordinate
from Containers.CrystalTableFile import CrystalTableFile, CrystalTableError, TableCrystal

from Simulations.SDTrimSP import DefaultValues, CrystalTableLimits

from TableWidgets.CrystalTableDialog import NewCrystalDialog


def setLayoutVisible(layout: QLayout, visible: bool):
    """Shows or hides all widgets in a layout (recursively)"""

    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item.widget() is not None:
            item.widget().setVisible(visible)
        elif item.layout() is not None:
            setLayoutVisible(item.layout(), visible)


class CrystalEditorDialog(QDialog):
    """
    Crystal editor window that extends QDialog

    :param parent: parent widget
    :param simulation_configuration: <SimulationConfiguration>
    :param target_elements: list of elements
    :param table_target: <CompTable>
    :param element_data: (optional) <Elements> of the simulation, used for elements that are not in the target

    Since SDTrimSP 7.02 crystals are selected from the crystal table "tables/table.crystal" (table mode).
    """

    crystalDefinedChanged = pyqtSignal(bool)
    crystalCoordsChanged = pyqtSignal(dict)
    crystalMillerChanged = pyqtSignal(np.ndarray)
    crystalBasisChanged = pyqtSignal(np.ndarray)
    crystalListChanged = pyqtSignal(list)

    def __init__(
        self,
        parent,
        simulation_configuration: SimulationConfiguration,
        target_elements: List[Element],
        table_target: CompTable,
        element_data: Optional[Elements] = None
    ):
        super().__init__(parent)

        self.crystal_name = DefaultValues.crystal_name
        self.lattice_id = DefaultValues.lattice_id
        self.element_data = element_data

        # since 7.02 the crystals are defined in tables/table.crystal
        self.table_mode = DefaultValues(simulation_configuration.version).crystal_table
        self.table_file: Optional[CrystalTableFile] = None
        self.table_crystal_selected: Optional[TableCrystal] = None

        self.target_elements = target_elements
        self.table_target = table_target

        self.available_elements: List[Element] = []
        self.undefined_state = False

        # Set up window properties
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowTitle('Edit Crystal')

        self.simulation_configuration = simulation_configuration
        self.simulation_class = self.simulation_configuration.program_class()

        self.main_layout = QVBoxLayout(self)
        self.setLayout(self.main_layout)

        # three columns: parameters | definition of the crystal | previews
        self.orientation_hbox = QHBoxLayout()
        self.main_layout.addLayout(self.orientation_hbox, stretch=1)
        self.previews_vbox = QVBoxLayout()

        self.orientation_parameter_vbox = QVBoxLayout()
        self.orientation_parameter_vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.orientation_hbox.addLayout(self.orientation_parameter_vbox)

        # Miller indices Layout
        self.miller_indices_vbox = VBoxTitleLayout(self, 'Miller indices', spacing=2, add_stretch=False)
        self.orientation_parameter_vbox.addLayout(self.miller_indices_vbox)

        self.miller_indices_group_box = QGroupBox(self)
        self.miller_indices_vbox.addWidget(self.miller_indices_group_box)

        # Miller indices Widgets
        self.miller_ind = [SpinBox(0, input_range=SpinBoxRange.ZERO_INF) for _ in range(3)]
        self.layout_miller_ind = InputHBoxLayouts(
            'Miller Indices:',
            self.miller_ind,
            split=0,
            tooltip='<i>miller_ind = h,k,l</i><br>defines crystal direction',
            widgets_labels=['h:', 'k:', 'l:'],
            widgets_tooltips=[f'<i>miller_ind({j})</i><br>defines crystal direction' for j in ['h', 'k', 'l']],
        )
        self.miller_indices_group_box.setLayout(self.layout_miller_ind)

        for widget in self.miller_ind:
            widget.valueChanged.connect(lambda: self.millerIndChanged())

        # Basis vector layout
        self.basis_vectors_vbox = VBoxTitleLayout(self, 'Basis Vectors', spacing=2, add_stretch=False)
        self.orientation_parameter_vbox.addLayout(self.basis_vectors_vbox)

        self.basis_vectors_group_box = QGroupBox(self)
        self.basis_vectors_vbox.addWidget(self.basis_vectors_group_box)

        self.basis_vectors_group_box_vbox = QVBoxLayout(self)
        self.basis_vectors_group_box.setLayout(self.basis_vectors_group_box_vbox)

        self.basis_vecs = [[DoubleSpinBox(0, input_range=SpinBoxRange.INF_INF, decimals=7) for _ in range(3)] for _ in range(3)]
        for i, basis_vec in enumerate(self.basis_vecs):
            basis_vec[i].setAndDefault(1)

        self.layout_basis_vecs = [InputHBoxLayouts(
            f'\u00E2<sub>{i + 1}</sub> (x,y,z)',
            self.basis_vecs[i],
            split=0,
            tooltip=f'Basis vector \u00E2<sub>{i + 1}</sub>',
            widgets_tooltips=[f'Basis vector \u00E2<sub>{i + 1}</sub><br>in {j}-direction' for j in ['x', 'y', 'z']],
        ) for i in range(3)]

        for layout_basis_vec in self.layout_basis_vecs:
            self.basis_vectors_group_box_vbox.addLayout(layout_basis_vec)

        for i, basis_vec in enumerate(self.basis_vecs):
            for j, widget in enumerate(basis_vec):
                widget.valueChanged.connect(lambda: self.basisVecsChanged())

        # Beam-Settings
        self.beam_settings_vbox = VBoxTitleLayout(self, 'Beam-Settings', spacing=2, add_stretch=False)
        self.orientation_parameter_vbox.addLayout(self.beam_settings_vbox)

        self.beam_settings_group_box = QGroupBox(self)
        self.beam_settings_vbox.addWidget(self.beam_settings_group_box)

        self.beam_vbox = QVBoxLayout()
        self.beam_settings_group_box.setLayout(self.beam_vbox)

        # Beam setting widgets
        self.beam_hbox_1 = QHBoxLayout()
        self.beam_vbox.addLayout(self.beam_hbox_1)

        self.beam_dy = DoubleSpinBox(0, input_range=SpinBoxRange.INF_INF, decimals=7)
        self.layout_beam_dy = InputHBoxLayout(
            'Beam dy:',
            self.beam_dy,
            tooltip='<i>beam_dy</i><br>Surface-area of one crystal is periodical in y,z-direction. If input is 0 the value is calculated automatically'
        )
        self.beam_hbox_1.addLayout(self.layout_beam_dy)

        self.beam_dz = DoubleSpinBox(0, input_range=SpinBoxRange.INF_INF, decimals=7)
        self.layout_beam_dz = InputHBoxLayout(
            'Beam dz:',
            self.beam_dz,
            tooltip='<i>beam_dz</i><br>Surface-area of one crystal is periodical in y,z-direction. If input is 0 the value is calculated automatically'
        )
        self.beam_hbox_1.addLayout(self.layout_beam_dz)

        self.beam_hbox_2 = QHBoxLayout()
        self.beam_vbox.addLayout(self.beam_hbox_2)

        self.impact_parameter = DoubleSpinBox(3., input_range=SpinBoxRange.INF_INF, decimals=7)
        self.layout_impact_parameter = InputHBoxLayout(
            'Impact parameter:',
            self.impact_parameter,
            tooltip='<i>p_max</i><br>impact parameter'
        )
        self.beam_hbox_2.addLayout(self.layout_impact_parameter)

        self.lattice_constant = DoubleSpinBox(3., input_range=SpinBoxRange.INF_INF, decimals=7)
        self.layout_lattice_constant = InputHBoxLayout(
            'Lattice constant [Å]:',
            self.lattice_constant,
            tooltip='<i>lattice_constant</i><br>is used to scale the basis-vectors in [Å]'
        )
        self.beam_hbox_2.addLayout(self.layout_lattice_constant)

        self.beam_hbox_3 = QHBoxLayout()
        self.beam_vbox.addLayout(self.beam_hbox_3)

        self.id_matrices = [3, 5]
        self.layout_matrices = [InputHBoxLayout(
            f'Matrix {i}x{i}x{i}',
            None,
            checkbox=False,
            tooltip=f'<i>matrix_id = {i}</i><br>The simulation is looking for the next collision partner in {i}x{i}x{i} field of the nearest target atoms'
        ) for i in self.id_matrices]
        self.resetMatrix(DefaultValues.matrix_id)

        for i, layout_matrix in enumerate(self.layout_matrices):
            self.beam_hbox_3.addLayout(layout_matrix)
            layout_matrix.checkbox.clicked.connect(lambda _, lm=layout_matrix: self.matrixClicked(lm))

        # Additional settings layout
        self.additional_settings_vbox = VBoxTitleLayout(self, 'Crystal orientation preview settings', spacing=2, add_stretch=False)
        self.orientation_parameter_vbox.addLayout(self.additional_settings_vbox)

        self.additional_settings_group_box = QGroupBox(self)
        self.additional_settings_vbox.addWidget(self.additional_settings_group_box)

        self.additional_vbox = QVBoxLayout()
        self.additional_settings_group_box.setLayout(self.additional_vbox)

        self.show_coordinate_system = InputHBoxLayout(
            'Show coordinate system',
            None,
            checkbox=False,
            tooltip='Toggles if coordinate system is shown in Crystal orientation preview'
        )
        self.additional_vbox.addLayout(self.show_coordinate_system)
        self.show_coordinate_system.checkbox.clicked.connect(lambda: self.showCoordinateSystem())

        # Crystal orientation preview
        self.orientation_preview_vbox = VBoxTitleLayout(self, 'Crystal Orientation Preview', spacing=2, add_stretch=False)
        self.previews_vbox.addLayout(self.orientation_preview_vbox, stretch=1)

        self.orientation_preview_group_box = QGroupBox(self)
        self.orientation_preview_vbox.addWidget(self.orientation_preview_group_box)

        self.orientation_preview_plot_vbox = QVBoxLayout()
        self.orientation_preview_group_box.setLayout(self.orientation_preview_plot_vbox)

        self.orientation_preview = CrystalPreview(
            self,
            show_beam=True,
            show_basis_vecs=True,
            show_surface=True,
            show_legend=True,
            atom_size=100,
            width=6,
            height=10,
            disable_interaction=False
        )
        self.orientation_preview_plot_vbox.addWidget(self.orientation_preview, stretch=1)

        self.output_plot_toolbar_orientation_preview = NoMessageToolbar(self.orientation_preview, self)
        self.orientation_preview_plot_vbox.addWidget(self.orientation_preview, stretch=1)
        self.orientation_preview_plot_vbox.addWidget(self.output_plot_toolbar_orientation_preview)

        # Crystal editor in the same row (second column)
        self.crystal_edit_hbox = self.orientation_hbox

        # Crystal editor VBox
        self.lattice_parameter_vbox = QVBoxLayout()
        self.lattice_parameter_vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.crystal_edit_hbox.addLayout(self.lattice_parameter_vbox)

        # Crystal Default Box
        self.default_para_vbox = VBoxTitleLayout(self, 'Default Crystal', spacing=2, add_stretch=False)
        self.lattice_parameter_vbox.addLayout(self.default_para_vbox)
        self.default_para_group_box = QGroupBox(self)
        self.default_para_vbox.addWidget(self.default_para_group_box)
        self.default_para_hbox = QHBoxLayout()
        self.default_para_group_box.setLayout(self.default_para_hbox)

        # Default buttons
        self.bcc_para_button = QPushButton('bcc')
        self.bcc_para_button.setAutoDefault(False)
        self.bcc_para_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.default_para_hbox.addWidget(self.bcc_para_button)
        self.bcc_para_button.clicked.connect(lambda: self.setBccParameter())
        self.bcc_para_button.setToolTip('Creates a bcc structure using the first element in the available element list')

        self.fcc_para_button = QPushButton('fcc')
        self.fcc_para_button.setAutoDefault(False)
        self.fcc_para_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.default_para_hbox.addWidget(self.fcc_para_button)
        self.fcc_para_button.clicked.connect(lambda: self.setFccParameter())
        self.fcc_para_button.setToolTip('Creates a fcc structure using the first element in the available element list')

        self.hex_para_button = QPushButton('hex')
        self.hex_para_button.setAutoDefault(False)
        self.hex_para_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.default_para_hbox.addWidget(self.hex_para_button)
        self.hex_para_button.clicked.connect(lambda: self.setHexParameter())
        self.hex_para_button.setToolTip('Creates a hex structure using the first element in the available element list')

        # Crystal parameter table
        self.crystal_table_vbox = VBoxTitleLayout(self, 'Crystal parameter table', spacing=2, add_stretch=False)
        self.lattice_parameter_vbox.addLayout(self.crystal_table_vbox)

        self.crystal_table_group_box = QGroupBox(self)
        self.crystal_table_vbox.addWidget(self.crystal_table_group_box)

        self.crystal_table_hbox = QHBoxLayout()
        self.crystal_table_group_box.setLayout(self.crystal_table_hbox)

        self.table_crystal = CrystalTable(
            self,
            target_elements=self.target_elements,
            row_fields=self.simulation_class.CrystalRowSettings.rowFields,
            custom_comp_row=self.simulation_class.CrystalRowSettings,
            version=self.simulation_configuration.version
        )

        self.table_crystal.coordinateChanged.connect(lambda: self.crystalCoordinatesChanged())
        self.crystal_table_hbox.addWidget(self.table_crystal)

        # Finish editing button
        self.hbox_button_done = QHBoxLayout()
        self.lattice_parameter_vbox.addLayout(self.hbox_button_done)

        self.button_done = QPushButton('Finish editing')
        self.button_done.setAutoDefault(False)
        self.hbox_button_done.addWidget(self.button_done, Qt.AlignmentFlag.AlignHCenter)
        self.button_done.pressed.connect(self.close)

        # Crystal orientation preview
        self.crystal_preview_vbox = VBoxTitleLayout(self, 'Crystal Preview', spacing=2, add_stretch=False)
        self.previews_vbox.addLayout(self.crystal_preview_vbox, stretch=1)

        self.crystal_preview_group_box = QGroupBox(self)
        self.crystal_preview_vbox.addWidget(self.crystal_preview_group_box)

        self.preview_plot_vbox = QVBoxLayout()
        self.crystal_preview_group_box.setLayout(self.preview_plot_vbox)

        self.crystal_preview = CrystalPreview(
            self,
            show_basis_vecs=True,
            atom_size=100,
            width=6,
            height=10,
            disable_interaction=False
        )
        self.preview_plot_vbox.addWidget(self.crystal_preview, stretch=1)

        self.output_plot_toolbar_crystal_preview = NoMessageToolbar(self.crystal_preview, self)
        self.preview_plot_vbox.addWidget(self.crystal_preview, stretch=1)
        self.preview_plot_vbox.addWidget(self.output_plot_toolbar_crystal_preview)

        # previews in the third column, the parameters and the crystal definition share the remaining space
        self.orientation_hbox.addLayout(self.previews_vbox, stretch=5)
        self.orientation_hbox.setStretch(0, 3)
        self.orientation_hbox.setStretch(1, 3)

        # finish button below all columns
        self.lattice_parameter_vbox.removeItem(self.hbox_button_done)
        self.main_layout.addLayout(self.hbox_button_done)

        if self.table_mode:
            self.setupTableMode()

    def setupTableMode(self):
        """
        Replaces the definition of the unit cell by a selection of up to three crystals from tables/table.crystal.
        The fractions of the crystals in the layers are defined in the target structure.
        """

        # hide widgets that are defined in table.crystal or per crystal
        for layout in [self.basis_vectors_vbox, self.default_para_vbox, self.crystal_table_vbox, self.miller_indices_vbox]:
            setLayoutVisible(layout, False)
        for layout in [self.layout_impact_parameter, self.layout_lattice_constant, *self.layout_matrices]:
            setLayoutVisible(layout, False)

        # crystals (first column)
        self.table_vbox = VBoxTitleLayout(self, 'Crystals from table.crystal', spacing=2, add_stretch=False)
        self.orientation_parameter_vbox.insertLayout(0, self.table_vbox)

        self.table_group_box = QGroupBox(self)
        self.table_vbox.addWidget(self.table_group_box)
        table_layout = QVBoxLayout()
        self.table_group_box.setLayout(table_layout)

        self.crystal_list = QTableWidget(0, 4, self)
        self.crystal_list.setHorizontalHeaderLabels(['Crystal', 'h', 'k', 'l'])
        self.crystal_list.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.crystal_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.crystal_list.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.crystal_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.crystal_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.crystal_list.setToolTip(
            '<i>name_cryst1..3, miller_ind1..3</i><br>Up to three crystals from tables/table.crystal and their miller indices.<br>'
            'The fractions of the crystals in the layers are set in the target structure.<br>'
            'The selected crystal is shown in the previews'
        )
        self.crystal_list.itemSelectionChanged.connect(self.tableCrystalChanged)
        table_layout.addWidget(self.crystal_list)

        buttons_layout = QHBoxLayout()
        self.add_crystal_button = QPushButton(getIcon('add'), ' Add')
        self.add_crystal_button.setAutoDefault(False)
        self.add_crystal_button.setToolTip(f'Add a crystal (at most {CrystalTableLimits.max_crystals})')
        self.add_crystal_button.clicked.connect(lambda: self.addTableCrystal())
        buttons_layout.addWidget(self.add_crystal_button)

        self.remove_crystal_button = QPushButton(getIcon('close'), ' Remove')
        self.remove_crystal_button.setAutoDefault(False)
        self.remove_crystal_button.setToolTip('Remove the selected crystal')
        self.remove_crystal_button.clicked.connect(self.removeTableCrystal)
        buttons_layout.addWidget(self.remove_crystal_button)

        self.new_crystal_button = QPushButton(getIcon('new'), ' New crystal...')
        self.new_crystal_button.setAutoDefault(False)
        self.new_crystal_button.setToolTip('Create a new crystal or import one from a CIF or VASP file and add it to table.crystal')
        self.new_crystal_button.clicked.connect(self.newTableCrystal)
        buttons_layout.addWidget(self.new_crystal_button)
        buttons_layout.addStretch(1)
        table_layout.addLayout(buttons_layout)

        self.crystal_dyn = InputHBoxLayout(
            'Dynamic amorphization of the crystals',
            None,
            checkbox=DefaultValues.l_crystal_dyn,
            tooltip='<i>l_crystal_dyn</i><br>If checked the amorphization of the crystals is calculated'
        )
        table_layout.addLayout(self.crystal_dyn)

        self.table_crystal_validation = QLabel('')
        self.table_crystal_validation.setWordWrap(True)
        self.table_crystal_validation.setStyleSheet('color: #bf3e2f;')
        table_layout.addWidget(self.table_crystal_validation)

        # selected crystal (second column)
        self.selected_vbox = VBoxTitleLayout(self, 'Selected crystal', spacing=2, add_stretch=False)
        self.lattice_parameter_vbox.insertLayout(0, self.selected_vbox)

        self.selected_group_box = QGroupBox(self)
        self.selected_vbox.addWidget(self.selected_group_box)
        selected_layout = QVBoxLayout()
        self.selected_group_box.setLayout(selected_layout)

        self.table_crystal_info = QLabel('')
        self.table_crystal_info.setWordWrap(True)
        self.table_crystal_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        selected_layout.addWidget(self.table_crystal_info)

        self.table_atoms = QTableWidget(0, 4, self)
        self.table_atoms.setHorizontalHeaderLabels(['Element', 'a₁', 'a₂', 'a₃'])
        self.table_atoms.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_atoms.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_atoms.setToolTip(
            'Atoms of the selected crystal in relative coordinates along the basis vectors a₁, a₂, a₃ of the unit cell, defined in table.crystal.<br>'
            'The orientation of the unit cell relative to the target is given by the miller index'
        )
        selected_layout.addWidget(self.table_atoms, stretch=1)
        self.lattice_parameter_vbox.setStretch(0, 1)

        self.loadCrystalTable()
        self.addTableCrystal()

    def crystalTablePath(self) -> Optional[Path]:
        """Returns path to table.crystal of the simulation"""

        folder = self.simulation_configuration.folder
        if folder is None:
            return None
        return folder / 'tables' / 'table.crystal'

    def loadCrystalTable(self, select: Optional[str] = None):
        """
        (Re)loads table.crystal of the simulation and updates the selectable crystals

        :param select: (optional) name of crystal to set for the selected crystal
        """

        if not self.table_mode:
            return

        path = self.crystalTablePath()
        self.table_file = None
        error = ''
        try:
            if path is None:
                raise CrystalTableError('No simulation folder defined')
            self.table_file = CrystalTableFile(path, CrystalTableLimits(self.simulation_configuration.version))
        except CrystalTableError as table_error:
            error = str(table_error)

        for row in range(self.crystal_list.rowCount()):
            combobox = self.crystal_list.cellWidget(row, 0)
            if combobox is not None:
                self.fillCrystalCombobox(combobox, combobox.currentData())

        if select is not None:
            row = self.selectedCrystalRow()
            if row >= 0 and self.crystal_list.cellWidget(row, 0) is not None:
                combobox = self.crystal_list.cellWidget(row, 0)
                combobox.setCurrentIndex(max(0, combobox.findData(select)))

        self.new_crystal_button.setEnabled(self.table_file is not None)
        if error:
            self.table_crystal_info.setText(f'<span style="color: #bf3e2f;">Could not read table.crystal: {error}</span>')
        self.tableCrystalChanged()

    def fillCrystalCombobox(self, combobox: QComboBox, name: Optional[str] = None):
        """Fills a combobox with the crystals of table.crystal and selects name if possible"""

        combobox.blockSignals(True)
        combobox.clear()
        if self.table_file is not None:
            for crystal in self.table_file.crystals:
                combobox.addItem(f'{crystal.name}  ({crystal.compositionStr()})', crystal.name)
        if name is not None:
            index = combobox.findData(name)
            if index < 0:
                # keep unknown names (e.g. from loaded files), they are marked as invalid
                combobox.addItem(f'{name}  (not in table.crystal)', name)
                index = combobox.count() - 1
            combobox.setCurrentIndex(index)
        combobox.blockSignals(False)

    def addTableCrystal(self, name: Optional[str] = None, miller: Optional[List[float]] = None):
        """Adds a crystal to the list of crystals"""

        if self.crystal_list.rowCount() >= CrystalTableLimits.max_crystals:
            return

        row = self.crystal_list.rowCount()
        self.crystal_list.blockSignals(True)
        self.crystal_list.insertRow(row)

        combobox = QComboBox(self)
        self.fillCrystalCombobox(combobox, name)
        if name is None and combobox.count() > row:
            combobox.setCurrentIndex(row)
        combobox.currentIndexChanged.connect(lambda _: self.tableCrystalChanged())
        self.crystal_list.setCellWidget(row, 0, combobox)

        if miller is None:
            miller = list(DefaultValues.miller_ind)
        for column, value in enumerate(miller, start=1):
            box = DoubleSpinBox(0, input_range=SpinBoxRange.INF_INF, decimals=2)
            box.setValue(float(value))
            box.setMinimumWidth(50)
            box.valueChanged.connect(lambda _: self.tableCrystalChanged())
            self.crystal_list.setCellWidget(row, column, box)
        self.crystal_list.blockSignals(False)

        self.crystal_list.selectRow(row)
        self.crystalsChanged()

    def removeTableCrystal(self):
        """Removes the selected crystal (at least one crystal stays)"""

        row = self.selectedCrystalRow()
        if self.crystal_list.rowCount() <= 1 or row < 0:
            return
        self.crystal_list.removeRow(row)
        self.crystal_list.selectRow(min(row, self.crystal_list.rowCount() - 1))
        self.crystalsChanged()

    def selectedCrystalRow(self) -> int:
        """Returns the row of the selected crystal or -1"""

        rows = {index.row() for index in self.crystal_list.selectedIndexes()}
        if rows:
            return min(rows)
        return 0 if self.crystal_list.rowCount() else -1

    def tableCrystalsList(self) -> List[dict]:
        """Returns the crystals as list of {'name': str, 'miller': list}"""

        crystals = []
        for row in range(self.crystal_list.rowCount()):
            if any(self.crystal_list.cellWidget(row, column) is None for column in range(4)):
                continue
            name = self.crystal_list.cellWidget(row, 0).currentData()
            miller = [self.crystal_list.cellWidget(row, column).value() for column in (1, 2, 3)]
            crystals.append({'name': name or '', 'miller': miller})
        return crystals

    def crystalsChanged(self):
        """Emits the names of the crystals (the target structure shows a column for each crystal)"""

        if not self.table_mode:
            return
        self.add_crystal_button.setEnabled(self.crystal_list.rowCount() < CrystalTableLimits.max_crystals)
        self.remove_crystal_button.setEnabled(self.crystal_list.rowCount() > 1)
        self.crystalListChanged.emit([crystal['name'] for crystal in self.tableCrystalsList()])
        self.tableCrystalChanged()

    def newTableCrystal(self):
        """Opens the dialog to create a new crystal in table.crystal"""

        if self.table_file is None:
            return

        symbols = []
        if self.element_data is not None:
            symbols = [element.symbol for element in self.element_data.elements]
        symbols += [element.symbol for element in self.available_elements]

        dialog = NewCrystalDialog(self, self.table_file, symbols)
        if dialog.exec() and dialog.created_crystal is not None:
            self.loadCrystalTable(select=dialog.created_crystal.name)

    def elementFromSymbol(self, symbol: str) -> Optional[Element]:
        """Returns the element with given symbol from the target elements or the element data"""

        for element in self.available_elements:
            if element.symbol == symbol:
                return element
        if self.element_data is not None:
            return self.element_data.elementFromSymbol(symbol)
        return None

    def validateTableCrystals(self) -> List[str]:
        """Returns problems of the crystals that prevent saving (the fractions in the layers are checked by the simulation)"""

        errors = []
        crystals = self.tableCrystalsList()
        names = [crystal['name'] for crystal in crystals]
        target_symbols = [element.symbol for element in self.available_elements]

        if self.table_file is None:
            errors.append('table.crystal could not be read')
            return errors

        for i, name in enumerate(names, start=1):
            crystal = self.table_file.crystal(name)
            if crystal is None:
                errors.append(f'Crystal {i} "{name}" does not exist in table.crystal')
                continue
            missing = [symbol for symbol in crystal.distinctElements() if symbol not in target_symbols]
            if missing:
                errors.append(f'The target must contain the element(s) {", ".join(missing)} of crystal {i} "{name}"')
        if len(set(names)) != len(names):
            errors.append('Each crystal can only be used once')
        return errors

    def tableCrystalChanged(self):
        """Updates info, atoms, previews and validation of the selected crystal"""

        if not hasattr(self, 'crystal_list'):
            return

        row = self.selectedCrystalRow()
        if row >= 0 and self.crystal_list.cellWidget(row, 0) is None:
            # row is being created
            return
        name = self.crystal_list.cellWidget(row, 0).currentData() if row >= 0 else None
        crystal = self.table_file.crystal(name) if self.table_file is not None and name is not None else None
        self.table_crystal_selected = crystal
        self.table_atoms.setRowCount(0)

        crystal_coordinates_dict = {}
        if crystal is None:
            if self.table_file is not None:
                self.table_crystal_info.setText('No crystal selected')
        else:
            structure = self.table_file.structure(crystal.structure)
            structure_name = structure.name if structure is not None else f'{crystal.structure} (missing)'
            info = (
                f'<b>{crystal.name}</b>: {crystal.compositionStr()}, structure {structure_name}<br>'
                f'dx = dy = {crystal.dx:g} Å, dz = {crystal.dz:g} Å, density = {crystal.density:g} at./Å³<br>'
                f'ΔH_f = {crystal.deltahf:g} eV, p_max = {crystal.p_max:g} Å, matrix {crystal.matrix_id}x{crystal.matrix_id}x{crystal.matrix_id}'
            )
            if len(crystal.distinctElements()) > 1:
                ratios = ', '.join(f'{element}: {count / len(crystal.elements):.4g}' for element, count in crystal.composition().items())
                info += f'<br><i>Stoichiometry of the crystal: {ratios}</i>'
            self.table_crystal_info.setText(info)

            if structure is not None:
                for element, position in zip(crystal.elements, structure.positions):
                    atom_row = self.table_atoms.rowCount()
                    self.table_atoms.insertRow(atom_row)
                    self.table_atoms.setItem(atom_row, 0, QTableWidgetItem(element))
                    for column, value in enumerate(position, start=1):
                        self.table_atoms.setItem(atom_row, column, QTableWidgetItem(f'{value:.4f}'))

            _, coordinates = self.table_file.basisAndCoordinates(crystal)
            for symbol, positions in coordinates.items():
                element = self.elementFromSymbol(symbol)
                if element is None:
                    continue
                crystal_coordinates_dict[element] = np.vstack([getPeriodicCoords(position) for position in positions])

        errors = self.validateTableCrystals()
        self.table_crystal_validation.setText('<br>'.join(errors))
        self.undefined_state = bool(errors)
        self.crystalDefinedChanged.emit(self.undefined_state)

        basis_vecs = np.identity(3)
        if crystal is not None and crystal.dx > 0:
            basis_vecs = np.diag([1., 1., crystal.dz / crystal.dx])
        crystals = self.tableCrystalsList()
        miller_ind = np.array(crystals[row]['miller']) if 0 <= row < len(crystals) else np.zeros(3)

        for preview in (self.orientation_preview, self.crystal_preview):
            preview.updateParams(basis_vecs=basis_vecs, crystal_coords=crystal_coordinates_dict, miller_ind=miller_ind)
        self.crystalBasisChanged.emit(basis_vecs)
        self.crystalCoordsChanged.emit(crystal_coordinates_dict)
        self.crystalMillerChanged.emit(miller_ind)

    def getRowArguments(self) -> List[CrystalRowArguments]:
        """Returns the atoms of the crystal as list of <CrystalRowArguments> (in table mode the atoms of the first crystal)"""

        if not self.table_mode:
            return self.table_crystal.getArguments()

        rows = []
        crystals = self.tableCrystalsList()
        crystal = self.table_file.crystal(crystals[0]['name']) if crystals and self.table_file is not None else None
        if crystal is None:
            return rows
        structure = self.table_file.structure(crystal.structure)
        if structure is None:
            return rows
        for element, position in zip(crystal.elements, structure.positions):
            rows.append(CrystalRowArguments(symbol=element, coord=Coordinate(list(position))))
        return rows

    def reset(self):
        """Resets the crystal parameters and table"""

        # Reset miller indices
        self.layout_miller_ind.reset()

        # Reset Basis vectors
        for layout_basis_vec in self.layout_basis_vecs:
            layout_basis_vec.reset()

        # Reset Beam Settings
        self.beam_dy.reset()
        self.beam_dz.reset()
        self.impact_parameter.reset()
        self.lattice_constant.reset()

        # Reset matrices
        self.resetMatrix(DefaultValues.matrix_id)

        # Reset Crystal orientation settings
        self.show_coordinate_system.reset()

        # Reset crystal table
        self.table_crystal.resetTable()

        # one crystal from table.crystal in all layers
        if self.table_mode:
            self.crystal_dyn.reset()
            self.crystal_list.setRowCount(0)
            self.loadCrystalTable()
            self.addTableCrystal()

    def resetMatrix(self, selected_matrix: int) -> bool:
        """Select given matrix"""

        matrix_check_flag = False
        for layout_matrix, id_matrix in zip(self.layout_matrices, self.id_matrices):
            if selected_matrix != id_matrix:
                layout_matrix.checkbox.setChecked(False)
            else:
                layout_matrix.checkbox.setChecked(True)
                matrix_check_flag = True
        if not matrix_check_flag:
            self.layout_matrices[0].checkbox.setChecked(True)

        return matrix_check_flag

    def addRow(self):
        """Adds a Row to the table"""
        self.table_crystal.addRow()

    def elementChanged(self):
        """Gets called if an element was changed"""

        self.available_elements = []
        for row in self.table_target.rows:
            row.blockSignals(True)
            if row.element.symbol:
                self.available_elements.append(row.element)
            row.blockSignals(False)

        self.table_crystal.blockSignals(True)
        self.table_crystal.updateAvailableElements(self.available_elements)
        self.table_crystal.blockSignals(False)

        for row in self.table_crystal.getRows():
            row.blockSignals(True)
            row.setAvailableElements(self.available_elements)
            row.blockSignals(False)

        if self.table_mode:
            self.tableCrystalChanged()
            return

        self.table_crystal.coordinateChanged.emit()

    def crystalCoordinatesChanged(self):
        """Gets called if any crystal coordinate was changed"""

        # in table mode the coordinates are defined in table.crystal
        if self.table_mode:
            return

        crystal_coordinates_dict = {}
        total_coord_list = []

        for element in self.available_elements:
            crystal_coordinates_dict[element] = []

        self.undefined_state = False
        for row in self.table_crystal.getRows():
            element = row.getSelectedElement()
            if element not in self.available_elements:
                setWidgetHighlight(row.element_combobox, True)
                self.undefined_state = True
                continue
            coord = np.array([coord_inp.value() for coord_inp in row.coords])
            coord_list = crystal_coordinates_dict[element]

            seen_flag = False
            for coord_l in total_coord_list:
                coord_l = np.atleast_2d(coord_l)
                if np.any(np.all(coord_l == coord, axis=1)):
                    for coord_inp in row.coords:
                        setWidgetHighlight(coord_inp, True)
                    seen_flag = True
                    continue
                if seen_flag:
                    continue

            for coord_inp in row.coords:
                setWidgetHighlight(coord_inp, seen_flag)
            if seen_flag:
                continue

            coords = getPeriodicCoords(coord)
            coord_list.append(coords)
            total_coord_list.append(coords)
            crystal_coordinates_dict[element] = coord_list

            setWidgetHighlight(row.element_combobox, not row.element_combobox.currentIndex())

        self.crystalDefinedChanged.emit(self.undefined_state)

        for (element, coord_list) in crystal_coordinates_dict.items():
            if coord_list:
                crystal_coordinates_dict[element] = np.vstack(coord_list)

        self.orientation_preview.updateParams(crystal_coords=crystal_coordinates_dict)
        self.crystal_preview.updateParams(crystal_coords=crystal_coordinates_dict)

        self.crystalCoordsChanged.emit(crystal_coordinates_dict)

    def millerIndChanged(self):
        """Gets called if miller index was changed"""

        # in table mode the miller indices are defined per crystal
        if self.table_mode:
            return

        miller_ind = np.array([widget.value() for widget in self.miller_ind])

        self.orientation_preview.updateParams(miller_ind=miller_ind)
        self.crystal_preview.updateParams(miller_ind=miller_ind)

        self.crystalMillerChanged.emit(miller_ind)

    def basisVecsChanged(self):
        """Gets called if basis vectors were changed"""

        # in table mode the basis vectors are defined in table.crystal
        if self.table_mode:
            return

        basis_vecs = np.array([
            [widget.value() for widget in self.basis_vecs[0]],
            [widget.value() for widget in self.basis_vecs[1]],
            [widget.value() for widget in self.basis_vecs[2]],
        ])

        self.orientation_preview.updateParams(basis_vecs=basis_vecs)
        self.crystal_preview.updateParams(basis_vecs=basis_vecs)

        self.crystalBasisChanged.emit(basis_vecs)

    def showCoordinateSystem(self):
        """Gets called if show_coordinate_system button is checked"""
        self.orientation_preview.updateParams(show_coordinate_system=self.show_coordinate_system.checkbox.isChecked())

    def matrixClicked(self, layout_matrix_clicked):
        """Gets called if matrix button changes"""

        for layout_matrix in self.layout_matrices:
            layout_matrix.checkbox.setChecked(False)

        layout_matrix_clicked.checkbox.setChecked(True)

    def getMatrixId(self) -> int:
        """Get id of selected matrix"""

        for i, layout_matrix in enumerate(self.layout_matrices):
            if layout_matrix.checkbox.isChecked():
                return self.id_matrices[i]
        return DefaultValues.matrix_id

    def getArguments(self) -> GeneralCrystalArguments:
        """" get <GeneralCrystalArgument> """

        if self.table_mode:
            crystals = self.tableCrystalsList()
            first = self.table_file.crystal(crystals[0]['name']) if crystals and self.table_file is not None else None
            dx = first.dx if first is not None else DefaultValues.lattice_constant
            dz = first.dz if first is not None else DefaultValues.lattice_constant
            return GeneralCrystalArguments(
                name=crystals[0]['name'] if crystals else '',
                lattice_id=1,
                lattice_constant=dx,

                basis_vec_a1=BasisVector([1, 0, 0]),
                basis_vec_a2=BasisVector([0, 1, 0]),
                basis_vec_a3=BasisVector([0, 0, dz / dx if dx else 1]),
                miller_ind=MillerIndex(list(crystals[0]['miller']) if crystals else [0, 0, 0]),

                beam_dy=self.beam_dy.value(),
                beam_dz=self.beam_dz.value(),
                crystal_dyn=self.crystal_dyn.checkbox.isChecked(),
                crystals=crystals,
                table_crystal=True
            )

        return GeneralCrystalArguments(
            name=self.crystal_name,
            lattice_id=self.lattice_id,
            lattice_constant=self.lattice_constant.value(),

            basis_vec_a1=BasisVector([widget.value() for widget in self.basis_vecs[0]]),
            basis_vec_a2=BasisVector([widget.value() for widget in self.basis_vecs[1]]),
            basis_vec_a3=BasisVector([widget.value() for widget in self.basis_vecs[2]]),
            miller_ind=MillerIndex([widget.value() for widget in self.miller_ind]),

            p_max=self.impact_parameter.value(),
            beam_dy=self.beam_dy.value(),
            beam_dz=self.beam_dz.value(),
            matrix_id=self.getMatrixId()
        )

    def loadArguments(self, arguments: SimulationArguments) -> List[str]:
        """Loads <SimulationArguments> container. Returns list of not loadable parameters (default used)"""

        crystal_args = arguments.crystal_args
        if not isinstance(crystal_args, GeneralCrystalArguments):
            return []

        assumed = arguments.optional.get('assumed')
        if not isinstance(assumed, list):
            assumed = []
        not_loadable = []

        if self.table_mode:
            return self.loadTableArguments(crystal_args, assumed)

        # name
        crystal_name = crystal_args.name
        if 'name' in assumed:
            crystal_name = DefaultValues.crystal_name
            not_loadable.append('name')
        # TODO: highlight if we have field available and set value properly
        self.crystal_name = crystal_name

        # lattice id
        lattice_id = crystal_args.lattice_id
        if 'lattice_id' in assumed:
            lattice_id = DefaultValues.lattice_id
            not_loadable.append('lattice_id')
        # TODO: highlight if we have field available and set value properly
        self.lattice_id = lattice_id

        # basis vectors
        basis_vec_a1 = crystal_args.basis_vec_a1
        if 'basis_vec_a1' in assumed:
            basis_vec_a1 = DefaultValues.basis_vec_a1
            self.layout_basis_vecs[0].mark()
            not_loadable.append('basis_vec_a1')

        for widget, val in zip(self.basis_vecs[0], basis_vec_a1):
            widget.setValue(val)

        basis_vec_a2 = crystal_args.basis_vec_a2
        if 'basis_vec_a2' in assumed:
            basis_vec_a2 = DefaultValues.basis_vec_a2
            self.layout_basis_vecs[1].mark()
            not_loadable.append('basis_vec_a2')

        for widget, val in zip(self.basis_vecs[1], basis_vec_a2):
            widget.setValue(val)

        basis_vec_a3 = crystal_args.basis_vec_a3
        if 'basis_vec_a3' in assumed:
            basis_vec_a3 = DefaultValues.basis_vec_a3
            self.layout_basis_vecs[2].mark()
            not_loadable.append('basis_vec_a3')

        for widget, val in zip(self.basis_vecs[2], basis_vec_a3):
            widget.setValue(val)

        # miller indices
        miller_ind = crystal_args.miller_ind
        if 'miller_indices_list' in assumed:
            miller_ind = DefaultValues.miller_ind
            self.layout_miller_ind.mark()
            not_loadable.append('miller_indices_list')

        for widget, val in zip(self.miller_ind, miller_ind):
            widget.setValue(val)

        # beam parameters
        beam_dy = crystal_args.optional.get('beam_dy', DefaultValues.beam_dy)
        if 'beam_dy' in assumed:
            beam_dy = DefaultValues.beam_dy
            self.layout_beam_dy.mark()
            not_loadable.append('beam_dy')

        self.beam_dy.setValue(beam_dy)

        beam_dz = crystal_args.optional.get('beam_dz', DefaultValues.beam_dz)
        if 'beam_dz' in assumed:
            beam_dz = DefaultValues.beam_dz
            self.layout_beam_dz.mark()
            not_loadable.append('beam_dz')

        self.beam_dz.setValue(beam_dz)

        p_max = crystal_args.optional.get('p_max', DefaultValues.p_max)
        if 'p_max' in assumed:
            p_max = DefaultValues.p_max
            self.layout_impact_parameter.mark()
            not_loadable.append('p_max')

        self.impact_parameter.setValue(p_max)

        lattice_constant = crystal_args.lattice_constant
        if 'lattice_constant' in assumed:
            lattice_constant = DefaultValues.lattice_constant
            self.layout_lattice_constant.mark()
            not_loadable.append('lattice_constant')

        self.lattice_constant.setValue(lattice_constant)

        #matrix
        matrix_id = crystal_args.optional.get('matrix_id', DefaultValues.matrix_id)
        if 'matrix_id' in assumed:
            matrix_id = DefaultValues.matrix_id
            for layout_matrix in self.layout_matrices:
                layout_matrix.mark()
            not_loadable.append('matrix_id')

        if not self.resetMatrix(matrix_id):
            for layout_matrix in self.layout_matrices:
                layout_matrix.mark()
            not_loadable.append('matrix_id')

        return not_loadable

    def loadTableArguments(self, crystal_args: GeneralCrystalArguments, assumed: list) -> List[str]:
        """Loads the crystal arguments in table mode. Returns list of not loadable parameters (default used)"""

        from Simulations.SDTrimSP import tableCrystals

        not_loadable = []

        # crystals from table.crystal
        self.loadCrystalTable()
        self.crystal_list.setRowCount(0)
        crystals = tableCrystals(crystal_args)
        if 'miller_indices_list' in assumed:
            not_loadable.append('miller_indices_list')
        for crystal in crystals:
            self.addTableCrystal(crystal['name'], crystal['miller'])
            if self.table_file is None or self.table_file.crystal(crystal['name']) is None or 'name' in assumed:
                not_loadable.append(f'crystal "{crystal["name"]}" (not found in table.crystal)')
        if not crystals:
            self.addTableCrystal()

        self.crystalsChanged()

        # beam parameters
        for key, widget, layout in [('beam_dy', self.beam_dy, self.layout_beam_dy), ('beam_dz', self.beam_dz, self.layout_beam_dz)]:
            value = crystal_args.optional.get(key, getattr(DefaultValues, key))
            if key in assumed:
                value = getattr(DefaultValues, key)
                layout.mark()
                not_loadable.append(key)
            widget.setValue(value)

        # dynamic amorphization
        crystal_dyn = crystal_args.optional.get('crystal_dyn', DefaultValues.l_crystal_dyn)
        self.crystal_dyn.checkbox.setChecked(bool(crystal_dyn))

        self.crystal_list.selectRow(0)
        self.tableCrystalChanged()
        return not_loadable

    def open(self):
        """Opens the dialog, in table mode table.crystal is reloaded (it might have changed)"""

        if self.table_mode:
            self.loadCrystalTable()
        super().open()

    def setBasisSpinboxes(self, a: List[List[float]]):
        """
        Sets values of basis spinboxes

        :param a: basis vectors
        """

        for basis_vec, ai in zip(self.basis_vecs, a):
            for v, aii in zip(basis_vec, ai):
                v.setValue(aii)

    def setLatticePoints(self, lattice_points: List[List[float]]):
        """
        Sets lattice points

        :param lattice_points: lattice points
        """

        self.table_crystal.resetTable()
        self.table_crystal.blockSignals(True)

        for _ in lattice_points:
            self.table_crystal.addRow()

        self.table_crystal.blockSignals(False)

        for i, row in enumerate(self.table_crystal.getRows()):
            row.blockSignals(True)
            for j in range(3):
                row.coords[j].setValue(lattice_points[i][j])

            if row.element_combobox.count() > 1:
                row.element_combobox.setCurrentIndex(1)
            else:
                row.element_combobox.setCurrentIndex(0)

            row.blockSignals(False)
            self.table_crystal.coordinateChanged.emit()

    def setBccParameter(self):
        """Standard bcc crystal"""

        self.setBasisSpinboxes([
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, 1]
        ])
        self.setLatticePoints([
            [0, 0, 0],
            [0.5, 0.5, 0.5]
        ])

    def setFccParameter(self):
        """Standard fcc crystal"""

        self.setBasisSpinboxes([
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, 1]
        ])
        self.setLatticePoints([
            [0, 0, 0],
            [0.5, 0.5, 0],
            [0, 0.5, 0.5],
            [0.5, 0, 0.5]
        ])

    def setHexParameter(self):
        """Standard hex crystal"""

        self.setBasisSpinboxes([
            [1, 0, 0],
            [0, np.sqrt(3) / 2, 0],
            [0, 0, 1]
        ])
        self.setLatticePoints([
            [0, 0.5, 0],
            [0, 0, 0.25],
            [0, 0, 0.75]
        ])
