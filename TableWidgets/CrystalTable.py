from typing import List, Union, Optional

from PyQt6.QtCore import pyqtSignal

from Utility.Functions import limitSum
from Utility.ModifyWidget import setWidgetBackground
from Utility.Layouts import ComboBox, DoubleSpinBox, SpinBoxRange

from TableWidgets.CustomTable import CustomRowField, CustomRow, CustomTable

from Containers.Element import Element
from Containers.Arguments import CrystalRowArguments
from Containers.Crystal import Coordinate


class CrystalRow(CustomRow):
    """
    Row for crystal lattice point

    :param available_elements: list of available <Element>s
    """

    coordinateChanged = pyqtSignal()
    elementChanged = pyqtSignal(Element)
    limitedObjectChanged = pyqtSignal(bool)

    rowFields = [
        CustomRowField(
            unique='crystal_element',
            label='Element',
            tooltip='<i>species</i><br>Choose the element from available element list which sits on the coordinates (a1,a2,a3)'
        ),
        CustomRowField(
            unique='a_1',
            label='a\u2081',
            tooltip='<i>a\u2081</i><br>Atom position in unit cell in a\u2081 direction value is between 0 and 1',
            synced=False
        ),
        CustomRowField(
            unique='a_2',
            label='a\u2082',
            tooltip='<i>a\u2082</i><br>Atom position in unit cell in a\u2082 direction value is between 0 and 1',
            synced=False
        ),
        CustomRowField(
            unique='a_3',
            label='a\u2083',
            tooltip='<i>a\u2083</i><br>Atom position in unit cell in a\u2083 direction value is between 0 and 1',
            synced=False
        )
    ]

    def __init__(self, available_elements: Optional[List[Element]] = None):
        super().__init__()

        if available_elements is None:
            available_elements = []

        self.available_elements = available_elements
        self.available_elements_symbols = [element.symbol for element in available_elements]
        self.available_elements_symbols.insert(0, 'No element chosen')

        self.remove.setToolTip('Remove this element from the composition')
        self.enabled = True
        self.clearSpinboxButtons()

        self.element_combobox = ComboBox(
            entries=self.available_elements_symbols,
            label_default=False
        )

        self.element_combobox.currentIndexChanged.connect(self.coordinateChanged.emit)
        self.element_combobox.mouseReleaseEvent = lambda _: setWidgetBackground(self.element_combobox, False)

        self.coords = [DoubleSpinBox(
            default=0,
            input_range=SpinBoxRange.ZERO_ONE,
            step_size=0.01,
            decimals=7
        ) for _ in range(3)]

        self.row_widgets += [
            self.element_combobox,
            *self.coords
        ]

        for coord in self.coords:
            coord.valueChanged.connect(self.coordinateChanged.emit)

        self.clearSpinboxButtons()

    def selectRowInput(self):
        """Select row as input"""

        self.element_combobox.setFocus()

    def setEnabled(self, enabled: bool):
        """
        Set row disabled or enabled

        :param enabled: enable/disable
        """

        self.enabled = enabled
        for field, widget in zip(self.rowFields, self.row_widgets[1:]):
            if field.synced:
                widget.setEnabled(enabled)

    def getArguments(self) -> CrystalRowArguments:
        """Returns <CrystalRowArguments> container of parameters for row"""

        return CrystalRowArguments(
            symbol=self.element_combobox.currentText(),
            coord=Coordinate([coord.value() for coord in self.coords])
        )

    def setArguments(self, arguments: CrystalRowArguments):
        """
        Sets <RowArguments> container of parameters for row

        :param arguments: Container of <RowArguments>
        """

        assumed = arguments.get('assumed')
        if not isinstance(assumed, list):
            assumed = []

        # coordinates
        coord = arguments.get('coord')
        if 'coord' in assumed:
            coord = Coordinate()

        for widget, val in zip(self.coords, coord):
            widget.setValue(val)

        # symbol
        symbol = arguments.get('symbol')
        if 'symbol' in assumed or symbol not in self.available_elements_symbols:
            self.element_combobox.setCurrentIndex(0)
            setWidgetBackground(self.element_combobox, True)
        else:
            self.element_combobox.setValue(symbol, from_entries=True)

    def setAvailableElements(self, available_elements: List[Element]):
        """
        Sets the available element list

        :param available_elements: list of available elements
        """

        index = 0
        available_elements_symbols = [element.symbol for element in available_elements]
        if self.element_combobox.currentText() in available_elements_symbols:
            index = available_elements_symbols.index(self.element_combobox.currentText()) + 1

        self.available_elements = available_elements
        self.available_elements_symbols = available_elements_symbols
        self.available_elements_symbols.insert(0, 'No element chosen')

        self.element_combobox.clear()

        self.element_combobox.addItems(self.available_elements_symbols)
        self.element_combobox.setCurrentIndex(index)

    def getSelectedElement(self) -> Element:
        """Returns the selected element"""

        index = self.element_combobox.currentIndex()
        if index == 0:
            return Element()
        else:
            return self.available_elements[index - 1]

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
    :param row_fields: list of CustomRowField elements for unique id, label and tooltip
    :param custom_comp_row: type of custom CrystalRow (optional)
    :param version: version string (optional)
    """

    coordinateChanged = pyqtSignal()
    rowRemoved = pyqtSignal(int)
    rowAdded = pyqtSignal(CustomRow)
    elementChanged = pyqtSignal(CrystalRow, Element)
    elementClicked = pyqtSignal(CrystalRow)

    def __init__(
        self,
        parent,
        target_elements: List[Element],
        row_fields: List[CustomRowField] = None,
        custom_comp_row=CrystalRow,
        version: str = ''
    ):
        if row_fields is None:
            row_fields = []
        self.row_fields = row_fields
        self.labels = [row_field.label for row_field in self.row_fields]
        self.tooltips = [row_field.tooltip for row_field in self.row_fields]
        self.component_row = custom_comp_row
        self.target_elements = target_elements
        self.version = version

        super().__init__(0, self.labels, parent)
        self.rows: List[CrystalRow] = []

        self.add_button.setToolTip('Add a new element to the composition')

        for i, tooltip in enumerate(self.tooltips, 1):
            if tooltip:
                self.horizontalHeaderItem(i).setToolTip(tooltip)

    def createRow(self, row_idx) -> CrystalRow:
        """
        Creates a new row

        :param row_idx: index of row
        """

        return self.component_row(self.target_elements)

    def addRow(self, update: bool = True, connect: bool = True) -> Union[CrystalRow, bool]:
        """
        Add a new row

        :param update: if updates should happen
        :param connect: if row should be connected
        """

        row = super().addRow(update=update, connect=connect)
        row.coordinateChanged.connect(self.coordinateChanged.emit)

        row.elementChanged.connect(lambda element: self.elementChanged.emit(row, element))

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

        super().removeCustomRow(row_idx)
        self.rowRemoved.emit(row_idx)
        if row_idx > 0:
            self.coordinateChanged.emit()

    def maxCompReached(self, max_reached: bool):
        """
        Called when maximum number of components are reached

        :param max_reached: if maximum is reached
        """

        self.add_button.setDisabled(max_reached)

    def limitColumns(self):
        """Limits columns to maximum value (if defined)"""

        for i, field in enumerate(self.row_fields, 1):
            if not field.limit:
                continue
            objects = [row.row_widgets[i] for row in self.rows]
            limitSum(objects, field.limit)

    def getArguments(self) -> List[CrystalRowArguments]:
        """Returns list of <CrystalRowArguments> containers of parameters for each row"""

        return [row.getArguments() for row in self.rows]

    def setArguments(self, arguments: List[CrystalRowArguments], connect: bool = True) -> list:
        """
        Sets list of <CrystalRowArguments> containers of parameters for each row
        :param arguments: list of <CrystalRowArguments> containers
        :param connect: if it should be connected
        """

        not_loadable = []
        rows = []
        for _ in arguments:
            rows.append(self.addRow(connect=False))

        for argument, row in zip(arguments, rows):
            row.setArguments(argument)

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

    def updateAvailableElements(self, target_elements: List[Element]):
        """Updates available elements"""
        self.target_elements = target_elements

    def getRows(self):
        """Returns rows"""
        return self.rows
