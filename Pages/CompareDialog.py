"""
Dialog to compare the results of several simulations (of the same simulation program), e.g. sputter yields of different
versions, energies or targets: summary values in a table and plots (lines over a parameter or 2D maps over two parameters
of a parameter scan), or the same plot of all simulations overlaid
"""

from __future__ import annotations
from typing import List, Optional, Tuple, Iterable, Dict, Any
from json import load
from pathlib import Path
from re import findall
import csv

import numpy as np
from matplotlib.colors import Normalize

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QSplitter, QListWidget, QListWidgetItem, QPushButton, QComboBox, QLabel,
    QTabWidget, QTableWidget, QTableWidgetItem, QFileDialog, QWidget, QAbstractItemView, QHeaderView, QCheckBox, QGridLayout
)

from Containers.MplCanvasSettings import MplCanvasSettings
from Utility.Layouts import MplCanvas, PlotToolbar
from Utility.Dialogs import selectFileDialog
from Utility.Functions import pathToStr
from Utility.Icons import getIcon
from Utility.Colors import paletteRgb, paletteColormap
from Utility.Typing import notNone


# calls of the plots that draw data (they are copied for each simulation) and that set up the axes (copied once)
DRAWING_CALLS = ('plot', 'step', 'stairs', 'scatter', 'errorbar', 'fill_between', 'bar', 'hist', 'semilogx', 'semilogy', 'loglog')
LINE_CALLS = ('plot', 'step', 'stairs', 'errorbar', 'semilogx', 'semilogy', 'loglog')
STYLE_CALLS = (
    'set_xlabel', 'set_ylabel', 'set_xscale', 'set_yscale', 'set_title', 'set_thetamin', 'set_thetamax',
    'set_theta_zero_location', 'set_theta_direction', 'set_rlabel_position', 'set_rmin', 'set_rmax'
)
LINE_STYLES = ['-', '--', ':', '-.']
MARKERS = ['o', 's', '^', 'D', 'v', 'P', 'X']

# file in the folder of a parameter scan that describes the scan (parameters and values of each simulation)
SCAN_FILE = 'scan.json'
# parameter of the numbers in the folder names
NAME_NUMBER = 'Number in the folder name'
# x axis without parameter: the simulations side by side
SIDE_BY_SIDE = 'Simulations (side by side)'
ALL_VALUES = 'all (one line each)'


def numberInLabel(label: str) -> Optional[float]:
    """Returns the last number in a label (e.g. the value of a scan in the folder name "e0_1000") or None"""

    numbers = findall(r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?', label)
    return float(numbers[-1]) if numbers else None


def readScanFile(folder: Path) -> Optional[Dict[str, dict]]:
    """Returns the description of a parameter scan (scan.json) as {folder name: {parameter: value}} or None"""

    try:
        with open(folder / SCAN_FILE, 'r', encoding='utf-8') as file:
            scan = load(file)
        names = scan['parameters']
        return {run['folder']: dict(zip(names, run['values'])) for run in scan['runs']}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def isNumber(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def formatParameter(value: Any) -> str:
    return f'{value:g}' if isNumber(value) else str(value)


def intervalEdges(values: List[float]) -> Tuple[np.ndarray, bool]:
    """
    Returns the edges of cells around sorted values and if the values are logarithmically spaced (then the edges are the
    geometric means)
    """

    array = np.array(values, dtype=float)
    if len(array) == 1:
        return np.array([array[0] - 0.5, array[0] + 0.5]) if array[0] <= 0 else np.array([array[0] / 1.5, array[0] * 1.5]), bool(array[0] > 0)
    logarithmic = bool(np.all(array > 0) and array[-1] / array[0] > 20)
    if logarithmic:
        logs = np.log(array)
        middles = (logs[1:] + logs[:-1]) / 2
        edges = np.concatenate([[2 * logs[0] - middles[0]], middles, [2 * logs[-1] - middles[-1]]])
        return np.exp(edges), True
    middles = (array[1:] + array[:-1]) / 2
    return np.concatenate([[2 * array[0] - middles[0]], middles, [2 * array[-1] - middles[-1]]]), False


class CompareWidget(QWidget):
    """
    Widget to compare the results of several simulations (in the window <CompareDialog> or in the results tab of a
    parameter scan)

    :param parent: parent widget
    :param analysis_class: class of the analysis of the simulation program (<SimulationsAnalysis>)
    :param element_data: <Elements> of the simulation
    :param folders: (optional) folders of the simulations
    :param values: (optional) values of one scanned parameter for each folder (x axis)
    :param parameter: (optional) name of the scanned parameter of values
    :param parameters: (optional) values of the scanned parameters of each folder as {parameter: value}
    """

    def __init__(self, parent, analysis_class, element_data, folders: Iterable[Path] = (), values: Optional[List[float]] = None,
                 parameter: str = '', parameters: Optional[List[dict]] = None):
        super().__init__(parent)

        self.analysis_class = analysis_class
        self.element_data = element_data
        self.entries: List[dict] = []
        self.data: Tuple[List[str], List[list]] = ([], [])
        self.filters: Dict[str, QComboBox] = {}

        layout = QVBoxLayout(self)
        splitter = QSplitter(self)
        layout.addWidget(splitter)
        self.splitter = splitter

        # simulations
        left = QWidget(self)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel('Simulations (checked ones are compared):'))
        self.list = QListWidget(self)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.itemChanged.connect(lambda _: self.update())
        left_layout.addWidget(self.list)
        buttons = QHBoxLayout()
        self.button_add = QPushButton(getIcon('add'), 'Add...', self)
        self.button_add.setToolTip('Add the folder of a simulation. If the folder contains no output, all its subfolders with output are '
                                   'added (e.g. a parameter scan, its parameters are read from scan.json)')
        self.button_add.clicked.connect(self.selectFolder)
        self.button_remove = QPushButton(getIcon('close'), 'Remove', self)
        self.button_remove.setToolTip('Remove the selected simulations from the comparison')
        self.button_remove.clicked.connect(self.removeSelected)
        buttons.addWidget(self.button_add)
        buttons.addWidget(self.button_remove)
        left_layout.addLayout(buttons)
        self.numbers_from_names = QCheckBox('Parameter: numbers in the folder names', self)
        self.numbers_from_names.setToolTip('The last number in the folder names (e.g. "energy_1000") is used as parameter')
        self.numbers_from_names.stateChanged.connect(lambda _: self.parametersChanged())
        left_layout.addWidget(self.numbers_from_names)
        self.status = QLabel('', self)
        self.status.setWordWrap(True)
        left_layout.addWidget(self.status)
        splitter.addWidget(left)

        # plot and table
        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        top.addWidget(QLabel('Compare:'))
        self.quantity = QComboBox(self)
        self.quantity.setToolTip('Main results of the simulations or a plot of all simulations')
        self.quantity.currentIndexChanged.connect(lambda _: self.updatePlot())
        top.addWidget(self.quantity, stretch=1)
        self.button_export = QPushButton(getIcon('save'), 'CSV', self)
        self.button_export.setToolTip('Export the data of the comparison as CSV file')
        self.button_export.clicked.connect(self.exportData)
        top.addWidget(self.button_export)
        right_layout.addLayout(top)

        # settings of the plots of the results over the parameters
        self.parameter_widget = QWidget(self)
        self.parameter_layout = QGridLayout(self.parameter_widget)
        self.parameter_layout.setContentsMargins(0, 0, 0, 0)
        self.plot_type = QComboBox(self)
        self.plot_type.addItems(['Lines', '2D map'])
        self.plot_type.setToolTip('Lines over the parameter of the x axis or a 2D map over two parameters (color: result)')
        self.x_parameter = QComboBox(self)
        self.y_parameter = QComboBox(self)
        self.species = QComboBox(self)
        self.species.setToolTip('Species of the result (the 2D map shows one species)')
        for combobox in (self.plot_type, self.x_parameter, self.y_parameter, self.species):
            combobox.currentIndexChanged.connect(lambda _: self.updatePlot())
        self.plot_type.currentIndexChanged.connect(lambda _: self.updateFilters())
        self.x_parameter.currentIndexChanged.connect(lambda _: self.updateFilters())
        self.y_parameter.currentIndexChanged.connect(lambda _: self.updateFilters())
        for column, (label, widget) in enumerate((('Plot:', self.plot_type), ('x axis:', self.x_parameter),
                                                  ('y axis:', self.y_parameter), ('Species:', self.species))):
            self.parameter_layout.addWidget(QLabel(label), 0, 2 * column)
            self.parameter_layout.addWidget(widget, 0, 2 * column + 1)
        self.filter_layout = QHBoxLayout()
        self.parameter_layout.addLayout(self.filter_layout, 1, 0, 1, 8)
        right_layout.addWidget(self.parameter_widget)

        self.tabs = QTabWidget(self)
        plot_widget = QWidget(self)
        plot_layout = QVBoxLayout(plot_widget)
        self.canvas = MplCanvas()
        self.toolbar = PlotToolbar(self.canvas, self)
        plot_layout.addWidget(self.canvas, stretch=1)
        plot_layout.addWidget(self.toolbar)
        self.tabs.addTab(plot_widget, 'Plot')
        self.table = QTableWidget(self)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabs.addTab(self.table, 'Table of results')
        right_layout.addWidget(self.tabs)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 25)
        splitter.setStretchFactor(1, 75)

        folders = list(folders)
        if parameters is None and values is not None:
            parameters = [{parameter or 'Value': value} for value in values]
        self.addFolders(folders, parameters)

    # --- simulations ---

    def addFolders(self, folders: List[Path], parameters: Optional[List[dict]] = None):
        """
        Adds simulations to the comparison

        :param folders: folders of the simulations
        :param parameters: (optional) values of the scanned parameters of each folder
        """

        skipped = []
        scans: Dict[Path, Optional[dict]] = {}
        self.list.blockSignals(True)
        for i, folder in enumerate(folders):
            if any(entry['folder'] == folder for entry in self.entries):
                continue
            analysis = self.analysis_class(self.element_data)
            if not analysis.loadFolder(folder):
                skipped.append(folder.name)
                continue
            values = parameters[i] if parameters is not None and i < len(parameters) else None
            if values is None:
                # parameters of a scan from scan.json in the folder of the scan
                if folder.parent not in scans:
                    scans[folder.parent] = readScanFile(folder.parent)
                values = (scans[folder.parent] or {}).get(folder.name)
            entry = {'folder': folder, 'label': folder.name, 'parameters': dict(values or {}), 'name_value': numberInLabel(folder.name),
                     'analysis': analysis, 'summary': analysis.summary()}
            self.entries.append(entry)
            item = QListWidgetItem(folder.name)
            item.setToolTip(pathToStr(folder) + ''.join(f'\n{name} = {formatParameter(value)}' for name, value in entry['parameters'].items()))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.list.addItem(item)
        self.list.blockSignals(False)
        self.status.setText(f'No output found in: {", ".join(skipped)}' if skipped else '')
        self.updateQuantities()
        self.parametersChanged()

    def clearEntries(self):
        """Removes all simulations from the comparison"""

        self.entries = []
        self.list.blockSignals(True)
        self.list.clear()
        self.list.blockSignals(False)
        self.status.setText('')
        self.updateQuantities()
        self.parametersChanged()

    def selectFolder(self):
        """Adds a folder selected in a dialog (or its subfolders with output)"""

        start = self.entries[-1]['folder'].parent if self.entries else None
        folder = QFileDialog.getExistingDirectory(self, 'Select the folder of a simulation or of a parameter scan', pathToStr(start))
        if not folder:
            return
        folder = Path(folder)
        analysis = self.analysis_class(self.element_data)
        if analysis.loadFolder(folder):
            self.addFolders([folder])
        else:
            self.addFolders(sorted(path for path in folder.iterdir() if path.is_dir()))

    def removeSelected(self):
        """Removes the selected simulations"""

        rows = sorted((self.list.row(item) for item in self.list.selectedItems()), reverse=True)
        for row in rows:
            self.list.takeItem(row)
            del self.entries[row]
        self.updateQuantities()
        self.parametersChanged()

    def checkedEntries(self) -> List[dict]:
        """Returns the checked simulations"""

        return [entry for i, entry in enumerate(self.entries) if notNone(self.list.item(i)).checkState() == Qt.CheckState.Checked]

    # --- parameters ---

    def parameterValues(self, entry: dict) -> dict:
        """Returns the parameters of a simulation (also the number in the folder name if selected)"""

        values = dict(entry['parameters'])
        if self.numbers_from_names.isChecked() and entry['name_value'] is not None:
            values[NAME_NUMBER] = entry['name_value']
        return values

    def parameterNames(self) -> List[str]:
        """Returns the parameters of all simulations"""

        names: List[str] = []
        for entry in self.entries:
            for name in self.parameterValues(entry):
                if name not in names:
                    names.append(name)
        return names

    def uniqueValues(self, name: str, entries: Optional[List[dict]] = None) -> list:
        """Returns the sorted values of a parameter"""

        values = [self.parameterValues(entry).get(name) for entry in (entries if entries is not None else self.entries)]
        values = [value for value in dict.fromkeys(values) if value is not None]
        if all(isNumber(value) for value in values):
            return sorted(values)
        return values

    def parametersChanged(self):
        """Updates the settings of the plots over the parameters"""

        names = self.parameterNames()
        self.parameter_widget.setHidden(not names)
        for combobox, items in ((self.x_parameter, [SIDE_BY_SIDE] + names), (self.y_parameter, names)):
            current = combobox.currentText()
            combobox.blockSignals(True)
            combobox.clear()
            combobox.addItems(items)
            index = combobox.findText(current)
            combobox.setCurrentIndex(index if index >= 0 else (1 if combobox is self.x_parameter and names else 0))
            combobox.blockSignals(False)
        if self.y_parameter.currentText() == self.x_parameter.currentText() and len(names) > 1:
            self.y_parameter.setCurrentIndex(1 if self.y_parameter.currentIndex() == 0 else 0)
        self.updateFilters()
        self.updateTable()
        self.updatePlot()

    def updateFilters(self):
        """Selection of the values of the parameters that are not on an axis"""

        map_plot = self.plot_type.currentIndex() == 1
        self.y_parameter.setEnabled(map_plot)
        axes = {self.x_parameter.currentText()} | ({self.y_parameter.currentText()} if map_plot else set())
        current = {name: combobox.currentText() for name, combobox in self.filters.items()}
        while self.filter_layout.count():
            widget = self.filter_layout.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.filters = {}
        for name in self.parameterNames():
            if name in axes:
                continue
            combobox = QComboBox(self)
            if not map_plot:
                combobox.addItem(ALL_VALUES)
            combobox.addItems([formatParameter(value) for value in self.uniqueValues(name)])
            index = combobox.findText(current.get(name, ''))
            combobox.setCurrentIndex(max(index, 0))
            combobox.currentIndexChanged.connect(lambda _: self.updatePlot())
            self.filter_layout.addWidget(QLabel(f'{name}:'))
            self.filter_layout.addWidget(combobox)
            self.filters[name] = combobox
        self.filter_layout.addStretch(1)
        self.updatePlot()

    # --- quantities, table and plots ---

    def quantities(self) -> List[str]:
        """Returns all quantities of the summaries (in the order of their first occurrence)"""

        quantities: List[str] = []
        for entry in self.entries:
            for quantity in entry['summary']:
                if quantity not in quantities:
                    quantities.append(quantity)
        return quantities

    def updateQuantities(self):
        """Updates the selection of the compared quantity or plot"""

        current = self.quantity.currentData()
        self.quantity.blockSignals(True)
        self.quantity.clear()
        for quantity in self.quantities():
            self.quantity.addItem(f'Results: {quantity}', ('summary', quantity))
        for function, title in self.analysis_class.ComparablePlots.items():
            self.quantity.addItem(f'Plot: {title}', ('plot', function))
        self.quantity.setCurrentIndex(max(self.indexOf(current), 0))
        self.quantity.blockSignals(False)

    def indexOf(self, selection) -> int:
        """Returns the index of a selection ('summary', quantity) or ('plot', function) or -1"""

        for i in range(self.quantity.count()):
            if tuple(self.quantity.itemData(i) or ()) == tuple(selection or ()):
                return i
        return -1

    def select(self, kind: str, name: str):
        """Selects a quantity of the summaries ('summary') or a plot ('plot')"""

        self.quantity.setCurrentIndex(self.indexOf((kind, name)))

    def update(self):
        """Updates table and plot"""

        self.updateTable()
        self.updatePlot()

    def speciesOf(self, quantity: str, entries: Optional[List[dict]] = None) -> List[str]:
        """Returns the species of a quantity in the simulations"""

        species: List[str] = []
        for entry in (entries if entries is not None else self.entries):
            for name in entry['summary'].get(quantity, {}):
                if name not in species:
                    species.append(name)
        return species

    def updateTable(self):
        """Table of the results of all simulations"""

        names = self.parameterNames()
        columns = [(quantity, species) for quantity in self.quantities() for species in self.speciesOf(quantity)]
        self.table.clear()
        self.table.setRowCount(len(self.entries))
        self.table.setColumnCount(1 + len(names) + len(columns))
        self.table.setHorizontalHeaderLabels(['Simulation'] + names + [f'{quantity} ({species})' for quantity, species in columns])
        for row, entry in enumerate(self.entries):
            self.table.setItem(row, 0, QTableWidgetItem(entry['label']))
            values = self.parameterValues(entry)
            for column, name in enumerate(names, start=1):
                self.table.setItem(row, column, QTableWidgetItem(formatParameter(values[name]) if name in values else ''))
            for column, (quantity, species) in enumerate(columns, start=1 + len(names)):
                value = entry['summary'].get(quantity, {}).get(species)
                self.table.setItem(row, column, QTableWidgetItem('' if value is None else f'{value:.6g}'))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    def updatePlot(self):
        """Draws the selected comparison"""

        selection = self.quantity.currentData()
        entries = self.checkedEntries()
        self.parameter_widget.setEnabled(bool(selection) and selection[0] == 'summary')
        if selection is None or not entries:
            settings = MplCanvasSettings()
            settings.axes.set_title('No simulations selected' if not entries else 'Nothing to compare')
            self.data = ([], [])
        elif selection[0] == 'summary':
            quantity = selection[1]
            self.updateSpecies(quantity, entries)
            if self.x_parameter.currentText() in ('', SIDE_BY_SIDE):
                settings = self.sideBySidePlot(quantity, entries)
            elif self.plot_type.currentIndex() == 1:
                settings = self.mapPlot(quantity, entries)
            else:
                settings = self.linePlot(quantity, entries)
        else:
            settings = self.overlayPlot(selection[1], entries)
        settings.apply(self.canvas)

    def updateSpecies(self, quantity: str, entries: List[dict]):
        """Species of the selected quantity"""

        species = self.reducedSpecies(quantity, entries)
        if [self.species.itemText(i) for i in range(self.species.count())] == ['all'] + species:
            return
        current = self.species.currentText()
        self.species.blockSignals(True)
        self.species.clear()
        self.species.addItems(['all'] + species)
        index = self.species.findText(current)
        self.species.setCurrentIndex(index if index >= 0 else 0)
        self.species.blockSignals(False)

    def reducedSpecies(self, quantity: str, entries: List[dict]) -> List[str]:
        """Species of a quantity, without "total" if it equals the only species"""

        species = [name for name in self.speciesOf(quantity, entries) if any(name in entry['summary'].get(quantity, {}) for entry in entries)]
        if len(species) == 2 and 'total' in species:
            single = species[0] if species[1] == 'total' else species[1]
            if all(entry['summary'].get(quantity, {}).get(single) == entry['summary'].get(quantity, {}).get('total') for entry in entries):
                species = [single]
        return species

    def selectedSpecies(self, quantity: str, entries: List[dict]) -> List[str]:
        species = self.reducedSpecies(quantity, entries)
        selected = self.species.currentText()
        return [selected] if selected in species else species

    def filteredEntries(self, entries: List[dict]) -> Tuple[List[dict], List[str]]:
        """Returns the simulations with the selected values of the parameters that are not on an axis and the parameters
        with all values (one line each)"""

        varying = []
        for name, combobox in self.filters.items():
            text = combobox.currentText()
            if text == ALL_VALUES:
                varying.append(name)
                continue
            entries = [entry for entry in entries if formatParameter(self.parameterValues(entry).get(name)) == text]
        return entries, varying

    def sideBySidePlot(self, quantity: str, entries: List[dict]) -> MplCanvasSettings:
        """Bars of a quantity of the simulations side by side"""

        settings = MplCanvasSettings()
        species = self.selectedSpecies(quantity, entries)
        x = np.arange(len(entries), dtype=float)
        width = 0.8 / max(len(species), 1)
        labels = ['Simulation']
        columns: List[list] = [[entry['label'] for entry in entries]]
        for j, name in enumerate(species):
            y = np.array([entry['summary'].get(quantity, {}).get(name, np.nan) for entry in entries], dtype=float)
            settings.axes.bar(x + (j - (len(species) - 1) / 2) * width, y, width=width, color=paletteRgb(j), label=name)
            labels.append(f'{quantity} ({name})')
            columns.append(list(y))
        settings.axes.set_xticks(x, [entry['label'] for entry in entries], rotation=20, ha='right')
        settings.axes.set_xlabel('Simulation')
        settings.axes.set_ylabel(quantity)
        settings.axes.set_title(quantity)
        if species:
            settings.axes.legend()
        self.data = (labels, columns)
        return settings

    def linePlot(self, quantity: str, entries: List[dict]) -> MplCanvasSettings:
        """Lines of a quantity over the parameter of the x axis, one line per species and value of the other parameters"""

        settings = MplCanvasSettings()
        x_name = self.x_parameter.currentText()
        entries, varying = self.filteredEntries([entry for entry in entries if x_name in self.parameterValues(entry)])
        species = self.selectedSpecies(quantity, entries)
        x_values = self.uniqueValues(x_name, entries)
        numeric = all(isNumber(value) for value in x_values)

        groups: Dict[tuple, List[dict]] = {}
        for entry in entries:
            key = tuple(self.parameterValues(entry).get(name) for name in varying)
            groups.setdefault(key, []).append(entry)

        labels: List[str] = []
        columns: List[list] = []
        line = 0
        for key, group in groups.items():
            group = sorted(group, key=lambda entry: x_values.index(self.parameterValues(entry)[x_name]))
            x = [self.parameterValues(entry)[x_name] for entry in group]
            x_plot = np.array(x, dtype=float) if numeric else np.array([x_values.index(value) for value in x], dtype=float)
            # the legend shows the values of the other parameters, their names are the title of the legend
            description = ', '.join(formatParameter(value) for value in key)
            for j, name in enumerate(species):
                y = np.array([entry['summary'].get(quantity, {}).get(name, np.nan) for entry in group], dtype=float)
                label = (f'{name}: {description}' if len(species) > 1 else description) if description else name
                settings.axes.plot(x_plot, y, marker=MARKERS[j % len(MARKERS)], color=paletteRgb(line), label=label)
                labels += [f'{x_name} ({label})', f'{quantity} ({label})']
                columns += [list(x), list(y)]
                line += 1
        if not numeric:
            settings.axes.set_xticks(np.arange(len(x_values)), [formatParameter(value) for value in x_values], rotation=20, ha='right')
        elif x_values and all(value > 0 for value in x_values) and x_values[-1] / x_values[0] > 20:
            settings.axes.set_xscale('log')
        settings.axes.set_xlabel(x_name)
        settings.axes.set_ylabel(quantity)
        settings.axes.set_title(quantity)
        if line:
            title = ', '.join(varying)
            if len(species) == 1 and varying:
                title = f'{species[0]}: {title}'
            settings.axes.legend(fontsize='small', title=title or None, title_fontsize='small', ncol=2 if line > 8 else 1)
        self.data = (labels, columns)
        return settings

    def mapPlot(self, quantity: str, entries: List[dict]) -> MplCanvasSettings:
        """2D map of a quantity (one species) over two parameters, the other parameters have the selected values"""

        settings = MplCanvasSettings()
        x_name, y_name = self.x_parameter.currentText(), self.y_parameter.currentText()
        if x_name == y_name:
            settings.axes.set_title('Select two different parameters for the x and y axis')
            self.data = ([], [])
            return settings
        entries, _ = self.filteredEntries([entry for entry in entries if x_name in self.parameterValues(entry) and y_name in self.parameterValues(entry)])
        species = self.selectedSpecies(quantity, entries)
        if not entries or not species:
            settings.axes.set_title('No simulations with these parameters')
            self.data = ([], [])
            return settings
        name = species[0]
        x_values, y_values = self.uniqueValues(x_name, entries), self.uniqueValues(y_name, entries)
        z = np.full((len(y_values), len(x_values)), np.nan)
        for entry in entries:
            values = self.parameterValues(entry)
            z[y_values.index(values[y_name]), x_values.index(values[x_name])] = entry['summary'].get(quantity, {}).get(name, np.nan)

        def axis(values: list):
            if all(isNumber(value) for value in values):
                edges, logarithmic = intervalEdges(values)
                return edges, logarithmic, None
            return np.arange(len(values) + 1) - 0.5, False, [formatParameter(value) for value in values]

        x_edges, x_log, x_ticks = axis(x_values)
        y_edges, y_log, y_ticks = axis(y_values)
        finite = z[np.isfinite(z)]
        norm = Normalize(vmin=float(finite.min()) if finite.size else 0., vmax=float(finite.max()) if finite.size else 1.)
        colormap = paletteColormap()
        # the canvas adds the colorbar of the pcolormesh
        settings.axes.pcolormesh(x_edges, y_edges, np.ma.masked_invalid(z), cmap=colormap, norm=norm, shading='flat')
        settings.axes.pcolormesh_label(f'{quantity} ({name})')
        if x_log:
            settings.axes.set_xscale('log')
        if y_log:
            settings.axes.set_yscale('log')
        if x_ticks is not None:
            settings.axes.set_xticks(np.arange(len(x_ticks)), x_ticks, rotation=20, ha='right')
        if y_ticks is not None:
            settings.axes.set_yticks(np.arange(len(y_ticks)), y_ticks)

        # values in the cells of small maps
        if z.size <= 144:
            x_centers = [np.sqrt(x_edges[i] * x_edges[i + 1]) if x_log else (x_edges[i] + x_edges[i + 1]) / 2 for i in range(len(x_values))]
            y_centers = [np.sqrt(y_edges[i] * y_edges[i + 1]) if y_log else (y_edges[i] + y_edges[i + 1]) / 2 for i in range(len(y_values))]
            for i, y_center in enumerate(y_centers):
                for k, x_center in enumerate(x_centers):
                    if np.isfinite(z[i, k]):
                        bright = norm(z[i, k]) > 0.6
                        settings.axes.text(x_center, y_center, f'{z[i, k]:.3g}', ha='center', va='center', fontsize='small',
                                           color='#202020' if bright else 'white')
        settings.axes.set_xlabel(x_name)
        settings.axes.set_ylabel(y_name)
        fixed = ', '.join(f'{n} = {combobox.currentText()}' for n, combobox in self.filters.items())
        settings.axes.set_title(f'{quantity} ({name})' + (f'\n{fixed}' if fixed else ''))

        x_grid, y_grid = np.meshgrid(x_values, y_values)
        self.data = ([x_name, y_name, f'{quantity} ({name})'], [list(x_grid.ravel()), list(y_grid.ravel()), list(z.ravel())])
        return settings

    def overlayPlot(self, function: str, entries: List[dict]) -> MplCanvasSettings:
        """The same plot of all simulations in one axes: one color per simulation, one line style per curve of a simulation"""

        settings = MplCanvasSettings()
        labels: List[str] = []
        columns: List[list] = []
        first = True
        drawn = False
        for i, entry in enumerate(entries):
            try:
                result = getattr(entry['analysis'], function)()
            except Exception as error:
                self.status.setText(f'{entry["label"]}: {error}')
                continue
            if result is None or result[1] is None:
                continue
            data, plot_settings = result
            fig_calls, axes_calls = plot_settings.get_calls()
            if first:
                for call in fig_calls:
                    if call[0] == 'func' and call[1] == 'add_subplot':
                        settings.fig.add_subplot(*call[2], **call[3])
                for call in axes_calls:
                    if call[0] == 'func' and call[1] in STYLE_CALLS:
                        getattr(settings.axes, call[1])(*call[2], **call[3])
                first = False

            series = 0
            for call in axes_calls:
                if call[0] != 'func' or call[1] not in DRAWING_CALLS:
                    continue
                kwargs = dict(call[3])
                label = kwargs.get('label')
                kwargs['color'] = paletteRgb(i)
                kwargs.pop('c', None)
                if call[1] in LINE_CALLS:
                    kwargs['linestyle'] = LINE_STYLES[series % len(LINE_STYLES)]
                if label and not str(label).startswith('_'):
                    kwargs['label'] = f'{entry["label"]}: {label}'
                else:
                    kwargs['label'] = entry['label'] if series == 0 else '_nolegend_'
                getattr(settings.axes, call[1])(*call[2], **kwargs)
                series += 1
                drawn = True

            if data is not None and len(data) == 2 and data[0] is not None:
                for column, label in zip(data[0], data[1]):
                    labels.append(f'{entry["label"]}: {label}')
                    columns.append(list(np.ravel(column)))

        if drawn:
            settings.axes.legend(fontsize='small')
        else:
            settings.axes.set_title('No data in the selected simulations')
        self.data = (labels, columns)
        return settings

    def exportData(self):
        """Exports the data of the comparison as CSV file"""

        labels, columns = self.data
        if not labels:
            return
        start = self.entries[0]['folder'].parent / 'comparison.csv' if self.entries else None
        path = selectFileDialog(self, True, 'Export the comparison as...', start, 'CSV files (*.csv)')
        if path is None:
            return
        rows = max(len(column) for column in columns)
        with open(path, 'w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(labels)
            for i in range(rows):
                writer.writerow(['' if i >= len(column) or column[i] is None else column[i] for column in columns])


class CompareDialog(CompareWidget):
    """
    Window to compare the results of several simulations, see <CompareWidget>
    """

    def __init__(self, parent, analysis_class, element_data, folders: Iterable[Path] = (), values: Optional[List[float]] = None,
                 parameter: str = '', parameters: Optional[List[dict]] = None):
        super().__init__(parent, analysis_class, element_data, folders, values, parameter, parameters)

        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowMinMaxButtonsHint | Qt.WindowType.WindowCloseButtonHint)
        self.setWindowTitle('Compare simulations')
        self.resize(1400, 850)
