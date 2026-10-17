"""
Parameter scan: a series of simulations in which up to 5 parameters of a simulation tab are varied (all combinations).
Parameters: energies and angles of the beam species, energies and properties of the elements, the composition and
thickness of the target, fluence, number of projectiles and the version of the simulation program (other configurations).
The scan is shown in the sub-tabs "Parameter scan" and "Parameter scan results" of the simulation tab (enabled with a
checkbox in its toolbar), the rest of the GUI can be used while it runs. The simulations are written into subfolders of
a scan folder in the folder of the simulation (described in scan.json, which also allows to open the scan again), run
with at most GlobalConf.max_parallel_runs at the same time (with a lower priority than the GUI) and compared in a
<CompareWidget>
"""

from __future__ import annotations
from typing import List, Optional, Callable, Any, Dict, TYPE_CHECKING
from copy import deepcopy
from itertools import product
from json import dump, load
from locale import getpreferredencoding
from os import cpu_count
from pathlib import Path
from re import sub

import numpy as np

from PyQt6.QtCore import Qt, QProcess, QTimer
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QLineEdit, QPushButton, QDoubleSpinBox, QSpinBox, QListWidget,
    QListWidgetItem, QProgressBar, QMessageBox, QGridLayout, QFileDialog, QWidget, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QApplication
)

from GlobalConf import GlobalConf

from Pages.CompareDialog import CompareWidget, SCAN_FILE

from Simulations.Simulations import writeInputFiles

from Utility.Dialogs import showMessageBox
from Utility.Functions import pathToStr, lowerProcessPriority
from Utility.Icons import getIcon
from Utility.Typing import notNone

if TYPE_CHECKING:
    from Pages.ProgramPage import SimulationPage


# maximum number of parameters of a scan
MAX_PARAMETERS = 5

# scales of the range of values
SCALES = ['linear', 'logarithmic (dense at start)', 'logarithmic (dense at end)']

# icons of the states of the simulations of a scan
STATUS_ICONS = {'waiting': 'clock', 'running': 'play', 'finished': 'okay', 'not started': 'abort', 'not run': 'abort'}


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
    :param apply: function that sets a value in the arguments
    :param integer: integer values
    """

    def __init__(self, key: str, label: str, current: Callable[..., Any], apply: Callable[..., None], integer: bool = False):
        self.key = key
        self.label = label
        self.current = current
        self.apply = apply
        self.integer = integer


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


def setThickness(arguments, value: float):
    """Sets the thickness of the target, the layers keep their relative thickness"""

    total = sum(layer.thickness for layer in arguments.structure)
    for layer in arguments.structure:
        layer.thickness = layer.thickness * value / total if total > 0 else value / max(len(arguments.structure), 1)
    arguments.target_args.thickness = float(value)


def scanParameters(arguments, simulation_name: str, supports_azimuth: bool = True) -> List[ScanParameter]:
    """Returns the parameters that can be scanned for the arguments of a simulation"""

    parameters = []
    for i, row in enumerate(arguments.beam_rows):
        if not row.symbol:
            continue
        symbol = row.symbol
        parameters.append(ScanParameter(f'energy_{symbol}', f'Energy of {symbol} [eV]', lambda a, i=i: a.beam_rows[i].energy,
                                        lambda a, v, i=i: setattr(a.beam_rows[i], 'energy', float(v))))
        parameters.append(ScanParameter(f'angle_{symbol}', f'Angle of incidence of {symbol} [°]', lambda a, i=i: a.beam_rows[i].angle,
                                        lambda a, v, i=i: setattr(a.beam_rows[i], 'angle', float(v))))
        if supports_azimuth and simulation_name == 'SDTrimSP':
            parameters.append(ScanParameter(f'azimuth_{symbol}', f'Azimuthal angle of {symbol} [°]',
                                            lambda a, i=i: a.beam_rows[i].get('azimuth') or 0.,
                                            lambda a, v, i=i: a.beam_rows[i].optional.__setitem__('azimuth', float(v))))

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


class ParameterRow(QFrame):
    """Inputs of one scanned parameter: parameter, range (from, to, number, scale) and in a second line the values"""

    def __init__(self, scan_page: ParameterScanPage):
        super().__init__(scan_page)
        self.scan_page = scan_page
        self.setFrameShape(QFrame.Shape.StyledPanel)
        grid = QGridLayout(self)
        grid.setContentsMargins(6, 4, 6, 4)
        grid.setVerticalSpacing(2)
        self.parameter = QComboBox(self)
        for parameter in scan_page.parameters:
            self.parameter.addItem(parameter.label, parameter.key)
        if scan_page.other_versions:
            self.parameter.addItem('Version (configurations)', 'version')
        self.parameter.setMinimumWidth(260)
        self.start = QDoubleSpinBox(self)
        self.stop = QDoubleSpinBox(self)
        for spinbox in (self.start, self.stop):
            spinbox.setRange(-1e12, 1e12)
            spinbox.setDecimals(4)
            spinbox.valueChanged.connect(lambda _: self.updateValues())
        self.number = QSpinBox(self)
        self.number.setRange(1, 1000)
        self.number.setValue(5)
        self.number.valueChanged.connect(lambda _: self.updateValues())
        self.scale = QComboBox(self)
        self.scale.addItems(SCALES)
        self.scale.setToolTip(
            'Spacing of the values of the range: linear or logarithmic with dense values at the start or at the end of the '
            'range (e.g. at grazing incidence for angles from 0° to 89°). Ranges that include 0 are shifted.'
        )
        self.scale.currentIndexChanged.connect(lambda _: self.updateValues())
        self.values = QLineEdit(self)
        self.values.setToolTip('Values of the parameter separated by commas (filled from the range, can be edited)')
        self.values.textChanged.connect(lambda _: scan_page.updateCount())
        self.remove = QPushButton(getIcon('close'), '', self)
        self.remove.setToolTip('Remove this parameter from the scan')
        self.remove.clicked.connect(lambda: scan_page.removeParameterRow(self))

        line = QHBoxLayout()
        for widget in (self.parameter, QLabel('from'), self.start, QLabel('to'), self.stop, QLabel('number'), self.number, self.scale):
            line.addWidget(widget)
        line.addStretch(1)
        grid.addLayout(line, 0, 0, 1, 2)
        grid.addWidget(self.remove, 0, 2)
        grid.addWidget(QLabel('Values:'), 1, 0)
        grid.addWidget(self.values, 1, 1, 1, 2)
        grid.setColumnStretch(1, 1)
        self.parameter.currentIndexChanged.connect(lambda _: self.parameterChanged())

    def key(self) -> str:
        return self.parameter.currentData() or ''

    def scanParameter(self) -> Optional[ScanParameter]:
        return next((parameter for parameter in self.scan_page.parameters if parameter.key == self.key()), None)

    def parameterChanged(self):
        """Default range around the current value"""

        is_version = self.key() == 'version'
        for widget in (self.start, self.stop, self.number, self.scale, self.values):
            widget.setEnabled(not is_version)
        self.scan_page.versions.setHidden(not any(row.key() == 'version' for row in self.scan_page.rows))
        self.scan_page.updateFolder()
        parameter = self.scanParameter()
        if parameter is None:
            self.scan_page.updateCount()
            return
        try:
            current = float(parameter.current(self.scan_page.page.makeArguments()) or 0.)
        except Exception:
            current = 0.
        for widget in (self.start, self.stop, self.number, self.scale):
            widget.blockSignals(True)
        if parameter.key.startswith(('angle_', 'azimuth_')):
            self.start.setValue(0.)
            self.stop.setValue(80. if parameter.key.startswith('angle_') else 90.)
            self.number.setValue(9 if parameter.key.startswith('angle_') else 4)
            self.scale.setCurrentIndex(0)
        elif parameter.key.startswith('fraction_'):
            self.start.setValue(0.1)
            self.stop.setValue(0.9)
            self.number.setValue(5)
            self.scale.setCurrentIndex(0)
        elif current > 0:
            logarithmic = parameter.key.startswith('energy_')
            self.start.setValue(current / 10 if logarithmic else current / 2)
            self.stop.setValue(current * 10 if logarithmic else current * 2)
            self.number.setValue(5)
            self.scale.setCurrentIndex(1 if logarithmic else 0)
        else:
            self.scale.setCurrentIndex(0)
        for widget in (self.start, self.stop, self.number, self.scale):
            widget.blockSignals(False)
        self.updateValues()

    def updateValues(self):
        """Fills the values from the range"""

        values = rangeValues(self.start.value(), self.stop.value(), self.number.value(), self.scale.currentIndex())
        parameter = self.scanParameter()
        if parameter is not None and parameter.integer:
            values = np.unique(np.round(values).astype(int))
        self.values.setText(', '.join(formatRangeValue(value) for value in values))

    def scanValues(self) -> list:
        """Values of the scan (configurations for the version)"""

        if self.key() == 'version':
            return [sc for i, sc in enumerate(self.scan_page.other_versions) if notNone(self.scan_page.versions.item(i)).checkState() == Qt.CheckState.Checked]
        values = []
        for text in self.values.text().replace(';', ',').split(','):
            try:
                values.append(float(text))
            except ValueError:
                pass
        return values

    def state(self) -> dict:
        """Returns the settings of the row (for scan.json and the configuration)"""

        return {'key': self.key(), 'start': self.start.value(), 'stop': self.stop.value(), 'number': self.number.value(),
                'scale': self.scale.currentIndex(), 'values': self.values.text()}

    def setState(self, state: dict):
        """Sets the settings of the row from state()"""

        index = self.parameter.findData(state.get('key'))
        if index < 0:
            return
        for widget in (self.parameter, self.start, self.stop, self.number, self.scale):
            widget.blockSignals(True)
        self.parameter.setCurrentIndex(index)
        try:
            self.start.setValue(float(state.get('start', self.start.value())))
            self.stop.setValue(float(state.get('stop', self.stop.value())))
            self.number.setValue(int(state.get('number', self.number.value())))
            self.scale.setCurrentIndex(int(state.get('scale', 0)))
        except (TypeError, ValueError):
            pass
        for widget in (self.parameter, self.start, self.stop, self.number, self.scale):
            widget.blockSignals(False)
        is_version = self.key() == 'version'
        for widget in (self.start, self.stop, self.number, self.scale, self.values):
            widget.setEnabled(not is_version)
        if isinstance(state.get('values'), str):
            self.values.setText(state['values'])
        else:
            self.updateValues()


class ParameterScanPage(QWidget):
    """
    Tab "Parameter scan" of a simulation tab (shown with the checkbox in its toolbar). The scan uses the current parameters
    of the simulation, its simulations are written into a folder in the folder of the simulation. The results are shown in
    the tab "Parameter scan results" (self.results). The settings of the scan are stored in the simulation configuration,
    so the scan (and its results) are shown again after a restart

    :param page: <SimulationPage> of the simulation
    """

    def __init__(self, page: SimulationPage):
        super().__init__(page)

        self.page = page
        self.main_window = page.main_window
        self.configuration = page.simulation_configuration
        self.simulation_class = page.simulation_class
        self.analysis_class = type(page.evaluation_class.analysis)
        self.jobs: List[dict] = []
        self.queue: List[dict] = []
        self.running: List[dict] = []
        self.parameter_names: List[str] = []
        self.results_loaded: List[Path] = []
        # automatic folder of the scan (changes with the parameters until the user selects a folder)
        self.auto_folder = ''

        supports_azimuth = bool(getattr(getattr(page.simulation_class, 'default_values', None), 'supports_beta0', True))
        self.parameters = scanParameters(page.makeArguments(), page.simulation_class.Name, supports_azimuth)
        self.other_versions = [
            sc for sc in page.main_window.simulation_configs
            if sc.program_name == self.configuration.program_name and sc.folder is not None and sc.binary is not None
        ]
        if len(self.other_versions) < 2:
            self.other_versions = []
        self.rows: List[ParameterRow] = []

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f'Simulations with the current parameters of this tab in which up to {MAX_PARAMETERS} parameters are varied '
            '(all combinations are simulated):'
        ))
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(4)
        layout.addLayout(self.rows_layout)

        buttons_parameters = QHBoxLayout()
        self.button_add = QPushButton(getIcon('add'), 'Add parameter', self)
        self.button_add.clicked.connect(lambda: self.addParameterRow())
        buttons_parameters.addWidget(self.button_add)
        self.count = QLabel('', self)
        buttons_parameters.addWidget(self.count)
        buttons_parameters.addStretch(1)
        layout.addLayout(buttons_parameters)

        # versions: other configurations of the same simulation program
        self.versions = QListWidget(self)
        for sc in self.other_versions:
            item = QListWidgetItem(f'{sc.title} ({sc.version})')
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.versions.addItem(item)
        self.versions.itemChanged.connect(lambda _: self.updateCount())
        self.versions.setMaximumHeight(120)
        self.versions.setHidden(True)
        layout.addWidget(self.versions)

        # folder of the scan
        grid = QGridLayout()
        grid.addWidget(QLabel('Scan folder:'), 0, 0)
        self.folder = QLineEdit(self)
        self.folder.setToolTip('Each simulation of the scan is written into a subfolder of this folder (by default a folder in the '
                               'folder of the simulation)')
        grid.addWidget(self.folder, 0, 1)
        self.button_folder = QPushButton(getIcon('open'), '', self)
        self.button_folder.setToolTip('Select the folder of the scan')
        self.button_folder.clicked.connect(self.selectFolder)
        grid.addWidget(self.button_folder, 0, 2)
        self.button_open = QPushButton(getIcon('open_workdir'), 'Open scan...', self)
        self.button_open.setToolTip('Open an existing scan (a folder with scan.json): its parameters, the state of its '
                                    'simulations and its results are shown without running it again')
        self.button_open.clicked.connect(lambda: self.openScan())
        grid.addWidget(self.button_open, 0, 3)
        layout.addLayout(grid)

        # runs
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(True)
        self.progress.setFormat('%p %')
        layout.addWidget(self.progress)
        self.runs = QTableWidget(0, 1, self)
        self.runs.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.runs.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.runs.setAlternatingRowColors(True)
        self.runs.setShowGrid(False)
        self.runs.setWordWrap(False)
        vertical_header = notNone(self.runs.verticalHeader())
        vertical_header.setVisible(False)
        vertical_header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        vertical_header.setDefaultSectionSize(self.fontMetrics().height() + 4)
        layout.addWidget(self.runs, stretch=1)

        buttons = QHBoxLayout()
        self.button_run = QPushButton(getIcon('play'), 'Run scan', self)
        self.button_run.setToolTip('Write the input files of all simulations of the scan and run them (at most "Simultaneous '
                                   'simulations" at the same time, with a lower priority than the GUI)')
        self.button_run.clicked.connect(self.run)
        self.button_abort = QPushButton(getIcon('abort'), 'Abort', self)
        self.button_abort.clicked.connect(self.abort)
        self.button_abort.setEnabled(False)
        self.button_results = QPushButton(getIcon('chart'), 'Show results', self)
        self.button_results.setToolTip('Show the results of the finished simulations of the scan in the tab "Parameter scan results"')
        self.button_results.clicked.connect(lambda: self.page.tab_widget.setCurrentWidget(self.results))
        self.button_results.setEnabled(False)
        buttons.addWidget(self.button_run)
        buttons.addWidget(self.button_abort)
        buttons.addStretch(1)
        buttons.addWidget(self.button_results)
        layout.addLayout(buttons)

        # results of the scan
        self.results = CompareWidget(page, self.analysis_class, self.simulation_class.element_data)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.updateProgress)

        self.addParameterRow()

    # --- parameters ---

    def addParameterRow(self, key: Optional[str] = None) -> Optional[ParameterRow]:
        """Adds a parameter to the scan (the first parameter that is not scanned yet or key)"""

        if len(self.rows) >= MAX_PARAMETERS:
            return None
        row = ParameterRow(self)
        used = [r.key() for r in self.rows]
        if key:
            index = row.parameter.findData(key)
        else:
            index = next((i for i in range(row.parameter.count()) if row.parameter.itemData(i) not in used), 0)
        row.parameter.blockSignals(True)
        row.parameter.setCurrentIndex(max(index, 0))
        row.parameter.blockSignals(False)
        self.rows.append(row)
        self.rows_layout.addWidget(row)
        row.parameterChanged()
        self.button_add.setEnabled(len(self.rows) < MAX_PARAMETERS)
        return row

    def removeParameterRow(self, row: ParameterRow, keep_one: bool = True):
        """Removes a parameter from the scan (at least one remains if keep_one)"""

        if keep_one and len(self.rows) <= 1:
            return
        self.rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        self.versions.setHidden(not any(r.key() == 'version' for r in self.rows))
        self.button_add.setEnabled(True)
        self.updateFolder()
        self.updateCount()

    def updateFolder(self):
        """Default folder of the scan: a folder in the folder of the simulation, named after the parameters"""

        save_folder = self.configuration.save_folder
        if save_folder is None or self.folder.text() not in ('', self.auto_folder):
            return
        self.auto_folder = pathToStr(save_folder / f'scan_{"_".join(row.key() for row in self.rows)}')
        self.folder.setText(self.auto_folder)

    def updateCount(self):
        """Shows the number of simulations of the scan"""

        count = 1
        for row in self.rows:
            count *= len(row.scanValues())
        self.count.setText(f'{count} simulation{"s" if count != 1 else ""}')

    def selectFolder(self):
        """Selects the scan folder"""

        start = self.folder.text() or pathToStr(self.configuration.save_folder)
        folder = QFileDialog.getExistingDirectory(self, 'Select the folder of the scan', start)
        if folder:
            self.folder.setText(folder)

    # --- state (scan.json and the simulation configuration) ---

    def state(self) -> dict:
        """Returns the settings of the scan"""

        return {
            'folder': self.folder.text(),
            'rows': [row.state() for row in self.rows],
            'versions': [sc.title for i, sc in enumerate(self.other_versions)
                         if notNone(self.versions.item(i)).checkState() == Qt.CheckState.Checked]
        }

    def setState(self, state: dict, load_runs: bool = True):
        """
        Sets the settings of the scan from state() and shows the simulations of the scan in its folder

        :param state: settings of the scan
        :param load_runs: (optional) show the simulations and results of the scan from scan.json in its folder
        """

        rows = [row for row in state.get('rows', []) if isinstance(row, dict)][:MAX_PARAMETERS]
        if rows:
            for row in list(self.rows):
                self.removeParameterRow(row, keep_one=False)
            for row_state in rows:
                # scans of older versions only store the label of the parameter
                key = row_state.get('key') or self.keyOfLabel(row_state.get('label'))
                if key is None:
                    continue
                added = self.addParameterRow(key)
                if added is not None:
                    added.setState(dict(row_state, key=key))
            if not self.rows:
                self.addParameterRow()
        versions = state.get('versions')
        if isinstance(versions, list):
            for i, sc in enumerate(self.other_versions):
                notNone(self.versions.item(i)).setCheckState(Qt.CheckState.Checked if sc.title in versions else Qt.CheckState.Unchecked)
        folder = state.get('folder')
        if isinstance(folder, str) and folder:
            self.folder.setText(folder)
            if load_runs and (Path(folder) / SCAN_FILE).is_file():
                self.loadRuns(Path(folder))
        self.updateCount()

    def keyOfLabel(self, label) -> Optional[str]:
        """Returns the key of the parameter with a label or None"""

        if label == 'Version (configurations)':
            return 'version' if self.other_versions else None
        return next((parameter.key for parameter in self.parameters if parameter.label == label), None)

    def openScan(self, folder: Optional[Path] = None) -> bool:
        """
        Opens an existing scan: its parameters (if stored in scan.json), the state of its simulations and its results

        :param folder: (optional) folder of the scan, otherwise a dialog asks for it
        """

        if self.isRunning():
            showMessageBox(self, QMessageBox.Icon.Warning, 'Warning!', 'The scan is running')
            return False
        if folder is None:
            start = self.folder.text() or pathToStr(self.configuration.save_folder)
            folder_str = QFileDialog.getExistingDirectory(self, 'Select the folder of a parameter scan (with scan.json)', start)
            if not folder_str:
                return False
            folder = Path(folder_str)
        scan = readScanDescription(folder)
        if scan is None:
            showMessageBox(self, QMessageBox.Icon.Warning, 'Warning!', f'No parameter scan ({SCAN_FILE}) found in "{pathToStr(folder)}"')
            return False
        self.setState({'folder': pathToStr(folder), 'rows': scan.get('rows', []), 'versions': scan.get('versions')}, load_runs=False)
        self.loadRuns(folder)
        self.page.tab_widget.setCurrentWidget(self.results if self.button_results.isEnabled() else self)
        return True

    def loadRuns(self, folder: Path):
        """Shows the simulations of the scan in a folder (from scan.json) with their state and resets the results"""

        scan = readScanDescription(folder)
        if scan is None:
            return
        self.parameter_names = [str(name) for name in scan.get('parameters', [])]
        jobs = []
        for run in scan.get('runs', []):
            if not isinstance(run, dict) or 'folder' not in run:
                continue
            job_folder = folder / str(run['folder'])
            log_file = job_folder / 'scan_log.txt'
            log = log_file.read_text(encoding='utf-8', errors='replace') if log_file.is_file() else ''
            status = 'not run'
            if log or any(job_folder.glob('output*')):
                problem = self.simulation_class.runFailed(job_folder, log, 0, self.configuration.version)
                status = 'finished' if problem is None else f'failed ({problem})'
            jobs.append({'values': list(run.get('values', [])), 'label': str(run['folder']), 'folder': job_folder, 'log': log,
                         'status': status, 'process': None, 'configuration': self.configuration, 'simulation': self.simulation_class})
        self.showJobs(jobs)
        self.progress.setValue(100 if jobs else 0)
        self.button_results.setEnabled(any(job['status'] == 'finished' for job in jobs))
        if self.page.tab_widget.currentWidget() is self.results:
            self.refreshResults()

    # --- run ---

    def prepareJobs(self) -> Optional[List[dict]]:
        """Writes the input files of all simulations of the scan and returns the jobs or None if the scan can not be run"""

        # the scan is written into the folder of the simulation: the simulation is saved first (asks for a folder)
        if self.configuration.save_folder is None:
            if not self.page.saveSettings() or self.configuration.save_folder is None:
                return None
            self.updateFolder()

        folder = Path(self.folder.text()) if self.folder.text() else None
        if folder is None:
            showMessageBox(self, QMessageBox.Icon.Warning, 'Warning!', 'Select a folder for the scan')
            return None
        keys = [row.key() for row in self.rows]
        if len(set(keys)) != len(keys):
            showMessageBox(self, QMessageBox.Icon.Warning, 'Warning!', 'A parameter is scanned twice')
            return None

        base = self.page.makeArguments()
        problems = self.simulation_class.checkArguments(base, self.configuration.version)
        if problems:
            showMessageBox(self, QMessageBox.Icon.Warning, 'Warning!', 'The simulation does not accept these parameters',
                           detailed_message='\n'.join(problems))
            return None

        value_lists = [row.scanValues() for row in self.rows]
        if any(not values for values in value_lists):
            showMessageBox(self, QMessageBox.Icon.Warning, 'Warning!', 'No values for the scan')
            return None

        jobs: List[Dict[str, Any]] = []
        simulations: Dict[int, Any] = {}
        for combination in product(*value_lists):
            arguments = deepcopy(base)
            sc = self.configuration
            values: list = []
            labels = []
            for row, value in zip(self.rows, combination):
                if row.key() == 'version':
                    sc = value
                    values.append(sc.title)
                    labels.append(formatValue(sc.title))
                    continue
                parameter = row.scanParameter()
                if parameter is None:
                    continue
                if parameter.integer:
                    value = int(round(value))
                parameter.apply(arguments, value)
                values.append(value)
                labels.append(f'{parameter.key}_{formatValue(value)}')
            if sc is self.configuration:
                simulation = self.simulation_class
            else:
                if id(sc) not in simulations:
                    simulations[id(sc)] = sc.program_class()
                    simulations[id(sc)].update(sc.folder, sc.binary, sc.version)
                    simulations[id(sc)].updateElements(sc.folder, sc.version)
                simulation = simulations[id(sc)]
            jobs.append({'values': values, 'label': '__'.join(labels), 'configuration': sc, 'simulation': simulation,
                         'arguments': arguments, 'folder': folder / '__'.join(labels), 'log': '', 'status': 'waiting', 'process': None})

        # warnings of all simulations (the user decides)
        warnings: List[str] = []
        for job in jobs:
            for warning in job['simulation'].checkWarnings(job['arguments'], job['configuration'].version):
                if warning not in warnings:
                    warnings.append(warning)
        if warnings:
            _, result = showMessageBox(
                self, QMessageBox.Icon.Warning, 'Warning!', 'Some simulations might fail, give wrong results or create very large files',
                info_message='Press "OK" to run the scan anyway.', detailed_message='\n\n'.join(warnings),
                standard_buttons=QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel, expand_details=True
            )
            if result == QMessageBox.StandardButton.Cancel:
                return None

        # input files (the output of previous scans is removed) and the description of the scan
        for job in jobs:
            if job['folder'].is_dir():
                for path in job['folder'].iterdir():
                    if path.is_file():
                        path.unlink()
            sc = job['configuration']
            job['files'] = writeInputFiles(job['simulation'], job['arguments'], job['folder'], sc.folder, sc.version)
        self.parameter_names = [row.parameter.currentText() for row in self.rows]
        with open(folder / SCAN_FILE, 'w', encoding='utf-8') as file:
            dump(dict(self.state(), **{
                'simulation': pathToStr(self.configuration.save_folder),
                'parameters': self.parameter_names,
                'runs': [{'folder': job['folder'].name, 'values': job['values']} for job in jobs]
            }), file, indent=2)
        return jobs

    def showJobs(self, jobs: List[dict]):
        """Shows the simulations of the scan in the table"""

        self.jobs = jobs
        self.runs.clear()
        self.runs.setColumnCount(len(self.parameter_names) + 1)
        self.runs.setHorizontalHeaderLabels(['Status'] + self.parameter_names)
        self.runs.setRowCount(len(jobs))
        for i, job in enumerate(jobs):
            job['item'] = QTableWidgetItem()
            job['item'].setToolTip(pathToStr(job['folder']))
            self.runs.setItem(i, 0, job['item'])
            for j, value in enumerate(job['values']):
                item = QTableWidgetItem(value if isinstance(value, str) else f'{value:g}')
                alignment = Qt.AlignmentFlag.AlignLeft if isinstance(value, str) else Qt.AlignmentFlag.AlignRight
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | alignment)
                self.runs.setItem(i, j + 1, item)
            self.setJobStatus(job, job['status'])
        header = notNone(self.runs.horizontalHeader())
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(False)
        self.results.clearEntries()
        self.results_loaded = []

    def run(self):
        """Writes the input files and starts the simulations of the scan"""

        jobs = self.prepareJobs()
        if not jobs:
            return
        self.showJobs(jobs)
        self.queue = list(jobs)
        self.running = []
        self.button_run.setEnabled(False)
        self.button_open.setEnabled(False)
        self.button_abort.setEnabled(True)
        self.button_results.setEnabled(False)
        self.progress.setValue(0)
        self.startJobs()
        self.timer.start()
        self.updateTabs()

    def maxParallelRuns(self) -> int:
        """At most GlobalConf.max_parallel_runs simulations, one processor is left for the GUI"""

        return max(1, min(GlobalConf.max_parallel_runs, (cpu_count() or 2) - 1))

    def startJobs(self):
        """Starts simulations until maxParallelRuns() simulations run"""

        while self.queue and len(self.running) < self.maxParallelRuns():
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
            (job['folder'] / 'scan_log.txt').write_text(job['log'], encoding='utf-8')
        except OSError:
            pass
        job['process'].deleteLater()
        job['process'] = None
        self.startJobs()
        self.updateProgress()
        if not self.running and not self.queue:
            self.timer.stop()
            self.button_run.setEnabled(True)
            self.button_open.setEnabled(True)
            self.button_abort.setEnabled(False)
            self.button_results.setEnabled(any(job['status'] == 'finished' for job in self.jobs))
            self.progress.setValue(100)
            self.updateTabs()
            self.main_window.writeStatusBar(f'Parameter scan of "{self.configuration.title}" finished', 8000)
            if self.page.tab_widget.currentWidget() is self.results:
                self.refreshResults()

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
                job['item'].setToolTip(f'{pathToStr(job["folder"])}\n{status}\nThe output of the simulation is in scan_log.txt')
            job['shown_status'] = status
        job['status'] = status
        text = f'{status} ({percent:.0f} %)' if percent is not None and percent >= 0 else status
        if job['item'].text() != text:
            job['item'].setText(text)

    def updateProgress(self):
        """Overall progress of the scan"""

        if not self.jobs:
            return
        total = 0.
        for job in self.jobs:
            if job['status'] == 'running':
                try:
                    percent = job['simulation'].getProgress(job['folder'], job.get('last_log', ''), job['configuration'].version)
                except Exception:
                    percent = -1
                total += max(percent, 0)
                self.setJobStatus(job, 'running', percent)
            elif job['status'] != 'waiting':
                total += 100
        self.progress.setValue(int(total / len(self.jobs)))
        self.updateTabs()

    def updateTabs(self):
        """Shows the progress of a running scan in the title of its tab"""

        index = self.page.tab_widget.indexOf(self)
        if index >= 0:
            text = f'Parameter scan ⧖ {self.progress.value()} %' if self.isRunning() else 'Parameter scan'
            if self.page.tab_widget.tabText(index) != text:
                self.page.tab_widget.setTabText(index, text)

    def abort(self):
        """Aborts the scan"""

        for job in self.queue:
            self.setJobStatus(job, 'not started')
        self.queue = []
        for job in list(self.running):
            job['process'].kill()

    def refreshResults(self):
        """Adds the finished simulations of the scan to the results (the results are loaded when they are shown)"""

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
                    self, QMessageBox.Icon.Question, 'Abort scan?', 'The simulations of the parameter scan are still running',
                    info_message='They will be aborted.',
                    standard_buttons=QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
                )
                if result == QMessageBox.StandardButton.Cancel:
                    return False
            self.abort()
            for job in list(self.running):
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
