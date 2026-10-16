"""
Parameter scan: a series of simulations in which one parameter of a simulation tab is varied (energy or angle of a beam
species, fluence, number of histories, target thickness or the version of the simulation program). The simulations are
written into subfolders of a scan folder, run with at most GlobalConf.max_parallel_runs at the same time and compared
in the <CompareDialog>
"""

from __future__ import annotations
from typing import List, Optional, TYPE_CHECKING
from copy import deepcopy
from locale import getpreferredencoding
from pathlib import Path
from re import sub

import numpy as np

from PyQt6.QtCore import Qt, QProcess, QTimer
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QLineEdit, QPushButton, QDoubleSpinBox, QSpinBox,
    QListWidget, QListWidgetItem, QProgressBar, QMessageBox, QGridLayout, QFileDialog
)

from GlobalConf import GlobalConf

from Pages.CompareDialog import CompareDialog

from Simulations.Simulations import writeInputFiles

from Utility.Dialogs import showMessageBox
from Utility.Functions import pathToStr
from Utility.Icons import getIcon

if TYPE_CHECKING:
    from Pages.ProgramPage import SimulationPage


def formatValue(value: float) -> str:
    """Returns a value for a folder name, e.g. 1000.0 -> "1000", 0.5 -> "0.5" """

    return f'{value:g}'.replace('+', '')


class ParameterScanDialog(QDialog):
    """
    Dialog for a parameter scan of the simulation of a tab

    :param page: <SimulationPage> of the simulation
    """

    def __init__(self, page: SimulationPage):
        super().__init__(page)

        self.page = page
        self.configuration = page.simulation_configuration
        self.setWindowTitle(f'Parameter scan of "{self.configuration.title}"')
        self.jobs: List[dict] = []
        self.queue: List[dict] = []
        self.running: List[dict] = []
        self.compare_dialog: Optional[CompareDialog] = None

        arguments = page.makeArguments()
        # parameters: (label, key, index of beam row)
        self.parameters = []
        for i, row in enumerate(arguments.beam_rows):
            if row.symbol:
                self.parameters.append((f'Energy of {row.symbol} [eV]', 'energy', i))
                self.parameters.append((f'Angle of incidence of {row.symbol} [°]', 'angle', i))
        self.parameters.append(('Fluence [atoms/Å²]', 'fluence', None))
        for name, label in (('histories', 'Number of histories'), ('projectiles', 'Number of projectiles')):
            if isinstance(arguments.settings.get(name), (int, float)):
                self.parameters.append((label, name, None))
                break
        self.parameters.append(('Target thickness [Å]', 'thickness', None))
        self.other_versions = [
            sc for sc in page.main_window.simulation_configs
            if sc.program_name == self.configuration.program_name and sc.folder is not None and sc.binary is not None
        ]
        if len(self.other_versions) > 1:
            self.parameters.append(('Version (configurations)', 'version', None))

        layout = QVBoxLayout(self)
        grid = QGridLayout()
        layout.addLayout(grid)

        grid.addWidget(QLabel('Parameter:'), 0, 0)
        self.parameter = QComboBox(self)
        for label, key, index in self.parameters:
            self.parameter.addItem(label, (key, index))
        self.parameter.currentIndexChanged.connect(lambda _: self.parameterChanged())
        grid.addWidget(self.parameter, 0, 1, 1, 4)

        # values: from start to stop or a list
        self.label_range = QLabel('From, to, number:')
        grid.addWidget(self.label_range, 1, 0)
        self.start = QDoubleSpinBox(self)
        self.stop = QDoubleSpinBox(self)
        for spinbox in (self.start, self.stop):
            spinbox.setRange(0, 1e12)
            spinbox.setDecimals(4)
            spinbox.valueChanged.connect(lambda _: self.updateValues())
        self.number = QSpinBox(self)
        self.number.setRange(1, 1000)
        self.number.setValue(5)
        self.number.valueChanged.connect(lambda _: self.updateValues())
        self.scale = QComboBox(self)
        self.scale.addItems(['linear', 'logarithmic'])
        self.scale.currentIndexChanged.connect(lambda _: self.updateValues())
        grid.addWidget(self.start, 1, 1)
        grid.addWidget(self.stop, 1, 2)
        grid.addWidget(self.number, 1, 3)
        grid.addWidget(self.scale, 1, 4)
        self.label_values = QLabel('Values:')
        grid.addWidget(self.label_values, 2, 0)
        self.values = QLineEdit(self)
        self.values.setToolTip('Values of the parameter separated by commas (filled from the range, can be edited)')
        grid.addWidget(self.values, 2, 1, 1, 4)

        # versions: other configurations of the same simulation program
        self.versions = QListWidget(self)
        for sc in self.other_versions:
            item = QListWidgetItem(f'{sc.title} ({sc.version})')
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.versions.addItem(item)
        grid.addWidget(self.versions, 3, 0, 1, 5)

        # folder of the scan
        grid.addWidget(QLabel('Scan folder:'), 4, 0)
        self.folder = QLineEdit(self)
        self.folder.setToolTip('Each simulation of the scan is written into a subfolder of this folder')
        grid.addWidget(self.folder, 4, 1, 1, 3)
        self.button_folder = QPushButton(getIcon('open'), '', self)
        self.button_folder.clicked.connect(self.selectFolder)
        grid.addWidget(self.button_folder, 4, 4)

        # runs
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(True)
        self.progress.setFormat('%p %')
        layout.addWidget(self.progress)
        self.runs = QListWidget(self)
        layout.addWidget(self.runs)

        buttons = QHBoxLayout()
        self.button_run = QPushButton(getIcon('play'), 'Run scan', self)
        self.button_run.clicked.connect(self.run)
        self.button_abort = QPushButton(getIcon('abort'), 'Abort', self)
        self.button_abort.clicked.connect(self.abort)
        self.button_abort.setEnabled(False)
        self.button_compare = QPushButton(getIcon('search'), 'Compare results', self)
        self.button_compare.setToolTip('Compare the results of the simulations of the scan in a table and plots')
        self.button_compare.clicked.connect(self.openComparison)
        self.button_compare.setEnabled(False)
        buttons.addWidget(self.button_run)
        buttons.addWidget(self.button_abort)
        buttons.addStretch(1)
        buttons.addWidget(self.button_compare)
        layout.addLayout(buttons)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.updateProgress)

        self.resize(800, 600)
        self.parameterChanged()

    def currentParameter(self):
        """Returns (key, index of the beam row) of the selected parameter"""

        return self.parameter.currentData() or ('energy', 0)

    def parameterChanged(self):
        """Shows the inputs of the selected parameter and sets a default range around the current value"""

        key, index = self.currentParameter()
        is_version = key == 'version'
        for widget in (self.label_range, self.start, self.stop, self.number, self.scale, self.label_values, self.values):
            widget.setHidden(is_version)
        self.versions.setHidden(not is_version)

        arguments = self.page.makeArguments()
        current = {
            'energy': lambda: arguments.beam_rows[index].energy,
            'angle': lambda: arguments.beam_rows[index].angle,
            'fluence': lambda: arguments.settings.fluence,
            'histories': lambda: arguments.settings.get('histories'),
            'projectiles': lambda: arguments.settings.get('projectiles'),
            'thickness': lambda: arguments.target_args.thickness,
        }.get(key, lambda: 0.)()
        current = float(current or 0.)
        for spinbox in (self.start, self.stop, self.number, self.scale):
            spinbox.blockSignals(True)
        if key == 'angle':
            self.start.setValue(0.)
            self.stop.setValue(80.)
            self.number.setValue(9)
            self.scale.setCurrentIndex(0)
        elif current > 0:
            self.start.setValue(current / 10 if key == 'energy' else current / 2)
            self.stop.setValue(current * 10 if key == 'energy' else current * 2)
            self.number.setValue(5)
            self.scale.setCurrentIndex(1 if key == 'energy' else 0)
        for spinbox in (self.start, self.stop, self.number, self.scale):
            spinbox.blockSignals(False)
        self.updateValues()

        if self.configuration.save_folder is not None:
            name = sub(r'[^A-Za-z0-9_]+', '_', self.parameter.currentText().split('[')[0].strip()).strip('_').lower()
            self.folder.setText(pathToStr(self.configuration.save_folder.parent / f'{self.configuration.save_folder.name}_scan_{name}'))

    def updateValues(self):
        """Fills the values from the range"""

        start, stop, number = self.start.value(), self.stop.value(), self.number.value()
        if self.scale.currentIndex() == 1 and start > 0 and stop > 0:
            values = np.geomspace(start, stop, number)
        else:
            values = np.linspace(start, stop, number)
        key, _ = self.currentParameter()
        if key in ('histories', 'projectiles'):
            values = np.unique(np.round(values).astype(int))
        self.values.setText(', '.join(f'{value:.6g}' for value in values))

    def scanValues(self) -> List[float]:
        """Returns the values of the scan"""

        values = []
        for text in self.values.text().replace(';', ',').split(','):
            try:
                values.append(float(text))
            except ValueError:
                pass
        return values

    def selectFolder(self):
        """Selects the scan folder"""

        folder = QFileDialog.getExistingDirectory(self, 'Select the folder of the scan', self.folder.text())
        if folder:
            self.folder.setText(folder)

    @staticmethod
    def applyValue(arguments, key: str, index: Optional[int], value: float):
        """Sets the value of the scanned parameter in the arguments"""

        if key == 'energy':
            arguments.beam_rows[index].energy = float(value)
        elif key == 'angle':
            arguments.beam_rows[index].angle = float(value)
        elif key == 'fluence':
            arguments.settings.fluence = float(value)
        elif key in ('histories', 'projectiles'):
            arguments.settings.optional[key] = int(value)
        elif key == 'thickness':
            # the layers keep their relative thickness
            total = sum(layer.thickness for layer in arguments.structure)
            for layer in arguments.structure:
                layer.thickness = layer.thickness * value / total if total > 0 else value / max(len(arguments.structure), 1)
            arguments.target_args.thickness = float(value)

    def prepareJobs(self) -> Optional[List[dict]]:
        """Writes the input files of all simulations of the scan and returns the jobs or None if the scan can not be run"""

        key, index = self.currentParameter()
        folder = Path(self.folder.text()) if self.folder.text() else None
        if folder is None:
            showMessageBox(self, QMessageBox.Icon.Warning, 'Warning!', 'Select a folder for the scan')
            return None

        base = self.page.makeArguments()
        problems = self.page.simulation_class.checkArguments(base, self.configuration.version)
        if problems:
            showMessageBox(self, QMessageBox.Icon.Warning, 'Warning!', 'The simulation does not accept these parameters',
                           detailed_message='\n'.join(problems))
            return None

        # (value, label, configuration) of the simulations
        runs = []
        if key == 'version':
            for i, sc in enumerate(self.other_versions):
                if self.versions.item(i).checkState() == Qt.CheckState.Checked:
                    runs.append((None, sub(r'[^A-Za-z0-9_.]+', '_', sc.title), sc))
        else:
            for value in self.scanValues():
                runs.append((value, f'{key}_{formatValue(value)}', self.configuration))
        if not runs:
            showMessageBox(self, QMessageBox.Icon.Warning, 'Warning!', 'No values for the scan')
            return None

        jobs = []
        for value, label, sc in runs:
            arguments = deepcopy(base)
            if value is not None:
                self.applyValue(arguments, key, index, value)
            if sc is self.configuration:
                simulation = self.page.simulation_class
            else:
                simulation = sc.program_class()
                simulation.update(sc.folder, sc.binary, sc.version)
                simulation.updateElements(sc.folder, sc.version)
            jobs.append({'value': value, 'label': label, 'configuration': sc, 'simulation': simulation,
                         'arguments': arguments, 'folder': folder / label, 'log': '', 'status': 'waiting', 'process': None})

        # warnings of all simulations (the user decides)
        warnings = []
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

        # input files (the output of previous scans is removed)
        for job in jobs:
            if job['folder'].is_dir():
                for path in job['folder'].iterdir():
                    if path.is_file():
                        path.unlink()
            sc = job['configuration']
            job['files'] = writeInputFiles(job['simulation'], job['arguments'], job['folder'], sc.folder, sc.version)
        return jobs

    def run(self):
        """Writes the input files and starts the simulations of the scan"""

        jobs = self.prepareJobs()
        if not jobs:
            return
        self.jobs = jobs
        self.queue = list(jobs)
        self.running = []
        self.runs.clear()
        for job in jobs:
            job['item'] = QListWidgetItem(f'{job["label"]}: waiting')
            self.runs.addItem(job['item'])
        self.button_run.setEnabled(False)
        self.button_abort.setEnabled(True)
        self.button_compare.setEnabled(False)
        self.progress.setValue(0)
        self.startJobs()
        self.timer.start()

    def startJobs(self):
        """Starts simulations until GlobalConf.max_parallel_runs simulations run"""

        while self.queue and len(self.running) < max(1, GlobalConf.max_parallel_runs):
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
            job['process'] = process
            job['status'] = 'running'
            job['item'].setText(f'{job["label"]}: running')
            self.running.append(job)
            process.start()

    def readLog(self, job: dict):
        """Reads the output of a simulation"""

        text = bytes(job['process'].readAll()).decode(getpreferredencoding(), 'ignore')
        job['log'] = (job['log'] + text)[-20000:]
        job['last_log'] = text

    def jobFinished(self, job: dict, exit_code: int, exit_status):
        """A simulation of the scan has finished"""

        if job in self.running:
            self.running.remove(job)
        sc = job['configuration']
        problem = None
        if exit_status == QProcess.ExitStatus.NormalExit:
            problem = job['simulation'].runFailed(job['folder'], job['log'], exit_code, sc.version)
        else:
            problem = 'aborted'
        job['status'] = 'finished' if problem is None else f'failed ({problem})'
        job['item'].setText(f'{job["label"]}: {job["status"]}')
        (job['folder'] / 'scan_log.txt').write_text(job['log'], encoding='utf-8')
        self.startJobs()
        self.updateProgress()
        if not self.running and not self.queue:
            self.timer.stop()
            self.button_run.setEnabled(True)
            self.button_abort.setEnabled(False)
            self.button_compare.setEnabled(any(job['status'] == 'finished' for job in self.jobs))
            self.progress.setValue(100)
            if self.button_compare.isEnabled() and self.isVisible():
                self.openComparison()

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
            elif job['status'] != 'waiting':
                total += 100
        self.progress.setValue(int(total / len(self.jobs)))

    def abort(self):
        """Aborts the scan"""

        for job in self.queue:
            job['status'] = 'not started'
            job['item'].setText(f'{job["label"]}: not started')
        self.queue = []
        for job in list(self.running):
            job['process'].kill()

    def openComparison(self):
        """Compares the results of the finished simulations"""

        finished = [job for job in self.jobs if job['status'] == 'finished']
        if not finished:
            return
        key, _ = self.currentParameter()
        values = None if key == 'version' else [job['value'] for job in finished]
        self.compare_dialog = CompareDialog(
            self,
            type(self.page.evaluation_class.analysis),
            self.page.simulation_class.element_data,
            [job['folder'] for job in finished],
            values,
            '' if key == 'version' else self.parameter.currentText()
        )
        self.compare_dialog.show()

    def closeEvent(self, event):
        """Running simulations of the scan are aborted when the dialog is closed"""

        if self.running:
            _, result = showMessageBox(
                self, QMessageBox.Icon.Question, 'Abort scan?', 'The simulations of the scan are still running',
                info_message='Closing the dialog aborts them.',
                standard_buttons=QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
            )
            if result == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            self.abort()
        super().closeEvent(event)
