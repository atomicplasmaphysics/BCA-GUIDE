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
from string import ascii_lowercase

from PyQt5.QtCore import pyqtSignal, Qt, QSize, QEvent
from PyQt5.QtWidgets import (
    QDialog, QGridLayout, QLabel, QTableWidget, QListWidget, QAbstractItemView,
    QHBoxLayout, QVBoxLayout, QListWidgetItem
)

from GlobalConf import GlobalConf
from Styles import Styles

from Containers.Element import Element, Elements


class HoverLabel(QLabel):
    """
    QLabel with signals attached to hover over

    :param parent: parent widget
    """

    mouseEnter = pyqtSignal(Element)
    mouseLeave = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)
        self.element = None

    def enterEvent(self, event):
        """
        Mouse over

        :param event: enter event
        """

        self.mouseEnter.emit(self.element)

    def leaveEvent(self, event):
        """
        Mouse out

        :param event: leave event
        """

        self.mouseLeave.emit()


class ElementWidget(HoverLabel):
    """
    QLabel for one element

    :param parent: parent widget
    :param element: element class
    :param element_data: all elements; used to get isotopes
    """

    mouseRelease = pyqtSignal(Element)
    widgetSize = 35

    sColor = (0, 0, 255, 75)
    pColor = (0, 255, 0, 75)
    dColor = (255, 255, 0, 75)
    fColor = (255, 0, 0, 75)

    def __init__(self, parent, element, element_data):
        super().__init__(parent)
        self.element = element
        self.setText(self.element.periodic_table_symbol)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(int(ElementWidget.widgetSize), int(ElementWidget.widgetSize))

        # Color the element according to its position in the periodic table
        self.setAutoFillBackground(True)
        self.color = ElementWidget.sColor
        if self.element.period > 7 or (self.element.period in [6, 7] and self.element.group == 3):
            self.color = ElementWidget.fColor
        elif self.element.period > 1 and self.element.group > 12:
            self.color = ElementWidget.pColor
        elif self.element.period > 3 and self.element.group in range(3, 13):
            self.color = ElementWidget.dColor
        self.style_sheet = f'background-color: {self.tupleToColor(self.color)};'

        # Underline the element's symbol if it has multiple isotopes to choose from
        self.isotopes = element_data.getIsotopes(element.atomic_nr)
        if len(self.isotopes) > 1:
            self.style_sheet += 'text-decoration: underline;'

        self.default_style = self.style_sheet
        self.setStyleSheet(self.style_sheet)

    @staticmethod
    def tupleToColor(color: tuple) -> str:
        """
        Converts a tuple to a rgba color

        :param color: tupe of (r, g, b, a)
        """

        if len(color) != 4:
            return 'rgba(100, 100, 100, 75)'

        return f'rgba({color[0]}, {color[1]}, {color[2]}, {color[3]})'

    def mouseReleaseEvent(self, event):
        """
        Mouse click release

        :param event: mouse release event
        """

        self.mouseRelease.emit(self.element)

    def borderForSelectedElement(self, border_color: str = None):
        """
        Set border with color to element. If border_color is None, remove border

        :param border_color: color of border
        """

        if border_color is None:
            self.setStyleSheet(self.default_style)
        else:
            self.default_style = self.style_sheet
            self.setStyleSheet(self.style_sheet + f'border: 2px inset {border_color};')

    def greyOutSelectedElement(self, greyed: bool = False):
        """
        Grey out element

        :param greyed: True:  will be greyed out
                       False: will not be greyed out
        """

        if not greyed:
            self.setStyleSheet(self.default_style)
        else:
            self.default_style = self.style_sheet


class IsotopeWidget(HoverLabel):
    """
    QLabel for one isotope

     :param parent: parent widget
    :param element: element class
    """

    isotopeChosen = pyqtSignal(Element)

    def __init__(self, parent, element):
        super().__init__(parent)
        self.element = element
        self.setFixedHeight(30)
        self.setMaximumWidth(parent.width())
        self.setText(f'{self.element.symbol} ({format(self.element, GlobalConf.language)})')

    def mouseDoubleClickEvent(self, event):
        """
        On double click

        :param event: double click event
        """

        self.isotopeChosen.emit(self.element)


class PeriodicTableDialog(QDialog):
    """
    QDialog with periodic table

    :param parent: parent widget
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.element_data = None
        self.disallowed_elements = []
        self.disallowed_element_widgets = []
        self.search_text = ''
        self.search_results = []
        self.isotope = None
        self.last_selected_element = None
        self.previous_chosen_element = None
        self.existing_elements_symbols = []

        self.search_text_placeholder = 'Type to search'

        self.row_count = 9
        self.column_count = 18
        self.isotope_list_width = 250

        # Set up window properties
        self.setFocusPolicy(Qt.ClickFocus)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setWindowTitle('Select an element')

        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(10)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)

        self.setLayout(self.grid_layout)

        self.cancel_hbox = QHBoxLayout()
        self.element_info = QLabel(self)
        self.cancel_hbox.addWidget(self.element_info)
        self.cancel_hbox.addStretch(1)
        self.cancel_hbox.addWidget(QLabel('[ESC]: Cancel', self))
        self.grid_layout.addLayout(self.cancel_hbox, 0, 0)

        self.element_widgets: List[ElementWidget] = []

        self.periodic_table_hbox = QHBoxLayout()
        # Create an empty periodic table
        self.table = QTableWidget(self.row_count, self.column_count, self)
        for r in range(self.row_count):
            for c in range(self.column_count):
                if r == 0 and c == 3:
                    self.search_label = QLabel(self)
                    self.table.setCellWidget(r, c, self.search_label)
                    self.table.setSpan(r, c, 2, 8)
                else:
                    self.table.setCellWidget(r, c, QLabel())

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.horizontalHeader().hide()
        self.table.verticalHeader().hide()
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.horizontalHeader().setMinimumSectionSize(int(ElementWidget.widgetSize))
        self.table.verticalHeader().setMinimumSectionSize(int(ElementWidget.widgetSize))
        self.table.setShowGrid(False)
        self.table.installEventFilter(self)
        self.periodic_table_hbox.addWidget(self.table)

        self.isotopes_vbox = QVBoxLayout()
        self.isotopes_vbox.setSpacing(0)
        self.title_isotopes_hbox = QHBoxLayout()
        self.title_isotopes = QLabel('Isotope list', self)
        self.title_isotopes.setStyleSheet(Styles.title_style)
        self.title_isotopes.setMaximumHeight(20)
        self.isotopeTitleHeight = self.title_isotopes.height()
        self.title_isotopes_hbox.addWidget(self.title_isotopes)
        self.isotopes_vbox.addLayout(self.title_isotopes_hbox)
        self.isotope_list = QListWidget(self)
        self.isotope_list.setMaximumWidth(self.isotope_list_width)
        self.isotope_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.isotope_list.installEventFilter(self)
        self.isotopes_vbox.addWidget(self.isotope_list)
        self.periodic_table_hbox.addLayout(self.isotopes_vbox)

        self.grid_layout.addLayout(self.periodic_table_hbox, 1, 0)

        self.hints_hbox = QHBoxLayout()
        self.hint_label = QLabel('Click an element to select it. Type to search elements and press [Return] to select the first search result. Elements with multiple isotopes are underlined.', self)
        self.hint_label.setWordWrap(True)
        self.hints_hbox.addWidget(self.hint_label)
        self.isotope_hint_label = QLabel('Double click or press [Return] to choose an isotope from the list.', self)
        self.isotope_hint_label.setWordWrap(True)
        self.isotope_hint_label.setMaximumWidth(self.isotope_list_width)
        self.isotope_hint_label.setAlignment(Qt.AlignRight)
        self.hints_hbox.addWidget(self.isotope_hint_label)
        self.grid_layout.addLayout(self.hints_hbox, 2, 0)

        self.no_data_hbox = QHBoxLayout()
        self.hint_simulation_data = QLabel('Warning: The simulation does not provide any element data. Elements and element specific data references default values of this GUI.', self)
        self.hint_simulation_data.setStyleSheet(f'color: {Styles.red_hex};')
        self.hint_simulation_data.setWordWrap(True)
        self.no_data_hbox.addWidget(self.hint_simulation_data)
        self.grid_layout.addLayout(self.no_data_hbox, 3, 0)

    def openDialog(self, element: Element, existing_elements: List[Element] = None):
        """
        Open QDialog

        :param element: selected element
        :param existing_elements: (optional) list of already existing elements (should be greyed out)
        """

        super().open()
        if existing_elements is None:
            existing_elements = []

        self.search_text = ''
        self.updateSearch()
        for widget in self.element_widgets:
            widget.setEnabled(True)

        self.isotope_list.clear()
        self.previous_chosen_element = None

        if element is not None and element.symbol:
            for element_widget in self.element_widgets:
                if element_widget.element.atomic_nr != element.atomic_nr:
                    continue

                self.previous_chosen_element = element_widget
                if len(self.previous_chosen_element.isotopes) > 1:
                    for i in range(self.isotope_list.count()):
                        if self.isotope_list.itemWidget(self.isotope_list.item(i)).element.symbol == element.symbol:
                            self.isotope_list.setCurrentRow(i)
                            break
                break

        self.existing_elements_symbols = [existing_element.symbol for existing_element in existing_elements]
        disallowed_element_widgets = []
        for existing_element in existing_elements:
            existing_element_atomic_nr = existing_element.atomic_nr
            for element_widget in self.element_widgets:
                if element_widget.element.atomic_nr != existing_element_atomic_nr:
                    continue

                if len(element_widget.isotopes) == 1:
                    disallowed_element_widgets.append(element_widget)
                    break

                if all(isotope_symbol in self.existing_elements_symbols for isotope_symbol in [isotope.symbol for isotope in element_widget.isotopes]):
                    disallowed_element_widgets.append(element_widget)
                    break

        self.setDisallowedElements(self.existing_elements_symbols, disallowed_element_widgets)

        self.last_selected_element = None
        self.chosenElementHighlight(deselect_all=True)

    def setElementData(self, element_data: Elements, default_data: bool = False):
        """
        Sets its own contents to specified elements of simulation

        :param element_data: element data
        :param default_data: (optional) if default data is used -> show warning
        """

        self.last_selected_element = None
        self.previous_chosen_element = None
        self.element_widgets = []
        self.element_data = element_data

        self.hint_simulation_data.setHidden(not default_data)

        f_block_counter = 1
        for atomic_nr in range(1, 104):
            element = self.element_data.elementFromNr(atomic_nr)

            # no element present
            if element is None:
                continue

            row = element.period - 1
            if element.group is not None:
                column = element.group - 1
            else:
                if row == 6 and f_block_counter == 15:
                    f_block_counter = 1
                row += 2
                column = f_block_counter + 2
                f_block_counter += 1

            widget = ElementWidget(self, element, self.element_data)
            self.table.setCellWidget(row, column, widget)
            self.element_widgets.append(widget)

        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()
        width = self.table.horizontalHeader().length() + 2  # to fit content exactly
        height = self.table.verticalHeader().length() + 2
        self.table.setFixedSize(width, height)
        self.isotope_list.setMaximumHeight(height - self.isotopeTitleHeight)

        # table width + isotope list width + 2 * 10 (content margin) + 1 * 10 (spacing)
        width = self.table.width() + self.isotope_list_width + 30
        # table height + 2 * (label height) + 2 * 10 (content margin) + 3 * 10 (spacing)
        height = self.table.height() + self.hint_label.height() + self.element_info.height() + 50
        self.setFixedSize(width, height)

        for widget in self.element_widgets:
            widget.mouseEnter.connect(lambda e: self.element_info.setText(e.getInfo(GlobalConf.language)))
            widget.mouseLeave.connect(lambda: self.element_info.clear())
            widget.mouseRelease.connect(lambda _, w=widget: self.setChosenElement(w))

    def setChosenElement(self, element_widget: ElementWidget = None):
        """
        Sets element to chosen element

        :param element_widget: chosen element widget
        """

        self.isotope_list.clear()
        if element_widget is None:
            return

        if self.last_selected_element is not None:
            self.last_selected_element.borderForSelectedElement(None)
        self.last_selected_element = element_widget
        element_widget.borderForSelectedElement('#808080')

        element = element_widget.element
        isotopes = self.element_data.getIsotopes(element.atomic_nr)

        if len(isotopes) == 1:
            self.dialogFinished(element)
            return

        for element in isotopes:
            item = QListWidgetItem()
            self.isotope_list.addItem(item)
            widget = IsotopeWidget(self.isotope_list, element)
            widget.isotopeChosen.connect(self.dialogFinished)
            widget.mouseEnter.connect(lambda e: self.element_info.setText(e.getInfo(GlobalConf.language)))
            widget.mouseLeave.connect(lambda: self.element_info.clear())
            if element.symbol in self.disallowed_elements:
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                widget.setEnabled(False)
            else:
                item.setFlags(item.flags() | Qt.ItemIsSelectable)
                widget.setEnabled(True)
            item.setSizeHint(QSize(0, widget.height()))
            self.isotope_list.setItemWidget(item, widget)
        self.isotope_list.setFocus()
        self.isotope_list.setCurrentRow(0)

    def chosenElementHighlight(self, deselect_all=False):
        """
        Highlight chosen element widget

        :param deselect_all: if all should be deselected
        """

        if deselect_all:
            for element_widget_deselect in self.element_widgets:
                element_widget_deselect.borderForSelectedElement(None)
        if self.previous_chosen_element is not None:
            self.previous_chosen_element.borderForSelectedElement('#006699')

    def keyPress(self, event):
        """
        Detect keypress to start search of element

        :param event: keypress event
        """

        super().keyPressEvent(event)
        if event.isAutoRepeat() or self.element_data is None:
            return

        # Search in periodic element table
        search_text_previous = self.search_text
        search = str.lower(event.text())
        if search in ascii_lowercase:
            if len(self.search_text) < 7:
                self.search_text += search
        elif event.key() == Qt.Key_Backspace:
            self.search_text = self.search_text[:-1]
        elif event.key() in [Qt.Key_Return, Qt.Key_Enter]:
            if self.isotope_list.count():
                selected_items = self.isotope_list.selectedItems()
                if len(selected_items):
                    selected_element = self.isotope_list.itemWidget(selected_items[0]).element
                    self.dialogFinished(selected_element)
            if self.isSearching():
                for widget in self.element_widgets:
                    if not widget.isEnabled():
                        continue
                    if widget.element.atomic_nr in [search_result.atomic_nr for search_result in self.search_results]:
                        self.setChosenElement(widget)
                        break

        if not self.search_text:
            self.element_info.clear()

        if search_text_previous != self.search_text:
            self.updateSearch()

    def isSearching(self):
        """Check if a search text is present"""

        return True if self.search_text else False

    def updateSearch(self):
        """Updates search results"""

        self.isotope_list.clear()
        self.chosenElementHighlight()
        self.updateSearchPeriodicElements()
        if self.isSearching():
            self.highlightFirstAvailableElement()
        self.updateSearchIsotopes()

        if not self.isSearching() and self.last_selected_element is not None:
            self.last_selected_element.borderForSelectedElement(None)
            self.chosenElementHighlight()

    def updateSearchPeriodicElements(self):
        """Updates search results in periodic table of elements"""

        if self.isSearching():
            self.search_label.setText(self.search_text)
            self.search_label.setStyleSheet(Styles.search_style)
            self.search_results = self.element_data.elementsMatching(self.search_text)
        else:
            self.search_label.setText(self.search_text_placeholder)
            self.search_label.setStyleSheet(Styles.search_style_placeholder)
        self.updateAllowedElements()

    def updateSearchIsotopes(self):
        """Updates search results in isotopes list"""

        selected = False
        for i in range(self.isotope_list.count()):
            list_item = self.isotope_list.item(i)
            isotope = self.isotope_list.itemWidget(list_item)
            list_item.setFlags(list_item.flags() | Qt.ItemIsSelectable)
            isotope.setEnabled(True)
            if self.search_text not in isotope.text().lower() or isotope.element.symbol in self.disallowed_elements:
                isotope.setEnabled(False)
                list_item.setFlags(list_item.flags() & ~Qt.ItemIsSelectable)
            elif not selected:
                list_item.setSelected(True)
                selected = True

    def updateAllowedElements(self):
        """Update allowed elements for search"""

        for widget in self.element_widgets:
            widget.setEnabled(True)
            if self.isSearching() and widget.element.atomic_nr not in [search_result.atomic_nr for search_result in self.search_results]:
                widget.setEnabled(False)
                continue
            # disable used elements without multiple isotopes
            if len(self.element_data.getIsotopes(widget.element.atomic_nr)) == 1 and widget.element.symbol in self.disallowed_elements:
                widget.setEnabled(False)
                continue
            # disable elements where all isotopes are used
            if widget in self.disallowed_element_widgets:
                widget.setEnabled(False)
                continue

    def highlightFirstAvailableElement(self):
        """Highlight first available element"""

        self.isotope_list.clear()
        if self.last_selected_element is not None:
            self.last_selected_element.borderForSelectedElement(None)
        for widget in self.element_widgets:
            if widget.isEnabled():
                widget.borderForSelectedElement('#808080')
                widget.enterEvent(None)
                self.last_selected_element = widget
                if len(self.element_data.getIsotopes(widget.element.atomic_nr)) > 1:
                    self.setChosenElement(widget)
                break

    def setDisallowedElements(self, element_symbols: List[str], element_widgets: List[ElementWidget]):
        """
        Disallow element symbols and widgets

        :param element_symbols: list of disallowed elements
        :param element_widgets: list of disallowed element widgets
        """

        self.disallowed_elements = element_symbols
        self.disallowed_element_widgets = element_widgets

        for element_widget in self.disallowed_element_widgets:
            element_widget.setDisabled(True)

    def eventFilter(self, obj, event):
        """
        Filters events to obtain key presses

        :param obj: ?
        :param event: event
        """

        res = super().eventFilter(obj, event)

        if event.type() == QEvent.KeyPress:
            self.keyPress(event)
        
        return res

    def dialogFinished(self, element):
        """
        Finish dialog window and set isotope to element

        :param element: selected element
        """

        self.isotope = element
        for element_widget in self.element_widgets:
            if element_widget.element.atomic_nr != element.atomic_nr:
                continue
            self.previous_chosen_element = element_widget
            break
        self.done(QDialog.Accepted)
