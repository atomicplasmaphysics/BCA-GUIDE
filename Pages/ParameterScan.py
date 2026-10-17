"""
Parameter scan: a series of simulations in which any number of parameters of a simulation tab are varied (all combinations).
The scan is enabled with the scan button in the toolbar of the simulation tab. Then the input fields that can be scanned
show a small mark in their corner: a click opens a popup in which several values are entered (directly or as linear or
logarithmic range, or a selection of the choices of a combo box), the field then shows its values. Parameters: energies,
angles, starting depth and charge of the beam species, the properties of the elements (also the inelastic loss model), the
atomic fractions (first layer), thickness and number of segments of the target, the numeric simulation settings (e.g.
fluence, number of histories), the models of the simulation settings (interaction potential, integration method, surface
binding model) and the version of the simulation program (other configurations, menu of the scan button).
The simulations of the scan are written into subfolders of the folder of the simulation, the scan is described in
scan.json in this folder (opening scan.json opens the scan again, each subfolder is a simulation on its own). The
simulations run with a lower priority than the GUI and at most GlobalConf.max_parallel_runs simulations of all tabs run
at the same time (see MainWindow.startQueuedSimulations), the results are compared in a <CompareWidget>
"""

from __future__ import annotations
from typing import List, Optional, Callable, Any, Dict, Tuple, Iterator, TYPE_CHECKING
from itertools import product
from json import dump, load
from locale import getpreferredencoding
from pathlib import Path
from re import sub

import numpy as np

from PyQt6 import sip
from PyQt6.QtCore import Qt, QProcess, QTimer, QObject, QEvent, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QPolygon, QColor, QMouseEvent, QPaintEvent
from PyQt6.QtWidgets import (
    QComboBox, QLabel, QLineEdit, QPushButton, QDoubleSpinBox, QSpinBox, QMessageBox, QGridLayout, QWidget, QFrame,
    QTableWidgetItem, QHeaderView, QApplication, QHBoxLayout, QListWidget, QListWidgetItem
)

from Pages.CompareDialog import CompareWidget, SCAN_FILE

from Simulations.Simulations import writeInputFiles

from TableWidgets.CompTable import setSpinboxValue

from Utility.Styles import paletteQColor
from Utility.Dialogs import showMessageBox
from Utility.Functions import pathToStr, lowerProcessPriority
from Utility.Icons import getIcon
from Utility.Layouts import InputHBoxLayouts
from Utility.Typing import notNone

if TYPE_CHECKING:
    from Pages.ProgramPage import SimulationPage
    from Containers.Arguments import SimulationArguments


# scales of the range of values
SCALES = ['linear', 'logarithmic (dense at start)', 'logarithmic (dense at end)']

# icons of the states of the simulations of a scan
STATUS_ICONS = {'waiting': 'clock', 'running': 'play', 'finished': 'okay', 'not started': 'abort', 'not run': 'abort'}

# log of the simulations of a scan (in their folders)
LOG_FILE = 'scan_log.txt'

# fields of the rows of the composition tables: attribute of the row, key of the parameter (with the symbol)
ROW_FIELDS = [
    ('kinetic_energy', 'energy'), ('angle', 'angle'), ('azimuth', 'azimuth'), ('atomic_mass', 'mass'),
    ('atomic_density', 'density'), ('surface_binding_energy', 'sbe'), ('displacement_energy', 'ed'),
    ('cutoff_energy', 'ecut'), ('cutoff_energy_input', 'ecut'), ('bulk_binding_energy', 'ebulk'),
    ('heat_of_formation', 'dhf'), ('inelastic_correction', 'ck'), ('start_depth', 'x0'), ('charge', 'charge')
]

# fields of the rows of the composition tables whose value is set in the field before the arguments are created:
# attribute of the row, key of the parameter (with the symbol), label
ROW_WIDGET_FIELDS = [
    ('max_concentration', 'qumax', 'Maximum atomic fraction'), ('maximum_concentration', 'qumax', 'Maximum atomic fraction')
]

# combo boxes of the rows of the composition tables: attribute of the row, key of the parameter (with the symbol), label
ROW_CHOICES = [
    ('inelastic_loss_model', 'inel', 'Inelastic loss model'), ('action_switch', 'ires', 'Action at the maximum atomic fraction')
]

# fields of the simulation settings that are parameters with own keys (attribute: key)
SETTINGS_KEYS = {'fluence': 'fluence', 'histories_total': 'histories', 'projectiles': 'projectiles'}

# numeric fields of the simulation settings that are not scanned (they do not change the results)
SETTINGS_EXCLUDED = {'histories_between', 'threads', 'log_frequency', 'integral_frequency', 'output_frequency'}

# numeric fields of the beam and target settings that are not scanned (calculated from other fields or not working)
BEAM_TARGET_EXCLUDED = {'segment_thickness', 'sweep'}

# combo boxes of the simulation settings that can be scanned (attribute: label)
SETTINGS_CHOICES = {
    'potential': 'Interaction potential', 'integration': 'Integration method', 'surface_binding_model': 'Surface binding model',
    'inelastic_loss_model': 'Electronic stopping mode'
}


def formatValue(value) -> str:
    """Returns a value for a folder name, e.g. 1000.0 -> "1000", 0.5 -> "0.5" """

    if isinstance(value, str):
        return sub(r'[^A-Za-z0-9_.]+', '_', value)
    return f'{value:g}'.replace('+', '')


class ScanParameter:
    """
    Parameter that can be varied in a scan

    :param key: unique key (used in folder names)
    :param label: label with unit
    :param current: function that returns the current value from the arguments
    :param apply: function that sets a value in the arguments or None: the value is set in the widgets of the parameter
        before the arguments are created (fields of the simulation settings)
    :param integer: integer values
    :param choices: (optional) texts of the choices of a combo box, the values are the indices of the choices
    """

    def __init__(self, key: str, label: str, current: Callable[..., Any], apply: Optional[Callable[..., None]], integer: bool = False,
                 choices: Optional[List[str]] = None):
        self.key = key
        self.label = label
        self.current = current
        self.apply = apply
        self.integer = integer or choices is not None
        self.choices = choices
        # input fields of the parameter
        self.widgets: List[QWidget] = []


def rangeValues(start: float, stop: float, number: int, scale: int = 0) -> np.ndarray:
    """
    Returns the values of a range

    :param start: first value
    :param stop: last value
    :param number: number of values
    :param scale: (optional) index in SCALES: linear, logarithmic (dense at start) or logarithmic (dense at end). Ranges
        that include 0 or negative values (e.g. angles from 0°) are shifted for the logarithmic spacing
    """

    if scale == 0 or start == stop or number < 3:
        return np.linspace(start, stop, number)
    if scale == 2:
        return start + stop - rangeValues(start, stop, number, 1)[::-1]
    if start > 0 and stop > 0:
        return np.geomspace(start, stop, number)
    # shifted, so that the smaller value is 1
    offset = 1 - min(start, stop)
    values = np.geomspace(start + offset, stop + offset, number) - offset
    values[0], values[-1] = start, stop
    return values


def formatRangeValue(value: float) -> str:
    """Returns a value of a range rounded to 4 significant digits, e.g. 632.456 -> "632.5", 20000.0 -> "20000" """

    return f'{float(f"{value:.4g}"):.10g}'


def parseValues(text: str, integer: bool = False) -> list:
    """Returns the values of a comma separated text (integer values are rounded, duplicates removed)"""

    values: list = []
    for part in text.replace(';', ',').split(','):
        try:
            value = float(part)
        except ValueError:
            continue
        if integer:
            value = int(round(value))
        if value not in values:
            values.append(value)
    return values


def defaultRange(key: str, current: float) -> dict:
    """Default range of values of a parameter around its current value"""

    if key.startswith(('angle_', 'azimuth_')):
        angle = key.startswith('angle_')
        return {'start': 0., 'stop': 80. if angle else 90., 'number': 9 if angle else 4, 'scale': 0}
    if key.startswith(('fraction_', 'qubeam_')):
        return {'start': 0.1, 'stop': 0.9, 'number': 5, 'scale': 0}
    if key.startswith('qumax_'):
        return {'start': 0.2, 'stop': 1., 'number': 5, 'scale': 0}
    if current > 0:
        logarithmic = key.startswith('energy_') or key in ('fluence', 'histories', 'projectiles')
        return {'start': current / 10 if logarithmic else current / 2, 'stop': current * 10 if logarithmic else current * 2,
                'number': 5, 'scale': 1 if logarithmic else 0}
    return {'start': current, 'stop': current + 1, 'number': 5, 'scale': 0}


def elementRows(arguments, symbol: str) -> list:
    """Returns the beam and target rows of an element"""

    return [row for row in arguments.beam_rows + arguments.target_rows if row.symbol == symbol]


def setElementValue(arguments, symbol: str, attribute: str, value: float):
    """Sets a property of an element (in the beam and in the target) and marks the element as modified"""

    for row in elementRows(arguments, symbol):
        element = row.element
        if element.getOriginal() is None:
            element.original = element.copy(copy_original=False)
        setattr(element, attribute, float(value))
        element.modified = True


def setRowValue(arguments, symbol: str, key: str, value: float):
    """Sets an optional value of the rows of an element (e.g. cutoff_energy)"""

    for row in elementRows(arguments, symbol):
        row.optional[key] = float(value)


def setTargetFraction(arguments, symbol: str, value: float):
    """Sets the atomic fraction of an element in the first layer of the target, the other elements keep their ratios"""

    target_rows = [row for row in arguments.target_rows if row.symbol]
    symbols = [row.symbol for row in target_rows]
    if symbol not in symbols:
        return
    value = min(max(float(value), 0.), 1.)
    index = symbols.index(symbol)
    layers = arguments.structure[:1] if arguments.structure else []
    for layer in layers:
        others = sum(a for i, a in enumerate(layer.abundances) if i != index)
        layer.abundances = [
            value if i == index else (a / others * (1 - value) if others > 0 else (1 - value) / max(len(symbols) - 1, 1))
            for i, a in enumerate(layer.abundances)
        ]
    for i, row in enumerate(target_rows):
        if layers and i < len(layers[0].abundances):
            row.abundance = layers[0].abundances[i]


def setBeamFraction(arguments, symbol: str, value: float):
    """Sets the fraction of an element in the beam, the other elements of the beam keep their ratios"""

    rows = [row for row in arguments.beam_rows if row.symbol]
    if not any(row.symbol == symbol for row in rows):
        return
    value = min(max(float(value), 0.), 1.)
    others = sum(row.abundance for row in rows if row.symbol != symbol)
    for row in rows:
        if row.symbol == symbol:
            row.abundance = value
        elif others > 0:
            row.abundance = row.abundance / others * (1 - value)
        else:
            row.abundance = (1 - value) / max(len(rows) - 1, 1)


def setSegments(arguments, value: float):
    """Sets the number of segments of the target (nqx), the layers keep their relative number of segments (at least 1)"""

    number = max(int(round(value)), 1)
    arguments.target_args.segments = number
    layers = arguments.structure
    total = sum(layer.segments for layer in layers)
    if not layers or total <= 0:
        return
    remaining = number
    for i, layer in enumerate(layers):
        if i == len(layers) - 1:
            segments = max(remaining, 1)
        else:
            segments = min(max(int(round(layer.segments * number / total)), 1), max(remaining - (len(layers) - 1 - i), 1))
        layer.segments = segments
        remaining -= segments


def choiceTexts(widget: QComboBox) -> List[str]:
    """Texts of the choices of a combo box (without the mark of the default choice)"""

    return [widget.itemText(i).replace(' (default)', '') for i in range(widget.count())]


def choiceEnabled(widget: QComboBox, index: int) -> bool:
    """Returns if a choice of a combo box can be selected"""

    model = widget.model()
    if model is None:
        return True
    return bool(model.flags(model.index(index, 0)) & Qt.ItemFlag.ItemIsEnabled)


def setThickness(arguments, value: float):
    """Sets the thickness of the target, the layers keep their relative thickness"""

    total = sum(layer.thickness for layer in arguments.structure)
    for layer in arguments.structure:
        layer.thickness = layer.thickness * value / total if total > 0 else value / max(len(arguments.structure), 1)
    arguments.target_args.thickness = float(value)


def scanParameters(arguments, simulation_name: str, supports_azimuth: bool = True) -> List[ScanParameter]:
    """Returns the parameters that can be scanned for the arguments of a simulation (without the simulation settings)"""

    parameters = []
    beam_elements = len([row for row in arguments.beam_rows if row.symbol])
    for i, row in enumerate(arguments.beam_rows):
        if not row.symbol:
            continue
        symbol = row.symbol
        if beam_elements > 1:
            parameters.append(ScanParameter(f'qubeam_{symbol}', f'Fraction of {symbol} in the beam',
                                            lambda a, i=i: a.beam_rows[i].abundance, lambda a, v, s=symbol: setBeamFraction(a, s, v)))
        parameters.append(ScanParameter(f'energy_{symbol}', f'Energy of {symbol} [eV]', lambda a, i=i: a.beam_rows[i].energy,
                                        lambda a, v, i=i: setattr(a.beam_rows[i], 'energy', float(v))))
        parameters.append(ScanParameter(f'angle_{symbol}', f'Angle of incidence of {symbol} [°]', lambda a, i=i: a.beam_rows[i].angle,
                                        lambda a, v, i=i: setattr(a.beam_rows[i], 'angle', float(v))))
        if supports_azimuth and simulation_name == 'SDTrimSP':
            parameters.append(ScanParameter(f'azimuth_{symbol}', f'Azimuthal angle of {symbol} [°]',
                                            lambda a, i=i: a.beam_rows[i].get('azimuth') or 0.,
                                            lambda a, v, i=i: a.beam_rows[i].optional.__setitem__('azimuth', float(v))))
        if simulation_name == 'SDTrimSP':
            for key, name, option in (('x0', 'Starting depth', 'start_depth'), ('charge', 'Charge', 'charge')):
                parameters.append(ScanParameter(
                    f'{key}_{symbol}', f'{name} of {symbol}' + (' [Å]' if key == 'x0' else ''),
                    lambda a, i=i, o=option: float(a.beam_rows[i].get(o) or 0.),
                    lambda a, v, i=i, o=option: a.beam_rows[i].optional.__setitem__(o, float(v))
                ))

    symbols = list(dict.fromkeys(row.symbol for row in arguments.beam_rows + arguments.target_rows if row.symbol))
    element_properties = [
        ('sbe', 'Surface binding energy', '[eV]', 'surface_binding_energy'),
        ('ed', 'Displacement energy', '[eV]', 'displacement_energy'),
        ('density', 'Atomic density', '[atoms/Å³]', 'atomic_density'),
        ('mass', 'Atomic mass', '[amu]', 'atomic_mass'),
    ]
    for symbol in symbols:
        for key, name, unit, attribute in element_properties:
            parameters.append(ScanParameter(
                f'{key}_{symbol}', f'{name} of {symbol} {unit}',
                lambda a, s=symbol, at=attribute: getattr(elementRows(a, s)[0].element, at) or 0.,
                lambda a, v, s=symbol, at=attribute: setElementValue(a, s, at, v)
            ))
        if simulation_name == 'SDTrimSP':
            for key, name, option in (('ecut', 'Cutoff energy', 'cutoff_energy'), ('ebulk', 'Bulk binding energy', 'bulk_binding_energy'),
                                      ('dhf', 'Heat of formation', 'heat_of_formation')):
                parameters.append(ScanParameter(
                    f'{key}_{symbol}', f'{name} of {symbol} [eV]',
                    lambda a, s=symbol, o=option: max(float(elementRows(a, s)[0].get(o) or 0.), 0.),
                    lambda a, v, s=symbol, o=option: setRowValue(a, s, o, v)
                ))
            parameters.append(ScanParameter(
                f'ck_{symbol}', f'Correction of the electronic stopping of {symbol} (ck_elec)',
                lambda a, s=symbol: float(elementRows(a, s)[0].get('inelastic_correction') or 1.),
                lambda a, v, s=symbol: setRowValue(a, s, 'inelastic_correction', v)
            ))
        else:
            parameters.append(ScanParameter(
                f'ecut_{symbol}', f'Cutoff energy of {symbol} [eV]', lambda a, s=symbol: elementRows(a, s)[0].element.cutoff_energy or 0.,
                lambda a, v, s=symbol: setElementValue(a, s, 'cutoff_energy', v)
            ))
        if any(row in arguments.target_rows for row in elementRows(arguments, symbol)):
            parameters.append(ScanParameter(
                f'fraction_{symbol}', f'Atomic fraction of {symbol} in the target (first layer)',
                lambda a, s=symbol: next((r.abundance for r in a.target_rows if r.symbol == s), 0.),
                lambda a, v, s=symbol: setTargetFraction(a, s, v)
            ))

    parameters.append(ScanParameter('thickness', 'Target thickness [Å]', lambda a: a.target_args.thickness, setThickness))
    if isinstance(getattr(arguments.target_args, 'segments', None), int):
        parameters.append(ScanParameter('segments', 'Target segments (nqx)', lambda a: a.target_args.segments, setSegments, integer=True))
    parameters.append(ScanParameter('fluence', 'Fluence [atoms/Å²]', lambda a: a.settings.fluence,
                                    lambda a, v: setattr(a.settings, 'fluence', float(v))))
    labels = {'histories': 'Number of histories (nh)', 'projectiles': 'Projectiles per history (nr_pproj)'}
    if simulation_name != 'SDTrimSP':
        labels = {'projectiles': 'Number of projectiles (pspr)'}
    for name, label in labels.items():
        if isinstance(arguments.settings.get(name), (int, float)):
            parameters.append(ScanParameter(name, label, lambda a, n=name: a.settings.get(n),
                                            lambda a, v, n=name: a.settings.optional.__setitem__(n, int(round(v))), integer=True))
    return parameters


def plainLabel(text: str) -> str:
    """Label of an input field without html, colon and trailing spaces"""

    return sub(r'<[^>]+>', '', text).strip().rstrip(':').strip()


def settingsFields(owner, excluded: Optional[set] = None) -> List[Tuple[str, str, QWidget]]:
    """
    Returns the numeric input fields of a settings layout as (attribute name, label, widget): the spin boxes of the
    <InputHBoxLayouts> that are attributes of the layout

    :param owner: settings layout (e.g. VlSimulationSettings)
    :param excluded: (optional) attribute names of fields that are not returned (default: SETTINGS_EXCLUDED)
    """

    excluded = SETTINGS_EXCLUDED if excluded is None else excluded

    names = {id(value): name for name, value in vars(owner).items() if isinstance(value, (QSpinBox, QDoubleSpinBox))}
    fields = []
    for layout in vars(owner).values():
        if not isinstance(layout, InputHBoxLayouts):
            continue
        if layout.label is not None:
            label = plainLabel(layout.label.text())
        elif layout.checkbox is not None:
            label = plainLabel(layout.checkbox.text())
        else:
            continue
        spinboxes = [widget for widget in layout.widgets if id(widget) in names and names[id(widget)] not in excluded]
        for i, widget in enumerate(spinboxes):
            fields.append((names[id(widget)], f'{label} ({i + 1})' if len(spinboxes) > 1 else label, widget))
    return fields


def fieldWidgets(page: SimulationPage) -> Iterator[Tuple[str, QWidget]]:
    """Returns the input fields of the parameters of the composition tables and the target as (key, widget)"""

    for table in (page.table_beam, page.table_target):
        for row in table.rows:
            symbol = row.element.symbol
            if not symbol:
                continue
            for attribute, prefix in ROW_FIELDS:
                widget = getattr(row, attribute, None)
                if isinstance(widget, QWidget) and widget in row.row_widgets:
                    yield f'{prefix}_{symbol}', widget
            # fraction of the element in the beam
            abundance = getattr(row, 'abundance', None)
            if table is page.table_beam and isinstance(abundance, QWidget) and abundance in row.row_widgets:
                yield f'qubeam_{symbol}', abundance

    # atomic fractions of the first layer
    layers = page.target_layers.rows
    if layers:
        for i, row in enumerate(page.table_target.rows):
            if row.element.symbol and i < len(layers[0].element_cells):
                yield f'fraction_{row.element.symbol}', layers[0].element_cells[i]

    for name in ('thickness', 'segments'):
        widget = getattr(page.general_target_settings, name, None)
        if isinstance(widget, QWidget):
            yield name, widget


class ScanFieldOverlay(QWidget):
    """
    Mark of an input field that can be scanned (shown while the scan is enabled): a small triangle in the upper left
    corner, or, if several values are entered, the values on top of the field. A click opens the popup for the values

    :param scan: <ParameterScan> of the simulation tab
    :param field: input field
    """

    SIZE = 9

    def __init__(self, scan: ParameterScan, field: QWidget):
        super().__init__(field)
        self.scan = scan
        self.field = field
        self.key = ''
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        field.installEventFilter(self)

    def eventFilter(self, obj: Optional[QObject], event: Optional[QEvent]) -> bool:
        if obj is self.field and event is not None and event.type() in (QEvent.Type.Resize, QEvent.Type.EnabledChange):
            self.updateOverlay()
        return False

    def updateOverlay(self):
        """Shows the values of the field or the mark"""

        text = self.scan.valuesText(self.key)
        label = self.scan.labels.get(self.key, self.key)
        if text:
            self.setGeometry(self.field.rect())
            self.setToolTip(f'<b>{label}</b><br>Values of the parameter scan: {", ".join(self.scan.valuesStrings(self.key))}'
                            '<br>Click to change the values')
        else:
            self.setGeometry(0, 0, self.SIZE, self.SIZE)
            self.setToolTip(f'<b>{label}</b><br>Click to enter several values for the parameter scan')
        self.setVisible(self.scan.enabled and bool(self.key) and (bool(text) or self.field.isEnabled()))
        self.raise_()
        self.update()

    def paintEvent(self, event: Optional[QPaintEvent]):
        painter = QPainter(self)
        color = paletteQColor(0)
        text = self.scan.valuesText(self.key)
        if not text:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawPolygon(QPolygon([QPoint(0, 0), QPoint(self.SIZE, 0), QPoint(0, self.SIZE)]))
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        background = QColor(self.palette().base().color())
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(color)
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 2, 2)
        fill = QColor(color)
        fill.setAlpha(45)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 2, 2)
        painter.setPen(self.palette().text().color())
        text_rect = rect.adjusted(4, 0, -2, 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         self.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width()))

    def mousePressEvent(self, event: Optional[QMouseEvent]):
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self.scan.editValues(self.key, self.field)
            event.accept()


class ScanValuesEditor(QFrame):
    """
    Popup for the values of a parameter of the scan: a range (from, to, number, linear or logarithmic) fills the values,
    which can also be edited. The values are applied immediately

    :param scan: <ParameterScan> of the simulation tab
    :param parameter: parameter
    :param field: input field of the parameter (the popup is shown below it)
    """

    def __init__(self, scan: ParameterScan, parameter: ScanParameter, field: QWidget):
        super().__init__(field.window(), Qt.WindowType.Popup)
        self.scan = scan
        self.parameter = parameter
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAutoFillBackground(True)

        grid = QGridLayout(self)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setVerticalSpacing(4)
        grid.addWidget(QLabel(f'<b>{parameter.label}</b>: values of the parameter scan', self), 0, 0, 1, 2)

        # combo box: selection of the choices
        self.choices: Optional[QListWidget] = None
        if parameter.choices is not None:
            self.choices = QListWidget(self)
            self.choices.setToolTip('The simulations of the scan are run with each selected choice')
            combo = field if isinstance(field, QComboBox) else None
            for i, text in enumerate(parameter.choices):
                item = QListWidgetItem(text, self.choices)
                enabled = combo is None or choiceEnabled(combo, i)
                item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled if enabled else Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
            self.choices.setMinimumWidth(360)
            self.choices.setMaximumHeight(min(self.choices.sizeHintForRow(0) * len(parameter.choices) + 6, 300))
            self.choices.itemChanged.connect(lambda _: self.choicesChanged())
            grid.addWidget(self.choices, 1, 0, 1, 2)

        self.start = QDoubleSpinBox(self)
        self.stop = QDoubleSpinBox(self)
        for spinbox in (self.start, self.stop):
            spinbox.setRange(-1e12, 1e12)
            spinbox.setDecimals(4)
            spinbox.valueChanged.connect(lambda _: self.updateValues())
        self.number = QSpinBox(self)
        self.number.setRange(1, 1000)
        self.number.valueChanged.connect(lambda _: self.updateValues())
        self.scale = QComboBox(self)
        self.scale.addItems(SCALES)
        self.scale.setToolTip(
            'Spacing of the values of the range: linear or logarithmic with dense values at the start or at the end of the '
            'range (e.g. at grazing incidence for angles from 0° to 89°). Ranges that include 0 are shifted.'
        )
        self.scale.currentIndexChanged.connect(lambda _: self.updateValues())
        line = QHBoxLayout()
        range_widgets: List[QWidget] = [QLabel('from', self), self.start, QLabel('to', self), self.stop, QLabel('number', self), self.number, self.scale]
        for widget in range_widgets:
            line.addWidget(widget)
        values_label = QLabel('Values:', self)
        self.values = QLineEdit(self)
        self.values.setToolTip('Values of the parameter separated by commas (filled from the range, can be edited)')
        self.values.setMinimumWidth(360)
        self.values.textChanged.connect(lambda _: self.apply())
        if self.choices is None:
            grid.addLayout(line, 1, 0, 1, 2)
            grid.addWidget(values_label, 2, 0)
            grid.addWidget(self.values, 2, 1)
        else:
            # the values (indices of the choices) are set by the selection
            for widget in range_widgets + [values_label, self.values]:
                widget.setHidden(True)

        buttons = QHBoxLayout()
        self.count = QLabel('', self)
        buttons.addWidget(self.count, stretch=1)
        self.button_remove = QPushButton(getIcon('close'), 'Single value', self)
        self.button_remove.setToolTip('Remove the values of the scan, the value of the input field is used again')
        self.button_remove.clicked.connect(self.removeValues)
        buttons.addWidget(self.button_remove)
        self.button_done = QPushButton(getIcon('okay'), 'Done', self)
        self.button_done.clicked.connect(self.close)
        buttons.addWidget(self.button_done)
        grid.addLayout(buttons, 3, 0, 1, 2)

        state = scan.values.get(parameter.key)
        if state is None and parameter.choices is not None:
            # all choices that can be selected
            selectable = [i for i in range(len(parameter.choices)) if not isinstance(field, QComboBox) or choiceEnabled(field, i)]
            state = {'values': ', '.join(str(i) for i in selectable)}
        elif state is None:
            current = float(field.value()) if isinstance(field, (QSpinBox, QDoubleSpinBox)) else 0.
            state = defaultRange(parameter.key, current)
        self.setState(state)
        self.apply()

        # below the field, inside the screen
        position = field.mapToGlobal(QPoint(0, field.height()))
        screen = field.screen()
        if screen is not None:
            available = screen.availableGeometry()
            size = self.sizeHint()
            position.setX(max(available.left(), min(position.x(), available.right() - size.width())))
            if position.y() + size.height() > available.bottom():
                position.setY(field.mapToGlobal(QPoint(0, 0)).y() - size.height())
        self.move(position)
        self.values.setFocus()

    def setState(self, state: dict):
        """Sets the range and the values (state of ParameterScan.values)"""

        for widget in (self.start, self.stop, self.number, self.scale):
            widget.blockSignals(True)
        try:
            self.start.setValue(float(state.get('start', 0.)))
            self.stop.setValue(float(state.get('stop', 1.)))
            self.number.setValue(int(state.get('number', 5)))
            self.scale.setCurrentIndex(int(state.get('scale', 0)))
        except (TypeError, ValueError):
            pass
        for widget in (self.start, self.stop, self.number, self.scale):
            widget.blockSignals(False)
        if isinstance(state.get('values'), str):
            self.values.blockSignals(True)
            self.values.setText(state['values'])
            self.values.blockSignals(False)
        else:
            self.updateValues()
        if self.choices is not None:
            selected = parseValues(self.values.text(), True)
            self.choices.blockSignals(True)
            for i in range(self.choices.count()):
                notNone(self.choices.item(i)).setCheckState(Qt.CheckState.Checked if i in selected else Qt.CheckState.Unchecked)
            self.choices.blockSignals(False)

    def choicesChanged(self):
        """The selection of the choices sets the values (indices of the choices)"""

        if self.choices is None:
            return
        selected = [i for i in range(self.choices.count()) if notNone(self.choices.item(i)).checkState() == Qt.CheckState.Checked]
        self.values.setText(', '.join(str(i) for i in selected))

    def state(self) -> dict:
        if self.choices is not None:
            return {'values': self.values.text()}
        return {'start': self.start.value(), 'stop': self.stop.value(), 'number': self.number.value(),
                'scale': self.scale.currentIndex(), 'values': self.values.text()}

    def updateValues(self):
        """Fills the values from the range"""

        values = rangeValues(self.start.value(), self.stop.value(), self.number.value(), self.scale.currentIndex())
        if self.parameter.integer:
            values = np.unique(np.round(values).astype(int))
        self.values.setText(', '.join(formatRangeValue(value) for value in values))

    def apply(self):
        """Applies the values to the scan"""

        self.scan.setValues(self.parameter.key, self.state())
        number = len(parseValues(self.values.text(), self.parameter.integer))
        self.count.setText(f'{number} value{"s" if number != 1 else ""}, {self.scan.count()} simulations in the scan')

    def removeValues(self):
        self.scan.setValues(self.parameter.key, None)
        self.close()


class ParameterScan(QObject):
    """
    Parameter scan of a simulation tab (see the module description). The values of the parameters are entered in the input
    fields of the tab, the simulations are written into subfolders of the folder of the simulation

    :param page: <SimulationPage> of the simulation
    """

    # the values of the parameters have changed
    changed = pyqtSignal()

    def __init__(self, page: SimulationPage):
        super().__init__(page)

        self.page = page
        self.main_window = page.main_window
        self.configuration = page.simulation_configuration
        self.simulation_class = page.simulation_class
        self.analysis_class = type(page.evaluation_class.analysis)

        # scan shown (input fields with values)
        self.enabled = False
        # values of the parameters: {key: {start, stop, number, scale, values (text)}}, in the order of the scan
        self.values: Dict[str, dict] = {}
        # titles of other configurations of the same program (version of the simulation program)
        self.versions: List[str] = []
        # labels of the parameters (of the current input fields) and the texts of the choices of combo boxes
        self.labels: Dict[str, str] = {}
        self.choices: Dict[str, List[str]] = {}
        self.overlays: List[ScanFieldOverlay] = []
        self.editor: Optional[ScanValuesEditor] = None

        # simulations of the scan
        self.jobs: List[dict] = []
        self.queue: List[dict] = []
        self.running: List[dict] = []
        self.aborted = False
        self.parameter_names: List[str] = []
        self.results_loaded: List[Path] = []
        # comparison of the results (tab "Parameter scan results"), created when needed
        self.results: Optional[CompareWidget] = None

        # the marks of the fields are updated after changes of the tab (e.g. new elements)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.setInterval(100)
        self.refresh_timer.timeout.connect(self.refreshFields)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.updateProgress)

    # --- parameters and their values ---

    def otherVersions(self) -> list:
        """Other configurations of the same simulation program (with folder and binary)"""

        return [
            sc for sc in self.main_window.simulation_configs
            if sc is not self.configuration and sc.program_name == self.configuration.program_name
            and sc.folder is not None and sc.binary is not None
        ]

    def parameters(self) -> Dict[str, ScanParameter]:
        """Returns the parameters that can be scanned with their input fields"""

        page = self.page
        supports_azimuth = bool(getattr(getattr(page.simulation_class, 'default_values', None), 'supports_beta0', True))
        parameters = {parameter.key: parameter for parameter in scanParameters(page.makeArguments(), page.simulation_class.Name, supports_azimuth)}
        for key, widget in fieldWidgets(page):
            if key in parameters:
                parameters[key].widgets.append(widget)
        # numeric fields whose value is set in the field before the arguments are created: simulation settings, beam
        # and target settings (e.g. thin film thickness, global density) and fields of the rows (e.g. maximum fraction)
        fields: List[Tuple[str, str, QWidget]] = [
            (SETTINGS_KEYS.get(name, name), label, widget) for name, label, widget in settingsFields(page.settings_group_layout_settings)
        ]
        for owner in (page.general_beam_settings, page.general_target_settings):
            fields += settingsFields(owner, BEAM_TARGET_EXCLUDED)
        for table in (page.table_beam, page.table_target):
            for row in table.rows:
                symbol = row.element.symbol
                for attribute, prefix, label in ROW_WIDGET_FIELDS:
                    field = getattr(row, attribute, None)
                    if symbol and isinstance(field, (QSpinBox, QDoubleSpinBox)) and field in row.row_widgets:
                        fields.append((f'{prefix}_{symbol}', f'{label} of {symbol}', field))
        for key, label, widget in fields:
            if key in parameters:
                if widget not in parameters[key].widgets:
                    parameters[key].widgets.append(widget)
                continue
            parameter = ScanParameter(key, label, lambda a, w=widget: w.value(), None, integer=isinstance(widget, QSpinBox))
            parameter.widgets.append(widget)
            parameters[key] = parameter
        # combo boxes of the simulation settings and of the composition tables (the choice is set in the combo box)
        choices: List[Tuple[str, str, Any]] = [
            (name, label, getattr(page.settings_group_layout_settings, name, None)) for name, label in SETTINGS_CHOICES.items()
        ]
        for table in (page.table_beam, page.table_target):
            for row in table.rows:
                symbol = row.element.symbol
                for attribute, prefix, label in ROW_CHOICES:
                    combo = getattr(row, attribute, None)
                    if symbol and combo in row.row_widgets:
                        choices.append((f'{prefix}_{symbol}', f'{label} of {symbol}', combo))
        for key, label, widget in choices:
            if not isinstance(widget, QComboBox):
                continue
            if key in parameters:
                parameters[key].widgets.append(widget)
                continue
            parameter = ScanParameter(key, label, lambda a, w=widget: w.currentIndex(), None, choices=choiceTexts(widget))
            parameter.widgets.append(widget)
            parameters[key] = parameter
        return parameters

    def setValues(self, key: str, state: Optional[dict]) -> bool:
        """
        Sets the values of a parameter (None: the parameter is not scanned), returns False if too many parameters

        :param key: key of the parameter
        :param state: range and values (see ScanValuesEditor.state)
        """

        if state is None:
            if key not in self.values:
                return True
            self.values.pop(key)
        else:
            if self.values.get(key) == state:
                return True
            self.values[key] = dict(state)
        self.updateOverlays()
        self.page.setEdited(True)
        self.changed.emit()
        return True

    def setVersions(self, titles: List[str]):
        """Sets the other configurations of the scan (version of the simulation program)"""

        self.versions = list(titles)
        self.page.setEdited(True)
        self.changed.emit()

    def clearValues(self):
        """Removes all values of the scan"""

        self.values = {}
        self.versions = []
        self.updateOverlays()
        self.page.setEdited(True)
        self.changed.emit()

    def valuesStrings(self, key: str) -> List[str]:
        state = self.values.get(key)
        if state is None:
            return []
        choices = self.choices.get(key)
        if choices is not None:
            return [choices[i] if 0 <= i < len(choices) else str(i) for i in parseValues(state.get('values', ''), True)]
        return [formatRangeValue(value) for value in parseValues(state.get('values', ''))]

    def valuesText(self, key: str) -> str:
        """Short text of the values of a parameter (shown in its field) or '' if it is not scanned"""

        strings = self.valuesStrings(key)
        if not strings:
            return ''
        if len(strings) <= 4:
            return ', '.join(strings)
        return f'{strings[0]}, {strings[1]} … {strings[-1]} ({len(strings)})'

    def hasParameters(self) -> bool:
        """Returns if values of parameters (or versions) are entered"""

        return bool(self.versions) or any(self.valuesStrings(key) for key in self.values)

    def count(self) -> int:
        """Number of simulations of the scan"""

        count = 1
        for key in self.values:
            count *= max(len(self.valuesStrings(key)), 1)
        # the configuration of the tab and the other versions
        titles = {sc.title for sc in self.otherVersions()}
        return count * (1 + len([title for title in self.versions if title in titles]))

    def editValues(self, key: str, field: QWidget):
        """Opens the popup for the values of a parameter below its field"""

        parameter = self.parameters().get(key)
        if parameter is None:
            return
        if self.editor is not None and not sip.isdeleted(self.editor):
            self.editor.close()
        self.editor = ScanValuesEditor(self, parameter, field)
        self.editor.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.editor.show()

    # --- marks of the input fields ---

    def setEnabled(self, enabled: bool):
        """Shows or hides the marks and values of the input fields"""

        self.enabled = enabled
        if enabled:
            self.refreshFields()
        else:
            self.updateOverlays()

    def scheduleRefresh(self):
        """Updates the marks of the input fields after changes of the tab"""

        if self.enabled:
            self.refresh_timer.start()

    def refreshFields(self):
        """Adds marks to the input fields that can be scanned and updates them"""

        try:
            parameters = self.parameters()
        except Exception:
            return
        self.labels = {key: parameter.label for key, parameter in parameters.items()}
        self.choices = {key: parameter.choices for key, parameter in parameters.items() if parameter.choices is not None}
        overlays = []
        for key, parameter in parameters.items():
            for widget in parameter.widgets:
                overlay = next((child for child in widget.findChildren(ScanFieldOverlay, options=Qt.FindChildOption.FindDirectChildrenOnly)), None)
                if overlay is None:
                    overlay = ScanFieldOverlay(self, widget)
                overlay.key = key
                overlays.append(overlay)
        # fields that are not scannable anymore (e.g. an element was removed from the target)
        for overlay in self.overlays:
            if not sip.isdeleted(overlay) and overlay not in overlays:
                overlay.key = ''
        self.overlays = overlays + [overlay for overlay in self.overlays if not sip.isdeleted(overlay) and overlay not in overlays]
        self.updateOverlays()

    def updateOverlays(self):
        self.overlays = [overlay for overlay in self.overlays if not sip.isdeleted(overlay)]
        for overlay in self.overlays:
            overlay.updateOverlay()

    # --- simulations of the scan ---

    def plan(self) -> Tuple[List[dict], List[str]]:
        """
        Returns the simulations of the scan (without writing them) as list of {values, label, assignments, configuration}
        and the labels of the parameters. Parameters without input field (e.g. of a removed element) are skipped
        """

        parameters = self.parameters()
        dimensions: List[list] = []
        names = []
        for key in self.values:
            parameter = parameters.get(key)
            parsed = parseValues(self.values[key].get('values', ''), parameter.integer if parameter else False)
            if parameter is None or not parsed:
                continue
            dimensions.append([(parameter, value) for value in parsed])
            names.append(parameter.label)
        versions = [sc for sc in self.otherVersions() if sc.title in self.versions]
        if versions:
            dimensions.append([(None, sc) for sc in [self.configuration] + versions])
            names.append('Version')
        simulations = []
        for combination in product(*dimensions):
            values: list = []
            labels = []
            configuration = self.configuration
            assignments = []
            for parameter, value in combination:
                if parameter is None:
                    configuration = value
                    values.append(value.title)
                    labels.append(formatValue(value.title))
                    continue
                # combo boxes: the text of the choice (the folder name contains its index)
                choices = parameter.choices
                values.append(choices[value] if choices is not None and 0 <= value < len(choices) else value)
                labels.append(f'{parameter.key}_{formatValue(value)}')
                assignments.append((parameter, value))
            simulations.append({'values': values, 'label': '__'.join(labels), 'assignments': assignments, 'configuration': configuration})
        return simulations, names

    def arguments(self, assignments: List[Tuple[ScanParameter, Any]]) -> SimulationArguments:
        """Returns the arguments of the tab with the values of a simulation of the scan"""

        restore: List[Tuple[Any, Any, bool]] = []
        for parameter, value in assignments:
            if parameter.apply is not None:
                continue
            for widget in parameter.widgets:
                if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    restore.append((widget, widget.value(), widget.signalsBlocked()))
                    widget.blockSignals(True)
                    setSpinboxValue(widget, value)
                elif isinstance(widget, QComboBox) and 0 <= int(value) < widget.count():
                    restore.append((widget, widget.currentIndex(), widget.signalsBlocked()))
                    widget.blockSignals(True)
                    widget.setCurrentIndex(int(value))
        try:
            arguments = self.page.makeArguments()
        finally:
            for widget, value, blocked in reversed(restore):
                if isinstance(widget, QComboBox):
                    widget.setCurrentIndex(int(value))
                else:
                    setSpinboxValue(widget, value)
                widget.blockSignals(blocked)
        for parameter, value in assignments:
            if parameter.apply is not None:
                parameter.apply(arguments, value)
        return arguments

    def description(self, simulations: List[dict]) -> dict:
        """Description of the scan (scan.json): settings of the scan, parameters and values of the simulations"""

        return {
            'rows': [dict(state, key=key) for key, state in self.values.items()],
            'versions': list(self.versions),
            'parameters': list(self.parameter_names),
            'runs': [{'folder': simulation['label'], 'values': simulation['values']} for simulation in simulations]
        }

    def writeDescription(self, simulations: Optional[List[dict]] = None):
        """Writes scan.json into the folder of the simulation"""

        folder = self.configuration.save_folder
        if folder is None or not folder.is_dir():
            return
        if simulations is None:
            try:
                simulations, self.parameter_names = self.plan()
            except Exception:
                return
        try:
            with open(folder / SCAN_FILE, 'w', encoding='utf-8') as file:
                dump(self.description(simulations), file, indent=2)
        except OSError:
            pass

    def state(self) -> dict:
        """Settings of the scan (for the configuration of the tab)"""

        return {'rows': [dict(state, key=key) for key, state in self.values.items()], 'versions': list(self.versions)}

    def setState(self, state: dict):
        """Sets the settings of the scan from state() or scan.json"""

        self.values = {}
        labels = {parameter.label: key for key, parameter in self.safeParameters().items()}
        for row in state.get('rows', []):
            if not isinstance(row, dict):
                continue
            # scans of older versions only store the label of the parameter
            key = row.get('key') or labels.get(str(row.get('label')))
            if isinstance(key, str) and key:
                self.values[key] = {name: row[name] for name in ('start', 'stop', 'number', 'scale', 'values') if name in row}
        versions = state.get('versions')
        self.versions = [str(title) for title in versions] if isinstance(versions, list) else []
        if self.enabled:
            self.refreshFields()
        else:
            self.updateOverlays()
        self.changed.emit()

    def safeParameters(self) -> Dict[str, ScanParameter]:
        try:
            return self.parameters()
        except Exception:
            return {}

    def loadFolder(self, folder: Optional[Path]):
        """Reads the scan of a folder (scan.json): its values and the state of its simulations"""

        scan = readScanDescription(folder) if folder is not None else None
        if scan is None:
            self.values = {}
            self.versions = []
            self.showJobs([])
            self.updateOverlays()
            self.changed.emit()
            return
        self.setState(scan)
        self.loadRuns()

    def loadRuns(self):
        """Shows the simulations of the scan of the folder (from scan.json) with their state and resets the results"""

        folder = self.configuration.save_folder
        scan = readScanDescription(folder) if folder is not None else None
        if folder is None or scan is None:
            self.showJobs([])
            return
        self.parameter_names = [str(name) for name in scan.get('parameters', [])]
        jobs = []
        for run in scan.get('runs', []):
            if not isinstance(run, dict) or 'folder' not in run:
                continue
            job_folder = folder / str(run['folder'])
            log_file = job_folder / LOG_FILE
            log = log_file.read_text(encoding='utf-8', errors='replace') if log_file.is_file() else ''
            status = 'not run'
            if log or any(job_folder.glob('output*')):
                problem = self.simulation_class.runFailed(job_folder, log, 0, self.configuration.version)
                status = 'finished' if problem is None else f'failed ({problem})'
            jobs.append({'values': list(run.get('values', [])), 'label': str(run['folder']), 'folder': job_folder, 'log': log,
                         'status': status, 'process': None, 'configuration': self.configuration, 'simulation': self.simulation_class})
        self.showJobs(jobs)

    def prepareJobs(self, check_warnings: bool = True) -> Optional[List[dict]]:
        """Writes the input files of all simulations of the scan and returns the jobs or None if the scan can not be run"""

        folder = self.configuration.save_folder
        if folder is None:
            return None
        simulations, names = self.plan()
        if not simulations or not names:
            showMessageBox(self.page, QMessageBox.Icon.Warning, 'Warning!', 'No values for the parameter scan',
                           info_message='Click on the mark in the corner of an input field to enter several values.')
            return None

        jobs: List[Dict[str, Any]] = []
        programs: Dict[int, Any] = {}
        for simulation in simulations:
            sc = simulation['configuration']
            if sc is self.configuration:
                program = self.simulation_class
            else:
                if id(sc) not in programs:
                    programs[id(sc)] = sc.program_class()
                    programs[id(sc)].update(sc.folder, sc.binary, sc.version)
                    programs[id(sc)].updateElements(sc.folder, sc.version)
                program = programs[id(sc)]
            jobs.append(dict(simulation, simulation=program, arguments=self.arguments(simulation['assignments']),
                             folder=folder / simulation['label'], log='', status='waiting', process=None))

        problems: List[str] = []
        for job in jobs:
            for problem in job['simulation'].checkArguments(job['arguments'], job['configuration'].version):
                if problem not in problems:
                    problems.append(problem)
        if problems:
            showMessageBox(self.page, QMessageBox.Icon.Warning, 'Warning!', 'The simulation does not accept these parameters',
                           detailed_message='\n'.join(problems))
            return None

        # warnings of all simulations (the user decides)
        warnings: List[str] = []
        if check_warnings:
            for job in jobs:
                for warning in job['simulation'].checkWarnings(job['arguments'], job['configuration'].version):
                    if warning not in warnings:
                        warnings.append(warning)
        if warnings:
            _, result = showMessageBox(
                self.page, QMessageBox.Icon.Warning, 'Warning!', 'Some simulations might fail, give wrong results or create very large files',
                info_message='Press "OK" to run the scan anyway.', detailed_message='\n\n'.join(warnings),
                standard_buttons=QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel, expand_details=True
            )
            if result == QMessageBox.StandardButton.Cancel:
                return None

        # input files (the output of previous runs is removed) and the description of the scan
        for job in jobs:
            if job['folder'].is_dir():
                for path in job['folder'].iterdir():
                    if path.is_file():
                        path.unlink()
            sc = job['configuration']
            job['files'] = writeInputFiles(job['simulation'], job['arguments'], job['folder'], sc.folder, sc.version)
        self.parameter_names = names
        self.writeDescription(simulations)
        return jobs

    def showJobs(self, jobs: List[dict]):
        """Shows the simulations of the scan in the table of the tab "Run status" and in the lists of the tab"""

        self.jobs = jobs
        table = self.page.scan_runs
        table.clear()
        table.setColumnCount(len(self.parameter_names) + 1)
        table.setHorizontalHeaderLabels(['Status'] + self.parameter_names)
        table.setRowCount(len(jobs))
        for i, job in enumerate(jobs):
            job['item'] = QTableWidgetItem()
            job['item'].setToolTip(pathToStr(job['folder']))
            table.setItem(i, 0, job['item'])
            for j, value in enumerate(job['values']):
                item = QTableWidgetItem(value if isinstance(value, str) else f'{value:g}')
                alignment = Qt.AlignmentFlag.AlignLeft if isinstance(value, str) else Qt.AlignmentFlag.AlignRight
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | alignment)
                table.setItem(i, j + 1, item)
            self.setJobStatus(job, job['status'])
        header = table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            header.setStretchLastSection(False)
        if self.results is not None:
            self.results.clearEntries()
        self.results_loaded = []
        self.page.updateScanLists()

    def jobText(self, job: dict) -> str:
        """Values of a simulation of the scan as text, e.g. "Energy of Ar [eV] = 500, Angle of incidence of Ar [°] = 0" """

        return ', '.join(f'{name} = {value if isinstance(value, str) else f"{value:g}"}' for name, value in zip(self.parameter_names, job['values']))

    def run(self, check_warnings: bool = True) -> bool:
        """Writes the input files and starts the simulations of the scan, returns if the scan was started"""

        jobs = self.prepareJobs(check_warnings)
        if not jobs:
            return False
        self.showJobs(jobs)
        self.queue = list(jobs)
        self.running = []
        self.aborted = False
        page = self.page
        page.setProcessWidgetsEnabled(False)
        page.run_progress.startTiming()
        page.run_progress.setValue(0)
        page.setRunStatus(page.RunStatus.RUNNING)
        page.setProgressStatus(0)
        self.startJobs()
        self.timer.start()
        self.updateProgress()
        return True

    def startJobs(self):
        """Starts simulations of the queue while the limit of simultaneous simulations of all tabs is not reached"""

        while self.queue and self.main_window.freeRunSlots() > 0:
            job = self.queue.pop(0)
            sc = job['configuration']
            qcmd, qpipe, _ = job['simulation'].cmd(sc.binary, job['folder'], job['files'][1], sc.version)
            process = QProcess(self)
            process.setWorkingDirectory(pathToStr(job['folder']))
            if qpipe:
                process.setStandardInputFile(pathToStr(job['folder'] / job['files'][1]))
            process.setProgram(qcmd)
            process.readyRead.connect(lambda job=job: self.readLog(job))
            process.finished.connect(lambda code, status, job=job: self.jobFinished(job, code, status))
            # the simulations run with a lower priority, so that the GUI stays responsive
            process.started.connect(lambda process=process: lowerProcessPriority(process.processId()))
            job['process'] = process
            self.setJobStatus(job, 'running')
            self.running.append(job)
            process.start()

    def readLog(self, job: dict):
        """Reads the output of a simulation"""

        text = bytes(job['process'].readAll().data()).decode(getpreferredencoding(), 'ignore')
        job['log'] = (job['log'] + text)[-20000:]
        job['last_log'] = text
        self.page.showScanLog(job, text)

    def jobFinished(self, job: dict, exit_code: int, exit_status):
        """A simulation of the scan has finished"""

        if job in self.running:
            self.running.remove(job)
        sc = job['configuration']
        if exit_status == QProcess.ExitStatus.NormalExit:
            problem = job['simulation'].runFailed(job['folder'], job['log'], exit_code, sc.version)
        else:
            problem = 'aborted'
        self.setJobStatus(job, 'finished' if problem is None else f'failed ({problem})')
        try:
            (job['folder'] / LOG_FILE).write_text(job['log'], encoding='utf-8')
        except OSError:
            pass
        job['process'].deleteLater()
        job['process'] = None
        if not self.running and not self.queue:
            self.finished()
        # next simulations (of all tabs)
        self.main_window.startQueuedSimulations()
        self.updateProgress()

    def finished(self):
        """All simulations of the scan have finished"""

        page = self.page
        self.timer.stop()
        failed = [job for job in self.jobs if job['status'] != 'finished']
        page.run_progress.stopTiming()
        page.run_progress.setValue(100)
        if self.aborted:
            page.setRunStatus(page.RunStatus.ABORTED)
        elif failed:
            page.setRunStatus(page.RunStatus.ERROR)
        else:
            page.setRunStatus(page.RunStatus.DONE)
        page.setProcessWidgetsEnabled(True)
        page.setProgressStatus(100)
        finished = len(self.jobs) - len(failed)
        self.main_window.writeStatusBar(f'Parameter scan of "{self.configuration.title}": {finished} of {len(self.jobs)} simulations finished', 8000)
        page.updateScanLists()
        if page.resultsShown():
            self.refreshResults()
        # "Run all"
        self.main_window.simulationFinished(page)

    def setJobStatus(self, job: dict, status: str, percent: Optional[float] = None):
        """
        Shows the status of a simulation of the scan with an icon

        :param job: simulation of the scan
        :param status: waiting, running, finished, not started, not run or failed (...)
        :param percent: (optional) progress of a running simulation
        """

        if job.get('shown_status') != status:
            job['item'].setIcon(getIcon(STATUS_ICONS.get(status, 'error')))
            if status.startswith('failed'):
                job['item'].setToolTip(f'{pathToStr(job["folder"])}\n{status}\nThe output of the simulation is in {LOG_FILE}')
            job['shown_status'] = status
        job['status'] = status
        text = f'{status} ({percent:.0f} %)' if percent is not None and percent >= 0 else status
        if job['item'].text() != text:
            job['item'].setText(text)

    def progress(self) -> int:
        """Overall progress of the scan (in %)"""

        if not self.jobs:
            return 0
        total = 0.
        for job in self.jobs:
            if job['status'] == 'running':
                total += max(job.get('percent', 0), 0)
            elif job['status'] != 'waiting':
                total += 100
        return int(total / len(self.jobs))

    def updateProgress(self):
        """Progress of the running simulations and of the scan (progress bar and status of the tab)"""

        if not self.jobs:
            return
        for job in self.jobs:
            if job['status'] == 'running':
                try:
                    job['percent'] = job['simulation'].getProgress(job['folder'], job.get('last_log', ''), job['configuration'].version)
                except Exception:
                    job['percent'] = -1
                self.setJobStatus(job, 'running', job['percent'])
        if not self.isRunning():
            return
        progress = self.progress()
        self.page.run_progress.setValue(progress)
        self.page.setProgressStatus(progress)
        done = sum(job['status'] not in ('waiting', 'running') for job in self.jobs)
        self.page.run_status_text.setText(f'Scan {done}/{len(self.jobs)}')

    def abort(self):
        """Aborts the scan"""

        if not self.isRunning():
            return
        self.aborted = True
        for job in self.queue:
            self.setJobStatus(job, 'not started')
        self.queue = []
        for job in list(self.running):
            job['process'].kill()
        if not self.running:
            self.finished()

    def refreshResults(self):
        """Adds the finished simulations of the scan to the results (the results are loaded when they are shown)"""

        if self.results is None:
            return
        finished = [job for job in self.jobs if job['status'] == 'finished' and job['folder'] not in self.results_loaded]
        if not finished:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.results.addFolders([job['folder'] for job in finished],
                                    parameters=[dict(zip(self.parameter_names, job['values'])) for job in finished])
        finally:
            QApplication.restoreOverrideCursor()
        self.results_loaded += [job['folder'] for job in finished]

    def createResults(self) -> CompareWidget:
        """Comparison of the results of the scan"""

        if self.results is None:
            self.results = CompareWidget(self.page, self.analysis_class, self.simulation_class.element_data)
        return self.results

    def isRunning(self) -> bool:
        """Returns if simulations of the scan run or wait"""

        return bool(self.running or self.queue)

    def stop(self, ask: bool = True) -> bool:
        """
        Aborts running simulations of the scan (after asking), returns False if the user cancels

        :param ask: (optional) ask before running simulations are aborted
        """

        if self.isRunning():
            if ask:
                _, result = showMessageBox(
                    self.page, QMessageBox.Icon.Question, 'Abort scan?', 'The simulations of the parameter scan are still running',
                    info_message='They will be aborted.',
                    standard_buttons=QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
                )
                if result == QMessageBox.StandardButton.Cancel:
                    return False
            running = list(self.running)
            self.abort()
            for job in running:
                if job['process'] is not None:
                    job['process'].waitForFinished(3000)
        self.timer.stop()
        return True


def readScanDescription(folder: Path) -> Optional[dict]:
    """
    Returns the description of a parameter scan (scan.json in its folder) or None. Scans of older versions of the GUI only
    contain the labels of the parameters: the rows of the parameters are derived from them

    :param folder: folder of the scan
    """

    try:
        with open(folder / SCAN_FILE, 'r', encoding='utf-8') as file:
            scan = load(file)
    except (OSError, ValueError):
        return None
    if not isinstance(scan, dict) or not isinstance(scan.get('runs'), list) or not isinstance(scan.get('parameters'), list):
        return None
    if not isinstance(scan.get('rows'), list):
        rows = []
        for i, label in enumerate(scan['parameters']):
            values = []
            for run in scan['runs']:
                run_values = run.get('values', []) if isinstance(run, dict) else []
                if i < len(run_values) and run_values[i] not in values:
                    values.append(run_values[i])
            rows.append({'label': label, 'values': ', '.join(f'{value:g}' if isinstance(value, (int, float)) else str(value) for value in values)})
        scan['rows'] = rows
    return scan
