"""
Editor for the input files of energy and angle distributions of SDTrimSP:
energy.inp (energy02.inp, ...), angle.inp (angle02.inp, ...) and ene_ang.inp

The first line of energy.inp and angle.inp is a header, since 7.07 it must start with "!" or "#".
ene_ang.inp has two formats:
  since 7.05: header, number of angles, (min, max, step) of angles, number of energies, (min, max, step) of energies, matrix
  until 7.02: two numbers (not used), then the same as since 7.05. The values of the matrix are fluxes in atoms/(s m^2)
              and the fluence is calculated from their sum (flc = sum * 17e-20 * 500)
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
from math import isfinite

import numpy as np

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
    QWidget, QHeaderView, QDialogButtonBox, QFileDialog, QDoubleSpinBox, QAbstractItemView
)

from Utility.Icons import getIcon
from Utility.Layouts import MplCanvas, PlotToolbar
from Utility.Typing import notNone


def readDistributionFile(path: Path) -> List[List[float]]:
    """
    Reads a distribution file (energy.inp or angle.inp): header line, then rows of upper bound and value

    :param path: path to file
    :return: list of [upper bound, value]
    """

    rows = []
    with open(path, 'r', encoding='utf-8', errors='replace') as file:
        lines = file.read().splitlines()[1:]
    for line in lines:
        values = line.split('!')[0].split()
        if len(values) < 2:
            continue
        try:
            rows.append([float(values[0].replace('D', 'E')), float(values[1].replace('D', 'E'))])
        except ValueError:
            break
    return rows


def finiteNumber(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def validDistributions(distributions) -> Dict[str, Any]:
    """
    Returns the valid parts of the distributions of the arguments (e.g. of a damaged input.json):
    {'energy' and 'angle': {symbol: [[upper limit, value], ...]}, 'energy_angle': {'angle', 'energy': [min, max, step],
    'matrix': rows of equal length}}
    """

    result: Dict[str, Any] = {}
    if not isinstance(distributions, dict):
        return result
    for kind in ('energy', 'angle'):
        species = distributions.get(kind)
        if not isinstance(species, dict):
            continue
        valid = {}
        for symbol, rows in species.items():
            if isinstance(symbol, str) and isinstance(rows, list):
                rows = [[float(row[0]), float(row[1])] for row in rows
                        if isinstance(row, (list, tuple)) and len(row) == 2 and all(finiteNumber(value) for value in row)]
                if rows:
                    valid[symbol] = rows
        if valid:
            result[kind] = valid
    data = distributions.get('energy_angle')
    if isinstance(data, dict):
        ranges: List[Any] = [data.get('angle'), data.get('energy')]
        matrix = data.get('matrix')
        if all(isinstance(r, (list, tuple)) and len(r) == 3 and all(finiteNumber(value) for value in r) for r in ranges) \
                and isinstance(matrix, list) and matrix and all(isinstance(row, list) and row and all(finiteNumber(value) for value in row) for row in matrix) \
                and len({len(row) for row in matrix}) == 1:
            result['energy_angle'] = {'angle': list(ranges[0]), 'energy': list(ranges[1]), 'matrix': matrix}
    return result


def writeDistributionFile(rows: List[List[float]], header: str) -> str:
    """Returns the content of a distribution file (energy.inp or angle.inp)"""

    lines = [header]
    lower = 0.
    for upper, value in rows:
        lines.append(f'{upper:12.5f} {value:14.6f}        ! {lower:g} - {upper:g}')
        lower = upper
    return '\n'.join(lines) + '\n'


def isNumber(text: str) -> bool:
    """Returns True if text is a (Fortran) number"""

    try:
        float(text.replace('D', 'E').replace('d', 'e'))
        return True
    except ValueError:
        return False


def readEnergyAngleFile(path: Path) -> Optional[dict]:
    """
    Reads ene_ang.inp (both formats): number of angles, (min, max, step) of angles, number of energies,
    (min, max, step) of energies, matrix

    :return: {'angle': [min, max, step], 'energy': [min, max, step], 'matrix': rows of energies with values for each angle}
    """

    with open(path, 'r', encoding='utf-8', errors='replace') as file:
        lines = [line.split('!')[0].split() for line in file.read().splitlines()]
    # only lines with numbers, the header (since 7.05) is skipped
    values = [line for line in lines if line and isNumber(line[0])]
    # until 7.02 two single numbers precede the number of angles
    if len(values) > 2 and len(values[1]) < 3:
        values = values[2:]
    try:
        angle_count = int(values[0][0])
        angle = [float(v) for v in values[1][:3]]
        energy_count = int(values[2][0])
        energy = [float(v) for v in values[3][:3]]
        matrix = [[float(v) for v in row[:angle_count]] for row in values[4:4 + energy_count]]
    except (IndexError, ValueError):
        return None
    if len(matrix) != energy_count or any(len(row) != angle_count for row in matrix):
        return None
    return {'angle': angle, 'energy': energy, 'matrix': matrix}


def writeEnergyAngleFile(data: dict, legacy: bool = False) -> str:
    """
    Returns the content of ene_ang.inp

    :param data: {'angle': [min, max, step], 'energy': [min, max, step], 'matrix': rows}
    :param legacy: format until SDTrimSP 7.02 (two numbers instead of the header)
    """

    matrix = data['matrix']
    angle_min, angle_max, angle_step = data['angle']
    energy_min, energy_max, energy_step = data['energy']
    if legacy:
        header = [
            f'{0.:10.4f}                          ! not used (created with BCA-GUIDE)',
            f'{0.:10.4f}                          ! not used',
        ]
    else:
        header = ['! Matrix of distribution or probabilities P=f(Angles, Energy), created with BCA-GUIDE']
    lines = header + [
        f'{len(matrix[0]) if matrix else 0:8d}                          ! columns  Angles',
        f'{angle_min:10.4f} {angle_max:10.4f} {angle_step:10.4f} ! Min      Max         dAngle      [degrees]',
        f'{len(matrix):8d}                          ! rows     Energy',
        f'{energy_min:10.4f} {energy_max:10.4f} {energy_step:10.4f} ! Min      Max         dE          [eV]',
    ]
    for row in matrix:
        lines.append(' '.join(f'{value:10.5f}' for value in row))
    return '\n'.join(lines) + '\n'


class DistributionTable(QWidget):
    """
    Table with intervals (upper bound, value) of a distribution and a preview

    :param unit: unit of the intervals, e.g. 'eV'
    :param rows: initial rows [upper bound, value]
    """

    def __init__(self, unit: str, rows: List[List[float]], parent=None):
        super().__init__(parent)
        self.unit = unit

        layout = QHBoxLayout(self)

        table_layout = QVBoxLayout()
        layout.addLayout(table_layout, stretch=2)

        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels([f'Upper bound [{unit}]', 'Particles per interval width'])
        notNone(self.table.horizontalHeader()).setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setToolTip(
            f'Each row is an interval from the upper bound of the previous row (or 0) to the upper bound of this row.<br>'
            f'The value is the number (or probability) of particles per {unit} in this interval, it is normalized by SDTrimSP'
        )
        self.table.itemChanged.connect(lambda _: self.updatePreview())
        table_layout.addWidget(self.table)

        buttons = QHBoxLayout()
        add = QPushButton(getIcon('add'), ' Add interval')
        add.setAutoDefault(False)
        add.clicked.connect(lambda: self.addRow())
        remove = QPushButton(getIcon('close'), ' Remove interval')
        remove.setAutoDefault(False)
        remove.clicked.connect(self.removeRow)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        table_layout.addLayout(buttons)

        preview_layout = QVBoxLayout()
        layout.addLayout(preview_layout, stretch=3)
        self.preview = MplCanvas(self, width=4, height=3)
        preview_layout.addWidget(self.preview, stretch=1)
        preview_layout.addWidget(PlotToolbar(self.preview, self))

        self.setRows(rows)

    def setRows(self, rows: List[List[float]]):
        """Sets the intervals"""

        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for upper, value in rows:
            self.addRow(upper, value)
        self.table.blockSignals(False)
        self.updatePreview()

    def addRow(self, upper: Optional[float] = None, value: float = 1.):
        """Adds an interval after the last one"""

        if upper is None:
            rows = self.rows()
            upper = (rows[-1][0] * 2 if rows and rows[-1][0] > 0 else 100.)
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(f'{upper:g}'))
        self.table.setItem(row, 1, QTableWidgetItem(f'{value:g}'))
        self.updatePreview()

    def removeRow(self):
        """Removes the selected intervals or the last one"""

        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True) or [self.table.rowCount() - 1]
        for row in rows:
            if row >= 0:
                self.table.removeRow(row)
        self.updatePreview()

    def rows(self) -> List[List[float]]:
        """Returns the valid intervals [upper bound, value]"""

        rows = []
        for row in range(self.table.rowCount()):
            # the items do not exist yet while a row is added
            bound_item, value_item = self.table.item(row, 0), self.table.item(row, 1)
            if bound_item is None or value_item is None:
                continue
            try:
                rows.append([float(bound_item.text().replace(',', '.')), float(value_item.text().replace(',', '.'))])
            except ValueError:
                continue
        return rows

    def problems(self) -> List[str]:
        """Returns problems of the intervals"""

        rows = self.rows()
        problems = []
        if not rows:
            problems.append('no intervals defined')
        if len(rows) != self.table.rowCount():
            problems.append('some rows are not valid numbers')
        if any(b[0] <= a[0] for a, b in zip(rows, rows[1:])):
            problems.append('the upper bounds must increase')
        if any(value < 0 for _, value in rows):
            problems.append('the values must not be negative')
        return problems

    def updatePreview(self):
        """Draws the distribution as bars"""

        rows = self.rows()
        self.preview.clear()
        axes = self.preview.axes
        lower = 0.
        for upper, value in rows:
            if upper > lower:
                axes.bar(lower, value, width=upper - lower, align='edge', alpha=0.6, color='C0', edgecolor=self.preview.fg_color)
            lower = upper
        axes.set_xlabel(f'[{self.unit}]')
        axes.set_ylabel('particles per interval width')
        self.preview.fig.tight_layout()
        self.preview.draw_idle()


class EnergyAngleTable(QWidget):
    """
    Matrix of the distribution of energies (rows) and angles (columns) for ene_ang.inp

    :param data: initial data {'angle': [min, max, step], 'energy': [min, max, step], 'matrix': rows}
    """

    def __init__(self, data: Optional[dict], parent=None, flux_note: bool = False):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        if flux_note:
            note = QLabel(
                'Until SDTrimSP 7.02 the values are fluxes in atoms/(s·m²) and the fluence is calculated from their sum '
                '(fluence = sum · 8.5·10⁻¹⁷ atoms/Å²), the fluence in the settings is not used.'
            )
            note.setWordWrap(True)
            layout.addWidget(note)

        grid = QGridLayout()
        layout.addLayout(grid)
        self.ranges = {}
        for row, (key, label, unit, default) in enumerate([
            ('angle', 'Angles', '°', [10., 80., 10.]),
            ('energy', 'Energies', 'eV', [10., 140., 10.])
        ]):
            grid.addWidget(QLabel(f'{label}:'), row, 0)
            boxes = []
            for column, name in enumerate(['min', 'max', 'step']):
                grid.addWidget(QLabel(f'{name} [{unit}]'), row, 1 + 2 * column)
                box = QDoubleSpinBox()
                box.setRange(0., 1e9 if key == 'energy' else 180.)
                box.setDecimals(4)
                box.setValue(default[column])
                grid.addWidget(box, row, 2 + 2 * column)
                boxes.append(box)
            self.ranges[key] = boxes

        update = QPushButton(getIcon('refresh'), ' Update matrix size')
        update.setAutoDefault(False)
        update.setToolTip('Creates the rows (energies) and columns (angles) of the matrix from the ranges, existing values are kept')
        update.clicked.connect(lambda: self.updateMatrix())
        grid.addWidget(update, 0, 7, 2, 1)

        layout.addWidget(QLabel('Number (or probability) of particles for each energy (row) and angle (column):'))
        self.table = QTableWidget(0, 0, self)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ContiguousSelection)
        layout.addWidget(self.table, stretch=1)

        if data:
            for key in ('angle', 'energy'):
                for box, value in zip(self.ranges[key], data[key]):
                    box.setValue(value)
            self.updateMatrix(data['matrix'])
        else:
            self.updateMatrix()

    @staticmethod
    def axis(values: List[float]) -> np.ndarray:
        """Returns the points from min to max with step"""

        minimum, maximum, step = values
        if step <= 0 or maximum < minimum:
            return np.array([minimum])
        return np.arange(minimum, maximum + step / 2, step)

    def updateMatrix(self, matrix: Optional[List[List[float]]] = None):
        """Creates the table with the current ranges, keeps existing values"""

        if matrix is None:
            matrix = self.matrix()
        angles = self.axis([box.value() for box in self.ranges['angle']])
        energies = self.axis([box.value() for box in self.ranges['energy']])

        self.table.setRowCount(len(energies))
        self.table.setColumnCount(len(angles))
        self.table.setHorizontalHeaderLabels([f'{angle:g}°' for angle in angles])
        self.table.setVerticalHeaderLabels([f'{energy:g} eV' for energy in energies])
        for row in range(len(energies)):
            for column in range(len(angles)):
                value = matrix[row][column] if row < len(matrix) and column < len(matrix[row]) else 0.
                self.table.setItem(row, column, QTableWidgetItem(f'{value:g}'))

    def matrix(self) -> List[List[float]]:
        """Returns the values of the matrix"""

        matrix = []
        for row in range(self.table.rowCount()):
            values = []
            for column in range(self.table.columnCount()):
                item = self.table.item(row, column)
                try:
                    values.append(float(item.text().replace(',', '.')) if item is not None else 0.)
                except ValueError:
                    values.append(0.)
            matrix.append(values)
        return matrix

    def data(self) -> dict:
        """Returns {'angle': [min, max, step], 'energy': [min, max, step], 'matrix': rows}"""

        return {
            'angle': [box.value() for box in self.ranges['angle']],
            'energy': [box.value() for box in self.ranges['energy']],
            'matrix': self.matrix()
        }


class DistributionDialog(QDialog):
    """
    Dialog to define the distributions of energies and angles of the projectiles (case_e0 = 1, case_alpha = 4, case_e0 = 6)

    :param parent: parent widget
    :param projectiles: symbols of the projectiles
    :param distributions: current distributions {'energy': {symbol: rows}, 'angle': {symbol: rows}, 'energy_angle': data}
    :param energy: edit energy distributions
    :param angle: edit angle distributions
    :param energy_angle: edit the combined distribution of energies and angles
    :param angle_per_projectile: one angle distribution per projectile (since SDTrimSP 7.05), otherwise one for all
    :param legacy_energy_angle: format of ene_ang.inp until SDTrimSP 7.02 (values are fluxes)
    """

    def __init__(self, parent, projectiles: List[str], distributions: Dict, energy: bool, angle: bool, energy_angle: bool,
                 angle_per_projectile: bool, legacy_energy_angle: bool = False):
        super().__init__(parent)
        self.setWindowTitle('Distributions of energies and angles')
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.resize(950, 600)

        self.distributions = distributions or {}
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            'The distributions are written to the input files of SDTrimSP (energy.inp, angle.inp, ene_ang.inp) when the settings are saved.'
        ))

        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs, stretch=1)
        self.energy_tables: Dict[str, DistributionTable] = {}
        self.angle_tables: Dict[str, DistributionTable] = {}
        self.energy_angle_table: Optional[EnergyAngleTable] = None

        default_energy = [[100., 1.], [200., 2.], [300., 1.]]
        default_angle = [[10., 1.], [30., 2.], [60., 1.]]

        if energy:
            for symbol in projectiles:
                rows = self.distributions.get('energy', {}).get(symbol) or default_energy
                self.energy_tables[symbol] = DistributionTable('eV', rows, self)
                self.tabs.addTab(self.energy_tables[symbol], f'Energy {symbol}')
        if angle:
            for symbol in (projectiles if angle_per_projectile else ['all']):
                rows = self.distributions.get('angle', {}).get(symbol) or default_angle
                self.angle_tables[symbol] = DistributionTable('°', rows, self)
                self.tabs.addTab(self.angle_tables[symbol], f'Angle {symbol}' if symbol != 'all' else 'Angle (all projectiles)')
        if energy_angle:
            self.energy_angle_table = EnergyAngleTable(self.distributions.get('energy_angle'), self, flux_note=legacy_energy_angle)
            self.tabs.addTab(self.energy_angle_table, 'Energy and angle')

        self.problems = QLabel('')
        self.problems.setWordWrap(True)
        self.problems.setStyleSheet('color: #bf3e2f;')
        layout.addWidget(self.problems)

        buttons_layout = QHBoxLayout()
        import_button = QPushButton(getIcon('convert'), ' Import file...')
        import_button.setAutoDefault(False)
        import_button.setToolTip('Load an existing energy.inp, angle.inp or ene_ang.inp file into the current tab')
        import_button.clicked.connect(self.importFile)
        buttons_layout.addWidget(import_button)
        buttons_layout.addStretch(1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        buttons_layout.addWidget(self.buttons)
        layout.addLayout(buttons_layout)

    def importFile(self):
        """Imports a file into the current tab"""

        file, _ = QFileDialog.getOpenFileName(self, 'Import distribution file', '', 'SDTrimSP input files (*.inp);;All files (*)')
        if not file:
            return
        widget = self.tabs.currentWidget()
        if isinstance(widget, DistributionTable):
            widget.setRows(readDistributionFile(Path(file)))
        elif isinstance(widget, EnergyAngleTable):
            data = readEnergyAngleFile(Path(file))
            if data is None:
                self.problems.setText(f'"{Path(file).name}" is not a valid ene_ang.inp file')
                return
            for key in ('angle', 'energy'):
                for box, value in zip(widget.ranges[key], data[key]):
                    box.setValue(value)
            widget.updateMatrix(data['matrix'])

    def distributionData(self) -> dict:
        """Returns the distributions"""

        result = dict(self.distributions)
        if self.energy_tables:
            result['energy'] = {symbol: table.rows() for symbol, table in self.energy_tables.items()}
        if self.angle_tables:
            result['angle'] = {symbol: table.rows() for symbol, table in self.angle_tables.items()}
        if self.energy_angle_table is not None:
            result['energy_angle'] = self.energy_angle_table.data()
        return result

    def accept(self):
        """Accepts only valid distributions"""

        problems = []
        for name, tables in (('Energy', self.energy_tables), ('Angle', self.angle_tables)):
            for symbol, table in tables.items():
                problems += [f'{name} {symbol}: {problem}' for problem in table.problems()]
        if self.energy_angle_table is not None:
            matrix = self.energy_angle_table.matrix()
            if not any(value > 0 for row in matrix for value in row):
                problems.append('Energy and angle: the matrix must contain at least one positive value')
            if any(value < 0 for row in matrix for value in row):
                problems.append('Energy and angle: the values must not be negative')
        if problems:
            self.problems.setText('<br>'.join(problems))
            return
        super().accept()
