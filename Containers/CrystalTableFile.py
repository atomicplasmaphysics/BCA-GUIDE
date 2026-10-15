from __future__ import annotations
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from shutil import copy2
import logging

import numpy as np


# limits of SDTrimSP (tableread.F90: max_struc, work.F90: max_atoms, length of character variables)
MAX_STRUCTURES = 10
MAX_ATOMS = 8
MAX_NAME_LENGTH = 10

# tolerance for comparing relative coordinates
COORD_TOLERANCE = 1e-4


@dataclass
class CrystalStructure:
    """
    Crystal structure (type) of table.crystal: relative coordinates of the atoms in the unit cell

    :param number: number of structure in table.crystal (starting at 1)
    :param name: name of structure, e.g. "fcc-type"
    :param positions: relative coordinates (x, y, z) of atoms
    """

    number: int
    name: str
    positions: List[Tuple[float, float, float]] = field(default_factory=list)

    def matchOrder(self, positions: List[Tuple[float, float, float]]) -> Optional[List[int]]:
        """
        Returns the order in which the given positions correspond to the positions of this structure, or None if they do not match.
        Positions are compared modulo 1 (periodic unit cell)

        :param positions: relative coordinates
        """

        if len(positions) != len(self.positions):
            return None

        own = np.mod(np.array(self.positions, dtype=float), 1)
        other = np.mod(np.array(positions, dtype=float), 1)
        order = []
        used = set()
        for position in own:
            difference = np.abs(other - position)
            difference = np.minimum(difference, 1 - difference)
            matches = [i for i in np.where(np.all(difference < COORD_TOLERANCE, axis=1))[0] if i not in used]
            if not matches:
                return None
            order.append(int(matches[0]))
            used.add(int(matches[0]))
        return order


@dataclass
class TableCrystal:
    """
    Crystal entry of table.crystal

    :param name: name of crystal (max. 10 characters, no spaces), e.g. "Cu_fcc"
    :param dx: lattice constant in x-direction (depth) in Angstrom
    :param dy: lattice constant in y-direction in Angstrom
    :param dz: lattice constant in z-direction in Angstrom
    :param density: atomic density in atoms/Angstrom^3
    :param deltahf: heat of formation in eV
    :param p_max: maximum impact parameter in Angstrom
    :param matrix_id: size of the field of nearest target atoms that is searched for collision partners (3 or 5)
    :param structure: number of crystal structure
    :param elements: element symbol of each atom of the structure
    """

    name: str
    dx: float
    dy: float
    dz: float
    density: float
    deltahf: float = 0.
    p_max: float = 3.
    matrix_id: int = 3
    structure: int = 1
    elements: List[str] = field(default_factory=list)

    def distinctElements(self) -> List[str]:
        """Returns the distinct elements in order of their first appearance"""

        distinct = []
        for element in self.elements:
            if element not in distinct:
                distinct.append(element)
        return distinct

    def composition(self) -> dict:
        """Returns dictionary of element: number of atoms"""

        return {element: self.elements.count(element) for element in self.distinctElements()}

    def compositionStr(self) -> str:
        """Returns composition as string, e.g. Na4 Cl4"""

        return ' '.join(f'{element}{count}' for element, count in self.composition().items())

    def calculatedDensity(self) -> float:
        """Returns the atomic density calculated from the number of atoms and the unit cell"""

        volume = self.dx * self.dy * self.dz
        return len(self.elements) / volume if volume > 0 else 0.

    def rowStr(self) -> str:
        """Returns the line for table.crystal"""

        return (
            f'  {self.name:<10}{self.dx:10.6f}{self.dy:10.6f}{self.dz:10.6f}{self.density:10.5f}'
            f'{self.deltahf:10.4f}{self.p_max:9.4f}{self.matrix_id:7d}{self.structure:9d}'
            f'{len(self.distinctElements()):8d}{len(self.elements):7d}     '
            + ' '.join(f'{element:<4}' for element in self.elements)
            + f'   ! created with BCA-GUIDE'
        )


class CrystalTableError(Exception):
    """Error while reading or writing table.crystal"""


class CrystalTableFile:
    """
    Reads and extends the crystal table "tables/table.crystal" of SDTrimSP (since version 7.02).
    The file is read in the same way as SDTrimSP does it (tableread.F90, subroutine table_crystal).
    New structures and crystals are inserted without changing the other lines of the file.

    :param path: path to table.crystal
    """

    def __init__(self, path: Path):
        self.path = path
        self.lines: List[str] = []
        self.structures: List[CrystalStructure] = []
        self.crystals: List[TableCrystal] = []

        self.count_line = 0
        self.structures_end_line = 0
        self.crystals_end_line = 0

        self.load()

    def load(self):
        """Reads the file, raises CrystalTableError if the format is not valid"""

        try:
            with open(self.path, 'r', encoding='utf-8', errors='replace') as file:
                self.lines = file.read().splitlines()
        except OSError as error:
            raise CrystalTableError(f'Could not open "{self.path}": {error}')

        self.structures = []
        self.crystals = []

        try:
            # line 1: title, line 2: number of structures, line 3: title
            self.count_line = 1
            structure_count = int(self.lines[1].split()[0])
            index = 3
            for _ in range(structure_count):
                values = self.lines[index].split()
                number, atom_count = int(values[0]), int(values[1])
                name = values[2] if len(values) > 2 and not values[2].startswith('!') else f'structure-{number}'
                positions = []
                for i in range(atom_count):
                    position = self.lines[index + 1 + i].split()[:3]
                    positions.append((float(position[0]), float(position[1]), float(position[2])))
                self.structures.append(CrystalStructure(number, name, positions))
                index += 1 + atom_count
        except (IndexError, ValueError) as error:
            raise CrystalTableError(f'Could not read the crystal structures of "{self.path}": {error}')

        self.structures_end_line = index

        # 4 header lines, then crystals until a line can not be read
        index += 4
        self.crystals_end_line = index
        while index < len(self.lines):
            crystal = self.parseCrystal(self.lines[index])
            if crystal is None:
                break
            self.crystals.append(crystal)
            index += 1
            self.crystals_end_line = index

    @staticmethod
    def parseCrystal(line: str) -> Optional[TableCrystal]:
        """Parses a crystal line, returns None if the line is not a crystal"""

        values = line.split()
        try:
            atom_count = int(values[10])
            elements = values[11:11 + atom_count]
            if len(elements) != atom_count or any(element.startswith('!') for element in elements):
                return None
            return TableCrystal(
                name=values[0],
                dx=float(values[1]),
                dy=float(values[2]),
                dz=float(values[3]),
                density=float(values[4]),
                deltahf=float(values[5]),
                p_max=float(values[6]),
                matrix_id=int(values[7]),
                structure=int(values[8]),
                elements=elements
            )
        except (IndexError, ValueError):
            return None

    def structure(self, number: int) -> Optional[CrystalStructure]:
        """Returns structure with given number"""

        for structure in self.structures:
            if structure.number == number:
                return structure
        return None

    def crystal(self, name: str) -> Optional[TableCrystal]:
        """Returns crystal with given name"""

        for crystal in self.crystals:
            if crystal.name == name:
                return crystal
        return None

    def findStructure(self, positions: List[Tuple[float, float, float]]) -> Tuple[Optional[CrystalStructure], Optional[List[int]]]:
        """
        Returns an existing structure with the same positions and the order of the given positions in that structure

        :param positions: relative coordinates
        """

        for structure in self.structures:
            order = structure.matchOrder(positions)
            if order is not None:
                return structure, order
        return None, None

    def validateCrystal(self, crystal: TableCrystal, positions: Optional[List[Tuple[float, float, float]]] = None) -> List[str]:
        """
        Returns a list of problems that prevent adding the crystal

        :param crystal: new crystal
        :param positions: relative coordinates, if a new structure might be needed
        """

        errors = []
        if not crystal.name or len(crystal.name) > MAX_NAME_LENGTH or any(char.isspace() for char in crystal.name) or '!' in crystal.name:
            errors.append(f'The name must have 1 to {MAX_NAME_LENGTH} characters without spaces and "!"')
        if self.crystal(crystal.name) is not None:
            errors.append(f'A crystal with name "{crystal.name}" already exists')
        if min(crystal.dx, crystal.dy, crystal.dz) <= 0:
            errors.append('The lattice constants must be positive')
        if abs(crystal.dx - crystal.dy) > 1e-6:
            errors.append('SDTrimSP scales the x- and y-coordinates with dx, so dy must be equal to dx')
        if not crystal.elements:
            errors.append('The crystal has no atoms')
        if len(crystal.elements) > MAX_ATOMS:
            errors.append(f'SDTrimSP supports at most {MAX_ATOMS} atoms in the unit cell')
        if crystal.matrix_id not in (3, 5):
            errors.append('The matrix id must be 3 or 5')
        if positions is not None:
            structure, _ = self.findStructure(positions)
            if structure is None and len(self.structures) >= MAX_STRUCTURES:
                errors.append(f'SDTrimSP supports at most {MAX_STRUCTURES} crystal structures in table.crystal')
        elif self.structure(crystal.structure) is None:
            errors.append(f'Structure {crystal.structure} does not exist')
        return errors

    def addCrystal(
        self,
        crystal: TableCrystal,
        positions: List[Tuple[float, float, float]],
        structure_name: str = ''
    ) -> TableCrystal:
        """
        Adds a crystal and, if no matching structure exists, a new structure to the file and saves it.
        Before the first change a backup "table.crystal.bck" is created.

        :param crystal: new crystal, the elements are given in the order of positions
        :param positions: relative coordinates of the atoms
        :param structure_name: (optional) name of a new structure

        :return: added crystal (with structure number and elements in the order of the structure)
        """

        errors = self.validateCrystal(crystal, positions)
        if errors:
            raise CrystalTableError('\n'.join(errors))

        if len(positions) != len(crystal.elements):
            raise CrystalTableError('The number of positions and elements must be the same')

        lines = list(self.lines)
        structure, order = self.findStructure(positions)

        # new structure: append after the last structure and increase the number of structures
        if structure is None:
            number = max([s.number for s in self.structures], default=0) + 1
            name = (structure_name or f'{crystal.name}-type').replace(' ', '_')
            structure_lines = [f' {number}  {len(positions)} {name:<24}!Nr-crystal, number-of-atoms, name (created with BCA-GUIDE)']
            structure_lines += [f'    {x:.4f}    {y:.4f}    {z:.4f}' for x, y, z in positions]
            lines[self.structures_end_line:self.structures_end_line] = structure_lines

            count_values = lines[self.count_line].split(maxsplit=1)
            comment = count_values[1] if len(count_values) > 1 else 'number of crystal-structure or type'
            lines[self.count_line] = f'{len(self.structures) + 1}  {comment}'

            crystals_end_line = self.crystals_end_line + len(structure_lines)
            elements = list(crystal.elements)
        else:
            number = structure.number
            crystals_end_line = self.crystals_end_line
            elements = [crystal.elements[i] for i in order]

        new_crystal = TableCrystal(
            name=crystal.name,
            dx=crystal.dx,
            dy=crystal.dy,
            dz=crystal.dz,
            density=crystal.density,
            deltahf=crystal.deltahf,
            p_max=crystal.p_max,
            matrix_id=crystal.matrix_id,
            structure=number,
            elements=elements
        )
        lines.insert(crystals_end_line, new_crystal.rowStr())

        # backup before the first change
        backup = self.path.with_name(self.path.name + '.bck')
        try:
            if not backup.exists():
                copy2(self.path, backup)
            with open(self.path, 'w', encoding='utf-8', newline='\n') as file:
                file.write('\n'.join(lines) + '\n')
        except OSError as error:
            raise CrystalTableError(f'Could not write "{self.path}": {error}')

        logging.info(f'Added crystal "{new_crystal.name}" to "{self.path}"')
        self.load()
        return new_crystal

    def basisAndCoordinates(self, crystal: TableCrystal) -> Tuple[np.ndarray, dict]:
        """
        Returns the basis vectors and the relative coordinates of each element of a crystal, as used by SDTrimSP:
        x- and y-coordinates are scaled with dx, z-coordinates with dz

        :param crystal: crystal from the table
        :return: (basis vectors as 3x3 array, {element symbol: array of relative coordinates})
        """

        basis = np.diag([crystal.dx, crystal.dx, crystal.dz])
        structure = self.structure(crystal.structure)
        coordinates = {}
        if structure is None:
            return basis, coordinates
        for element, position in zip(crystal.elements, structure.positions):
            coordinates.setdefault(element, []).append(position)
        return basis, {element: np.array(positions) for element, positions in coordinates.items()}
