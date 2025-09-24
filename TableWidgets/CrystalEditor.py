# TODO: this is not a very general class for different simulation codes, but rather only SDTrimSP...
#   we should create a base class and nest simulation code specific layouts into this at some point

from typing import List


from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QGroupBox, QSizePolicy, QPushButton

import numpy as np


from TableWidgets.CompTable import CompTable
from TableWidgets.CrystalTable import CrystalTable

from Utility.Layouts import (
    InputHBoxLayout, InputHBoxLayouts, VBoxTitleLayout, DoubleSpinBox, SpinBox, SpinBoxRange,
    CrystalPreview, NoMessageToolbar
)
from Utility.Functions import getPeriodicCoords
from Utility.ModifyWidget import setWidgetHighlight, setWidgetBackground

from Containers.SimulationConfiguration import SimulationConfiguration
from Containers.Element import Element
from Containers.Arguments import GeneralCrystalArguments, SimulationArguments
from Containers.Crystal import MillerIndex, BasisVector

from Simulations.SDTrimSP import DefaultValues


class CrystalEditorDialog(QDialog):
    """
    Crystal editor window that extends QDialog

    :param parent: parent widget
    :param simulation_configuration: <SimulationConfiguration>
    :param target_elements: list of elements
    :param table_target: <CompTable>
    """

    crystalDefinedChanged = pyqtSignal(bool)
    crystalCoordsChanged = pyqtSignal(dict)
    crystalMillerChanged = pyqtSignal(np.ndarray)
    crystalBasisChanged = pyqtSignal(np.ndarray)

    def __init__(
        self,
        parent,
        simulation_configuration: SimulationConfiguration,
        target_elements: List[Element],
        table_target: CompTable
    ):
        super().__init__(parent)

        self.crystal_name = DefaultValues.crystal_name
        self.lattice_id = DefaultValues.lattice_id

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

        self.orientation_hbox = QHBoxLayout()
        self.orientation_hbox.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.main_layout.addLayout(self.orientation_hbox)

        self.orientation_parameter_vbox = QVBoxLayout()
        self.orientation_parameter_vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.orientation_hbox.addLayout(self.orientation_parameter_vbox)
        self.orientation_parameter_vbox.setAlignment(Qt.AlignmentFlag.AlignLeft)

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
        self.orientation_hbox.addLayout(self.orientation_preview_vbox)

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
            axes_equal_radius=0.25,
            width=6,
            height=10,
            disable_interaction=False
        )
        self.orientation_preview_plot_vbox.addWidget(self.orientation_preview, stretch=1)

        self.output_plot_toolbar_orientation_preview = NoMessageToolbar(self.orientation_preview, self)
        self.orientation_preview_plot_vbox.addWidget(self.orientation_preview, stretch=1)
        self.orientation_preview_plot_vbox.addWidget(self.output_plot_toolbar_orientation_preview)

        # Crystal editor HBox
        self.crystal_edit_hbox = QHBoxLayout()
        self.crystal_edit_hbox.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.main_layout.addLayout(self.crystal_edit_hbox)

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
        self.bcc_para_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.default_para_hbox.addWidget(self.bcc_para_button)
        self.bcc_para_button.clicked.connect(lambda: self.setBccParameter())
        self.bcc_para_button.setToolTip('Creates a bcc structure using the first element in the available element list')

        self.fcc_para_button = QPushButton('fcc')
        self.fcc_para_button.setAutoDefault(False)
        self.fcc_para_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.default_para_hbox.addWidget(self.fcc_para_button)
        self.fcc_para_button.clicked.connect(lambda: self.setFccParameter())
        self.fcc_para_button.setToolTip('Creates a fcc structure using the first element in the available element list')

        self.hex_para_button = QPushButton('hex')
        self.hex_para_button.setAutoDefault(False)
        self.hex_para_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
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
        self.crystal_edit_hbox.addLayout(self.crystal_preview_vbox)

        self.crystal_preview_group_box = QGroupBox(self)
        self.crystal_preview_vbox.addWidget(self.crystal_preview_group_box)

        self.preview_plot_vbox = QVBoxLayout()
        self.crystal_preview_group_box.setLayout(self.preview_plot_vbox)

        self.crystal_preview = CrystalPreview(
            self,
            show_basis_vecs=True,
            atom_size=100,
            axes_equal_radius=0.5,
            width=6,
            height=10,
            disable_interaction=False
        )
        self.preview_plot_vbox.addWidget(self.crystal_preview, stretch=1)

        self.output_plot_toolbar_crystal_preview = NoMessageToolbar(self.crystal_preview, self)
        self.preview_plot_vbox.addWidget(self.crystal_preview, stretch=1)
        self.preview_plot_vbox.addWidget(self.output_plot_toolbar_crystal_preview)

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

        self.table_crystal.coordinateChanged.emit()

    def crystalCoordinatesChanged(self):
        """Gets called if any crystal coordinate was changed"""

        crystal_coordinates_dict = {}
        total_coord_list = []

        for element in self.available_elements:
            crystal_coordinates_dict[element] = []

        self.undefined_state = False
        for row in self.table_crystal.getRows():
            element = row.getSelectedElement()
            if element not in self.available_elements:
                setWidgetBackground(row.element_combobox, True)
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

            setWidgetBackground(row.element_combobox, not row.element_combobox.currentIndex())

        self.crystalDefinedChanged.emit(self.undefined_state)

        for (element, coord_list) in crystal_coordinates_dict.items():
            if coord_list:
                crystal_coordinates_dict[element] = np.vstack(coord_list)

        self.orientation_preview.updateParams(crystal_coords=crystal_coordinates_dict)
        self.crystal_preview.updateParams(crystal_coords=crystal_coordinates_dict)

        self.crystalCoordsChanged.emit(crystal_coordinates_dict)

    def millerIndChanged(self):
        """Gets called if miller index was changed"""

        miller_ind = np.array([widget.value() for widget in self.miller_ind])

        self.orientation_preview.updateParams(miller_ind=miller_ind)
        self.crystal_preview.updateParams(miller_ind=miller_ind)

        self.crystalMillerChanged.emit(miller_ind)

    def basisVecsChanged(self):
        """Gets called if basis vectors were changed"""

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
        assumed = arguments.optional.get('assumed')
        if not isinstance(assumed, list):
            assumed = []
        not_loadable = []

        # name
        crystal_name = crystal_args.name
        if 'name' in assumed:
            crystal_name = DefaultValues.crystal_name
            not_loadable.append('name')
        # TODO: highlight if we have field available and set value propperly
        self.crystal_name = crystal_name

        # lattice id
        lattice_id = crystal_args.lattice_id
        if 'lattice_id' in assumed:
            lattice_id = DefaultValues.lattice_id
            not_loadable.append('lattice_id')
        # TODO: highlight if we have field available and set value propperly
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
