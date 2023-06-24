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


from __future__ import annotations
from typing import Union, Optional, Tuple, List, Callable
from enum import Enum, auto

from Styles import Styles

from PyQt6.QtCore import Qt, QSize, QRect
from PyQt6.QtGui import QFont, QColor, QTextFormat, QPainter, QTextCursor, QIcon, QPalette
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QWidget, QVBoxLayout, QToolBar, QBoxLayout, QPlainTextEdit,
    QTextEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem
)

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.axes import Axes

from Utility.ModifyWidget import setWidgetBackground


class InputHBoxLayout(QHBoxLayout):
    """
    Quick horizontal layout for checkbox, label and input. Extends the QHBoxLayout.

    :param label: text of label for widget
    :param widget: widget to be displayed
    :param split: (optional) percentage split between label and widget
    :param disabled: (optional) enable/disable input
    :param hidden: (optional) hide input and label
    :param checkbox: (optional) add checkbox before label. set to True/False if it should be checked on startup
    :param checkbox_connected: (optional) determines if the widget should be enabled/disabled depending on the checkbox state
    """

    def __init__(self, label: str, widget: Optional[QWidget], tooltip: str = None, split: int = 50,
                 disabled: bool = False, hidden: bool = False,
                 checkbox: bool = None, checkbox_connected: bool = True, **kwargs):
        super().__init__(**kwargs)

        self.checkbox = None
        self.default_checkbox = checkbox
        self.label = None
        self.widget = widget

        # Label without checkbox
        if not isinstance(checkbox, bool):
            if widget is None:
                label = f'<b>{label}</b>'
            self.label = QLabel(label)
            if hidden:
                self.label.hide()
            if tooltip is not None:
                self.label.setToolTip(tooltip)
            self.label.mouseReleaseEvent = lambda _: self.mark(False)

            self.addWidget(self.label, stretch=split)
            if widget is None:
                return

        # Label with checkbox
        else:
            self.checkbox = QCheckBox(label)
            self.checkbox.setChecked(checkbox)
            if checkbox_connected and widget is not None:
                self.checkbox.toggled.connect(lambda state: self.widget.setEnabled(state))
            if hidden:
                self.checkbox.hide()
            if tooltip is not None:
                self.checkbox.setToolTip(tooltip)
            self.checkbox.clicked.connect(lambda _: self.mark(False))

            self.addWidget(self.checkbox, stretch=split)
            if widget is None:
                return

        # Widget
        self.widget = widget
        if tooltip is not None:
            self.widget.setToolTip(tooltip)
        if checkbox is False or disabled:
            self.widget.setEnabled(False)
        if hidden:
            self.widget.hide()
        self.addWidget(self.widget, stretch=100 - split)

        self.widget.mouseReleaseEvent = lambda _: self.mark(False)

        if isinstance(self.widget, QSpinBox) or isinstance(self.widget, QDoubleSpinBox):
            self.widget.valueChanged.connect(lambda _: self.mark(False))

    def setEnabled(self, state: bool):
        """
        Enables widget and checkbox

        :param state: True - enable; False - disable
        """

        if self.widget is not None:
            self.widget.setEnabled(state)
        if self.checkbox is not None:
            self.checkbox.setEnabled(state)

    def setHidden(self, state: bool = True):
        """
        Hides/Shows widget

        :param state: True - hide; False - show
        """

        self.label.setHidden(state)
        if self.widget is not None:
            self.widget.setHidden(state)
        if self.checkbox is not None:
            self.checkbox.setHidden(state)

    def mark(self, enable: bool = True):
        """
        Enables/disables widget background color

        :param enable: True - show background; False - no background
        """

        if self.widget is not None:
            setWidgetBackground(self.widget, enable)

    def reset(self):
        """Resets the widget and clears mark"""
        self.mark(False)
        if hasattr(self.widget, 'reset'):
            self.widget.reset()
        if self.checkbox is not None:
            self.checkbox.setChecked(self.default_checkbox)


class SpinBoxRange:
    """
    Special input ranges for SpinBox and DoubleSpinBox
    """

    INF = 2147483647
    NEG_INF = -2147483648
    INF_INF = (NEG_INF, INF)
    ZERO_INF = (0, INF)
    ONE_INF = (1, INF)
    NEG_INF_ZERO = (NEG_INF, 0)
    NEG_ONE_INF = (-1, INF)


class SpinBox(QSpinBox):
    """
    Extension of QSpinBox.

    :param default: default value to start with and reset
    :param step_size: (optional) step size for increasing/decreasing
    :param input_range: (optional) valid input range
    :param buttons: (optional) if buttons for increasing/decreasing should be displayed
    """

    def __init__(self, default: Union[float, int] = 0, step_size: int = None, input_range: Tuple[float, float] = None,
                 scroll: bool = False, buttons: bool = False, **kwargs):
        super().__init__(**kwargs)

        self.setMinimumSize(50, 20)

        default = int(default)
        self.default = default

        if step_size is not None:
            self.setSingleStep(step_size)

        if input_range is not None:
            self.setRange(int(input_range[0]), int(input_range[1]))

        if buttons is False:
            self.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)

        if not scroll:
            self.wheelEvent = lambda event: None

        self.setValue(default)

    def reset(self):
        """Resets itself to its default value"""
        self.setValue(self.default)


class DoubleSpinBox(QDoubleSpinBox):
    """
    Extension of QDoubleSpinBox.

    :param default: default value to start with and reset
    :param step_size: (optional) step size for increasing/decreasing
    :param input_range: (optional) valid input range
    :param decimals: (optional) number of decimal places
    :param buttons: (optional) if buttons for increasing/decreasing should be displayed
    """

    def __init__(self, default: float = 0, step_size: float = None, input_range: Tuple[float, float] = None,
                 scroll: bool = False, decimals: int = None, buttons: bool = False, **kwargs):
        super().__init__(**kwargs)

        self.setMinimumSize(50, 20)

        self.default = default
        self.decimals_min = 2

        if step_size is not None:
            self.setSingleStep(step_size)

        if input_range is not None:
            self.setRange(input_range[0], input_range[1])

        if decimals is not None:
            self.setDecimals(decimals)

        if buttons is False:
            self.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)

        if not scroll:
            self.wheelEvent = lambda event: None

        self.setValue(default)

    def reset(self):
        """Resets itself to its default value"""
        self.setValue(self.default)

    def textFromValue(self, value: float) -> str:
        """Removes unnecessary long tailing zeros in input field"""
        decimals_total = decimals = self.decimals()
        value_str = f'{value:.{decimals_total}f}'
        for char in value_str[::-1]:
            if char != '0':
                break
            decimals -= 1
        decimals = max(decimals, self.decimals_min)
        decimals_remove = decimals_total - decimals
        value_formatted_str = super().textFromValue(value)
        if decimals_remove:
            value_formatted_str = value_formatted_str[:-decimals_remove]
        return value_formatted_str


class LineEdit(QLineEdit):
    """
    Extension of QLineEdit

    :param default: default value to start with and reset
    :param placeholder: (optional) placeholder text
    :param max_length: (optional) maximum input length
    """

    def __init__(self, default: str = '', placeholder: str = None, max_length: int = None, **kwargs):
        super().__init__(**kwargs)

        self.default = default
        self.setText(default)

        if placeholder is not None:
            self.setPlaceholderText(placeholder)

        if max_length is not None:
            self.setMaxLength(max_length)

    def reset(self):
        """Resets itself to its default value"""
        self.setText(self.default)


class PasswordLineEdit(QLineEdit):
    """
    Extension of QLineEdit

    :param placeholder: (optional) placeholder text
    """

    def __init__(self, placeholder: str = None, **kwargs):
        super().__init__(**kwargs)
        self.setEchoMode(QLineEdit.EchoMode.Password)

        if placeholder is not None:
            self.setPlaceholderText(placeholder)

    def reset(self):
        """Resets itself to empty password"""
        self.setText('')


class ComboBox(QComboBox):
    """
    Extension of QComboBox

    :param default: default selected element
    :param entries: list of possible choices
    :param tooltips: (optional) list of tooltips when hovered over one choice
    :param entries_save: (optional) list of entries for saving
    :param numbering: (optional) numbers entries (starting from this index)
    :param label_default: (optional) labels the default selected
    :param disabled_list: (optional) enable/disable choices
    """

    def __init__(self, default: int = 0, entries: List[str] = None, tooltips: List[str] = None,
                 entries_save: list = None, numbering: int = None, label_default: bool = False,
                 disabled_list: List[int] = None, scroll: bool = False, **kwargs):
        super().__init__(**kwargs)

        self.default = default
        self.entries_save = entries_save

        if entries is None:
            entries = []
        self.entries = entries

        if numbering is not None:
            if default:
                self.default -= numbering
            entries = [f'{i + numbering}: {entry}' for i, entry in enumerate(entries)]

        if label_default:
            entries[self.default] = f'{entries[self.default]} (default)'

        self.addItems(entries)
        self.setCurrentIndex(self.default)

        if tooltips is not None and len(tooltips) == len(entries):
            for i, tip in enumerate(tooltips):
                self.setItemData(i, tip, Qt.ItemDataRole.ToolTipRole)

        if disabled_list is not None:
            for i in disabled_list:
                self.model().item(i, 0).setEnabled(False)

        if not scroll:
            self.wheelEvent = lambda event: None

    def reset(self):
        """Resets itself to its default value"""
        self.setCurrentIndex(self.default)

    def getValue(self, text: bool = False, save: bool = False):
        """
        Returns value of widget

        :param text: return text of selected choice
        :param save: return save element of selected choice
        """

        current_index = self.currentIndex()
        if text:
            return self.entries[current_index]
        if save and self.entries_save is not None:
            return self.entries_save[current_index]
        return current_index

    def setValue(self, value, from_entries_save: bool = False):
        """
        Sets value of widget

        :param value: value to be set
        :param from_entries_save: value is element of entries_save list
        """

        if from_entries_save:
            value = self.entries_save.index(value)
        return self.setCurrentIndex(value)

    def getDefaultSave(self):
        """Returns default from entry_save"""
        if self.default in range(len(self.entries_save)):
            return self.entries_save[self.default]
        return None

    def updateDisabledList(self, disabled_list: List[int] = None):
        """
        Update the disabled list

        :param disabled_list: new disabled list
        """

        if disabled_list is None:
            disabled_list = []

        for i in range(len(self.entries)):
            enable = True
            if i in disabled_list:
                enable = False
            self.model().item(i, 0).setEnabled(enable)


class FilePath(QWidget):
    """
    Extension of QLineEdit for selecting and displaying a file path local and remote

    :param placeholder: (optional) placeholder text
    :param function_loc: (optional) function that will be called when local button is pressed.
                                    Return value of the function will be displayed.
    :param icon_loc: (optional) icon of pushbutton for local file
    :param function_ssh: (optional) function that will be called when ssh button is pressed.
                                    Return value of the function will be displayed.
    :param icon_ssh: (optional) icon of pushbutton for ssh file
    """

    def __init__(self, placeholder: str = None, function_loc: Callable = None, icon_loc: QIcon = None,
                 function_ssh: Callable = None, icon_ssh: QIcon = None, **kwargs):
        super().__init__(**kwargs)

        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

        self.path = ''
        self.ssh = False

        self.path_display = QLineEdit()
        if placeholder is not None:
            self.path_display.setPlaceholderText(placeholder)
        self.path_display.setReadOnly(True)
        self.path_display.setMinimumWidth(300)
        self.layout.addWidget(self.path_display, Qt.AlignmentFlag.AlignLeft)

        self.function_loc = function_loc
        self.button_loc = QPushButton()
        if self.function_loc is not None:
            if icon_loc is None:
                self.button_loc.setText('...')
            else:
                self.button_loc.setIcon(icon_loc)
            self.button_loc.setMinimumSize(40, 10)
            self.button_loc.setMaximumSize(40, 30)
            self.layout.addWidget(self.button_loc, Qt.AlignmentFlag.AlignRight)

            self.button_loc.clicked.connect(self.select_path_loc)

        self.function_ssh = function_ssh
        self.button_ssh = QPushButton()
        if self.function_ssh is not None:
            if icon_loc is None:
                self.button_ssh.setText('...')
            else:
                self.button_ssh.setIcon(icon_ssh)
            self.button_ssh.setMinimumSize(40, 10)
            self.button_ssh.setMaximumSize(40, 30)
            self.layout.addWidget(self.button_ssh, Qt.AlignmentFlag.AlignRight)

            self.button_ssh.clicked.connect(self.select_path_ssh)

    def setPath(self, path: str, ssh: bool = False):
        """Sets a path and whether it is ssh"""
        self.path = path
        self.ssh = ssh
        self.displayPath()

    def displayPath(self):
        """Displays the path in QLineEdit"""
        if not self.path:
            self.path_display.setText('')
            return

        if self.function_ssh is None:
            self.path_display.setText(self.path)
        else:
            prefix = 'ssh' if self.ssh else 'local'
            self.path_display.setText(f'{prefix}: {self.path}')

    def setToolTip(self, tooltip: str):
        """Sets a tooltip"""
        super().setToolTip(tooltip)
        if self.function_ssh is not None:
            self.button_loc.setToolTip('<i>Local directory</i>\n' + tooltip)
            self.button_ssh.setToolTip('<i>SSH directory</i>\n' + tooltip)

    def select_path_loc(self):
        """Sets a new local path"""
        path = self.function_loc()
        if path is not None:
            self.path = path
            self.ssh = False
            self.displayPath()

    def select_path_ssh(self):
        """Sets a new ssh path"""
        path = self.function_ssh()
        if path is not None:
            self.path = path
            self.ssh = True
            self.displayPath()


# TODO: remove InputHLayout if no longer needed
class InputHLayout(QHBoxLayout):
    """
    WARNING: deprecated, use InputHBoxLayout instead

    Quick Layout for Label and Input

    :param parent: parent widget
    :param label: displayed title of widget
    :param input_type: type of supported inputs
    :param default_value: value assigned by default / placeholder for LINEEDIT and FILEPATH,
                          for COMBOBOX (default_value - numbering) is the default selected index
    :param input_range: (optional) valid input range (only used for SPINBOX or DOUBLESPINBOX)
    :param input_length: (optional) max input length (only used for LINEEDIT)
    :param tooltip: (optional) tooltip when hovered over
    :param tooltips: (optional) list of tooltips when hovered over one choice (only used for COMBOBOX)
    :param default_text: (optional) string of text in LINEEDIT
    :param split: (optional) percentage split between Label and Input
    :param decimals: (optional) decimals digits used for DOUBLESPINBOX
    :param step_size: (optional) step_size used for SPINBOX and DOUBLESPINBOX
    :param entries: (optional) possible choices (only used for COMBOBOX)
    :param entries_save: (optional) save value for possible choices (only used for COMBOBOX)
    :param numbering: (optional) integer - numbers entries (starting from this index) and labels the default selected
    :param checkbox: (optional) add checkbox before label. set to True/False if it should be checked on startup
    :param disabled: (optional) enable/disable input
    :param disabled_list: (optional) enable/disable choices (only used for COMBOBOX)
    :param hidden: (optional) hide input and label
    """

    class InputRange:
        """
        Special input ranges
        """

        INF = 2147483647
        NEG_INF = -2147483648
        INF_INF = (NEG_INF, INF)
        ZERO_INF = (0, INF)
        ONE_INF = (1, INF)
        NEG_INF_ZERO = (NEG_INF, 0)
        NEG_ONE_INF = (-1, INF)

    class InputType(Enum):
        """
        Types of supported Inputs
        """

        SPINBOX = auto()
        COMBOBOX = auto()
        LINEEDIT = auto()
        DOUBLESPINBOX = auto()
        FILEPATH = auto()
        LABEL = auto()

    def __init__(self, parent, label, input_type, default_value, input_range=(0, 1e8), input_length=100,
                 tooltip='', tooltips=None, default_text='', split=50, decimals=2, step_size=1, entries=None, entries_save=None,
                 numbering=None, checkbox=None, disabled=False, disabled_list=None, hidden=False):
        if tooltips is None:
            tooltips = []
        if entries is None:
            entries = []
        if disabled_list is None:
            disabled_list = []

        super().__init__()
        assert isinstance(input_type, InputHLayout.InputType)
        self.checkbox = checkbox
        self.label: Union[QLabel, QCheckBox, None] = None
        if self.checkbox is not None:
            self.label = QCheckBox(label, parent)
            self.label.clicked.connect(lambda _: self.mark(False))
        else:
            self.label = QLabel(label, parent)
            self.label.mouseReleaseEvent = lambda _: self.mark(False)
        self.addWidget(self.label, split)

        self.tooltip = tooltip
        self.input_type = input_type
        self.entries = entries
        self.entries_save = entries_save
        self.default_value = default_value
        self.numbering = numbering
        self.input: Union[QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit, QWidget, QLabel, None] = None

        # QSpinBox or QDoubleSpinBox
        if self.input_type in [InputHLayout.InputType.SPINBOX, InputHLayout.InputType.DOUBLESPINBOX]:
            if self.input_type == InputHLayout.InputType.SPINBOX:
                self.input = QSpinBox(parent)
                self.default_value = int(self.default_value)
                input_range = (int(input_range[0]), int(input_range[1]))
            else:
                self.input = QDoubleSpinBox(parent)
                self.input.setDecimals(decimals)
            self.input.setSingleStep(step_size)
            self.input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            self.input.setMinimumSize(50, 20)
            self.input.setRange(input_range[0], input_range[1])
            self.input.setValue(self.default_value)
            self.input.valueChanged.connect(lambda _: self.mark(False))

        # QComboBox
        elif self.input_type == InputHLayout.InputType.COMBOBOX:
            self.input = QComboBox(parent)

            if not isinstance(self.default_value, int):
                self.default_value = 0

            if self.numbering is not None:
                if not isinstance(self.numbering, int):
                    self.numbering = 0
                self.default_value -= self.numbering
                entries = [f'{i + self.numbering}: {entry}' for i, entry in enumerate(entries)]
                entries[self.default_value] = f'{entries[self.default_value]} (default)'

            self.input.addItems(entries)
            self.input.setCurrentIndex(self.default_value)

            if len(tooltips) == len(entries):
                for i, tip in enumerate(tooltips):
                    self.input.setItemData(i, tip, Qt.ItemDataRole.ToolTipRole)

            if len(disabled_list):
                for i in disabled_list:
                    self.input.model().item(i, 0).setEnabled(False)

        # QLineEdit
        elif self.input_type == InputHLayout.InputType.LINEEDIT:
            self.input = QLineEdit(parent)
            self.input.setPlaceholderText(str(self.default_value))
            self.input.setMaxLength(int(input_length))
            if default_text:
                self.input.setText(default_text)

        # Select File (= QLineEdit + QPushButton)
        elif self.input_type == InputHLayout.InputType.FILEPATH:
            self.input = QWidget()
            self.fileSelectLayout = QHBoxLayout()
            self.fileSelectLayout.setContentsMargins(0, 0, 0, 0)
            self.input.setLayout(self.fileSelectLayout)

            self.path = QLineEdit(parent)
            self.path.setPlaceholderText(str(self.default_value))
            self.path.setReadOnly(True)
            self.path.setMinimumWidth(300)
            self.fileSelectLayout.addWidget(self.path, Qt.AlignmentFlag.AlignLeft)

            self.fileBtn = QPushButton('...', parent)
            self.fileBtn.setMinimumSize(40, 10)
            self.fileBtn.setMaximumSize(40, 30)
            self.fileSelectLayout.addWidget(self.fileBtn, Qt.AlignmentFlag.AlignRight)

        # QLabel
        elif self.input_type == InputHLayout.InputType.LABEL:
            self.input = QLabel(f'<b>{self.default_value}</b>')

        self.addWidget(self.input, 100 - split)

        self.input.setDisabled(disabled)

        if hidden:
            self.label.hide()
            self.input.hide()

        if self.tooltip:
            self.label.setToolTip(tooltip)
            self.input.setToolTip(tooltip)

        if self.checkbox is not None:
            self.label.toggled.connect(lambda state: self.input.setEnabled(state))
            self.label.setChecked(checkbox)

        self.input.mouseReleaseEvent = lambda _: self.mark(False)

    def setDefault(self):
        """Resets to default value"""
        # QSpinBox or QDoubleSpinBox
        if self.input_type in [InputHLayout.InputType.SPINBOX, InputHLayout.InputType.DOUBLESPINBOX]:
            self.input.setValue(self.default_value)

        # QComboBox
        elif self.input_type == InputHLayout.InputType.COMBOBOX:
            self.input.setCurrentIndex(self.default_value)

    def getDefault(self, from_entries_save=False):
        """Returns to default value"""
        if not from_entries_save:
            return self.default_value
        return self.entries_save[self.default_value]

    def setEnabled(self, state: bool):
        """Enable/Disable widget"""
        if self.checkbox is None:
            self.input.setEnabled(state)
        else:
            self.label.setEnabled(state)
            self.input.setEnabled(self.label.isChecked())
        super().setEnabled(state)

    def setHidden(self, state: bool):
        """Hides/Shows widget"""
        if state:
            self.label.hide()
            self.input.hide()
            return
        self.label.show()
        self.input.show()

    def updateStepSize(self, step_size: Union[float, int]):
        """Updates the step size for DOUBLESPINBOX and SPINBOX only"""
        if self.input_type not in [InputHLayout.InputType.SPINBOX, InputHLayout.InputType.DOUBLESPINBOX]:
            return
        self.input.setSingleStep(step_size)

    def getValue(self, text=False, save=False):
        """Returns value of widget"""
        # Check if checkbox is not selected
        if self.checkbox is not None:
            if not self.label.isChecked():
                return False

        # QSpinBox or QDoubleSpinBox
        if self.input_type in [InputHLayout.InputType.SPINBOX, InputHLayout.InputType.DOUBLESPINBOX]:
            return self.input.value()

        # QComboBox
        elif self.input_type == InputHLayout.InputType.COMBOBOX:
            current_index = self.input.currentIndex()
            if text:
                return self.entries[current_index]
            if save and self.entries_save is not None:
                return self.entries_save[current_index]
            return current_index

        # QLineEdit
        elif self.input_type == InputHLayout.InputType.LINEEDIT:
            return self.input.text()

        # Select File (= QLineEdit + QPushButton)
        elif self.input_type == InputHLayout.InputType.FILEPATH:
            return self.path.text()

        # QLabel
        elif self.input_type == InputHLayout.InputType.LABEL:
            return True

    def setValue(self, value, from_entries_save=False):
        """Sets value of widget"""
        # Check if checkbox is not selected
        if self.checkbox is not None:
            if value is False:
                return self.label.setChecked(False)
            else:
                self.label.setChecked(True)

        # QSpinBox or QDoubleSpinBox
        if self.input_type in [InputHLayout.InputType.SPINBOX, InputHLayout.InputType.DOUBLESPINBOX]:
            return self.input.setValue(value)

        # QComboBox
        elif self.input_type == InputHLayout.InputType.COMBOBOX:
            if from_entries_save:
                value = self.entries_save.index(value)
            return self.input.setCurrentIndex(value)

        # QLineEdit
        elif self.input_type == InputHLayout.InputType.LINEEDIT:
            return self.input.setText(value)

        # Select File (= QLineEdit + QPushButton)
        elif self.input_type == InputHLayout.InputType.FILEPATH:
            return self.path.setText(value)

    def mark(self, enable=True):
        """Enables/disables widget background color"""
        setWidgetBackground(self.input, enable)

    def updateDisabledList(self, disabled_list: list = None):
        """Update the disabled list (only for COMBOBOX)"""
        if disabled_list is None:
            disabled_list = []

        if not self.input_type == InputHLayout.InputType.COMBOBOX:
            return

        for i in range(len(self.entries)):
            enable = True
            if i in disabled_list:
                enable = False
            self.input.model().item(i, 0).setEnabled(enable)


class TabWithToolbar(QWidget):
    """
    QWidget with toolbar
    """

    def __init__(self):
        super().__init__()
        self.super_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        self.super_layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        self.toolbar = QToolBar()
        self.toolbar.setFloatable(False)
        self.toolbar.setMovable(False)
        self.toolbar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)  # Disable the context menu of the toolbar itself
        self.toolbar.toggleViewAction().setEnabled(False)  # Disable the action in the context menus of the main window
        self.super_layout.addWidget(self.toolbar)

        # self.page as main layout
        self.page = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        self.super_layout.addLayout(self.page)
        self.setLayout(self.super_layout)


class VBoxTitleLayout(QVBoxLayout):
    """
    Class providing a QVBoxLayout with a title and style

    :param parent: parent widget
    :param title: title of top line
    :param title_style: style of title line
    :param title_style_busy: style of title line in busy mode
    :param busy_symbol: symbol when busy
    :param spacing: spacing of widgets
    :param add_stretch: if bool: addStretch(1) after title if True, else do nothing
                        if integer: addSpacing(addStretch) after title
    """

    def __init__(self, parent, title: str, title_style: str = Styles.title_style,
                 title_style_busy: str = Styles.title_style, busy_symbol: str = '⧖',
                 spacing: int = 0, add_stretch: Union[bool, int] = 0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent = parent
        self.title_str = title
        self.title_style = title_style
        self.title_style_busy = title_style_busy
        self.busy_symbol = busy_symbol

        self.setSpacing(spacing)
        self.hl = QHBoxLayout()

        self.title = QLabel(self.title_str, self.parent)
        self.title.setStyleSheet(title_style)
        self.hl.addWidget(self.title)

        if isinstance(add_stretch, bool) and add_stretch:
            self.hl.addStretch(1)
        elif isinstance(add_stretch, int):
            self.hl.addSpacing(add_stretch)

        self.addLayout(self.hl)

    def busy(self, busy: bool = True, busy_text: str = ''):
        """
        Title changes when busy

        :param busy: is busy or not
        :param busy_text: additional busy text displayed in title
        """

        if busy:
            if not busy_text:
                self.title.setText(f'{self.title_str} {self.busy_symbol}')
            else:
                self.title.setText(f'{self.title_str} {self.busy_symbol} ({busy_text})')
            self.title.setStyleSheet(self.title_style_busy)

        else:
            self.title.setText(self.title_str)
            self.title.setStyleSheet(self.title_style)


class ListWidgetItem(QListWidgetItem):
    """
    Can store a function with function arguments and execute it. Extends the functionality of QListWidgetItem.

    :param indent: (optional) indent level of item
    :param bold: (optional) set item font as bold
    :param grey: (optional) if item is greyed out
    :param selectable: (optional) if item should be selectable or greyed out
    :param tooltip: (optional) text to be displayed in tooltip
    :param function: (optional) function to be executed
    :param function_args: (optional) function arguments passed to function
    """

    def __init__(self, *args, indent: int = 0, bold: bool = False, grey: bool = False, selectable: bool = True,
                 tooltip: str = '', function: Callable = None, function_args: dict = None, **kwargs):
        if indent > 0 and args and isinstance(args[0], str):
            args = list(args)
            args[0] = '    ' * indent + args[0]
            args = tuple(args)

        super().__init__(*args, **kwargs)

        # check if function is callable
        self.function = None
        if callable(function):
            self.function = function

        if function_args is None:
            function_args = {}
        self.function_args = function_args

        # non selectable
        if not selectable or function is None:
            self.setFlags(Qt.ItemFlag.NoItemFlags)

        # if item should be greyed out
        self.grey = grey
        if grey:
            self.setForeground(QColor('#888888'))

        # bold
        if bold:
            item_font = self.font()
            item_font.setWeight(QFont.Weight.Bold)
            self.setFont(item_font)

        # tooltip for slow
        if tooltip:
            self.setToolTip(tooltip)

    def execute(self):
        """Executes the provided function with provided function arguments"""
        if self.function is not None:
            self.function(**self.function_args, text=self.text().strip())

    @staticmethod
    def convert(item: Union[QListWidgetItem, ListWidgetItem]) -> ListWidgetItem:
        """Convert into a ListWidgetItem"""
        if isinstance(item, ListWidgetItem):
            return item
        return ListWidgetItem(item.text())


class ListWidget(QListWidget):
    """
    Extends the QListWidget to accept ListWidgetItem and executes their function if item is selected
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.itemSelectionChanged.connect(self.executeFunction)
        self.font_color = self.palette().color(QPalette.ColorRole.Text)

    def executeFunction(self):
        """Executes function from ListWidgetItem if set"""
        selected_items = super().selectedItems()
        if not selected_items:
            return
        ListWidgetItem.convert(selected_items[0]).execute()

    def addItemEmpty(self):
        """Adds an empty item"""
        super().addItem(ListWidgetItem('', selectable=False))

    def addItem(self, item: ListWidgetItem):
        """Adds an item"""
        if not item.grey:
            item.setForeground(self.font_color)
        super().addItem(item)


class LineNumberArea(QWidget):
    """
    Line number area of CodeEditor

    :param editor: FileEditor
    """

    def __init__(self, editor: FileEditor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        """Returns size of line number area"""
        return QSize(self.editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        """Called when a paint event happens"""
        self.editor.lineNumberAreaPaintEvent(event)


class FileEditor(QPlainTextEdit):
    """
    QPlainTextEdit with line numbers and marks current line when clicked

    :param parent: parent widget
    :param line_numbering: (optional) if textbox should have line numbering
    :param readonly: (optional) if textbox should be readonly
    :param mono: (optional) if textbox should have mono font
    :param offset: (optional) offset for line numbers
    :param highlighting: (optional) enables highlighting of current selected line
    :param color_line_number: (optional) color of line number area
    :param color_line_number_dark: (optional) color of line number area in dark mode
    :param color_highlight: (optional) color of highlighting line
    :param color_highlight_dark: (optional) color of highlighting line in dark mode
    """

    def __init__(self, parent, line_numbering: bool = True, readonly: bool = True,
                 mono: bool = True, offset: int = 0, highlighting: bool = True,
                 color_line_number: QColor = QColor('#EEEEEE'), color_line_number_dark: QColor = QColor('#464646'),
                 color_highlight: QColor = QColor('#FFFEC8'), color_highlight_dark: QColor = QColor('#919173')):
        super().__init__(parent)
        self.line_numbering = line_numbering
        self.offset = offset

        # check color palette and decide if dark or light mode
        if self.palette().color(QPalette.ColorRole.Text).black() == 255:
            self.color_line_number = color_line_number
            self.color_highlight = color_highlight
            self.pen_color = Qt.GlobalColor.black
        else:
            self.color_line_number = color_line_number_dark
            self.color_highlight = color_highlight_dark
            self.pen_color = Qt.GlobalColor.white

        self.line_number_area = LineNumberArea(self)

        self.updateLineNumberAreaWidth()

        self.blockCountChanged.connect(lambda _: self.updateLineNumberAreaWidth())
        self.updateRequest.connect(self.updateLineNumberArea)
        if highlighting:
            self.cursorPositionChanged.connect(self.highlightCurrentLine)

        if readonly:
            self.setReadOnly(True)

        if mono:
            mono_font = QFont('Courier New')
            mono_font.setStyleHint(QFont.StyleHint.TypeWriter)
            self.setFont(mono_font)

    def updateOffset(self, offset: int):
        """Updates the offset of the line numbers"""
        self.offset = offset

    def lineNumberAreaWidth(self):
        """Returns the width of the line number area"""
        digits = len(str(self.blockCount() + self.offset))
        space = 5 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def updateLineNumberAreaWidth(self):
        """Updates width of line number area"""
        if not self.line_numbering:
            return

        self.setViewportMargins(self.lineNumberAreaWidth() + 5, 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        """Updates line number area"""
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth()

    def resizeEvent(self, event):
        """On resize"""
        super().resizeEvent(event)

        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        """Called when a paint event happens"""
        if not self.line_numbering:
            return

        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), self.color_line_number)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        # make sure to use the right font
        height = self.fontMetrics().height()
        while block.isValid() and (top <= event.rect().bottom()):
            if block.isVisible() and (bottom >= event.rect().top()):
                painter.setPen(self.pen_color)
                painter.drawText(
                    0,
                    int(top),
                    int(self.line_number_area.width()),
                    int(height),
                    Qt.AlignmentFlag.AlignRight,
                    str(block_number + 1 + self.offset)
                )

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def highlightCurrentLine(self):
        """Highlight current line"""
        selections = []

        text_cursor = self.textCursor()
        block = text_cursor.block()
        cursor_position = block.position()
        while True:
            new_text_cursor = QTextCursor(text_cursor)
            new_text_cursor.setPosition(cursor_position)
            cursor_position += 1
            if new_text_cursor.atBlockEnd():
                break

            selection = QTextEdit.ExtraSelection()
            selection.cursor = new_text_cursor
            selections.append(selection)

        for selection in selections:
            selection.format.setBackground(self.color_highlight)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)

        self.setExtraSelections(selections)


class MplCanvas(FigureCanvasQTAgg):
    """
    Canvas for matplotlib

    :param width: width of figure
    :param height: height of figure
    :param dpi: dpi for figure
    """

    def __init__(self, width: int = 4, height: int = 8, dpi: float = 100):
        self.fig: Figure = Figure(figsize=(width, height), dpi=dpi)
        self.axes: Axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
