from typing import List, Optional

from PyQt6.QtGui import QRegularExpressionValidator
from PyQt6.QtCore import pyqtSignal, QRegularExpression
from PyQt6.QtWidgets import QLineEdit, QPushButton, QWidget, QHBoxLayout, QVBoxLayout, QAbstractSpinBox

from Utility.ModifyWidget import setWidgetHighlight
from Utility.Functions import limitSum
from Utility.Layouts import SpinBox, DoubleSpinBox, SpinBoxRange
from Utility.Icons import getIcon

from TableWidgets.CustomTable import CustomTable, CustomRow

from Containers.Arguments import StructureArguments


class TargetLayerEntry:
    """
    Entry for target layer
    Stores the information to be written to the layers.inp file.
    Thus, only the segment thickness is needed

    :param segment_count: number of segments
    :param segment_thickness: thickness of layer
    :param abundances: abundances of elements (list)
    :param layer_name: name of layer
    """

    def __init__(self, segment_count, segment_thickness, abundances, layer_name):
        self.segment_count = segment_count
        self.segment_thickness = segment_thickness
        self.abundances = abundances
        self.layer_name = layer_name


class TargetLayersRow(CustomRow):
    """
    Row (=Layer) for target structure

    :param elements: all elements target structure
    :param crystal_count: (optional) number of crystals with a column for their fraction in the layer
    """

    def __init__(self, elements, crystal_count: int = 0):
        super().__init__()
        self.remove.setToolTip('Remove this layer from the target')

        self.edit_button = QWidget()
        self.edit_button_hl = QHBoxLayout()
        self.edit_button_hl.setSpacing(2)
        self.edit_button_hl.setContentsMargins(0, 0, 0, 0)
        self.edit_button_hl.addStretch(1)

        self.edit_button_hl.addWidget(self.remove)
        self.edit_button_hl.addStretch(1)

        self.move_top = QPushButton(getIcon('up'), '')
        self.move_top.setToolTip('Move this layer up')

        self.move_bottom = QPushButton(getIcon('down'), '')
        self.move_bottom.setToolTip('Move this layer down')

        self.move_top_bottom_button = QWidget()
        self.move_top_bottom_button.setFixedSize(30, 30)
        self.move_top_bottom_button_vl = QVBoxLayout()
        self.move_top_bottom_button_vl.setSpacing(0)
        self.move_top_bottom_button_vl.setContentsMargins(0, 0, 0, 0)
        self.move_top_bottom_button_vl.addWidget(self.move_top, 1)
        self.move_top_bottom_button_vl.addWidget(self.move_bottom, 1)
        self.move_top_bottom_button.setLayout(self.move_top_bottom_button_vl)

        # Center the add-top-bottom button by surrounding it with two stretches inside a horizontal layout
        self.move_top_bottom_button_parent = QWidget()
        self.move_top_bottom_button_parent_hl = QHBoxLayout()
        self.move_top_bottom_button_parent_hl.setSpacing(0)
        self.move_top_bottom_button_parent_hl.setContentsMargins(0, 0, 0, 0)
        self.move_top_bottom_button_parent_hl.addStretch(1)
        self.move_top_bottom_button_parent_hl.addWidget(self.move_top_bottom_button)
        self.move_top_bottom_button_parent_hl.addStretch(1)
        self.move_top_bottom_button_parent.setLayout(self.move_top_bottom_button_parent_hl)
        self.row_widgets.insert(-1, self.move_top_bottom_button_parent)

        self.edit_button_hl.addWidget(self.move_top_bottom_button_parent)
        self.edit_button_hl.addStretch(1)

        self.edit_button_hl.addStretch(1)
        self.edit_button.setLayout(self.edit_button_hl)

        self.name_validator = QRegularExpressionValidator(QRegularExpression('[a-zA-Z1-9]+'))
        self.element_cells = []
        self.segment_thickness = 0

        self.segment_count = SpinBox(
            input_range=SpinBoxRange.ZERO_INF
        )
        self.segment_count.valueChanged.connect(self.contentChanged.emit)

        self.layer_thickness = DoubleSpinBox(
            input_range=SpinBoxRange.ZERO_INF,
            decimals=2
        )
        self.layer_thickness.setEnabled(False)

        self.layer_name = QLineEdit()
        self.layer_name.setMaximumWidth(100)
        self.layer_name.setValidator(self.name_validator)
        self.layer_name.textChanged.connect(self.contentChanged.emit)

        self.row_widgets = [self.edit_button, self.segment_count, self.layer_thickness, self.layer_name]

        # crystals (since SDTrimSP 7.02): fraction of each crystal in the layer and miller index of the layer
        self.crystal_cells: List[DoubleSpinBox] = []
        self.miller_cells: List[DoubleSpinBox] = []
        self.miller_widget: Optional[QWidget] = None
        self.crystal_values: List[float] = []
        self.miller_values: List[float] = [0., 0., 0.]

        for _ in elements:
            self.addElementCell()

        self.setCrystalColumns(crystal_count)
        self.clearSpinboxButtons()

    def selectRowInput(self):
        """Select row as input"""

        self.layer_name.setFocus()

    def addElementCell(self):
        """Add a new cell for element abundance"""

        cell = DoubleSpinBox(
            default=0,
            input_range=(0, 1),
            step_size=1E-5,
            decimals=5
        )
        self.row_widgets.insert(3 + len(self.element_cells), cell)
        self.element_cells.append(cell)
        cell.valueChanged.connect(self.contentChanged.emit)
        return cell

    def removeElementCell(self, cell_idx):
        """
        Remove cell with index for element abundance

        :param cell_idx: index of cell
        """

        del self.row_widgets[cell_idx + 3]
        del self.element_cells[cell_idx]

    def storeCrystalValues(self):
        """Stores the values of the crystal cells (before the cells are removed)"""

        try:
            if self.crystal_cells:
                # values of further crystals (without cells yet, e.g. while loading) are kept
                self.crystal_values = [cell.value() for cell in self.crystal_cells] + self.crystal_values[len(self.crystal_cells):]
            if self.miller_cells:
                self.miller_values = [cell.value() for cell in self.miller_cells]
        except RuntimeError:
            # cells were already deleted
            pass

    def setCrystalColumns(self, crystal_count: int):
        """
        Creates the cells for the fractions of the crystals and the miller index of the layer

        :param crystal_count: number of crystals (0 removes the cells)
        """

        self.storeCrystalValues()
        for widget in self.crystal_cells + ([self.miller_widget] if self.miller_widget is not None else []):
            if widget in self.row_widgets:
                self.row_widgets.remove(widget)
        self.crystal_cells = []
        self.miller_cells = []
        self.miller_widget = None

        if not crystal_count:
            return

        # new layers consist of the first crystal
        values = (list(self.crystal_values) or [1.0]) + [0.] * crystal_count
        position = 3 + len(self.element_cells)
        for i in range(crystal_count):
            cell = DoubleSpinBox(default=0, input_range=(0, 1), step_size=0.1, decimals=4)
            cell.setValue(values[i])
            cell.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            cell.valueChanged.connect(self.contentChanged.emit)
            self.crystal_cells.append(cell)
            self.row_widgets.insert(position + i, cell)

        self.miller_widget = QWidget()
        miller_layout = QHBoxLayout()
        miller_layout.setContentsMargins(0, 0, 0, 0)
        miller_layout.setSpacing(2)
        self.miller_widget.setLayout(miller_layout)
        for value in self.miller_values:
            cell = DoubleSpinBox(default=0, input_range=(-99, 99), decimals=2)
            cell.setValue(value)
            cell.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            cell.setMinimumWidth(45)
            cell.valueChanged.connect(self.contentChanged.emit)
            self.miller_cells.append(cell)
            miller_layout.addWidget(cell)
        self.row_widgets.insert(position + crystal_count, self.miller_widget)

    def setCrystalValues(self, fractions: Optional[list], miller: Optional[list]):
        """Sets the fractions of the crystals and the miller index of the layer"""

        if isinstance(fractions, list):
            self.crystal_values = [float(f) for f in fractions]
            for cell, value in zip(self.crystal_cells, fractions):
                cell.setValue(float(value))
        if isinstance(miller, list) and len(miller) == 3:
            self.miller_values = [float(m) for m in miller]
            for cell, value in zip(self.miller_cells, miller):
                cell.setValue(float(value))

    def getRowData(self):
        """Returns data of row (CompEntry)"""
        return TargetLayerEntry(
            self.segment_count.value(),
            self.segment_thickness,
            [elementCell.value() for elementCell in self.element_cells],
            self.layer_name.text()
        )

    def setRowData(self, data: TargetLayerEntry):
        """
        Sets data of row (TargetLayerEntry)

        :param data: data to be set
        """

        self.segment_count.setValue(data.segment_count)
        self.segment_thickness = data.segment_thickness
        self.layer_thickness.setValue(data.segment_count * data.segment_thickness)
        for i in range(len(data.abundances)):
            element_cell = self.element_cells[i]
            element_cell.setValue(data.abundances[i])
        self.layer_name.setText(data.layer_name)

    def getArguments(self) -> StructureArguments:
        """Returns <StructureArguments> container of parameters for row"""

        crystal_arguments = {}
        if self.crystal_cells:
            crystal_arguments = {
                'crystal_fractions': [cell.value() for cell in self.crystal_cells],
                'miller': [cell.value() for cell in self.miller_cells]
            }
        return StructureArguments(
            name=self.layer_name.text(),
            segments=self.segment_count.value(),
            thickness=self.layer_thickness.value(),
            abundances=[element_cell.value() for element_cell in self.element_cells],
            **crystal_arguments
        )

    def setArguments(self, arguments: StructureArguments):
        """
        Sets <StructureArguments> container of parameters for row

        :param arguments: container of <StructureArguments>
        """

        self.layer_name.setText(arguments.name)
        self.layer_thickness.setValue(arguments.thickness)
        self.segment_count.setValue(arguments.segments)
        for i, abundance in enumerate(arguments.abundances):
            if i >= len(self.element_cells):
                break
            element_cell = self.element_cells[i]
            element_cell.setValue(abundance)
        self.setCrystalValues(arguments.get('crystal_fractions'), arguments.get('miller'))


class TargetLayersTable(CustomTable):
    """
    Table for target layers

    :param parent: parent widget
    :param target_thickness: target thickness
    :param target_segments_count: number of target segments
    :param labels: (optional) additional labels
    :param tooltips: (optional) additional tooltips
    :param custom_table_row: (optional) custom table row
    """

    layersChanged = pyqtSignal(list, list)

    generalLabels = [
        'Segments',
        'Layer thickness [Å]',
        'Name'
    ]
    generalTooltips = [
        'The amount of discrete segments a layer is made of.<br>The segments of all layer sum up to the maximum amount.',
        'The thickness of this layer, calculated from the total target thickness and the respective layer segment count.',
        'The name of the layer if multiple layers are defined.'
    ]
    abundanceTooltip = 'How much this element contributes to the composition of each layer (atomic fraction).<br>The abundances of all elements in a layer sum up to 1'
    crystalTooltip = 'Fraction of the layer that consists of this crystal (from the crystal editor).<br>The rest of the layer is amorphous with the composition given by the element abundances'
    millerTooltip = 'Miller index (h, k, l) of the crystals in this layer (layer.inp)'

    def __init__(
        self,
        parent,
        target_thickness: float,
        target_segments_count: int,
        labels=None,
        tooltips=None,
        custom_table_row=TargetLayersRow
    ):
        if labels is None:
            labels = []
        if tooltips is None:
            tooltips = []
        self.labels = self.generalLabels + labels
        self.tooltips = self.generalTooltips + tooltips
        self.target_row = custom_table_row

        super().__init__(0, self.labels, parent)
        self.rows: List[TargetLayersRow] = []

        self.elements = []
        self.crystal_names: List[str] = []
        self.segment_thickness = target_thickness / target_segments_count
        self.target_segments_count = target_segments_count

        self.add_button.setToolTip('Add a new layer to the target')
        self.label_row_idx = 0

        for i, tooltip in enumerate(self.tooltips):
            if tooltip:
                self.horizontalHeaderItem(i + 1).setToolTip(tooltip)

    def createRow(self, row_idx):
        """
        Creates a new row

        :param row_idx: index of row
        """

        row = TargetLayersRow(self.elements, len(self.crystal_names))
        row.segment_thickness = self.segment_thickness
        row.segment_count.setMaximum(self.target_segments_count)
        return row

    def addRow(self, update: bool = True, connect: bool = True) -> TargetLayersRow:
        """
        Add a new row

        :param update: if updates should happen
        :param connect: if row should be connected
        """

        row = super().addRow(update=update, connect=connect)
        self.label_row_idx += 1
        row.layer_name.setText(f'Layer{self.label_row_idx}')

        if connect:
            row.contentChanged.connect(self.updateLayers)
        row.move_top.clicked.connect(lambda: self.moveRow(row, -1))
        row.move_bottom.clicked.connect(lambda: self.moveRow(row, 1))

        if update:
            self.updateLayers(row)
            self.updateMoveButtons()

        return row

    def addRows(self, target_layer_entries: List[TargetLayerEntry]):
        """
        Add multiple rows

        :param target_layer_entries: list of layer entries
        """

        # Add the blank rows first and then fill in their data to fill up everything correctly
        for _ in target_layer_entries:
            self.addRow(update=False, connect=False)

        for i, entry in enumerate(target_layer_entries):
            self.rows[i].setRowData(entry)

        self.connectRows()
        self.updateLayers()

    def connectRows(self):
        """Connect all rows"""

        super().connectRows()
        for row in self.rows:
            row.contentChanged.connect(self.updateLayers)

    def moveRow(self, row: TargetLayersRow, step: int):
        """
        Moves a row with the provided step

        :param row: row to be moved
        :param step: how many steps this row should be moved
        """

        if row not in self.rows:
            return

        current_index = self.rows.index(row)
        destination_index = current_index + step

        if not step:
            return

        if current_index < 0 or destination_index < 0:
            return

        if current_index > len(self.rows) - 1 or destination_index > len(self.rows) - 1:
            return

        arguments = self.getArguments()
        arguments[current_index], arguments[destination_index] = arguments[destination_index], arguments[current_index]

        self.setArguments(arguments)
        self.updateMoveButtons()
        self.resizeTable()

    def removeCustomRow(self, row_idx: int, update: bool = True):
        """
        Remove row with index

        :param row_idx: index of row
        :param update: if update should happen
        """

        super().removeCustomRow(row_idx)
        if update:
            self.updateLayers()
            self.updateMoveButtons()

    def addElementColumn(self):
        """Add new abundance column (after the other abundance columns)"""

        column = 3 + len(self.elements)
        self.insertColumn(column)
        for i, row in enumerate(self.rows):
            row.addElementCell()
            self.updateCellWidgets(i)
        self.elements.append('??')

        self.header_labels.insert(column, '?? abundance')
        self.setHorizontalHeaderLabels(self.header_labels)
        self.horizontalHeaderItem(column).setToolTip(self.abundanceTooltip)
        self.updateLayers()

    def setCrystals(self, names: List[str]):
        """
        Shows a column for the fraction of each crystal and a column for the miller index of the layers

        :param names: names of the crystals, empty list removes the columns
        """

        names = list(names)
        if names == self.crystal_names:
            return

        column = 3 + len(self.elements)
        old_columns = len(self.crystal_names) + (1 if self.crystal_names else 0)
        for row in self.rows:
            row.storeCrystalValues()
        for _ in range(old_columns):
            self.removeColumn(column)
            del self.header_labels[column]

        self.crystal_names = names
        labels = [f'{name} fraction' for name in names] + (['Miller index (h k l)'] if names else [])
        for i, label in enumerate(labels):
            self.insertColumn(column + i)
            self.header_labels.insert(column + i, label)

        for i, row in enumerate(self.rows):
            row.setCrystalColumns(len(names))
            self.updateCellWidgets(i)

        self.setHorizontalHeaderLabels(self.header_labels)
        for i in range(len(names)):
            self.horizontalHeaderItem(column + i).setToolTip(self.crystalTooltip)
        if names:
            self.horizontalHeaderItem(column + len(names)).setToolTip(self.millerTooltip)
        self.resizeTable()
        self.updateLayers()

    def renameElementColumn(self, element_idx, new_name):
        """
        Rename abundance column for element

        :param element_idx: index for element
        :param new_name: new name
        """

        if len(self.elements) > element_idx:
            self.header_labels[element_idx + 3] = f'{new_name} abundance'
            self.elements[element_idx] = new_name
        self.setHorizontalHeaderLabels(self.header_labels)
        self.updateLayers()

    def removeElementColumn(self, element_idx):
        """
        Remove column for abundance of element

        :param element_idx: index for element
        """

        column_idx = element_idx + 3
        self.removeColumn(column_idx)
        del self.header_labels[column_idx]
        for i, row in enumerate(self.rows):
            row.removeElementCell(element_idx)
        del self.elements[element_idx]
        self.setHorizontalHeaderLabels(self.header_labels)
        self.updateLayers()

    def updateLayers(self, row=None):
        """
        Update layers (segments count)

        :param row: row to update
        """

        # Limit the total amount of segments
        limitSum([r.row_widgets[1] for r in self.rows], self.target_segments_count)

        # Update the abundance input fields of all target layers or optionally just the given layer (=row)
        rows = self.rows if row is None else [row]
        for i, row in enumerate(rows):
            row.layer_thickness.setValue(row.segment_count.value() * self.segment_thickness)
            limitSum(row.element_cells, 1.0)
            setWidgetHighlight(row.segment_count, row.segment_count.value() == 0)

            # the crystals can not make up more than the whole layer
            too_much_crystal = sum(cell.value() for cell in row.crystal_cells) > 1 + 1e-9
            for cell in row.crystal_cells:
                setWidgetHighlight(cell, too_much_crystal)

        # Highlight all abundance cells of an element if its abundance is zero in all of them
        # (not with crystals, elements might only be part of the crystals)
        element_indices = []
        for i in range(len(self.elements) if not self.crystal_names else 0):
            for j, row in enumerate(self.rows):
                if row.element_cells[i].value() > 0:
                    break
                elif j == len(self.rows) - 1:
                    # If we reach the last row, the whole column is zeros
                    element_indices.append(i)
        for row in self.rows:
            for i, cell in enumerate(row.element_cells):
                setWidgetHighlight(cell, i in element_indices)

        self.layersChanged.emit(self.elements, self.getData())
        emit_dict = {'layer_table_rows': len(self.rows)}
        if self.rows:
            emit_dict.update({'first_abundances': [element_cell.value() for element_cell in self.rows[0].element_cells]})
        self.emit(emit_dict)

    def updateMoveButtons(self):
        """Updates the move up and move down buttons"""

        for i, row in enumerate(self.rows):
            row.move_top.setEnabled(i != 0)
            row.move_bottom.setEnabled(i != len(self.rows) - 1)

    def setParameters(self, dictionary: dict):
        """
        Updates target segment count and segment thickness

        :param dictionary: dict that should contain keys 'thickness' and 'segments'
        """

        segments = dictionary.get('segments')
        if not segments:
            return
        self.setTargetSegmentsCount(segments)

        thickness = dictionary.get('thickness')
        if not thickness:
            return
        self.setSegmentThickness(thickness / segments)

    def setTargetSegmentsCount(self, target_segments_count):
        """
        Update target segment count

        :param target_segments_count: count of target segments
        """

        self.target_segments_count = target_segments_count
        for r in self.rows:
            r.segment_count.setMaximum(self.target_segments_count)
        self.resizeColumnsToContents()
        # Limit the total amount of segments
        limitSum([row.row_widgets[1] for row in self.rows], self.target_segments_count)

    def setSegmentThickness(self, segment_thickness):
        """
        Update segment thickness

        :param segment_thickness: thickness of segment
        """

        self.segment_thickness = segment_thickness
        for i, row in enumerate(self.rows):
            row.segmentThickness = segment_thickness
            row.layer_thickness.setValue(row.segment_count.value() * segment_thickness)
        self.resizeColumnsToContents()

    def resetTable(self):
        """Reset the table"""

        super().resetTable()
        self.label_row_idx = 0
        self.updateMoveButtons()

    def getArguments(self) -> List[StructureArguments]:
        """Returns list of <StructureArguments> containers for each row"""

        return [row.getArguments() for row in self.rows]

    def setArguments(self, arguments: List[StructureArguments]) -> list:
        """
        Sets list of <StructureArguments> containers of parameters for each row

        :param arguments: list of <StructureArguments> container
        """

        self.resetTable()
        not_loadable = []
        rows = []
        for _ in arguments:
            rows.append(self.addRow(update=False, connect=False))
        for argument, row in zip(arguments, rows):
            row.setArguments(argument)

        self.connectRows()
        self.updateLayers()
        self.updateMoveButtons()
        self.updateRemoveButtons()

        return not_loadable

    def receive(self, value_dict: dict):
        """
        Receives other settingsChanged pyqtSignal -> dict

        :param value_dict: dictionary to be received
        """

        enable_comp_table = value_dict.get('enable_layer_table')
        if enable_comp_table is not None:
            self.add_button.setEnabled(bool(enable_comp_table))
