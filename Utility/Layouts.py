from __future__ import annotations
from typing import Union, Optional, Tuple, List, Callable, Dict

from Styles import Styles

from PyQt6.QtCore import Qt, QSize, QRect
from PyQt6.QtGui import QPen, QFont, QFontMetrics, QColor, QTextFormat, QPainter, QTextCursor, QIcon, QPalette, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QWidget, QVBoxLayout, QToolBar, QBoxLayout, QPlainTextEdit,
    QTextEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QApplication
)

import numpy as np

from matplotlib import rc_context
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.axes import Axes

from Utility.ModifyWidget import setWidgetBackground
from Utility.Functions import getUniqueColor, setDictIfNotExists

from Containers.Element import Element


class SplashPixmap(QPixmap):
    """
    Class that extends the QPixmap for generating Splash Screen Images

    :param image: image path
    :param text: text string
    :param box: rectangular position for text
    :param align: alignment for text
    :param color: color for text
    :param font_size: font size for text
    """

    def __init__(
        self,
        image: str,
        text: str,
        box: QRect,
        align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignRight,
        color: Qt.GlobalColor | QColor = Qt.GlobalColor.black,
        font_size: int = 20
    ):
        super().__init__(image)

        self.painter = QPainter(self)
        self.painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.font = QApplication.font()
        self.font.setPixelSize(font_size)
        self.painter.setFont(self.font)
        self.painter.setPen(color)
        self.painter.drawText(box, align, text)
        self.painter.end()


class InputHBoxLayouts(QHBoxLayout):
    """
    Quick horizontal layout for checkbox, label and inputs. Extends the QHBoxLayout.

    :param label: text of label for widget
    :param widgets: list of widgets to be displayed
    :param tooltip: (optional) tooltip to be displayed
    :param widgets_labels: (optional) list of labels in front of widgets
    :param widgets_tooltips: (optional) tooltip to be displayed for every widget
    :param split: (optional) percentage split between label and widget
    :param disabled: (optional) enable/disable input
    :param hidden: (optional) hide input and label
    :param checkbox: (optional) add checkbox before label. set to True/False if it should be checked on startup
    :param checkbox_connected: (optional) determines if the widget should be enabled/disabled depending on the checkbox state
    """

    def __init__(
        self,
        label: str,
        widgets: Optional[List[QWidget]],
        tooltip: str = None,
        widgets_labels: Optional[List[str]] = None,
        widgets_tooltips: Optional[List[str]] = None,
        split: int = 50,
        disabled: bool = False,
        hidden: bool = False,
        checkbox: bool = None,
        checkbox_connected: bool = True,
        **kwargs
    ):
        super().__init__(**kwargs)

        self.checkbox = None
        self.default_checkbox = checkbox
        self.label = None
        self.widgets = widgets
        self.widgets_hbox = QHBoxLayout()
        self.widgets_list = []

        # Label without checkbox
        if not isinstance(checkbox, bool):
            if widgets is None or not len(widgets):
                label = f'<b>{label}</b>'
            self.label = QLabel(label)
            if hidden:
                self.label.hide()
            if tooltip is not None:
                self.label.setToolTip(tooltip)
            self.label.mouseReleaseEvent = lambda _: self.mark(False)

            self.addWidget(self.label, stretch=split)
            if widgets is None or not len(widgets):
                return

        # Label with checkbox
        else:
            self.checkbox = QCheckBox(label)
            self.checkbox.setChecked(checkbox)
            if checkbox_connected and widgets is not None and len(widgets):
                for widget in widgets:
                    self.checkbox.toggled.connect(lambda state: widget.setEnabled(state))
            if hidden:
                self.checkbox.hide()
            if tooltip is not None:
                self.checkbox.setToolTip(tooltip)
            self.checkbox.clicked.connect(lambda _: self.mark(False))

            self.addWidget(self.checkbox, stretch=split)
            if widgets is None or not len(widgets):
                return

        # Widget
        if tooltip is not None:
            for widget in self.widgets:
                widget.setToolTip(tooltip)
        if checkbox is False or disabled:
            for widget in self.widgets:
                widget.setEnabled(False)
        if hidden:
            for widget in self.widgets:
                widget.hide()

        if self.widgets is not None and len(self.widgets):
            if widgets_tooltips is not None:
                if len(widgets_tooltips) == len(self.widgets):
                    for widget, tooltip in zip(self.widgets, widgets_tooltips):
                        widget.setToolTip(tooltip)
                else:
                    raise ValueError(f'Length of widgets_tooltips ({len(widgets_tooltips)}) does not match length of widgets ({len(self.widgets)})')

        stretch_widgets_hbox = 100 - split
        self.addLayout(self.widgets_hbox, stretch=stretch_widgets_hbox)

        if self.widgets is not None and len(self.widgets):
            stretch_widget = 100 // len(self.widgets)
            if widgets_labels is not None:
                if len(widgets_labels) == len(self.widgets):
                    for widget, label_str in zip(self.widgets, widgets_labels):
                        label = QLabel(label_str)
                        hbox = QHBoxLayout()
                        hbox.addWidget(label, alignment=Qt.AlignmentFlag.AlignRight)
                        hbox.addWidget(widget, stretch=stretch_widget)
                        self.widgets_hbox.addLayout(hbox)
                        self.widgets_list.extend([label, widget])
                else:
                    raise ValueError(f'Length of widgets_labels ({len(widgets_labels)}) does not match length of widgets ({len(self.widgets)})')
            else:
                for widget in self.widgets:
                    self.widgets_hbox.addWidget(widget, stretch=stretch_widget)
                    self.widgets_list.append(widget)


        if self.widgets is not None:
            for widget in self.widgets:
                widget.mouseReleaseEvent = lambda _: self.mark(False)

                if isinstance(widget, QSpinBox) or isinstance(widget, QDoubleSpinBox):
                    widget.valueChanged.connect(lambda _: self.mark(False))

    def setEnabled(self, state: bool):
        """
        Enables widgets and checkbox

        :param state: True - enable; False - disable
        """

        if len(self.widgets_list):
            for widget in self.widgets_list:
                widget.setEnabled(state)

        if self.checkbox is not None:
            self.checkbox.setEnabled(state)

    def setHidden(self, state: bool = True):
        """
        Hides/Shows widgets

        :param state: True - hide; False - show
        """

        self.label.setHidden(state)

        if len(self.widgets_list):
            for widget in self.widgets_list:
                widget.setHidden(state)

        if self.checkbox is not None:
            self.checkbox.setHidden(state)

    def mark(self, enable: bool = True):
        """
        Enables/disables widgets background color

        :param enable: True - show background; False - no background
        """

        if len(self.widgets_list):
            for widget in self.widgets_list:
                setWidgetBackground(widget, enable)

    def reset(self):
        """Resets the widgets and clears mark"""
        self.mark(False)

        if len(self.widgets_list):
            for widget in self.widgets_list:
                if hasattr(widget, 'reset'):
                    widget.reset()

        if self.checkbox is not None:
            self.checkbox.setChecked(self.default_checkbox)


class InputHBoxLayout(InputHBoxLayouts):
    """
    Quick horizontal layout for checkbox, label and input. Extends the QHBoxLayout.

    :param label: text of label for widget
    :param widget: widget to be displayed
    :param tooltip: (optional) tooltip to be displayed
    :param split: (optional) percentage split between label and widget
    :param disabled: (optional) enable/disable input
    :param hidden: (optional) hide input and label
    :param checkbox: (optional) add checkbox before label. set to True/False if it should be checked on startup
    :param checkbox_connected: (optional) determines if the widget should be enabled/disabled depending on the checkbox state
    """

    def __init__(
        self,
        label: str,
        widget: Optional[QWidget],
        tooltip: str = None,
        split: int = 50,
        disabled: bool = False,
        hidden: bool = False,
        checkbox: bool = None,
        checkbox_connected: bool = True,
        **kwargs
    ):
        if widget is not None:
            widget = [widget]

        super().__init__(
            label=label,
            widgets=widget,
            tooltip=tooltip,
            split=split,
            disabled=disabled,
            hidden=hidden,
            checkbox=checkbox,
            checkbox_connected=checkbox_connected,
            **kwargs
        )


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
    ZERO_ONE = (0, 1)


class SpinBox(QSpinBox):
    """
    Extension of QSpinBox.

    :param default: default value to start with and reset
    :param step_size: (optional) step size for increasing/decreasing
    :param input_range: (optional) valid input range
    :param buttons: (optional) if buttons for increasing/decreasing should be displayed
    """

    def __init__(
        self,
        default: Union[float, int] = 0,
        step_size: int = None,
        input_range: Tuple[float, float] = None,
        scroll: bool = False,
        buttons: bool = False,
        **kwargs
    ):
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

    def setAndDefault(self, default: int):
        """Sets default and value"""
        self.default = default
        self.setValue(default)


class DoubleSpinBox(QDoubleSpinBox):
    """
    Extension of QDoubleSpinBox.

    :param default: default value to start with and reset
    :param step_size: (optional) step size for increasing/decreasing
    :param input_range: (optional) valid input range
    :param decimals: (optional) number of decimal places
    :param buttons: (optional) if buttons for increasing/decreasing should be displayed
    """

    def __init__(
        self,
        default: float = 0,
        step_size: float = None,
        input_range: Tuple[float, float] = None,
        scroll: bool = False,
        decimals: int = None,
        buttons: bool = False,
        **kwargs
    ):
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

    def setAndDefault(self, default: float):
        """Sets default and value"""
        self.default = default
        self.setValue(default)

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

    def __init__(
        self,
        default: str = '',
        placeholder: str = None,
        max_length: int = None,
        **kwargs
    ):
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

    def __init__(
        self,
        default: int = 0,
        entries: List[str] = None,
        tooltips: List[str] = None,
        entries_save: list = None,
        numbering: int = None,
        label_default: bool = False,
        disabled_list: List[int] = None,
        scroll: bool = False,
        **kwargs
    ):
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

    def setValue(self, value, from_entries: bool = False, from_entries_save: bool = False):
        """
        Sets value of widget

        :param value: value to be set
        :param from_entries: value is element of entries list
        :param from_entries_save: value is element of entries_save list
        """

        if from_entries:
            if value not in self.entries:
                value = self.default
            else:
                value = self.entries.index(value)

        elif from_entries_save:
            if self.entries_save is None or value not in self.entries_save:
                value = self.default
            else:
                value = self.entries_save.index(value)

        self.setCurrentIndex(value)

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

    def __init__(
        self,
        placeholder: str = None,
        function_loc: Callable = None,
        icon_loc: QIcon = None,
        function_ssh: Callable = None,
        icon_ssh: QIcon = None,
        **kwargs
    ):
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

    def __init__(
        self,
        parent,
        title: str,
        title_style: str = Styles.title_style,
        title_style_busy: str = Styles.title_style,
        busy_symbol: str = '⧖',
        spacing: int = 0,
        add_stretch: Union[bool, int] = 0,
        *args,
        **kwargs
    ):
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

    def __init__(
        self,
        *args,
        indent: int = 0,
        bold: bool = False,
        grey: bool = False,
        selectable: bool = True,
        tooltip: str = '',
        function: Callable = None,
        function_args: dict = None,
        **kwargs
    ):
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

    def __init__(
        self,
        parent,
        line_numbering: bool = True,
        readonly: bool = True,
        mono: bool = True,
        offset: int = 0,
        highlighting: bool = True,
        color_line_number: QColor = QColor('#EEEEEE'),
        color_line_number_dark: QColor = QColor('#464646'),
        color_highlight: QColor = QColor('#FFFEC8'),
        color_highlight_dark: QColor = QColor('#00003F')
    ):
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

    :param parent: parent widget
    :param width: (optional) width of figure
    :param height: (optional) height of figure
    :param dpi: (optional) dpi for figure
    :param enable_3d: (optional) enables 3D projection
    :param use_device_palette: (optional) uses device palette
    :param disable_interaction: (optional) disables user interaction
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        width: int = 4,
        height: int = 8,
        dpi: float = 100,
        enable_3d: bool = False,
        use_device_palette: bool = True,
        disable_interaction: bool = False
    ):
        self.disable_interaction = disable_interaction
        self.pal = parent.palette() if parent is not None else QApplication.instance().palette()

        # get QT colors
        self.bg_color = self.pal.color(QPalette.ColorRole.Window).name()
        self.fg_color = self.pal.color(QPalette.ColorRole.WindowText).name()

        self.palette_kwargs = {}
        if use_device_palette:
            self.palette_kwargs['facecolor'] = self.bg_color

        self.axes_kwargs = {}
        if enable_3d:
            self.axes_kwargs['projection'] = '3d'

        with rc_context(self.get_rc_context()):
            self.fig: Figure = Figure(figsize=(width, height), dpi=dpi, **self.palette_kwargs)
            self.axes: Axes = self.fig.add_subplot(**self.palette_kwargs, **self.axes_kwargs)

        super().__init__(self.fig)

    def get_rc_context(self):
        """Returns matplotlib rc parameter dictionary"""

        return {
            'lines.color': self.fg_color,
            'patch.edgecolor': self.fg_color,
            'text.color': self.fg_color,
            'axes.facecolor': self.bg_color,
            'axes.edgecolor': self.fg_color,
            'axes.labelcolor': self.fg_color,
            'xtick.color': self.fg_color,
            'xtick.labelcolor': self.fg_color,
            'ytick.color': self.fg_color,
            'ytick.labelcolor': self.fg_color,
            'xtick.top': True,
            'ytick.right': True,
            'xtick.direction': 'in',
            'ytick.direction': 'in',
            'figure.facecolor': self.bg_color,
            'figure.edgecolor': self.bg_color,
            'legend.frameon': False,
        }

    def clear(self):
        """Clears fig and resets axes"""
        with rc_context(self.get_rc_context()):
            self.fig.clf()
            self.axes = self.fig.add_subplot(**self.palette_kwargs, **self.axes_kwargs)

    def mousePressEvent(self, e):
        if not self.disable_interaction:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if not self.disable_interaction:
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if not self.disable_interaction:
            super().mouseReleaseEvent(e)

    def wheelEvent(self, e):
        if not self.disable_interaction:
            super().wheelEvent(e)

    def keyPressEvent(self, e):
        if not self.disable_interaction:
            super().keyPressEvent(e)


class NoMessageToolbar(NavigationToolbar2QT):
    """
    Custum NavigationToolbar2QT that does not show messages
    """

    def __init__(self, canvas: MplCanvas, parent, **kwargs):
        super().__init__(canvas, parent, **kwargs)
        self.canvas = canvas

    def set_message(self, s):
        """Message is set"""
        pass

    def home(self, *args):
        """Home button press"""

        if not isinstance(self.canvas, CrystalPreview):
            return super().home(*args)

        self.canvas.axes.view_init(self.canvas.elev, self.canvas.azim, self.canvas.roll)
        self.canvas.draw_idle()



class TargetPreview(QWidget):
    """
    QWidget for preview of target

    :param parent: parent widget
    """

    def __init__(self, parent):
        super().__init__(parent)

        self.antialiased = True
        self.setBackgroundRole(QPalette.ColorRole.Base)
        self.setAutoFillBackground(True)
        self.pen = QPen(self.palette().color(QPalette.ColorRole.Text))

        self.font = QFont()
        self.font_metrics = QFontMetrics(self.font)

        self.layers = []
        self.elements = []
        self.total_segments = 0
        self.element_widths = []

        self.legend_size = 15
        self.legend_margin = 2
        self.legend_spacing_x = 7
        self.legend_spacing_y = 5

        self.target_width = 120
        self.x_margin = 15
        self.y_margin = 15

    def minimumSizeHint(self):
        """Returns minimum size"""

        return QSize(150, 100)

    def setTargetInfo(self, elements: list, layers: list):
        """
        Sets elements in layers

        :param elements: list of elements
        :param layers: list of layers
        """

        self.elements = elements
        self.element_widths = []
        for element in self.elements:
            self.element_widths.append(self.font_metrics.horizontalAdvance(element))

        self.layers = []
        self.total_segments = 0
        for row in layers:
            self.layers.append([row.segment_count, row.layer_name, row.abundances])
            self.total_segments += row.segment_count
        self.update()

    def resizeEvent(self, event):
        """
        When widget is resized

        :param event: resize event
        """

        self.target_width = self.width() * 0.9
        self.x_margin = (self.width() - self.target_width) / 2
        self.y_margin = (self.height() * 0.05) / 2

    def paintEvent(self, event):
        """
        When widget is painted

        :param event: paint event
        """

        painter = QPainter(self)
        painter.setPen(self.pen)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, self.antialiased)

        x_coord = self.x_margin
        y_coord = self.y_margin

        # Draw elements legend
        if len(self.elements) > 0:
            for i in range(len(self.elements)):
                x_coord_new = x_coord + self.element_widths[i] + 2 * self.legend_margin + self.legend_spacing_x
                if x_coord + self.x_margin > self.target_width:
                    x_coord = self.x_margin
                    x_coord_new = x_coord + self.element_widths[i] + 2 * self.legend_margin + self.legend_spacing_x
                    y_coord = y_coord + self.legend_size + self.legend_spacing_y

                rect = QRect(
                    int(x_coord),
                    int(y_coord),
                    int(self.element_widths[i] + 2 * self.legend_margin),
                    int(self.legend_size)
                )
                painter.fillRect(rect, getUniqueColor(i, len(self.elements)))
                rect.translate(self.legend_margin, 0)
                rect.setSize(QSize(self.element_widths[i], self.legend_size))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f'{self.elements[i]}')

                x_coord = x_coord_new

        if not self.total_segments:
            return

        # Draw the target layers
        last_layer_y = int(y_coord + self.legend_size + self.legend_spacing_y)
        target_height = self.height() - last_layer_y - self.y_margin
        for i, layer in enumerate(self.layers):
            layer_height = round(target_height * layer[0] / self.total_segments)
            rect = QRect(
                int(self.x_margin),
                last_layer_y,
                int(self.target_width),
                layer_height
            )
            painter.drawRect(rect)

            # Color the layer depending on composition
            last_x = self.x_margin
            for j in range(len(self.elements)):
                w = self.target_width * layer[2][j]
                rect2 = QRect(
                    round(last_x),
                    last_layer_y,
                    round(last_x + w) - round(last_x),
                    layer_height
                )
                painter.fillRect(rect2, QColor.fromHsv(int(j * 359 / len(self.elements)), 255, 255, 127))
                last_x += w

            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f'{layer[1]}')
            last_layer_y += layer_height


class CrystalPreview(MplCanvas):
    """
    QWidget for preview of crystal

    :param parent: parent widget
    :param miller_ind: (optional) miller index
    :param basis_vecs: (optional) basis vectors
    :param crystal_coords: (optional) crystal coordinates
    :param show_beam: (optional) show the beam
    :param show_basis_vecs: (optional) show the basis vectors
    :param show_unrotated_cell: (optional) show the unrotated cell
    :param show_coordinate_system: (optional) show the coordinate system
    :param show_surface: (optional) show the surface
    :param show_legend: (optional) show legend
    :param atom_size: (optional) size of atoms
    :param line_width: (optional) line width
    :param axes_equal_radius: (optional) radius of equal axis
    :param elev: (optional) camera elevation
    :param azim: (optional) camera azimuthal
    :param roll: (optional) camera roll

    :param width: (optional) width of figure
    :param height: (optional) height of figure
    :param dpi: (optional) dpi for figure
    :param use_device_palette: (optional) uses device palette
    :param disable_interaction: (optional) disables user interaction

    :param size_hint: (optional): size hint for widget
    """

    def __init__(
        self,
        parent,
        miller_ind: np.ndarray = np.array([1, 0, 0]),
        basis_vecs: np.ndarray = np.identity(3),
        crystal_coords: Optional[Dict[Element, np.ndarray]] = None,
        show_beam: bool = False,
        show_basis_vecs: bool = False,
        show_unrotated_cell: bool = False,
        show_coordinate_system: bool = False,
        show_surface: bool = False,
        show_legend: bool = False,
        atom_size: int = 50,
        line_width: float = 1,
        axes_equal_radius: float = 1,
        elev: Optional[float] = -160,
        azim: Optional[float] = -120,
        roll: Optional[float] = None,
        size_hint: Optional[QSize] = QSize(100, 100),
        **kwargs
    ):
        self.miller_ind = miller_ind
        self.basis_vecs = basis_vecs
        if crystal_coords is None:
            crystal_coords = {}
        self.crystal_coords = crystal_coords

        self.miller_rot_mat = np.identity(3)
        self.display_mat = np.array([
            [0, 0, 1],
            [1, 0, 0],
            [0, 1, 0]
        ])

        self.show_beam = show_beam
        self.show_basis_vecs = show_basis_vecs
        self.show_unrotated_cell = show_unrotated_cell
        self.show_coordinate_system = show_coordinate_system
        self.show_surface = show_surface
        self.show_legend = show_legend

        self.atom_size = atom_size
        self.line_width = line_width
        self.axes_equal_radius = axes_equal_radius

        self.elev = elev
        self.azim = azim
        self.roll = roll

        self.size_hint = size_hint

        self.surf_xx, self.surf_yy = np.meshgrid(range(-2, 2), range(-1, 3))
        self.surf_z = 0 * (self.surf_xx + self.surf_yy)

        kwargs['enable_3d'] = True
        setDictIfNotExists(kwargs, 'width', 1)
        setDictIfNotExists(kwargs, 'height', 1)
        setDictIfNotExists(kwargs, 'disable_interaction', True)

        super().__init__(parent, **kwargs)

        self.axes.view_init(self.elev, self.azim, self.roll)

        self._updatePlot()

    def _setAxesEqual(self):
        # TODO: this does not really work
        """Make axes of 3D plot have equal scale so that spheres appear as spheres, cubes as cubes, etc."""

        x_limits = self.axes.get_xlim3d()
        y_limits = self.axes.get_ylim3d()
        z_limits = self.axes.get_zlim3d()

        x_range = abs(x_limits[1] - x_limits[0])
        x_middle = (x_limits[0] + x_limits[1]) / 2
        y_range = abs(y_limits[1] - y_limits[0])
        y_middle = (y_limits[0] + y_limits[1]) / 2
        z_range = abs(z_limits[1] - z_limits[0])
        z_middle = (z_limits[0] + z_limits[1]) / 2

        plot_radius = self.axes_equal_radius * max([x_range, y_range, z_range])

        self.axes.set_xlim3d([x_middle - plot_radius, x_middle + plot_radius])
        self.axes.set_ylim3d([y_middle - plot_radius, y_middle + plot_radius])
        self.axes.set_zlim3d([z_middle - plot_radius, z_middle + plot_radius])

    def _plotVec3(self, vector: np.ndarray, startpoint: np.ndarray = np.zeros(3), label: Optional[str] = None, label_pos: Optional[np.ndarray] = None, **plot_kwargs):
        """
        Plots vector on axis

        :param vector: vector to plot as <np.ndarray>
        :param startpoint: (optional) starting position for vector as <np.ndarray>, otherwise zero
        :param label: (optional) label of vector
        :param label_pos: (optional) label position as <np.ndarray>, otherwise midpoint
        :param plot_kwargs: (optional) parameters for plot
        """

        plot_params = {
            'linewidth': self.line_width,
            'color': self.fg_color
        }
        plot_params.update(plot_kwargs)

        self.axes.quiver(*startpoint, *vector, **plot_params)
        if label is not None:
            if label_pos is None:
                label_pos = startpoint + (vector - startpoint) / 2
            del plot_params['linewidth']
            self.axes.text(*(label_pos + 0.05), s=label, **plot_params)

    def _plotUnitCellOutlines(self, rotated: bool = True, **plot_kwargs):
        """
        Make outline of unit cell

        :param rotated: include rotation caused by miller indices
        :param plot_kwargs: (optional) parameters for plot
        """

        plot_params = {
            'linewidth': self.line_width,
            'color': self.fg_color
        }
        plot_params.update(plot_kwargs)

        b1, b2, b3 = self.basis_vecs
        if rotated:
            b1, b2, b3 = self.basis_vecs @ self.miller_rot_mat

        vertices = [i * b1 + j * b2 + k * b3 for i in (0, 1) for j in (0, 1) for k in (0, 1)]

        edges = []
        for v in vertices:
            for b in (b1, b2, b3):
                neighbor = v + b
                if any(np.allclose(neighbor, w) for w in vertices):
                    edges.append((v, neighbor))

        for v1, v2 in edges:
            self.axes.plot([v1[0], v2[0]], [v1[1], v2[1]], [v1[2], v2[2]], **plot_params)

    def _plotCoordSystem(self):
        """Plot the coordinate system"""

        self._plotVec3(np.array([0, 0, 1.5]), color='y', label='${X}$', label_pos=np.array([0, 0.1, 1.5]))
        self._plotVec3(np.array([1.5, 0, 0]), color='y', label='${Y}$', label_pos=np.array([1.5, 0.1, 0]))
        self._plotVec3(np.array([0, 1.5, 0]), color='y', label='${Z}$', label_pos=np.array([0, 1.5, 0.1]))

    def _plotBasisVecs(self, rotated: bool = True):
        """
        Plot the basis vectors

        :param rotated: include rotation caused by miller indices
        """

        labels = ['${\u00E2_1}$', '${\u00E2_2}$', '${\u00E2_3}$']
        basis_vecs = self.basis_vecs
        if rotated:
            basis_vecs = basis_vecs @ self.miller_rot_mat

        for basis_vec, label in zip(basis_vecs, labels):
            self._plotVec3(basis_vec, color='b', label=label)

    def _plotCoords(self, rotated: bool = True):
        """
        Plot atom coordinates

        :param rotated: include rotation caused by miller indices
        """

        for i, (element, coords) in enumerate(self.crystal_coords.items()):
            if not len(coords):
                continue
            color = getUniqueColor(i, len(self.crystal_coords)).name()
            coords = coords @ self.basis_vecs
            if rotated:
                coords = coords @ self.miller_rot_mat
            self.axes.scatter(
                coords[:, 0], coords[:, 1], coords[:, 2],
                c=color, s=self.atom_size / 3 * (1 + element.atomic_nr / 50), label=element.symbol
            )

    def _plotBeam(self):
        """Plots the beam"""
        self._plotVec3(np.array([0, 0, 1]), startpoint=np.array([0, 0, -1]), color='r', label='${beam}$', label_pos=np.array([0., 0.1, -0.5]))

    def _plotSurface(self):
        """Plot surface"""
        self.axes.plot_surface(self.surf_xx, self.surf_yy, self.surf_z, alpha=0.2)

    def _calcMillerRotMat(self):
        """Calculates rotation matrix based on miller indices"""

        a = np.array([1, 0, 0])
        if np.any(self.miller_ind):
            a = self.miller_ind / np.linalg.norm(self.miller_ind)
        r = np.linalg.norm(a[:2])

        sin_phi = 0
        cos_phi = 0
        if not np.isclose(r, 0):
            sin_phi = a[1] / r
            cos_phi = a[0] / r
        sin_theta = a[2]
        cos_theta = r

        self.miller_rot_mat = np.array([
           [-sin_phi, -cos_phi * sin_theta, cos_phi * cos_theta],
           [cos_phi , -sin_phi * sin_theta, sin_phi * cos_theta],
           [0       , cos_theta           , sin_theta          ]
        ])

    def _updatePlot(self):
        """Update the plot"""

        azim = self.axes.azim
        elev = self.axes.elev
        roll = self.axes.roll

        self.clear()
        self.axes.view_init(elev, azim, roll)
        self.draw_idle()
        self.axes.set_axis_off()

        self._calcMillerRotMat()

        if self.show_coordinate_system:
            self._plotCoordSystem()
        self._plotUnitCellOutlines()
        if self.show_basis_vecs:
            self._plotBasisVecs()
        if self.show_beam:
            self._plotBeam()
        if self.show_unrotated_cell:
            self._plotUnitCellOutlines(False)
            self._plotBasisVecs(False)
        self._plotCoords()

        if self.show_legend:
            handles, _ = self.axes.get_legend_handles_labels()
            if handles:
                legend = self.axes.legend(loc='upper right')
                legend.get_frame().set_facecolor(self.bg_color)
                legend.get_frame().set_edgecolor(self.fg_color)
                for text in legend.get_texts():
                    text.set_color(self.fg_color)

        self._setAxesEqual()

        if self.show_surface:
            self._plotSurface()

    def updateParams(
        self,
        miller_ind: Optional[np.ndarray] = None,
        basis_vecs: Optional[np.ndarray] = None,
        crystal_coords: Optional[Dict[Element, np.ndarray]] = None,
        show_beam: Optional[bool] = None,
        show_basis_vecs: Optional[bool] = None,
        show_unrotated_cell: Optional[bool] = None,
        show_coordinate_system: Optional[bool] = None,
        show_surface: Optional[bool] = None,
        show_legend: Optional[bool] = None
    ):
        """
        Update parameters; all parameters are optional

        :param miller_ind: (optional) miller index
        :param basis_vecs: (optional) basis vectors
        :param crystal_coords: (optional) crystal coordinates
        :param show_beam: (optional) show beam
        :param show_basis_vecs: (optional) show basis vectors
        :param show_unrotated_cell: (optional) show unrotated cell
        :param show_coordinate_system: (optional) show coordinate system
        :param show_surface: (optional) show surface
        :param show_legend: (optional) show legend
        """

        if miller_ind is not None:
            self.miller_ind = miller_ind
        if basis_vecs is not None:
            self.basis_vecs = basis_vecs
        if crystal_coords is not None:
            self.crystal_coords = crystal_coords
        if show_beam is not None:
            self.show_beam = show_beam
        if show_basis_vecs is not None:
            self.show_basis_vecs = show_basis_vecs
        if show_unrotated_cell is not None:
            self.show_unrotated_cell = show_unrotated_cell
        if show_coordinate_system is not None:
            self.show_coordinate_system = show_coordinate_system
        if show_surface is not None:
            self.show_surface = show_surface
        if show_legend is not None:
            self.show_legend = show_legend

        self._updatePlot()

    def sizeHint(self):
        """Returns size"""
        if self.size_hint is None:
            super().sizeHint()
        else:
            return self.size_hint

    def minimumSizeHint(self):
        """Returns minimum size"""
        return QSize(50, 50)
