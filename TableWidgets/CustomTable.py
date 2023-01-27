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

from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QTableWidget, QPushButton, QAbstractItemView, QHeaderView, QHBoxLayout, QWidget, QAbstractSpinBox


class CustomRowField:
    """
    Class for custom row fields

    :param unique: unique name of column
    :param label: label of column
    :param tooltip: (optional) tooltip of column
    :param synced: (optional) is this value synced with other values
    :param limit: (optional) limit column to maximum value or False
    :param reset_neg: (optional) resets to default value if negative
    :param enabled: (optional) if field is enabled
    """

    uniqueList = []
    uniqueIdLast = 0

    def __init__(self, unique: str, label: str, tooltip: str = '', synced: bool = True,
                 limit: Union[bool, int, float] = False, reset_neg: bool = False, enabled: bool = True):
        self.unique = unique
        self.label = label
        self.tooltip = tooltip
        self.synced = synced
        self.limit = limit
        self.reset_neg = reset_neg
        self.enabled = enabled

        self.unique_id = self.uniqueIdLast
        CustomRowField.uniqueIdLast += 1


class CustomRow(QObject):
    """
    Class for custom QObject row
    """

    contentChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.remove = QPushButton(QIcon(':/icons/delete.png'), '')
        self.remove.setFixedSize(30, 30)
        # Center the remove button by surrounding it with two stretches inside a horizontal layout
        self.remove_button_parent = QWidget()
        self.remove_button_parent_hl = QHBoxLayout()
        self.remove_button_parent_hl.setSpacing(0)
        self.remove_button_parent_hl.setContentsMargins(0, 0, 0, 0)
        self.remove_button_parent_hl.addStretch(1)
        self.remove_button_parent_hl.addWidget(self.remove)
        self.remove_button_parent_hl.addStretch(1)
        self.remove_button_parent.setLayout(self.remove_button_parent_hl)
        self.row_widgets = [self.remove_button_parent]

    def clearSpinboxButtons(self):
        """Clear QSpinBox buttons"""

        for widget in self.row_widgets:
            if isinstance(widget, QAbstractSpinBox):
                widget.setButtonSymbols(QAbstractSpinBox.NoButtons)

    def selectRowInput(self):
        """Select row as input"""

        raise NotImplementedError('Must override selectRowInput()')

    def containsData(self) -> bool:
        """Check if row contains data"""

        return True

    def getRowData(self):
        """Returns data of row"""

        raise NotImplementedError('Must override getRowData()')

    def getArguments(self):
        """Returns <Argument> container"""

        raise NotImplementedError('Must overwrite getArguments()')


class CustomTable(QTableWidget):
    """
    Class for custom QTableWidget

    :param row_count: number of rows
    :param header_labels: list of header labels
    :param parent: parent widget
    """

    settingsChanged = pyqtSignal(dict)
    contentChanged = pyqtSignal()

    def __init__(self, row_count: int, header_labels, parent):
        self.header_labels = [''] + header_labels
        super().__init__(row_count, len(self.header_labels), parent)
        self.rows: List[CustomRow] = []

        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.verticalHeader().setVisible(False)
        self.setHorizontalHeaderLabels(self.header_labels)

        self.horizontal_header = self.horizontalHeader()
        self.horizontal_header.setSectionResizeMode(QHeaderView.ResizeToContents)
        self.horizontal_header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.horizontal_header.setMinimumSectionSize(40)

        self.add_button = QPushButton(QIcon(':/icons/add.png'), '')
        self.add_button.setFixedSize(30, 30)
        self.add_button.clicked.connect(lambda: self.addRow())
        self.createAddButton()

    def createAddButton(self):
        """Creates add button"""

        self.insertRow(0)
        self.setCellWidget(0, 0, self.add_button)
        self.setSpan(0, 0, 1, len(self.header_labels))

    def createRow(self, row_idx: int):
        """
        Create row with index

        :param row_idx: index of row
        """

        raise NotImplementedError('Must override createRow()')

    def addRow(self, update: bool = True, connect: bool = True):
        """
        Add a new row

        :param update: if updates should happen
        :param connect: if row should be connected
        """

        row_idx = self.rowCount() - 1  # add it before the '+'-button-row
        row = self.createRow(row_idx)
        row.remove.clicked.connect(lambda: self.removeCustomRow(self.rows.index(row)))
        self.insertRow(row_idx)
        self.rows.append(row)
        self.updateCellWidgets(row_idx)

        if update:
            self.resizeTable()
            self.updateRemoveButtons()
        row.selectRowInput()
        self.contentChanged.emit()

        if connect:
            row.contentChanged.connect(self.contentChanged.emit)
        return row

    def connectRows(self):
        """Connect all rows"""

        for row in self.rows:
            row.contentChanged.connect(self.contentChanged.emit)

    def resizeTable(self):
        """Resizes the table"""

        self.resizeColumnsToContents()
        self.resizeRowsToContents()

        # first column needs to be resized as well
        if self.rowCount() > 1:
            first_width = self.cellWidget(0, 0).sizeHint().width()
            self.setColumnWidth(0, first_width)

    def removeCustomRow(self, row_idx: int, update: bool = True):
        """
        Remove row with index

        :param row_idx: index of row
        :param update: if update should happen
        """

        self.removeRow(row_idx)
        del self.rows[row_idx]
        if update:
            self.updateRemoveButtons()
            self.contentChanged.emit()

    def updateRemoveButtons(self):
        """Updates remove buttons of rows"""

        for i, row in enumerate(self.rows):
            row.remove.setEnabled(True)
        if len(self.rows) == 1:
            self.rows[0].remove.setEnabled(False)

    def updateCellWidgets(self, row_idx: int):
        """
        Update cell widgets in row with index

        :param row_idx: index of row
        """

        for i, widget in enumerate(self.rows[row_idx].row_widgets):
            self.setCellWidget(row_idx, i, widget)

    def getData(self):
        """
        Returns a list of custom 'entry'-objects (depending on the table type)
        containing the table's rows' data, if the row contains data
        """

        return [row.getRowData() for row in self.rows if row.containsData()]

    def resetTable(self):
        """Reset the table"""

        while len(self.rows) > 0:
            self.removeCustomRow(0, update=False)

    def getArguments(self):
        """Returns list of <Argument> containers for each row"""

        raise NotImplementedError('Must overwrite getArguments()')

    def emit(self, value_dict: dict = None):
        """
        Emits settingsChanged pyqtSignal

        :param value_dict: dictionary to emit
        """

        if value_dict is None:
            return
        self.settingsChanged.emit(value_dict)

    def receive(self, value_dict: dict):
        """Receives other settingsChanged pyqtSignal -> dict"""

        pass
