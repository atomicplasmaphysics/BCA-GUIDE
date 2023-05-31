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
from PyQt6.QtWidgets import QComboBox, QPushButton, QDoubleSpinBox, QSpinBox

from Utility.ModifyWidget import setWidgetHighlight, widgetGetValue, widgetSetValue
from Utility.Functions import limitSum

from TableWidgets.CustomTable import CustomRowField, CustomRow, CustomTable

from Containers.Arguments import RowArguments, GeneralArguments, SimulationArguments
from Containers.Element import Element, Elements


class CompRow(CustomRow):
    """
    Row for component specific parameters

    :param row_fields: list of CustomRowField elements for unique id, label and tooltip
    :param element: element for row (optional)
    """

    elementChanged = pyqtSignal(Element)
    limitedObjectChanged = pyqtSignal(bool)
    selectElementText = '...'

    def __init__(self, row_fields: List[CustomRowField], element=Element()):
        super().__init__()
        self.row_fields = row_fields
        self.element = element
        self.remove.setToolTip('Remove this element from the composition')
        self.enabled = True

        self.element_index = QSpinBox()
        self.element_index.setEnabled(False)
        self.selected_element = QPushButton(self.selectElementText)
        self.selected_element.setToolTip('Click to choose element from periodic table')

        self.row_widgets += [self.element_index, self.selected_element]

        self.clearSpinboxButtons()

    def selectRowInput(self):
        """Select row as input"""

        self.selected_element.setFocus()

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
        self.selected_element.setText(element.symbol)
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

    def getArguments(self) -> RowArguments:
        """Returns <RowArguments> container of parameters for row"""

        return RowArguments(
            index=self.element_index.value(),
            symbol=self.element.symbol,
            element=self.getElement()
        )

    def setArguments(self, arguments: RowArguments, general_arguments: Union[SimulationArguments, GeneralArguments]):
        """
        Sets <RowArguments> container of parameters for row

        :param arguments: Container of <RowArguments>
        :param general_arguments: Container of <GeneralArguments> or <SimulationArguments>
        """

        self.setElement(arguments.element)

    def receive(self, value_dict: dict):
        """
        Receives other settingsChanged pyqtSignal -> dict

        :param value_dict: dictionary to be received
        """

        pass


class CompTable(CustomTable):
    """
    Table for component rows

    :param parent: parent widget
    :param comp_count: component counter
    :param row_fields: list of CustomRowField elements for unique id, label and tooltip
    :param custom_comp_row: type of custom CompRow (optional)
    """

    rowRemoved = pyqtSignal(int)
    rowAdded = pyqtSignal(CustomRow)
    elementChanged = pyqtSignal(CompRow, Element)
    elementClicked = pyqtSignal(CompRow)

    generalRowFields = [
        CustomRowField(
            unique='id',
            label='#',
            tooltip='The index of the element as it occurs in the input file',
            synced=False
        ),
        CustomRowField(
            unique='symbol',
            label='Element',
            synced=False
        )
    ]

    def __init__(self, parent, comp_count, row_fields: List[CustomRowField] = None, custom_comp_row=CompRow):
        if row_fields is None:
            row_fields = []
        self.row_fields: List[CustomRowField] = self.generalRowFields + row_fields
        self.labels = [row_field.label for row_field in self.row_fields]
        self.tooltips = [row_field.tooltip for row_field in self.row_fields]
        self.component_row = custom_comp_row
        self.component_count = comp_count

        super().__init__(0, self.labels, parent)
        self.rows: List[CompRow] = []

        self.add_button.setToolTip('Add a new element to the composition')

        for i, tooltip in enumerate(self.tooltips):
            if tooltip:
                self.horizontalHeaderItem(i + 1).setToolTip(tooltip)

        self.component_count.maxReached.connect(lambda max_reached: self.maxCompReached(max_reached))

    def createRow(self, row_idx) -> CompRow:
        """
        Creates a new row

        :param row_idx: index of row
        """

        return self.component_row(self.row_fields)

    def addRow(self, update: bool = True, connect: bool = True) -> Union[CompRow, bool]:
        """
        Add a new row

        :param update: if updates should happen
        :param connect: if row should be connected
        """

        next_rank = self.component_count.getNext()
        if not next_rank:
            return False
        row = super().addRow(update=update, connect=connect)
        row.selected_element.clicked.connect(lambda checked: self.elementClicked.emit(row))
        row.elementChanged.connect(lambda element: self.elementChanged.emit(row, element))
        if connect:
            row.contentChanged.connect(self.limitColumns)
        next_rank.rankChanged.connect(lambda rank, r=row: r.element_index.setValue(rank))
        row.element_index.setValue(next_rank.value)
        if connect:
            self.limitColumns()
        self.rowAdded.emit(row)
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
        self.limitColumns()

    def connectRows(self):
        """Connect all rows"""

        for row in self.rows:
            row.contentChanged.connect(self.limitColumns)
        super().connectRows()

    def removeCustomRow(self, row_idx: int, update: bool = True):
        """
        Remove row with index

        :param row_idx: index of row
        :param update: if update should happen
        """

        self.component_count.delItem(self.rows[row_idx].element_index.value())
        super().removeCustomRow(row_idx)
        if update:
            self.limitColumns()
        self.rowRemoved.emit(row_idx)

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

    def updateAllSyncedValues(self, target_rows: List[CompRow]):
        """
        Updates all synced values

        :param target_rows: list of <CompRow>
        """

        synced_symbols = []
        for target_row in reversed(target_rows):
            # only sync with last entry of element (= editable element)
            target_row_symbol = target_row.element.symbol
            if target_row_symbol == '' or target_row_symbol in synced_symbols:
                continue
            synced_symbols.append(target_row_symbol)

            for field, widget in zip(target_row.row_fields, target_row.row_widgets[1:]):
                # field must be synced and widget must support value() call
                if field.synced:
                    widget_value = widgetGetValue(widget)
                    if widget_value is not None:
                        self.updateSyncedValue(target_row.element.symbol, field.unique_id, widget_value)

    def updateSyncedValue(self, element_symbol: str, unique_id: int, new_value: Union[int, float, str, bool]):
        """
        Sets a value given by the 'unique_id' of the element with name 'name' to the given 'new_value'

        :param element_symbol: element symbol that will be changed
        :param unique_id: refers to unique Id (-> column) in CustomRowField
        :param new_value: new value for specified unique name (-> column)
        """

        success = False
        i = 0
        for i, row_field in enumerate(self.row_fields):
            if row_field.unique_id == unique_id and row_field.synced:
                success = True
                break
        if not success:
            return

        for row in self.rows:
            if row.element.symbol == '' or row.element.symbol != element_symbol:
                continue
            widget = row.row_widgets[i + 1]
            widgetSetValue(widget, new_value)

    def updateSyncedFields(self, target_rows: List[CompRow]):
        """
        Dis-/Enables the certain input fields of each element in this table depending on whether the
        same element is also present in the target ('targetElements').

        :param target_rows: list of <CompRow> rows of CompTableTarget
        """

        symbols = [target_row.element.symbol for target_row in target_rows if target_row.element.symbol != '']
        for target_row in target_rows:
            if target_row.element.symbol == '':
                continue

            for row in self.rows:
                if target_row == row:
                    continue
                if row.element.symbol == '':
                    continue

                # Change enabled state and change values to target values if synced
                enabled = row.element.symbol not in symbols
                row.setEnabled(enabled)

    def getArguments(self) -> List[RowArguments]:
        """Returns list of <RowArguments> containers of parameters for each row"""

        return [row.getArguments() for row in self.rows]

    def setArguments(self, arguments: List[RowArguments], general_arguments: Union[SimulationArguments, GeneralArguments], elements: Elements, connect: bool = True) -> list:
        """
        Sets list of <RowArguments> containers of parameters for each row

        :param arguments: list of <RowArguments> containers
        :param general_arguments: <GeneralArguments> or <SimulationArguments> containers
        :param elements: element data
        :param connect: if should be connected
        """

        not_loadable = []
        rows = []
        for _ in arguments:
            rows.append(self.addRow(connect=False))
        for argument, row in zip(arguments, rows):
            old_element = argument.element
            if row is False:
                not_loadable.append(f'Element "{old_element.symbol}" ({old_element}) not loaded, too many elements')
                continue
            updated_element = elements.elementFromSymbol(old_element.symbol)
            if updated_element is None:
                not_loadable.append(f'Element "{old_element.symbol}" ({old_element}) not supported')
                continue
            argument.element = updated_element
            row.setArguments(argument, general_arguments)
            if old_element.modified:
                row.adaptElement(old_element)
        if connect:
            self.connectRows()
            self.limitColumns()
        return not_loadable

    def receive(self, value_dict: dict):
        """
        Receives other settingsChanged pyqtSignal -> dict

        :param value_dict: dictionary to be received
        """

        # forward value_dict to all rows
        for row in self.rows:
            row.receive(value_dict)


class CompTableTarget(CompTable):
    """
    Table for component rows of target
    """

    syncableValueChanged = pyqtSignal(str, int, float)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def addRow(self, update: bool = True, connect: bool = True) -> Union[CompRow, bool]:
        """
        Add a new row

        :param update: if updates should happen
        :param connect: if row should be connected
        """

        row = super().addRow(update=update, connect=connect)
        if row is False:
            return row

        for field, widget in zip(self.row_fields, row.row_widgets[1:]):
            if not field.synced:
                continue
            if isinstance(widget, QSpinBox) or isinstance(widget, QDoubleSpinBox):
                widget.valueChanged.connect(
                    lambda value, r=row, f=field: self.emitSyncableValueChange(f, value, r)
                )
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(
                    lambda value, r=row, f=field: self.emitSyncableValueChange(f, value, r)
                )
        return row

    def updateSyncedFields(self, target_rows: List[CompRow]):
        """
        Dis-/Enables the certain input fields of each element in this table depending on whether the
        same element is also present in the target ('targetElements'). Also syncs values of the fields

        :param target_rows: list of CompTableTarget rows
        """

        super().updateSyncedFields(target_rows)

        # Enable last rows of each element again
        enabled_symbols = []
        for row in reversed(self.rows):
            row_symbol = row.element.symbol
            if row_symbol == '' or row_symbol in enabled_symbols:
                continue
            enabled_symbols.append(row_symbol)
            row.setEnabled(True)
            for field, widget in zip(row.row_fields, row.row_widgets[1:]):
                if field.synced:
                    self.updateSyncedValue(row_symbol, field.unique_id, widgetGetValue(widget))
                    if field.enabled:
                        widget.setEnabled(True)

    def emitSyncableValueChange(self, field: CustomRowField, new_value: float, row: CompRow):
        """
        Emit a signal to sync values in beam table with target table for matching elements

        :param field: CustomRowField
        :param new_value: new value for specified unique name (-> column)
        :param row: row element
        """

        if field.reset_neg and new_value < 0:
            return
        if row.element.symbol == '':
            return
        self.syncableValueChanged.emit(row.element.symbol, field.unique_id, new_value)
