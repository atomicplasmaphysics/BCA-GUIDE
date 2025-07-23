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


from typing import List

from PyQt6.QtCore import pyqtSignal, Qt, QSize, QEvent
from PyQt6.QtWidgets import (
    QDialog, QGridLayout, QLabel, QHBoxLayout, QVBoxLayout, QGroupBox, QSizePolicy, QPushButton )

import numpy as np

from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT


from TableWidgets.CompTable import CompTable
from TableWidgets.CrystalTable import CrystalTable

from Utility.Layouts import SpinBoxRange
from Utility.ModifyWidget import setWidgetHighlight

from Utility.Layouts import InputHBoxLayout,  VBoxTitleLayout, MplCanvas, DoubleSpinBox
from Utility.Indexing import Counter
from Utility.Functions import getElementColor

from Containers.SimulationConfiguration import SimulationConfiguration
from Containers.Element import Element
from Containers.Arguments import GeneralCrystalArguments, SimulationArguments
from Simulations.SDTrimSP import DefaultValues

class CrystalEditorDialog(QDialog):
    """
    QDialog with crystal editor.

    :param parent: parent widget
    """

    def __init__(self, parent, simulation_configuration: SimulationConfiguration, target_elements: List[str], table_target: CompTable):
        super().__init__(parent)
        self.target_elements = target_elements
        self.table_target = table_target
        self.available_elements: List[Element] = []
        self.available_element_list = []
        self.crystal_coordinates_dict = {}
        self.basis = None
        self.basis_rotated = None
        self.rot_mat = np.identity(3)
        self.elev_prev = -160
        self.azim_prev = -30
        self.elev_orien = -160
        self.azim_orien = -30
        self.miller_vec = np.zeros(3)
        self.rot_mat_y = np.array([[0, 0, -1], [0, 1, 0.], [1, 0, 0]])
        self.number_of_species = 0
        self.species_list = []

        # Set up window properties
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowTitle('Edit Crystal')

        self.simulation_configuration = simulation_configuration
        self.simulation_class = self.simulation_configuration.program_class()

        # Counter for components
        self.component_count = Counter(maximum=self.simulation_class.MaxComponents)

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

        self.miller_indices_hbox = QHBoxLayout()
        self.miller_indices_hbox.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.miller_indices_group_box.setLayout(self.miller_indices_hbox)

        # Miller indices Widgets
        self.miller_indices_label = QLabel('Miller Indices:')

        self.miller_index_h_label = QLabel('h:')
        self.miller_index_h = DoubleSpinBox(1., input_range=SpinBoxRange.ZERO_INF)

        self.miller_index_k_label = QLabel('k:')
        self.miller_index_k = DoubleSpinBox(0., input_range=SpinBoxRange.ZERO_INF)

        self.miller_index_l = DoubleSpinBox(0., input_range=SpinBoxRange.ZERO_INF)
        self.miller_index_l_label = QLabel('l:')

        # Miller indices ToolTips
        self.miller_indices_tooltip = '<i>miller_ind = h,k,l</i><br>defines crystal direction'
        self.miller_indices_label.setToolTip(self.miller_indices_tooltip)

        self.miller_index_h.setToolTip(self.miller_indices_tooltip)
        self.miller_index_h_label.setToolTip(self.miller_indices_tooltip)

        self.miller_index_k.setToolTip(self.miller_indices_tooltip)
        self.miller_index_k_label.setToolTip(self.miller_indices_tooltip)

        self.miller_index_l_label.setToolTip(self.miller_indices_tooltip)
        self.miller_index_l.setToolTip(self.miller_indices_tooltip)

        # Miller indices connections
        self.miller_index_h.valueChanged.connect(lambda: self.crystalCoordinatesChanged())
        self.miller_index_k.valueChanged.connect(lambda: self.crystalCoordinatesChanged())
        self.miller_index_l.valueChanged.connect(lambda: self.crystalCoordinatesChanged())

        # add Miller indices widgets to miller indices layout
        self.miller_indices_hbox.addWidget(self.miller_indices_label)
        self.miller_indices_hbox.addWidget(self.miller_index_h_label)
        self.miller_indices_hbox.addWidget(self.miller_index_h)
        self.miller_indices_hbox.addWidget(self.miller_index_k_label)
        self.miller_indices_hbox.addWidget(self.miller_index_k)
        self.miller_indices_hbox.addWidget(self.miller_index_l_label)
        self.miller_indices_hbox.addWidget(self.miller_index_l)

        # Basis vector layout
        self.basis_vectors_vbox = VBoxTitleLayout(self, 'Basis Vectors', spacing=2, add_stretch=False)
        self.orientation_parameter_vbox.addLayout(self.basis_vectors_vbox)

        self.basis_vectors_group_box = QGroupBox(self)
        self.basis_vectors_vbox.addWidget(self.basis_vectors_group_box)

        self.basis_vectors_grid = QGridLayout(self)
        self.basis_vectors_grid.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.basis_vectors_group_box.setLayout(self.basis_vectors_grid)

        # Basis vector widgets
        self.basis_vector_a1_x = DoubleSpinBox(1, input_range=SpinBoxRange.INF_INF, decimals=7)
        self.basis_vector_a1_y = DoubleSpinBox(0, input_range=SpinBoxRange.INF_INF, decimals=7)
        self.basis_vector_a1_z = DoubleSpinBox(0, input_range=SpinBoxRange.INF_INF, decimals=7)
        self.a1 = [self.basis_vector_a1_x, self.basis_vector_a1_y, self.basis_vector_a1_z]

        self.basis_vector_a2_x = DoubleSpinBox(0, input_range=SpinBoxRange.INF_INF, decimals=7)
        self.basis_vector_a2_y = DoubleSpinBox(1, input_range=SpinBoxRange.INF_INF, decimals=7)
        self.basis_vector_a2_z = DoubleSpinBox(0, input_range=SpinBoxRange.INF_INF, decimals=7)
        self.a2 = [self.basis_vector_a2_x, self.basis_vector_a2_y, self.basis_vector_a2_z]

        self.basis_vector_a3_x = DoubleSpinBox(0, input_range=SpinBoxRange.INF_INF, decimals=7)
        self.basis_vector_a3_y = DoubleSpinBox(0, input_range=SpinBoxRange.INF_INF, decimals=7)
        self.basis_vector_a3_z = DoubleSpinBox(1, input_range=SpinBoxRange.INF_INF, decimals=7)
        self.a3 = [self.basis_vector_a3_x, self.basis_vector_a3_y, self.basis_vector_a3_z]

        # Add basis vector widgets to basis vector layout
        for i, component in enumerate(self.a1):
            self.basis_vectors_grid.addWidget(component, 0, i+1)

        for i, component in enumerate(self.a2):
            self.basis_vectors_grid.addWidget(component, 1, i+1)

        for i, component in enumerate(self.a3):
            self.basis_vectors_grid.addWidget(component, 2, i+1)

        self.basis_vectors_grid.addWidget(QLabel('\u00E2<sub>1</sub> (x,y,z)'), 0, 0)
        self.basis_vectors_grid.addWidget(QLabel('\u00E2<sub>2</sub> (x,y,z)'), 1, 0)
        self.basis_vectors_grid.addWidget(QLabel('\u00E2<sub>3</sub> (x,y,z)'), 2, 0)

        # a\u2081
        # Basis vector tooltips
        self.basis_vector_a1_x.setToolTip('Basis vector \u00E2<sub>1</sub> in x-direction')
        self.basis_vector_a1_y.setToolTip('Basis vector \u00E2<sub>1</sub> in y-direction')
        self.basis_vector_a1_z.setToolTip('Basis vector \u00E2<sub>1</sub> in z-direction')

        self.basis_vector_a2_x.setToolTip('Basis vector \u00E2<sub>2</sub> in x-direction')
        self.basis_vector_a2_y.setToolTip('Basis vector \u00E2<sub>2</sub> in y-direction')
        self.basis_vector_a2_z.setToolTip('Basis vector \u00E2<sub>2</sub> in z-direction')

        self.basis_vector_a3_x.setToolTip('Basis vector \u00E2<sub>3</sub> in x-direction')
        self.basis_vector_a3_y.setToolTip('Basis vector \u00E2<sub>3</sub> in y-direction')
        self.basis_vector_a3_z.setToolTip('Basis vector \u00E2<sub>3</sub> in z-direction')

        # basis vector connections
        self.basis_vector_a1_x.valueChanged.connect(lambda: self.crystalCoordinatesChanged())
        self.basis_vector_a1_y.valueChanged.connect(lambda: self.crystalCoordinatesChanged())
        self.basis_vector_a1_z.valueChanged.connect(lambda: self.crystalCoordinatesChanged())
        self.basis_vector_a2_x.valueChanged.connect(lambda: self.crystalCoordinatesChanged())
        self.basis_vector_a2_y.valueChanged.connect(lambda: self.crystalCoordinatesChanged())
        self.basis_vector_a2_z.valueChanged.connect(lambda: self.crystalCoordinatesChanged())
        self.basis_vector_a3_x.valueChanged.connect(lambda: self.crystalCoordinatesChanged())
        self.basis_vector_a3_y.valueChanged.connect(lambda: self.crystalCoordinatesChanged())
        self.basis_vector_a3_z.valueChanged.connect(lambda: self.crystalCoordinatesChanged())

        #
        # Beam-Settings
        # Beam setting layout
        self.beam_settings_vbox = VBoxTitleLayout(self, 'Beam-Settings', spacing=2, add_stretch=False)
        self.orientation_parameter_vbox.addLayout(self.beam_settings_vbox)

        self.beam_settings_group_box = QGroupBox(self)
        self.beam_settings_vbox.addWidget(self.beam_settings_group_box)

        self.beam_vbox = QVBoxLayout()
        self.beam_settings_group_box.setLayout(self.beam_vbox)
        self.beam_hbox = QHBoxLayout()
        self.beam_hbox_2 = QHBoxLayout()
        self.beam_hbox_3 = QHBoxLayout()

        self.matrix_5 = InputHBoxLayout(
            'Matrix 5x5x5',
            None,
            checkbox=False,
            tooltip='<i>matrix_id = 5</i><br> the simulation is looking for the next collision partner in 5x5x5 field of the nearest target atoms'
        )

        self.matrix_3 = InputHBoxLayout(
            'Matrix 3x3x3',
            None,
            checkbox=True,
            tooltip='<i>matrix_id = 3</i><br> the simulation is looking for the next collision partner in 3x3x3 field of the nearest target atoms'
        )

        self.beam_vbox.addLayout(self.beam_hbox)
        self.beam_vbox.addLayout(self.beam_hbox_2)
        self.beam_vbox.addLayout(self.beam_hbox_3)

        self.beam_hbox_3.addLayout(self.matrix_5)
        self.beam_hbox_3.addLayout(self.matrix_3)

        # Beam setting widgets

        self.beam_dy = DoubleSpinBox(0.0, input_range=SpinBoxRange.INF_INF, decimals=7)
        self.beam_dz = DoubleSpinBox(0.0, input_range=SpinBoxRange.INF_INF, decimals=7)
        self.beam_dy.setToolTip('<i>beam_dy</i><br> Surface-area of one crystal is periodical in y,z-direction. If input is 0 the value is calculated automatically')
        self.beam_dz.setToolTip('<i>beam_dz</i> <br> Surface-area of one crystal is periodical in y,z-direction. If input is 0 the value is calculated automatically')


        self.impact_parameter = DoubleSpinBox(3., input_range=SpinBoxRange.INF_INF, decimals=7)
        self.lattice_constant = DoubleSpinBox(3., input_range=SpinBoxRange.INF_INF, decimals=7)
        self.impact_parameter.setToolTip('<i>p_max </i> <br> impact_parameter')
        self.lattice_constant.setToolTip('<i>lattice_constant</i> <br> is used to scale the basis-vectors in [Å]')

        # Add beam setting Widgets to beam_hbox...
        self.beam_hbox.addWidget(QLabel('Beam dy:'))
        self.beam_hbox.addWidget(self.beam_dy)

        self.beam_hbox.addWidget(QLabel('Beam dz:'))
        self.beam_hbox.addWidget(self.beam_dz)

        self.beam_hbox_2.addWidget(QLabel('Impact parameter:'))
        self.beam_hbox_2.addWidget(self.impact_parameter)

        self.beam_hbox_2.addWidget(QLabel('Lattice constant [Å]:'))
        self.beam_hbox_2.addWidget(self.lattice_constant)

        # Beam setting connection
        self.matrix_5.checkbox.clicked.connect(lambda: self.matrixParametersChanged(self.matrix_5.checkbox, self.matrix_3.checkbox))
        self.matrix_3.checkbox.clicked.connect(lambda: self.matrixParametersChanged(self.matrix_3.checkbox, self.matrix_5.checkbox))

        #
        # Additional settings layout
        self.additional_settings_vbox = VBoxTitleLayout(self, 'Crystal orientation preview settings', spacing=2, add_stretch=False)
        self.orientation_parameter_vbox.addLayout(self.additional_settings_vbox)

        self.additional_settings_group_box = QGroupBox(self)
        self.additional_settings_vbox.addWidget(self.additional_settings_group_box)

        self.additional_vbox = QVBoxLayout()
        self.additional_hbox = QHBoxLayout()
        self.additional_hbox_2 = QHBoxLayout()

        self.additional_settings_group_box.setLayout(self.additional_vbox)

        self.show_coordinate_system = InputHBoxLayout(
            'Show coordinate system',
            None,
            checkbox=False,
            tooltip='Toggles if coordinate system is shown in Crystal orientation preview'
        )


        self.show_miller_vector = InputHBoxLayout(
            'Show Miller-Vector',
            None,
            checkbox=False,
            tooltip='Toggles if the vector composed of the miller indices is shown in Crystal orientation preview'
        )


        self.show_unrotated_cell = InputHBoxLayout(
            'Show unrotated cell',
            None,
            checkbox=False,
            tooltip='Toggles if the unrotated cell and its basis vectors are shown in Crystal orientation preview'
        )

        # Add layouts to additional_vbox and additional_hbox...
        self.additional_vbox.addLayout(self.additional_hbox)
        self.additional_vbox.addLayout(self.additional_hbox_2)

        self.additional_hbox.addLayout(self.show_coordinate_system)
        self.additional_hbox.addLayout(self.show_miller_vector)
        self.additional_hbox_2.addLayout(self.show_unrotated_cell)

        # Additional settings connections
        self.show_coordinate_system.checkbox.clicked.connect(lambda: self.crystalCoordinatesChanged())
        self.show_miller_vector.checkbox.clicked.connect(lambda: self.crystalCoordinatesChanged())
        self.show_unrotated_cell.checkbox.clicked.connect(lambda: self.crystalCoordinatesChanged())

        #
        # Crystal orientation preview
        self.orientation_preview_vbox = VBoxTitleLayout(self, 'Crystal Orientation Preview', spacing=2, add_stretch=False)
        self.orientation_hbox.addLayout(self.orientation_preview_vbox)

        self.orientation_preview_group_box = QGroupBox(self)
        self.orientation_preview_vbox.addWidget(self.orientation_preview_group_box)

        self.orientation_preview_plot_vbox = QVBoxLayout()
        self.orientation_preview_group_box.setLayout(self.orientation_preview_plot_vbox)

        self.orientation_preview = MplCanvas(enable_3d=True, dpi=100, width=6, height=10)
        self.orientation_preview_plot_vbox.addWidget(self.orientation_preview, stretch=1)

        #
        # Crystal editor HBox
        self.crystal_edit_hbox = QHBoxLayout()
        self.crystal_edit_hbox.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.main_layout.addLayout(self.crystal_edit_hbox)

        #
        # Crystal editor VBox
        self.lattice_parameter_vbox = QVBoxLayout()
        self.lattice_parameter_vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.crystal_edit_hbox.addLayout(self.lattice_parameter_vbox)

        #
        # Crystal Default Box
        self.default_para_vbox = VBoxTitleLayout(self, 'Default Crystal', spacing=2, add_stretch=False)
        self.lattice_parameter_vbox.addLayout(self.default_para_vbox)
        self.default_para_group_box = QGroupBox(self)
        self.default_para_vbox.addWidget(self.default_para_group_box)
        self.default_para_hbox = QHBoxLayout()
        self.default_para_group_box.setLayout(self.default_para_hbox)

        #
        # Default buttons
        self.bcc_para_button = QPushButton('bcc')
        self.bcc_para_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.default_para_hbox.addWidget(self.bcc_para_button)
        self.bcc_para_button.clicked.connect(lambda: self.setBccParameter())
        self.bcc_para_button.setToolTip('bcc-button creates a bcc structure using the first element in the available element list')

        self.fcc_para_button = QPushButton('fcc')
        self.fcc_para_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.default_para_hbox.addWidget(self.fcc_para_button)
        self.fcc_para_button.clicked.connect(lambda: self.setFccParameter())
        self.fcc_para_button.setToolTip('fcc-button creates a fcc structure using the first element in the available element list')

        self.hex_para_button = QPushButton('hex')
        self.hex_para_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.default_para_hbox.addWidget(self.hex_para_button)
        self.hex_para_button.clicked.connect(lambda: self.setHexParameter())
        self.hex_para_button.setToolTip('hex-button creates a hex structure using the first element in the available element list')


        #
        # Crystal parameter table
        self.crystal_table_vbox = VBoxTitleLayout(self, 'Crystal parameter table', spacing=2, add_stretch=False)
        self.lattice_parameter_vbox.addLayout(self.crystal_table_vbox)

        self.crystal_table_group_box = QGroupBox(self)
        self.crystal_table_vbox.addWidget(self.crystal_table_group_box)

        self.crystal_table_hbox = QHBoxLayout()
        self.crystal_table_group_box.setLayout(self.crystal_table_hbox)

        self.table_crystal = CrystalTable(
            self,
            comp_count=self.component_count,
            target_elements=self.target_elements,
            row_fields=self.simulation_class.CompRowCrystalSettings.rowFields,
            custom_comp_row=self.simulation_class.CompRowCrystalSettings,
            version=self.simulation_configuration.version
        )

        self.table_crystal.coordinateChanged.connect(lambda: self.crystalCoordinatesChanged())
        self.crystal_table_hbox.addWidget(self.table_crystal)

        #
        # Crystal orientation preview
        self.crystal_preview_vbox = VBoxTitleLayout(self, 'Crystal Preview', spacing=2, add_stretch=False)
        self.crystal_edit_hbox.addLayout(self.crystal_preview_vbox)

        self.crystal_preview_group_box = QGroupBox(self)
        self.crystal_preview_vbox.addWidget(self.crystal_preview_group_box)

        self.preview_plot_vbox = QVBoxLayout()
        self.crystal_preview_group_box.setLayout(self.preview_plot_vbox)

        self.crystal_preview = MplCanvas(enable_3d=True, dpi=100, width=6, height= 10)
        self.preview_plot_vbox.addWidget(self.crystal_preview, stretch=1)
        self.crystal_coordinates = []

        self.crystal_preview.axes.view_init(self.elev_prev, self.azim_prev)
        self.orientation_preview.axes.view_init(self.elev_orien, self.azim_orien)
        self.beam_vector = np.array([0., 0., 1])

        # Toolbar

        self.output_plot_toolbar = NavigationToolbar2QT(self.orientation_preview, self)
        self.orientation_preview_plot_vbox.addWidget(self.orientation_preview, stretch=1)
        self.orientation_preview_plot_vbox.addWidget(self.output_plot_toolbar)

        self.output_plot_toolbar = NavigationToolbar2QT(self.crystal_preview, self)
        self.preview_plot_vbox.addWidget(self.crystal_preview, stretch=1)
        self.preview_plot_vbox.addWidget(self.output_plot_toolbar)

        crystal_args = self.table_crystal.getArguments()


    def set_axes_equal(self, ax, r):
        """
        Make axes of 3D plot have equal scale so that spheres appear as spheres,
        cubes as cubes, etc.

        Input
          ax: a matplotlib axis, e.g., as output from plt.gca().
        """

        x_limits = ax.get_xlim3d()
        y_limits = ax.get_ylim3d()
        z_limits = ax.get_zlim3d()

        x_range = abs(x_limits[1] - x_limits[0])
        x_middle = np.mean(x_limits)
        y_range = abs(y_limits[1] - y_limits[0])
        y_middle = np.mean(y_limits)
        z_range = abs(z_limits[1] - z_limits[0])
        z_middle = np.mean(z_limits)

        # The plot bounding box is a sphere in the sense of the infinity
        # norm, hence I call half the max range the plot radius.
        plot_radius = r * max([x_range, y_range, z_range])

        ax.set_xlim3d([x_middle - plot_radius, x_middle + plot_radius])
        ax.set_ylim3d([y_middle - plot_radius, y_middle + plot_radius])
        ax.set_zlim3d([z_middle - plot_radius, z_middle + plot_radius])

    def plotUnitCellOutlines(self, b1, b2, b3, ax):
        b0 = np.zeros(3)
        b4 = b1 + b2
        b6 = b1 + b3
        b5 = b2 + b3

        ax.quiver(b0[0], b0[1], b0[2], b1[0], b1[1], b1[2], linewidth=1, ec='k', arrow_length_ratio=0)
        ax.quiver(b0[0], b0[1], b0[2], b2[0], b2[1], b2[2], linewidth=1, ec='k', arrow_length_ratio=0)
        ax.quiver(b0[0], b0[1], b0[2], b3[0], b3[1], b3[2], linewidth=1, ec='k', arrow_length_ratio=0)

        ax.quiver(b1[0], b1[1], b1[2], b2[0], b2[1], b2[2], linewidth=1, ec='k', arrow_length_ratio=0)
        ax.quiver(b1[0], b1[1], b1[2], b3[0], b3[1], b3[2], linewidth=1, ec='k', arrow_length_ratio=0)
        ax.quiver(b2[0], b2[1], b2[2], b1[0], b1[1], b1[2], linewidth=1, ec='k', arrow_length_ratio=0)

        ax.quiver(b2[0], b2[1], b2[2], b3[0], b3[1], b3[2], linewidth=1, ec='k', arrow_length_ratio=0)
        ax.quiver(b3[0], b3[1], b3[2], b1[0], b1[1], b1[2], linewidth=1, ec='k', arrow_length_ratio=0)
        ax.quiver(b3[0], b3[1], b3[2], b2[0], b2[1], b2[2], linewidth=1, ec='k', arrow_length_ratio=0)

        ax.quiver(b4[0], b4[1], b4[2], b3[0], b3[1], b3[2], linewidth=1, ec='k', arrow_length_ratio=0)
        ax.quiver(b6[0], b6[1], b6[2], b2[0], b2[1], b2[2], linewidth=1, ec='k', arrow_length_ratio=0)
        ax.quiver(b5[0], b5[1], b5[2], b1[0], b1[1], b1[2], linewidth=1, ec='k', arrow_length_ratio=0)

    def plotVector(self, vector, ax, startpoint=np.zeros(3), color='r', label='${beam}$', label_pos=None):

        ax.quiver(startpoint[0], startpoint[1], startpoint[2], vector[0], vector[1], vector[2], linewidth=2, ec=color)
        if label_pos is None:
            label_pos = []
            for i in range(len(vector)):
                label_pos.append(((vector[i] - startpoint[i]) / 2) + startpoint[i])
        ax.text(label_pos[0] + 0.05, label_pos[1] + 0.05, label_pos[2] + 0.05, label, c=color)

    def plotUnrotatedCrystal(self):

        self.plotUnitCellOutlines(self.getBasisVector(self.a1),
                                  self.getBasisVector(self.a2),
                                  self.getBasisVector(self.a3),
                                  self.orientation_preview.axes)

        self.plotBasisVectors(self.getBasis(), self.orientation_preview.axes, color='c')

    def plotCoordinatSystem(self, ax):
        self.plotVector(np.array([0., 0., 1.5]), ax, startpoint=np.array([0, 0, 0]),
                        color='y', label='${X}$', label_pos=np.array([0, 0.1, 1.5]))
        self.plotVector(np.array([0., 1.5, 0.]), ax, startpoint=np.array([0, 0, 0]),
                        color='y', label='${Y}$', label_pos=np.array([0, 1.5, 0.1]))
        self.plotVector(np.array([-1.5, 0., 0.]), ax, startpoint=np.array([0, 0, 0]),
                        color='y', label='${Z}$', label_pos=np.array([-1.5, 0., -0.1]))

    def plotBasisVectors(self, basis, ax, color='b'):
        labels = ['${\u00E2_1}$', '${\u00E2_2}$', '${\u00E2_3}$']
        for i in range(len(labels)):
            self.plotVector(basis[i, :], ax, color=color, label=labels[i])

    def getBasisVector(self, vector):
        return np.array([vector[0].value(), vector[1].value(), vector[2].value()]) @ self.rot_mat_y.T

    def getRotatedBasisVector(self, vector):
        return np.array([vector[0].value(), vector[1].value(), vector[2].value()]) @ self.rot_mat.T

    def getBasis(self):
        return np.vstack([self.getBasisVector(self.a1),
                          self.getBasisVector(self.a2),
                          self.getBasisVector(self.a3)]
                         )

    def getRotatedBasis(self):
        return np.vstack([self.getRotatedBasisVector(self.a1),
                          self.getRotatedBasisVector(self.a2),
                          self.getRotatedBasisVector(self.a3)]
                         )

    def updateMillerIndices(self):

        m = np.array([self.miller_index_h.value(), self.miller_index_k.value(), self.miller_index_l.value()])
        self.miller_vec = m
        if np.any(m) != 0:
            self.calcRotMat(m)
            return
        else:
            self.rot_mat = np.identity(3) @ self.rot_mat_y

    def calcRotMat(self, m):

        a = m / np.sqrt(np.dot(m, m))
        r = np.sqrt(np.square(a[0]) + np.square(a[1]))
        if r == 0:
            sin_phi = 0
            cos_phi = 0
        else:
            sin_phi = a[1] / r
            cos_phi = a[0] / r
        sin_theta = a[2]
        cos_theta = r
        self.rot_mat = np.array([
            [cos_phi * cos_theta, sin_phi * cos_theta, sin_theta],
            [-sin_phi, cos_phi, 0.],
            [-cos_phi * sin_theta, -sin_phi * sin_theta, cos_theta]
        ])
        self.rot_mat = self.rot_mat_y @ self.rot_mat

    def updatePlot(self):

        self.azim_prev, self.elev_prev = self.crystal_preview.axes.azim, self.crystal_preview.axes.elev
        self.azim_orien, self.elev_orien = self.orientation_preview.axes.azim, self.orientation_preview.axes.elev

        self.orientation_preview.fig.clf()
        self.orientation_preview.axes = self.orientation_preview.fig.add_subplot(projection='3d')

        self.crystal_preview.fig.clf()
        self.crystal_preview.axes = self.crystal_preview.fig.add_subplot(projection='3d')

        self.crystal_preview.draw_idle()
        self.orientation_preview.fig.canvas.draw_idle()

        self.crystal_preview.draw_idle()
        self.orientation_preview.fig.canvas.draw_idle()

        if self.show_unrotated_cell.checkbox.isChecked():
            self.plotUnrotatedCrystal()

        if self.show_coordinate_system.checkbox.isChecked():
            self.plotCoordinatSystem(self.orientation_preview.axes)

        if self.show_miller_vector.checkbox.isChecked():
            vector = self.miller_vec @ self.getBasis() #@ self.basis
            self.plotVector(vector, self.orientation_preview.axes, color='m', label='${millervec}$')

        self.plotUnitCellOutlines(self.getRotatedBasisVector(self.a1),
                                  self.getRotatedBasisVector(self.a2),
                                  self.getRotatedBasisVector(self.a3),
                                  self.orientation_preview.axes)

        self.plotVector(self.beam_vector,
                        self.orientation_preview.axes,
                        startpoint=np.array([0, 0, -1]),
                        label_pos=[0., 0.1, -0.5]
                        )

        self.plotUnitCellOutlines(self.getBasisVector(self.a1),
                                  self.getBasisVector(self.a2),
                                  self.getBasisVector(self.a3),
                                  self.crystal_preview.axes)

        self.plotBasisVectors(self.getBasis(), self.crystal_preview.axes, color='b')
        self.plotBasisVectors(self.getRotatedBasis(), self.orientation_preview.axes, color='b')

        for i, element in enumerate(self.crystal_coordinates_dict.keys()):
            c = []
            if self.crystal_coordinates_dict[element]:
                coordinates = np.array(self.crystal_coordinates_dict[element]) @ self.getRotatedBasis() # @ self.basis_rotated
                coordinates_preview = np.array(self.crystal_coordinates_dict[element]) @ self.getBasis() # @ self.basis

                for o in range(len(coordinates[:, 0])):
                    c.append(getElementColor(i, len(self.crystal_coordinates_dict)).name())

                self.orientation_preview.axes.scatter(coordinates[:, 0],
                                                      coordinates[:, 1],
                                                      coordinates[:, 2],
                                                      c=c,
                                                      s=100,
                                                      label=element
                                                      )

                self.orientation_preview.axes.legend(loc='upper right')

                self.crystal_preview.axes.scatter(coordinates_preview[:, 0],
                                                  coordinates_preview[:, 1],
                                                  coordinates_preview[:, 2],
                                                  c=c,
                                                  s=100
                                                  )

            self.crystal_preview.axes.set_position([0.05, 0.05, 0.9, 0.9])  # [left, bottom, width, height]
            self.orientation_preview.axes.set_position([0.05, 0.05, 0.9, 0.9])  # [left, bottom, width, height]

        self.crystal_preview.axes.set_axis_off()
        self.orientation_preview.axes.set_axis_off()

        xx, yy = np.meshgrid(range(-2, 2), range(-1, 3))
        z = 0*(xx + yy)
        self.orientation_preview.axes.plot_surface(xx, yy, z, alpha=0.2)

        self.set_axes_equal(self.orientation_preview.axes, 0.25)
        self.set_axes_equal(self.crystal_preview.axes, 0.5)

        self.crystal_preview.axes.view_init(self.elev_prev, self.azim_prev)
        self.orientation_preview.axes.view_init(self.elev_orien, self.azim_orien)

    def reset(self):
        """Resets the crystal parameters and table"""

        # Reset miller indices
        self.miller_index_h.setValue(1.)
        self.miller_index_k.setValue(0.)
        self.miller_index_l.setValue(0.)

        # Reset Basis vectors
        self.basis_vector_a1_x.setValue(1.)
        self.basis_vector_a1_y.setValue(0.)
        self.basis_vector_a1_z.setValue(0.)

        self.basis_vector_a2_x.setValue(0.)
        self.basis_vector_a2_y.setValue(1.)
        self.basis_vector_a2_z.setValue(0.)

        self.basis_vector_a3_x.setValue(0.)
        self.basis_vector_a3_y.setValue(0.)
        self.basis_vector_a3_z.setValue(1.)

        # Reset Beam Settings
        self.beam_dy.setValue(0.)
        self.beam_dz.setValue(0.)
        self.impact_parameter.setValue(3.)
        self.lattice_constant.setValue(3.)
        self.matrix_3.checkbox.setChecked(True)
        self.matrixParametersChanged(self.matrix_3.checkbox, self.matrix_5.checkbox)

        # Reset Crystal orientation settings
        self.show_coordinate_system.checkbox.setChecked(False)
        self.show_miller_vector.checkbox.setChecked(False)
        self.show_unrotated_cell.checkbox.setChecked(False)

        # Reset crystal table
        self.table_crystal.resetTable()

    def addRow(self):
        """Adds a Row to the table"""
        self.table_crystal.addRow()

    def openDialog(self):
        """
        Open QDialog

        :param element: selected element
        :param existing_elements: (optional) list of already existing elements (should be greyed out)
        """

        super().open()

    def elementChanged(self):
        """Gets called if an element was changed"""

        self.available_elements = []
        for row in self.table_target.rows:
            row.blockSignals(True)
            if row.element.symbol != "":
                self.available_elements.append(row.element.symbol)
            row.blockSignals(False)

        self.table_crystal.blockSignals(True)
        self.table_crystal.UpdateAvailableElements(self.available_elements)
        self.table_crystal.blockSignals(False)

        for row in self.table_crystal.getRows():
            row.blockSignals(True)
            row.setAvailableElements(self.available_elements.copy())
            row.blockSignals(False)

        self.table_crystal.coordinateChanged.emit()


    def crystalCoordinatesChanged(self):

        self.crystal_coordinates = []
        self.crystal_coordinates_dict = {}
        for element in self.available_elements:
            self.crystal_coordinates_dict[element] = []
        self.species_list = []

        self.updateMillerIndices()

        for row in self.table_crystal.getRows():
            row.crystalSymmetry()

            if row.element_combobox.currentText() in self.crystal_coordinates_dict.keys():
                for coordinates in row.getCoordinates():
                    all_coordinates = [coord for coords_list in self.crystal_coordinates_dict.values() for coord in coords_list]

                    if coordinates in all_coordinates:
                        setWidgetHighlight(row.coordinate_a1, True)
                        setWidgetHighlight(row.coordinate_a2, True)
                        setWidgetHighlight(row.coordinate_a3, True)
                        break
                    if row.element_combobox.currentText() not in self.species_list:
                        self.species_list.append(row.element_combobox.currentText())
                    if row.element_combobox.currentText() in self.crystal_coordinates_dict.keys():
                        self.crystal_coordinates_dict[row.element_combobox.currentText()].append(coordinates)
                    setWidgetHighlight(row.coordinate_a1, False)
                    setWidgetHighlight(row.coordinate_a2, False)
                    setWidgetHighlight(row.coordinate_a3, False)

            setWidgetHighlight(row.element_combobox, False)

            if row.element_combobox.currentText() == 'No element chosen':
                setWidgetHighlight(row.element_combobox, True)

        self.updatePlot()

    def matrixParametersChanged(self, checkbox_1, checkbox_2):
        if checkbox_1.isChecked():
            checkbox_2.setChecked(False)
        else:
            checkbox_2.setChecked(True)

    def getArguments(self) -> GeneralCrystalArguments:
        """" get CrystalArgument """

        return GeneralCrystalArguments(
            name='MyLittleCrystal',
            lattice_id=1,
            number_of_species=len(self.species_list),
            species=self.species_list,
            lattice_constant=self.lattice_constant.value(),

            basis_vector_a1_x=self.basis_vector_a1_x.value(),
            basis_vector_a1_y=self.basis_vector_a1_y.value(),
            basis_vector_a1_z=self.basis_vector_a1_z.value(),

            basis_vector_a2_x=self.basis_vector_a2_x.value(),
            basis_vector_a2_y=self.basis_vector_a2_y.value(),
            basis_vector_a2_z=self.basis_vector_a2_z.value(),

            basis_vector_a3_x=self.basis_vector_a3_x.value(),
            basis_vector_a3_y=self.basis_vector_a3_y.value(),
            basis_vector_a3_z=self.basis_vector_a3_z.value(),

            miller_index_h=self.miller_index_h.value(),
            miller_index_k=self.miller_index_k.value(),
            miller_index_l=self.miller_index_l.value(),

            p_max=self.impact_parameter.value(),
            beam_dy=self.beam_dy.value(),
            beam_dz=self.beam_dz.value(),
            matrix_3=self.matrix_3.checkbox.isChecked(),
            matrix_5=self.matrix_5.checkbox.isChecked()
        )

    def loadArguments(self, arguments: SimulationArguments) -> list:
        """Loads <SimulationArguments> container. Returns list of not loadable parameters (default used)"""

        crystal_args = arguments.crystal_args
        assumed = arguments.get('assumed')
        if not isinstance(assumed, list):
            assumed = []
        not_loadable = []

        # basis vectors
        basis_vector_a1_x = crystal_args.basis_vector_a1_x
        basis_vector_a1_y = crystal_args.basis_vector_a1_y
        basis_vector_a1_z = crystal_args.basis_vector_a1_z

        if 'basis_vector_a1_x' in assumed:
            basis_vector_a1_x = DefaultValues.basis_vector_a1_x
            # self.layout_thickness.mark()
            not_loadable.append('basis_vector_a1_x')

        if 'basis_vector_a1_y' in assumed:
            basis_vector_a1_y = DefaultValues.basis_vector_a1_y
            # self.layout_thickness.mark()
            not_loadable.append('basis_vector_a1_y')

        if 'basis_vector_a1_z' in assumed:
            basis_vector_a1_z = DefaultValues.basis_vector_a1_z
            # self.layout_thickness.mark()
            not_loadable.append('basis_vector_a1_z')

        basis_vector_a2_x = crystal_args.basis_vector_a2_x
        basis_vector_a2_y = crystal_args.basis_vector_a2_y
        basis_vector_a2_z = crystal_args.basis_vector_a2_z

        if 'basis_vector_a2_x' in assumed:
            basis_vector_a2_x = DefaultValues.basis_vector_a2_x
            # self.layout_thickness.mark()
            not_loadable.append('basis_vector_a2_x')

        if 'basis_vector_a2_y' in assumed:
            basis_vector_a2_y = DefaultValues.basis_vector_a2_y
            # self.layout_thickness.mark()
            not_loadable.append('basis_vector_a2_y')

        if 'basis_vector_a2_z' in assumed:
            basis_vector_a2_z = DefaultValues.basis_vector_a2_z
            # self.layout_thickness.mark()
            not_loadable.append('basis_vector_a2_z')

        basis_vector_a3_x = crystal_args.basis_vector_a3_x
        basis_vector_a3_y = crystal_args.basis_vector_a3_y
        basis_vector_a3_z = crystal_args.basis_vector_a3_z

        if 'basis_vector_a3_x' in assumed:
            basis_vector_a3_x = DefaultValues.basis_vector_a3_x
            # self.layout_thickness.mark()
            not_loadable.append('basis_vector_a3_x')

        if 'basis_vector_a3_y' in assumed:
            basis_vector_a3_y = DefaultValues.basis_vector_a3_y
            # self.layout_thickness.mark()
            not_loadable.append('basis_vector_a3_y')

        if 'basis_vector_a3_z' in assumed:
            basis_vector_a3_z = DefaultValues.basis_vector_a3_z
            # self.layout_thickness.mark()
            not_loadable.append('basis_vector_a3_z')

        self.basis_vector_a1_x.setValue(basis_vector_a1_x)
        self.basis_vector_a1_y.setValue(basis_vector_a1_y)
        self.basis_vector_a1_z.setValue(basis_vector_a1_z)

        self.basis_vector_a2_x.setValue(basis_vector_a2_x)
        self.basis_vector_a2_y.setValue(basis_vector_a2_y)
        self.basis_vector_a2_z.setValue(basis_vector_a2_z)

        self.basis_vector_a3_x.setValue(basis_vector_a3_x)
        self.basis_vector_a3_y.setValue(basis_vector_a3_y)
        self.basis_vector_a3_z.setValue(basis_vector_a3_z)

        # miller indices
        miller_index_h = crystal_args.miller_index_h
        miller_index_k = crystal_args.miller_index_k
        miller_index_l = crystal_args.miller_index_l

        if 'miller_index_h' in assumed:
            miller_index_h = DefaultValues.miller_index_h
            # self.layout_thickness.mark()
            not_loadable.append('miller_index_h')

        if 'miller_index_k' in assumed:
            basis_vector_a1_y = DefaultValues.miller_index_k
            # self.layout_thickness.mark()
            not_loadable.append('miller_index_k')

        if 'miller_index_l' in assumed:
            basis_vector_a1_z = DefaultValues.miller_index_l
            # self.layout_thickness.mark()
            not_loadable.append('miller_index_l')

        self.miller_index_h.setValue(miller_index_h)
        self.miller_index_k.setValue(miller_index_k)
        self.miller_index_l.setValue(miller_index_l)

        p_max = crystal_args.optional.get('p_max')

        if 'p_max' in assumed:
            p_max = DefaultValues.p_max
            # self.layout_thickness.mark()
            not_loadable.append('p_max')

        self.impact_parameter.setValue(p_max)

        beam_dy = crystal_args.optional.get('beam_dy')
        if 'beam_dy' in assumed:
            beam_dy = DefaultValues.beam_dy
            # self.layout_thickness.mark()
            not_loadable.append('beam_dy')

        self.beam_dy.setValue(beam_dy)

        beam_dz = crystal_args.optional.get('beam_dz')
        if 'beam_dz' in assumed:
            beam_dz = DefaultValues.beam_dz
            # self.layout_thickness.mark()
            not_loadable.append('beam_dz')

        self.beam_dz.setValue(beam_dz)

        matrix_3 = crystal_args.optional.get('matrix_3')
        if 'matrix_3' in assumed:
            matrix_3 = DefaultValues.matrix_3
            # self.layout_thickness.mark()
            not_loadable.append('matrix_3')

        self.matrix_3.checkbox.setChecked(matrix_3)

        matrix_5 = crystal_args.optional.get('matrix_5')
        if 'matrix_5' in assumed:
            matrix_5 = DefaultValues.matrix_5
            # self.layout_thickness.mark()
            not_loadable.append('matrix_5')

        self.matrix_5.checkbox.setChecked(matrix_5)

        self.matrixParametersChanged(self.matrix_5.checkbox, self.matrix_3.checkbox)

        lattice_constant = crystal_args.lattice_constant

        if 'lattice_constant' in assumed:
            lattice_constant = DefaultValues.lattice_constant
            # self.layout_thickness.mark()
            not_loadable.append('lattice_constant')

        self.lattice_constant.setValue(lattice_constant)

        return not_loadable

    def setBasisSpinboxes(self, a1, a2, a3):

        for i, component in enumerate(self.a1):
            component.setValue(a1[i])
        for i, component in enumerate(self.a2):
            component.setValue(a2[i])
        for i, component in enumerate(self.a3):
            component.setValue(a3[i])

    def setBccParameter(self):
        #do it
        a1 = [1., 0., 0.]
        a2 = [0., 1., 0.]
        a3 = [0., 0., 1.]
        lattice_points = [[0., 0., 0.], [0.5, 0.5, 0.5]]

        self.setBasisSpinboxes(a1, a2, a3)
        self.table_crystal.resetTable()
        self.setParameter(lattice_points)

    def setFccParameter(self):

        a1 = [1., 0., 0.]
        a2 = [0., 1., 0.]
        a3 = [0., 0., 1.]
        lattice_points = [[0., 0., 0.], [0.5, 0.5, 0.], [0., 0.5, 0.5], [0.5, 0., 0.5]]

        self.setBasisSpinboxes(a1, a2, a3)
        self.table_crystal.resetTable()
        self.setParameter(lattice_points)

    def setHexParameter(self):

        b = np.sqrt(3)/2
        a1 = [1., 0., 0.]
        a2 = [0., b, 0.]
        a3 = [0., 0., 1.]
        lattice_points = [[0., 0.5, 0.], [0., 0., 0.25], [0., 0., 0.75]]

        self.setBasisSpinboxes(a1, a2, a3)
        self.table_crystal.resetTable()
        self.setParameter(lattice_points)

    def setParameter(self, lattice_points):

        self.table_crystal.blockSignals(True)

        for _ in lattice_points:
            self.table_crystal.addRow()

        self.table_crystal.blockSignals(False)

        for i, row in enumerate(self.table_crystal.getRows()):
            row.blockSignals(True)
            row.coordinate_a1.setValue(lattice_points[i][0])
            row.coordinate_a2.setValue(lattice_points[i][1])
            row.coordinate_a3.setValue(lattice_points[i][2])

            if row.element_combobox.count() > 1:
                row.element_combobox.setCurrentIndex(1)
            else:
                row.element_combobox.setCurrentIndex(0)

            row.blockSignals(False)
            self.table_crystal.coordinateChanged.emit()
