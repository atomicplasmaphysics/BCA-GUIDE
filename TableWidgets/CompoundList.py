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


from typing import List, Tuple


from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QWidget, QLabel, QCheckBox, QHBoxLayout


from Containers.Compound import Compound
from Containers.Element import Element

from TableWidgets.CompTable import CompTable


class ListItemWidget(QWidget):
    """
    QWidget acting as list widget with checkbox and label for compound

    :param parent: parent widget
    :param compound: <Compound> container
    """

    def __init__(self, parent, compound: Compound):
        super().__init__(parent)

        self.compound = compound

        # layout for checkbox and label
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(7, 3, 7, 3)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(False)

        self.label = QLabel(compound.name)
        # transparent background color needs to be added for proper display
        self.label.setStyleSheet('background-color: transparent;')

        self.layout.addWidget(self.checkbox)
        self.layout.addWidget(self.label)
        self.setLayout(self.layout)


class CompoundList(QListWidget):
    """
    QListWidget to display possible compounds

    :param parent: parent widget
    :param compounds: list of <Compound> containers that are available
    :param table_beam: CompTable for beam
    :param table_target: CompTable for target
    """

    compoundChanged = pyqtSignal(Compound, bool)

    def __init__(self, parent, compounds: List[Compound], table_beam: CompTable, table_target: CompTable):
        super().__init__(parent)

        self.compounds = compounds
        self.available_elements: List[Element] = []
        self.table_beam = table_beam
        self.table_target = table_target

        # list widgets for all compounds
        for compound in self.compounds:
            item = QListWidgetItem()
            item.setFlags(Qt.ItemFlag.NoItemFlags)

            item_widget = ListItemWidget(parent, compound)
            item_widget.setDisabled(True)
            item_widget.checkbox.toggled.connect(lambda state, compound_copy=compound: self.toggleCompound(compound_copy, state))

            item.setSizeHint(item_widget.sizeHint())
            self.addItem(item)
            self.setItemWidget(item, item_widget)

    def itemWidget(self, item: QListWidgetItem) -> ListItemWidget:
        """Call is passed to original itemWidget() function, but the return type should be ListItemWidget"""
        item_widget = super().itemWidget(item)
        if isinstance(item_widget, ListItemWidget):
            return item_widget

    def disableItem(self, compound: Compound, disable: bool):
        """
        Disables/Enables item which matches the compound

        :param compound: compound which should be disabled of enabled
        :param disable: if compound should be disabled or enabled
        """

        for index in range(self.count()):
            item_widget = self.itemWidget(self.item(index))
            if item_widget.compound == compound:
                item_widget.setDisabled(disable)
                return

    def toggleCompound(self, compound: Compound, state: bool):
        """
        Called if state of compound is changed

        :param compound: changed compound
        :param state: state of compound
        """

        self.selectedToTop()
        self.compoundChanged.emit(compound, state)

    def updateElements(self, elements: List[Element] = None):
        """
        Updates selectable items and deselects not valid options

        :param elements: list of available <Element> containers
        """

        if not elements:
            elements = self.available_elements
        else:
            self.available_elements = elements

        possible_items = []
        uncheck_checkboxes = []

        # enable and disable compounds
        for index in range(self.count()):
            item = self.item(index)
            item_widget = self.itemWidget(item)
            state = item_widget.compound.matches(elements)
            item_widget.setDisabled(not state)

            if not state:
                uncheck_checkboxes.append(item_widget.checkbox)
            else:
                possible_items.append((index, item, item_widget))

        # move available compounds to top
        self.moveItems(possible_items)

        # uncheck checkboxes
        for checkbox in uncheck_checkboxes:
            checkbox.setChecked(False)

        # move selected compounds to top
        self.selectedToTop()

    def selectedToTop(self):
        """Moves selected compounds to top"""
        selected_items = []

        for index in range(self.count()):
            item = self.item(index)
            item_widget = self.itemWidget(item)
            if item_widget.checkbox.isChecked():
                selected_items.append((index, item, item_widget))

        self.moveItems(selected_items)

    def moveItems(self, items: List[Tuple[int, QListWidgetItem, ListItemWidget]]):
        """
        Moves items to top

        :param items: Items which should be moved to top. Items are a tuple of their row, ListWidgetItem and ListWidgetItem.ItemWidget
        """

        for i, (index, item, item_widget) in enumerate(items):
            new_item = QListWidgetItem()
            new_item.setFlags(Qt.ItemFlag.NoItemFlags)
            new_item.setSizeHint(item_widget.sizeHint())
            self.insertItem(i, new_item)
            self.setItemWidget(new_item, item_widget)
            self.takeItem(index + 1)

    def elementChanged(self):
        """Gets called if an element was changed"""
        self.available_elements = []

        for row in self.table_beam.rows + self.table_target.rows:
            self.available_elements.append(row.element)

        self.updateElements()

    def getCompounds(self) -> List[Compound]:
        """Returns list of selected <Compound> containers"""
        selected_compounds = []

        for index in range(self.count()):
            item_widget = self.itemWidget(self.item(index))
            if item_widget.checkbox.isChecked():
                selected_compounds.append(item_widget.compound)

        return selected_compounds

    def setCompounds(self, compounds: List[str]) -> list:
        """
        Checks given compounds if they are present

        :param compounds: list of compound names
        """

        for index in range(self.count()):
            item_widget = self.itemWidget(self.item(index))
            state = item_widget.compound.name_save in compounds
            item_widget.checkbox.setChecked(state)

        return []
