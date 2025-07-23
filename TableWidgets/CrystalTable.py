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


from typing import List, Union

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QSpinBox, QDoubleSpinBox

from Utility.Functions import limitSum

from TableWidgets.CustomTable import CustomRowField, CustomRow, CustomTable
from Containers.Arguments import StructureArguments
from Containers.Element import Element, Elements
from TableWidgets.CompTable import CompTable
from Containers.Arguments import RowArguments, GeneralArguments, SimulationArguments
from Utility.ModifyWidget import setWidgetHighlight, widgetGetValue, widgetSetValue

from Containers.Arguments import (
    ArgumentValues, GeneralBeamArguments, GeneralTargetArguments,
    GeneralArguments, RowArguments, CrystalRowArguments, SimulationArguments, StructureArguments
)


class CrystalRow(CustomRow):
    """
    Row for component specific parameters

    :param row_fields: list of CustomRowField elements for unique id, label and tooltip
    :param element: element for row (optional)
    """

    coordinateChanged = pyqtSignal()
    elementChanged = pyqtSignal(Element)
    limitedObjectChanged = pyqtSignal(bool)
    selectElementText = '...'

    def __init__(self, row_fields: List[CustomRowField], element=Element(), **kwargs):
        super().__init__()
        self.row_fields = row_fields
        self.element = element
        self.remove.setToolTip('Remove this element from the composition')
        self.enabled = True
        self.element_index = QSpinBox()
        self.element_index.setEnabled(False)
        self.row_widgets += [self.element_index]
        self.clearSpinboxButtons()

    def selectRowInput(self):
        """Select row as input"""

        #self.element.setFocus()

    def containsData(self) -> bool:
        """Check if row contains data"""

        return self.element.symbol != ''

    def getRowData(self) -> dict:
        """Returns data of row as CompEntry"""

        fields = [row_field.label for row_field in self.row_fields]
        values = []
        for widget in self.row_widgets[1:]:
            values.append(widgetGetValue(widget))

        return dict(zip(fields, values))

    def setElement(self, element: Element):
        """
        Sets rows element to element

        :param element: desired element
        """

        self.element = element
        self.elementChanged.emit(element)
        self.contentChanged.emit()

    def adaptElement(self, element: Element):
        """
        Adapts element specific parameters

        :param element: desired element
        """

        pass

    def getElement(self) -> Element:
        """Returns element"""

        return self.element

    def setRowData(self, data):
        """
        Sets data of row as CompEntry

        :param data: data to be set in row
        """

        self.setElement(data.element)

    def setEnabled(self, enabled: bool):
        """
        Set row disabled or enabled

        :param enabled: enable/disable
        """

        self.enabled = enabled
        for field, widget in zip(self.row_fields, self.row_widgets[1:]):
            if field.synced:
                widget.setEnabled(enabled)

    def isEnabled(self) -> bool:
        """Returns enabled state of row"""

        return self.enabled

    def updateHighlightSpinbox(self, spinbox: Union[QSpinBox, QDoubleSpinBox], default_value: float, digits: int = 10):
        """
        Update highlighting of spinbox if different from default value up to fixed digits

        :param spinbox: QSpinBox or QDoubleSpinBox
        :param default_value: default value for spinbox
        :param digits: number of digits that should be compared
        """

        if self.element.symbol == '':
            return
        highlight = False

        # Highlight if it's enabled and it differs from the default value
        if spinbox.isEnabled():
            highlight = abs(spinbox.value() - default_value) > float(f'1e-{digits}')
        setWidgetHighlight(spinbox, highlight)

    def resetSpinbox(self, spinbox: Union[QSpinBox, QDoubleSpinBox], default_value: float):
        """
        Resets spinbox to default value if value is negative

        :param spinbox: QSpinBox or QDoubleSpinBox
        :param default_value: default value for spinbox
        """

        if self.element.symbol == '':
            return

        if spinbox.isEnabled() and spinbox.value() < 0:
            spinbox.setValue(default_value)

    def updateHighlightAndResetSpinbox(self, spinbox: Union[QSpinBox, QDoubleSpinBox], default_value: float, digits: int = 10):
        """
        Resets spinbox to default value if value is negative
        Update highlighting of spinbox if different from default value up to fixed digits

        :param spinbox: QSpinBox or QDoubleSpinBox
        :param default_value: default value for spinbox
        :param digits: number of digits that should be compared
        """

        if self.element.symbol == '':
            return
        highlight = False

        # Highlight if it's enabled and it differs from the default value
        if spinbox.isEnabled():
            highlight = abs(spinbox.value() - default_value) > float(f'1e-{digits}')
            if spinbox.value() < 0:
                spinbox.setValue(default_value)
                highlight = False

        setWidgetHighlight(spinbox, highlight)

    @staticmethod
    def updateHighlightWidgetValue(widget, value: float):
        """
        Update highlighting of widget if it has specific value

        :param widget: widget to highlight
        :param value: value to be checked against
        """

        setWidgetHighlight(widget, widget.value() == value)

    def getArguments(self) -> CrystalRowArguments:
        """Returns <CrystalRowArguments> container of parameters for row"""

        return CrystalRowArguments(
            index=self.element_index.value(),
            symbol=self.element.symbol,
            element=self.getElement(),
        )

    def setArguments(self, arguments: CrystalRowArguments, general_arguments: Union[SimulationArguments, GeneralArguments]):
        """
        Sets <RowArguments> container of parameters for row

        :param arguments: Container of <RowArguments>
        :param general_arguments: Container of <GeneralArguments> or <SimulationArguments>
        """

        self.element_index = arguments.index
        self.element = arguments.symbol

    def receive(self, value_dict: dict):
        """
        Receives other settingsChanged pyqtSignal -> dict

        :param value_dict: dictionary to be received
        """

        pass

class CrystalTable(CustomTable):
    """
    Table for component rows

    :param parent: parent widget
    :param comp_count: component counter
    :param row_fields: list of CustomRowField elements for unique id, label and tooltip
    :param custom_comp_row: type of custom CrystalRow (optional)
    :param version: version string (optional)
    """
    coordinateChanged = pyqtSignal()
    rowRemoved = pyqtSignal(int)
    rowAdded = pyqtSignal(CustomRow)
    elementChanged = pyqtSignal(CrystalRow, Element)
    elementClicked = pyqtSignal(CrystalRow)

    generalRowFields = [
        CustomRowField(
            unique='id',
            label='#',
            tooltip='The index of the element as it occurs in the input file',
            synced=False
        )
    ]

    def __init__(self, parent, comp_count,  target_elements: List[str], row_fields: List[CustomRowField] = None,  custom_comp_row=CrystalRow, version: str = ''):

        if row_fields is None:
            row_fields = []
        self.row_fields: List[CustomRowField] = self.generalRowFields + row_fields
        self.labels = [row_field.label for row_field in self.row_fields]
        self.tooltips = [row_field.tooltip for row_field in self.row_fields]
        self.component_row = custom_comp_row
        self.component_count = comp_count
        self.target_elements = target_elements
        self.version = version

        super().__init__(0, self.labels, parent)
        self.rows: List[CrystalRow] = []

        self.add_button.setToolTip('Add a new element to the composition')

        for i, tooltip in enumerate(self.tooltips):
            if tooltip:
                self.horizontalHeaderItem(i + 1).setToolTip(tooltip)

    def createRow(self, row_idx) -> CrystalRow:
        """
        Creates a new row

        :param row_idx: index of row
        """

        return self.component_row(row_fields=self.row_fields, target_elements=self.target_elements, version=self.version, available_elements=self.target_elements)

    def addRow(self, update: bool = True, connect: bool = True) -> Union[CrystalRow, bool]:
        """
        Add a new row

        :param update: if updates should happen
        :param connect: if row should be connected
        """

        next_rank = self.component_count.getNext()
        if not next_rank:
            return False
        row = super().addRow(update=update, connect=connect)
        row.coordinateChanged.connect(self.coordinateChanged.emit)

        row.elementChanged.connect(lambda element: self.elementChanged.emit(row, element))
        next_rank.rankChanged.connect(lambda rank, r=row: r.element_index.setValue(rank))
        row.element_index.setValue(next_rank.value)
        # if connect:
            # self.limitColumns()
        self.rowAdded.emit(row)
        self.coordinateChanged.emit()
        self.emit({
            'row_added': True
        })

        return row

    def addRows(self, comp_entries: list):
        """
        Add multiple rows

        :param comp_entries: list of component entries
        """

        for comp_entry in comp_entries:
            row = self.addRow(connect=False)
            row.setRowData(comp_entry)
        self.connectRows()
        # self.limitColumns()

    def connectRows(self):
        """Connect all rows"""
        super().connectRows()

    def resetTable(self):
        """Reset the table"""
        super().resetTable()


    def removeCustomRow(self, row_idx: int, update: bool = True):
        """
        Remove row with index

        :param row_idx: index of row
        :param update: if update should happen
        """

        self.component_count.delItem(self.rows[row_idx].element_index.value())
        super().removeCustomRow(row_idx)
        self.rowRemoved.emit(row_idx)
        if row_idx >0:
            self.coordinateChanged.emit()

    def maxCompReached(self, max_reached: bool):
        """
        Called when maximum number of components are reached

        :param max_reached: if maximum is reached
        """

        self.add_button.setDisabled(max_reached)

    def limitColumns(self):
        """Limits columns to maximum value (if defined)"""

        for i, field in enumerate(self.row_fields):
            if not field.limit:
                continue
            objects = [row.row_widgets[i + 1] for row in self.rows]
            limitSum(objects, field.limit)

    def allRowsHaveData(self) -> bool:
        """Returns if all rows have a selected element"""

        return all([row.containsData() for row in self.rows])

    def getArguments(self) -> List[CrystalRowArguments]:
        """Returns list of <CrystalRowArguments> containers of parameters for each row"""

        return [row.getArguments() for row in self.rows]

    def setArguments(self, arguments: List[CrystalRowArguments], general_arguments: Union[SimulationArguments, GeneralArguments], connect: bool = True) -> list:
        """
        Sets list of <CrystalRowArguments> containers of parameters for each row
        :param arguments: list of <CrystalRowArguments> containers
        :param general_arguments: <GeneralArguments> or <SimulationArguments> containers
        :param connect: if should be connected
        """

        not_loadable = []
        rows = []
        for _ in arguments:
            rows.append(self.addRow(connect=False))

        for argument, row in zip(arguments, rows):
            row.setArguments(argument, general_arguments)

        if connect:
            self.connectRows()

        return not_loadable

    def receive(self, value_dict: dict):
        """
        Receives other settingsChanged pyqtSignal -> dict

        :param value_dict: dictionary to be received
        """
        # forward value_dict to all rows
        for row in self.rows:
            row.receive(value_dict)

    def UpdateAvailableElements(self, target_elements: [str]):
        self.target_elements = target_elements

    def getRows(self):
        return self.rows



