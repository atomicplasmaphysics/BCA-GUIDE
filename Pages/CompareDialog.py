"""
Dialog to compare the results of several simulations (of the same simulation program), e.g. sputter yields of different
versions, energies or targets: summary values in a table and a plot, or the same plot of all simulations overlaid
"""

from __future__ import annotations
from typing import List, Optional, Tuple, Iterable
from pathlib import Path
from re import findall
import csv

import numpy as np
from matplotlib import colormaps

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget, QListWidgetItem, QPushButton, QComboBox, QLabel,
    QTabWidget, QTableWidget, QTableWidgetItem, QFileDialog, QWidget, QAbstractItemView, QHeaderView, QCheckBox
)

from Containers.MplCanvasSettings import MplCanvasSettings
from Utility.Layouts import MplCanvas, PlotToolbar
from Utility.Dialogs import selectFileDialog
from Utility.Functions import pathToStr
from Utility.Icons import getIcon


# calls of the plots that draw data (they are copied for each simulation) and that set up the axes (copied once)
DRAWING_CALLS = ('plot', 'step', 'stairs', 'scatter', 'errorbar', 'fill_between', 'bar', 'hist', 'semilogx', 'semilogy', 'loglog')
LINE_CALLS = ('plot', 'step', 'stairs', 'errorbar', 'semilogx', 'semilogy', 'loglog')
STYLE_CALLS = (
    'set_xlabel', 'set_ylabel', 'set_xscale', 'set_yscale', 'set_title', 'set_thetamin', 'set_thetamax',
    'set_theta_zero_location', 'set_theta_direction', 'set_rlabel_position', 'set_rmin', 'set_rmax'
)
LINE_STYLES = ['-', '--', ':', '-.']


def numberInLabel(label: str) -> Optional[float]:
    """Returns the last number in a label (e.g. the value of a scan in the folder name "e0_1000") or None"""

    numbers = findall(r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?', label)
    return float(numbers[-1]) if numbers else None


class CompareDialog(QDialog):
    """
    Dialog to compare the results of several simulations

    :param parent: parent widget
    :param analysis_class: class of the analysis of the simulation program (<SimulationsAnalysis>)
    :param element_data: <Elements> of the simulation
    :param folders: (optional) folders of the simulations
    :param values: (optional) values of the scanned parameter for each folder (x axis)
    :param parameter: (optional) name of the scanned parameter
    """

    def __init__(self, parent, analysis_class, element_data, folders: Iterable[Path] = (), values: Optional[List[float]] = None,
                 parameter: str = ''):
        super().__init__(parent)

        self.setWindowTitle('Compare simulations')
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.analysis_class = analysis_class
        self.element_data = element_data
        self.parameter = parameter
        self.entries: List[dict] = []
        self.data: Tuple[List[str], List[list]] = ([], [])

        layout = QVBoxLayout(self)
        splitter = QSplitter(self)
        layout.addWidget(splitter)

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
        self.button_add.setToolTip('Add the folder of a simulation. If the folder contains no output, all its subfolders with output are added (e.g. a parameter scan)')
        self.button_add.clicked.connect(self.selectFolder)
        self.button_remove = QPushButton(getIcon('close'), 'Remove', self)
        self.button_remove.setToolTip('Remove the selected simulations from the comparison')
        self.button_remove.clicked.connect(self.removeSelected)
        buttons.addWidget(self.button_add)
        buttons.addWidget(self.button_remove)
        left_layout.addLayout(buttons)
        self.numbers_from_names = QCheckBox('x axis: numbers in the folder names', self)
        self.numbers_from_names.setToolTip('The simulations are compared over the last number in their folder names (e.g. "energy_1000"), '
                                           'otherwise they are shown side by side')
        self.numbers_from_names.setChecked(values is not None)
        self.numbers_from_names.setEnabled(values is None)
        self.numbers_from_names.stateChanged.connect(lambda _: self.update())
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
        self.quantity.setToolTip('Main results of the simulations (summary) or a plot of all simulations')
        self.quantity.currentIndexChanged.connect(lambda _: self.updatePlot())
        top.addWidget(self.quantity, stretch=1)
        self.button_export = QPushButton(getIcon('save'), 'Export CSV...', self)
        self.button_export.setToolTip('Export the data of the comparison as CSV file')
        self.button_export.clicked.connect(self.exportData)
        top.addWidget(self.button_export)
        right_layout.addLayout(top)

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

        self.resize(1300, 800)
        self.addFolders(list(folders), values)

    def addFolders(self, folders: List[Path], values: Optional[List[float]] = None):
        """
        Adds simulations to the comparison

        :param folders: folders of the simulations
        :param values: (optional) value of the scanned parameter of each folder
        """

        skipped = []
        self.list.blockSignals(True)
        for i, folder in enumerate(folders):
            if any(entry['folder'] == folder for entry in self.entries):
                continue
            analysis = self.analysis_class(self.element_data)
            if not analysis.loadFolder(folder):
                skipped.append(folder.name)
                continue
            value = values[i] if values is not None and i < len(values) else None
            entry = {'folder': folder, 'label': folder.name, 'value': value, 'name_value': numberInLabel(folder.name),
                     'analysis': analysis, 'summary': analysis.summary()}
            self.entries.append(entry)
            item = QListWidgetItem(folder.name)
            item.setToolTip(pathToStr(folder))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.list.addItem(item)
        self.list.blockSignals(False)
        self.status.setText(f'No output found in: {", ".join(skipped)}' if skipped else '')
        self.updateQuantities()
        self.update()

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
        self.update()

    def checkedEntries(self) -> List[dict]:
        """Returns the checked simulations"""

        return [entry for i, entry in enumerate(self.entries) if self.list.item(i).checkState() == Qt.CheckState.Checked]

    def quantities(self) -> List[str]:
        """Returns all quantities of the summaries (in the order of their first occurrence)"""

        quantities = []
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

    def xValue(self, entry: dict) -> Optional[float]:
        """Returns the value of a simulation for the x axis (scanned parameter or number in the folder name) or None"""

        if entry['value'] is not None:
            return entry['value']
        return entry['name_value'] if self.numbers_from_names.isChecked() else None

    def numericAxis(self, entries: List[dict]) -> bool:
        """Returns True if the simulations have numbers (e.g. the values of a parameter scan) for the x axis"""

        values = [self.xValue(entry) for entry in entries]
        return bool(entries) and all(value is not None for value in values) and len(set(values)) == len(values)

    def updateTable(self):
        """Table of the results of all simulations"""

        columns = [(quantity, species) for quantity in self.quantities() for species in self.speciesOf(quantity)]
        self.table.clear()
        self.table.setRowCount(len(self.entries))
        self.table.setColumnCount(len(columns) + 2)
        self.table.setHorizontalHeaderLabels(['Simulation', self.parameter or 'Value'] + [f'{quantity} ({species})' for quantity, species in columns])
        for row, entry in enumerate(self.entries):
            self.table.setItem(row, 0, QTableWidgetItem(entry['label']))
            value = self.xValue(entry)
            self.table.setItem(row, 1, QTableWidgetItem('' if value is None else f'{value:g}'))
            for column, (quantity, species) in enumerate(columns, start=2):
                value = entry['summary'].get(quantity, {}).get(species)
                self.table.setItem(row, column, QTableWidgetItem('' if value is None else f'{value:.6g}'))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    def speciesOf(self, quantity: str) -> List[str]:
        """Returns the species of a quantity in all simulations"""

        species = []
        for entry in self.entries:
            for name in entry['summary'].get(quantity, {}):
                if name not in species:
                    species.append(name)
        return species

    def updatePlot(self):
        """Draws the selected comparison"""

        selection = self.quantity.currentData()
        entries = self.checkedEntries()
        if selection is None or not entries:
            settings = MplCanvasSettings()
            settings.axes.set_title('No simulations selected' if not entries else 'Nothing to compare')
            self.data = ([], [])
        elif selection[0] == 'summary':
            settings = self.summaryPlot(selection[1], entries)
        else:
            settings = self.overlayPlot(selection[1], entries)
        settings.apply(self.canvas)

    def summaryPlot(self, quantity: str, entries: List[dict]) -> MplCanvasSettings:
        """Plot of a quantity of the summaries over the simulations (over the parameter if the simulations have values)"""

        settings = MplCanvasSettings()
        numeric = self.numericAxis(entries)
        species = [name for name in self.speciesOf(quantity) if any(name in entry['summary'].get(quantity, {}) for entry in entries)]
        # "total" of a single species is the same as the species
        if len(species) == 2 and 'total' in species:
            single = species[0] if species[1] == 'total' else species[1]
            if all(entry['summary'].get(quantity, {}).get(single) == entry['summary'].get(quantity, {}).get('total') for entry in entries):
                species = [single]
        colors = colormaps['tab10']
        if numeric:
            entries = sorted(entries, key=self.xValue)
        x = np.array([self.xValue(entry) for entry in entries], dtype=float) if numeric else np.arange(len(entries), dtype=float)
        width = 0.8 / max(len(species), 1)
        labels = ['Simulation', self.parameter or 'Value']
        columns = [[entry['label'] for entry in entries], [self.xValue(entry) for entry in entries]]
        for j, name in enumerate(species):
            y = np.array([entry['summary'].get(quantity, {}).get(name, np.nan) for entry in entries], dtype=float)
            if numeric:
                settings.axes.plot(x, y, marker='o', color=colors(j % 10), label=name)
            else:
                settings.axes.bar(x + (j - (len(species) - 1) / 2) * width, y, width=width, color=colors(j % 10), label=name)
            labels.append(f'{quantity} ({name})')
            columns.append(list(y))
        if numeric:
            settings.axes.set_xlabel(self.parameter or 'Value')
        else:
            settings.axes.set_xticks(x, [entry['label'] for entry in entries], rotation=20, ha='right')
            settings.axes.set_xlabel('Simulation')
        settings.axes.set_ylabel(quantity)
        settings.axes.set_title(quantity)
        if species:
            settings.axes.legend()
        self.data = (labels, columns)
        return settings

    def overlayPlot(self, function: str, entries: List[dict]) -> MplCanvasSettings:
        """The same plot of all simulations in one axes: one color per simulation, one line style per curve of a simulation"""

        settings = MplCanvasSettings()
        colors = colormaps['tab10']
        labels, columns = [], []
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
                kwargs['color'] = colors(i % 10)
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
