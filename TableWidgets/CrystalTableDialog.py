from typing import List, Optional, Tuple
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QComboBox, QDoubleSpinBox,
    QPushButton, QTableWidget, QHeaderView, QDialogButtonBox, QFileDialog, QAbstractItemView
)

from Styles import Styles

from Containers.CrystalTableFile import CrystalTableFile, TableCrystal, CrystalTableError

from Utility.CrystalImport import importCrystal, CrystalImportError, ImportedCrystal
from Utility.Icons import getIcon


class NewCrystalDialog(QDialog):
    """
    Dialog to create a new crystal in the crystal table "table.crystal" of SDTrimSP (since version 7.02).
    The atoms can be placed in an existing crystal structure of the table or in a new structure.
    Crystals can also be imported from CIF and VASP POSCAR files.

    :param parent: parent widget
    :param table_file: <CrystalTableFile> of the simulation
    :param element_symbols: symbols of all elements that can be used
    """

    NEW_STRUCTURE = -1

    def __init__(self, parent, table_file: CrystalTableFile, element_symbols: List[str]):
        super().__init__(parent)
        self.setWindowTitle('Create new crystal')
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(650)

        self.table_file = table_file
        self.element_symbols = sorted(set(element_symbols))
        self.created_crystal: Optional[TableCrystal] = None

        layout = QVBoxLayout(self)

        # import
        import_layout = QHBoxLayout()
        self.import_button = QPushButton(getIcon('convert'), ' Import crystal file...')
        self.import_button.setToolTip('Import a crystal structure from a CIF (*.cif) or VASP (POSCAR, CONTCAR, *.vasp) file')
        self.import_button.setAutoDefault(False)
        self.import_button.clicked.connect(self.importFile)
        import_layout.addWidget(self.import_button)
        self.import_label = QLabel('')
        self.import_label.setWordWrap(True)
        import_layout.addWidget(self.import_label, stretch=1)
        layout.addLayout(import_layout)

        # parameters
        grid = QGridLayout()
        layout.addLayout(grid)

        self.name = QLineEdit()
        self.name.setMaxLength(self.table_file.limits.max_name_length)
        self.name.setPlaceholderText('e.g. Au_fcc')
        self.name.setToolTip(f'Name of the crystal in table.crystal (max. {self.table_file.limits.max_name_length} characters, no spaces)')
        grid.addWidget(QLabel('Name:'), 0, 0)
        grid.addWidget(self.name, 0, 1, 1, 3)

        self.structure = QComboBox()
        for structure in self.table_file.structures:
            self.structure.addItem(f'{structure.number}: {structure.name} ({len(structure.positions)} atoms)', structure.number)
        self.structure.addItem('New structure', self.NEW_STRUCTURE)
        self.structure.setToolTip('Crystal structure (relative positions of the atoms in the unit cell)')
        grid.addWidget(QLabel('Structure:'), 1, 0)
        grid.addWidget(self.structure, 1, 1, 1, 3)

        self.structure_name = QLineEdit()
        self.structure_name.setPlaceholderText('name of the new structure, e.g. CsCl-type')
        grid.addWidget(QLabel('Structure name:'), 2, 0)
        grid.addWidget(self.structure_name, 2, 1, 1, 3)

        def spinbox(value: float, decimals: int, minimum: float, maximum: float, tooltip: str) -> QDoubleSpinBox:
            box = QDoubleSpinBox()
            box.setDecimals(decimals)
            box.setRange(minimum, maximum)
            box.setValue(value)
            box.setToolTip(tooltip)
            return box

        self.dx = spinbox(4., 6, 0.01, 1000., 'Lattice constant dx = dy in Angstrom (SDTrimSP scales x- and y-coordinates with dx)')
        self.dz = spinbox(4., 6, 0.01, 1000., 'Lattice constant dz in Angstrom')
        grid.addWidget(QLabel('dx = dy [Å]:'), 3, 0)
        grid.addWidget(self.dx, 3, 1)
        grid.addWidget(QLabel('dz [Å]:'), 3, 2)
        grid.addWidget(self.dz, 3, 3)

        self.deltahf = spinbox(0., 4, -1000., 1000., 'Heat of formation in eV (used if isbv = 4)')
        self.p_max = spinbox(3., 4, 0., 100., 'Maximum impact parameter p_max in Angstrom')
        grid.addWidget(QLabel('ΔH_f [eV]:'), 4, 0)
        grid.addWidget(self.deltahf, 4, 1)
        grid.addWidget(QLabel('p_max [Å]:'), 4, 2)
        grid.addWidget(self.p_max, 4, 3)

        self.matrix_id = QComboBox()
        self.matrix_id.addItem('3x3x3', 3)
        self.matrix_id.addItem('5x5x5', 5)
        self.matrix_id.setToolTip('The simulation searches the next collision partner in this field of the nearest target atoms')
        self.density = QLabel('')
        self.density.setToolTip('Atomic density = number of atoms / (dx · dy · dz)')
        grid.addWidget(QLabel('Matrix:'), 5, 0)
        grid.addWidget(self.matrix_id, 5, 1)
        grid.addWidget(QLabel('Density [at./Å³]:'), 5, 2)
        grid.addWidget(self.density, 5, 3)

        # atoms
        atoms_header = QHBoxLayout()
        atoms_header.addWidget(QLabel('<b>Atoms in the unit cell</b> (relative coordinates along the basis vectors a₁, a₂, a₃)'), stretch=1)
        self.add_atom = QPushButton(getIcon('add'), '')
        self.add_atom.setToolTip('Add atom')
        self.add_atom.setAutoDefault(False)
        self.add_atom.clicked.connect(lambda: self.addAtom())
        self.remove_atom = QPushButton(getIcon('close'), '')
        self.remove_atom.setToolTip('Remove selected atom')
        self.remove_atom.setAutoDefault(False)
        self.remove_atom.clicked.connect(self.removeAtom)
        atoms_header.addWidget(self.add_atom)
        atoms_header.addWidget(self.remove_atom)
        layout.addLayout(atoms_header)

        self.atoms = QTableWidget(0, 4)
        self.atoms.setHorizontalHeaderLabels(['Element', 'a₁', 'a₂', 'a₃'])
        self.atoms.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.atoms.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.atoms.setMinimumHeight(220)
        layout.addWidget(self.atoms)

        # validation and buttons
        self.validation = QLabel('')
        self.validation.setWordWrap(True)
        self.validation.setStyleSheet(f'color: {Styles.red_hex};')
        layout.addWidget(self.validation)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText('Save to table.crystal')
        self.buttons.accepted.connect(self.save)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        # signals
        self.structure.currentIndexChanged.connect(lambda _: self.structureChanged())
        for widget in (self.dx, self.dz):
            widget.valueChanged.connect(lambda _: self.validate())
        self.name.textChanged.connect(lambda _: self.validate())

        self.structureChanged()

    def addAtom(self, element: str = '', position: Tuple[float, float, float] = (0., 0., 0.), editable: bool = True):
        """Adds a row for an atom"""

        row = self.atoms.rowCount()
        self.atoms.insertRow(row)

        combobox = QComboBox()
        combobox.addItems(self.element_symbols)
        if element in self.element_symbols:
            combobox.setCurrentText(element)
        combobox.currentIndexChanged.connect(lambda _: self.validate())
        self.atoms.setCellWidget(row, 0, combobox)

        for column, value in enumerate(position, start=1):
            box = QDoubleSpinBox()
            box.setDecimals(4)
            box.setRange(0., 1.)
            box.setSingleStep(0.25)
            box.setValue(value)
            box.setEnabled(editable)
            box.valueChanged.connect(lambda _: self.validate())
            self.atoms.setCellWidget(row, column, box)

        self.validate()

    def removeAtom(self):
        """Removes the selected atom"""

        rows = sorted({index.row() for index in self.atoms.selectedIndexes()}, reverse=True) or [self.atoms.rowCount() - 1]
        for row in rows:
            if row >= 0:
                self.atoms.removeRow(row)
        self.validate()

    def atomsList(self) -> Tuple[List[str], List[Tuple[float, float, float]]]:
        """Returns elements and positions of the atoms"""

        elements = []
        positions = []
        for row in range(self.atoms.rowCount()):
            elements.append(self.atoms.cellWidget(row, 0).currentText())
            positions.append(tuple(self.atoms.cellWidget(row, column).value() for column in (1, 2, 3)))
        return elements, positions

    def structureChanged(self, elements: Optional[List[str]] = None):
        """Updates the atoms table if another structure is selected"""

        number = self.structure.currentData()
        new_structure = number == self.NEW_STRUCTURE
        self.structure_name.setEnabled(new_structure)
        self.add_atom.setEnabled(new_structure)
        self.remove_atom.setEnabled(new_structure)

        if new_structure:
            if self.atoms.rowCount() == 0:
                self.addAtom()
            else:
                for row in range(self.atoms.rowCount()):
                    for column in (1, 2, 3):
                        self.atoms.cellWidget(row, column).setEnabled(True)
            self.validate()
            return

        old_elements, _ = self.atomsList()
        structure = self.table_file.structure(number)
        self.atoms.setRowCount(0)
        for i, position in enumerate(structure.positions):
            element = ''
            if elements is not None and i < len(elements):
                element = elements[i]
            elif old_elements:
                element = old_elements[min(i, len(old_elements) - 1)]
            self.addAtom(element, position, editable=False)
        self.validate()

    def crystal(self) -> TableCrystal:
        """Returns the crystal defined in the dialog"""

        elements, positions = self.atomsList()
        structure = self.structure.currentData()
        crystal = TableCrystal(
            name=self.name.text().strip(),
            dx=self.dx.value(),
            dy=self.dx.value(),
            dz=self.dz.value(),
            density=0.,
            deltahf=self.deltahf.value(),
            p_max=self.p_max.value(),
            matrix_id=self.matrix_id.currentData(),
            structure=structure if structure != self.NEW_STRUCTURE else 0,
            elements=elements
        )
        crystal.density = crystal.calculatedDensity()
        return crystal

    def validate(self) -> bool:
        """Validates the input, shows problems and enables the save button"""

        crystal = self.crystal()
        _, positions = self.atomsList()
        self.density.setText(f'{crystal.density:.5f}')

        errors = self.table_file.validateCrystal(crystal, positions)
        if len(positions) > self.table_file.limits.max_atoms:
            errors.append(f'At most {self.table_file.limits.max_atoms} atoms are possible')
        seen = []
        for position in positions:
            if any(all(abs(a - b) < 1e-4 for a, b in zip(position, other)) for other in seen):
                errors.append('Two atoms have the same position')
                break
            seen.append(position)

        self.validation.setText('<br>'.join(errors))
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(not errors)
        return not errors

    def importFile(self):
        """Imports a crystal from a CIF or VASP POSCAR file"""

        file, _ = QFileDialog.getOpenFileName(
            self,
            'Import crystal structure',
            '',
            'Crystal files (*.cif *.vasp POSCAR* CONTCAR*);;CIF files (*.cif);;VASP files (*.vasp POSCAR* CONTCAR*);;All files (*)'
        )
        if not file:
            return

        try:
            imported = importCrystal(Path(file))
        except CrystalImportError as error:
            self.import_label.setText(f'<span style="color: {Styles.red_hex};">{error}</span>')
            return

        self.applyImported(imported)

    def applyImported(self, imported: ImportedCrystal):
        """Fills the dialog with an imported crystal"""

        messages = list(imported.warnings)
        a, b, c = imported.lengths
        if not imported.isOrthogonal():
            self.import_label.setText(
                f'<span style="color: {Styles.red_hex};">The unit cell of "{imported.name}" is not orthogonal '
                f'(angles {imported.angles[0]:.1f}°, {imported.angles[1]:.1f}°, {imported.angles[2]:.1f}°). '
                f'SDTrimSP only supports orthogonal unit cells.</span>'
            )
            return
        if abs(a - b) > 1e-6:
            messages.append(f'a = {a:.4f} Å and b = {b:.4f} Å differ, but SDTrimSP uses dx for x and y. dx is set to a')
        unknown = sorted({element for element in imported.elements if element not in self.element_symbols})
        if unknown:
            messages.append(f'Unknown elements for this simulation: {", ".join(unknown)}')

        self.name.setText(imported.name.replace(' ', '_')[:self.table_file.limits.max_name_length])
        self.dx.setValue(a)
        self.dz.setValue(c)

        structure, order = self.table_file.findStructure(imported.positions)
        if structure is not None:
            elements = [imported.elements[i] for i in order]
            self.structure.blockSignals(True)
            self.structure.setCurrentIndex(self.structure.findData(structure.number))
            self.structure.blockSignals(False)
            self.structureChanged(elements)
            messages.insert(0, f'Imported {len(imported.positions)} atoms, the existing structure "{structure.name}" is used')
        else:
            self.structure.blockSignals(True)
            self.structure.setCurrentIndex(self.structure.findData(self.NEW_STRUCTURE))
            self.structure.blockSignals(False)
            self.atoms.setRowCount(0)
            for element, position in zip(imported.elements, imported.positions):
                self.addAtom(element, position)
            self.structureChanged()
            self.structure_name.setText(f'{imported.name}-type'.replace(' ', '_'))
            messages.insert(0, f'Imported {len(imported.positions)} atoms, a new structure will be created')

        self.import_label.setText('<br>'.join(messages))
        self.validate()

    def save(self):
        """Writes the crystal to table.crystal"""

        if not self.validate():
            return

        elements, positions = self.atomsList()
        crystal = self.crystal()
        try:
            if self.structure.currentData() == self.NEW_STRUCTURE:
                self.created_crystal = self.table_file.addCrystal(crystal, positions, self.structure_name.text().strip())
            else:
                structure = self.table_file.structure(crystal.structure)
                self.created_crystal = self.table_file.addCrystal(crystal, list(structure.positions))
        except CrystalTableError as error:
            self.validation.setText(str(error).replace('\n', '<br>'))
            return

        self.accept()
