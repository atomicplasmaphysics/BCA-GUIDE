from typing import Generic, List, Union, Optional, TypeVar

from PyQt6.QtCore import pyqtSignal, QObject, Qt
from PyQt6.QtWidgets import QTableWidget, QPushButton, QAbstractItemView, QHeaderView, QHBoxLayout, QWidget, QAbstractSpinBox, QFrame

from Utility.Icons import getIcon
from Utility.Typing import notNone


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

    uniqueList: List[int] = []
    uniqueIdLast = 0

    def __init__(
        self,
        unique: str,
        label: str,
        tooltip: str = '',
        synced: bool = True,
        limit: Union[bool, int, float] = False,
        reset_neg: bool = False,
        enabled: bool = True
    ):
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
        self.remove = QPushButton(getIcon('close'), '')
        self.remove.setFixedSize(30, 30)
        self.remove.setAutoDefault(False)
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
                widget.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

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


# type of the rows of a table
RowT = TypeVar('RowT', bound=CustomRow)


class CustomTable(QTableWidget, Generic[RowT]):
    """
    Class for custom QTableWidget

    :param row_count: number of rows
    :param header_labels: list of header labels
    :param parent: parent widget
    :param frozen_columns: (optional) number of first columns that stay visible when scrolling horizontally
    """

    settingsChanged = pyqtSignal(dict)
    contentChanged = pyqtSignal()

    def __init__(self, row_count: int, header_labels, parent, frozen_columns: int = 0):
        self.header_labels = [''] + header_labels
        super().__init__(row_count, len(self.header_labels), parent)
        self.rows: List[RowT] = []

        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        notNone(self.verticalHeader()).setVisible(False)
        self.setHorizontalHeaderLabels(self.header_labels)

        self.horizontal_header = notNone(self.horizontalHeader())
        self.horizontal_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontal_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.horizontal_header.setMinimumSectionSize(40)

        # the first columns are shown in a second table on top of this one, which does not scroll horizontally
        self.frozen_columns = frozen_columns
        self.frozen: Optional[QTableWidget] = None
        if frozen_columns > 0:
            self.createFrozenTable()

        self.add_button = QPushButton(getIcon('add'), '')
        self.add_button.setFixedSize(30, 30)
        self.add_button.setAutoDefault(False)
        self.add_button.clicked.connect(lambda: self.addRow())
        self.createAddButton()

    def createFrozenTable(self):
        """Creates the table for the frozen first columns"""

        self.frozen = QTableWidget(self.rowCount(), self.frozen_columns, self)
        self.frozen.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.frozen.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        notNone(self.frozen.verticalHeader()).setVisible(False)
        self.frozen.setHorizontalHeaderLabels(self.header_labels[:self.frozen_columns])
        frozen_header = notNone(self.frozen.horizontalHeader())
        frozen_header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        frozen_header.setMinimumSectionSize(self.horizontal_header.minimumSectionSize())
        self.frozen.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.frozen.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.frozen.setFrameShape(QFrame.Shape.NoFrame)
        self.frozen.setVerticalScrollMode(self.verticalScrollMode())
        # opaque, otherwise the scrolled columns are visible below the frozen ones
        for widget in (self.frozen, self.frozen.viewport(), frozen_header, frozen_header.viewport()):
            notNone(widget).setAutoFillBackground(True)

        for column in range(self.frozen_columns):
            self.horizontal_header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        frozen_scroll_bar, scroll_bar = notNone(self.frozen.verticalScrollBar()), notNone(self.verticalScrollBar())
        frozen_scroll_bar.valueChanged.connect(scroll_bar.setValue)
        scroll_bar.valueChanged.connect(frozen_scroll_bar.setValue)
        self.horizontal_header.sectionResized.connect(self.frozenSectionResized)
        self.horizontal_header.geometriesChanged.connect(self.updateFrozenGeometry)

        notNone(self.viewport()).stackUnder(self.frozen)
        self.updateFrozenGeometry()
        self.frozen.show()

    def frozenSectionResized(self, column: int, _old_size: int, new_size: int):
        """Keeps the widths of the frozen columns equal to the ones of this table"""

        if self.frozen is None or column >= self.frozen_columns:
            return
        self.frozen.setColumnWidth(column, new_size)
        self.updateFrozenGeometry()

    def updateFrozenGeometry(self):
        """Places the table of the frozen columns on top of the first columns"""

        if self.frozen is None:
            return
        width = sum(self.columnWidth(column) for column in range(self.frozen_columns))
        header_height = self.horizontal_header.height()
        notNone(self.frozen.horizontalHeader()).setFixedHeight(header_height)
        self.frozen.setGeometry(
            self.frameWidth(),
            self.frameWidth(),
            width,
            notNone(self.viewport()).height() + header_height
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updateFrozenGeometry()

    def insertRow(self, row: int):
        super().insertRow(row)
        if self.frozen is not None:
            self.frozen.insertRow(row)

    def removeRow(self, row: int):
        super().removeRow(row)
        if self.frozen is not None:
            self.frozen.removeRow(row)

    def setCellWidget(self, row: int, column: int, widget: Optional[QWidget]):
        if self.frozen is not None and column < self.frozen_columns:
            self.frozen.setCellWidget(row, column, widget)
        else:
            super().setCellWidget(row, column, widget)

    def cellWidget(self, row: int, column: int) -> Optional[QWidget]:
        if self.frozen is not None and column < self.frozen_columns:
            return self.frozen.cellWidget(row, column)
        return super().cellWidget(row, column)

    def setSpan(self, row: int, column: int, row_span: int, column_span: int):
        super().setSpan(row, column, row_span, column_span)
        if self.frozen is not None and column < self.frozen_columns:
            span = min(column_span, self.frozen_columns - column)
            if row_span > 1 or span > 1:
                self.frozen.setSpan(row, column, row_span, span)

    def setHeaderToolTip(self, column: int, tooltip: str):
        """
        Sets the tooltip of the header of a column

        :param column: index of column
        :param tooltip: tooltip
        """

        notNone(self.horizontalHeaderItem(column)).setToolTip(tooltip)
        if self.frozen is not None and column < self.frozen_columns:
            notNone(self.frozen.horizontalHeaderItem(column)).setToolTip(tooltip)

    def createAddButton(self):
        """Creates add button"""

        self.insertRow(0)
        self.setCellWidget(0, 0, self.add_button)
        self.setSpan(0, 0, 1, len(self.header_labels))

    def createRow(self, row_idx: int) -> RowT:
        """
        Create row with index

        :param row_idx: index of row
        """

        raise NotImplementedError('Must override createRow()')

    def addRow(self, update: bool = True, connect: bool = True) -> Optional[RowT]:
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

        if self.frozen is not None:
            # the frozen columns get the size of their content in the frozen table, rows the larger height of both
            self.frozen.resizeColumnsToContents()
            self.frozen.resizeRowsToContents()
            header = self.horizontal_header
            for column in range(1, self.frozen_columns):
                width = max(self.frozen.columnWidth(column), header.sectionSizeHint(column))
                self.setColumnWidth(column, width)
            for row in range(self.rowCount()):
                height = max(self.rowHeight(row), self.frozen.rowHeight(row))
                self.setRowHeight(row, height)
                self.frozen.setRowHeight(row, height)

        # first column needs to be resized as well
        if self.rowCount() > 1:
            first_width = notNone(self.cellWidget(0, 0)).sizeHint().width()
            self.setColumnWidth(0, first_width)
        self.updateFrozenGeometry()

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

    def emit(self, value_dict: Optional[dict] = None):
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
