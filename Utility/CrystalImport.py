"""
Import of crystal structures from standard file formats:

- CIF (Crystallographic Information File, *.cif): symmetry operations are applied to get all atoms of the unit cell
- VASP POSCAR/CONTCAR (*.vasp, POSCAR, CONTCAR)

SDTrimSP describes crystals with an orthogonal unit cell (dx, dy, dz) and relative coordinates of the atoms,
so only structures with an orthogonal unit cell can be used.
"""

from __future__ import annotations
from typing import List, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from re import sub, findall, match
from fractions import Fraction
import shlex

import numpy as np


ANGLE_TOLERANCE = 1e-3  # degree
POSITION_TOLERANCE = 1e-4  # relative coordinates


class CrystalImportError(Exception):
    """Error while importing a crystal file"""


@dataclass
class ImportedCrystal:
    """
    Crystal structure read from a file

    :param name: suggested name
    :param lengths: lattice constants (a, b, c) in Angstrom
    :param angles: lattice angles (alpha, beta, gamma) in degree
    :param positions: relative coordinates of all atoms in the unit cell
    :param elements: element symbol of each atom
    :param warnings: problems that do not prevent the import
    """

    name: str
    lengths: Tuple[float, float, float]
    angles: Tuple[float, float, float] = (90., 90., 90.)
    positions: List[Tuple[float, float, float]] = field(default_factory=list)
    elements: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def isOrthogonal(self) -> bool:
        """Returns True if all lattice angles are 90 degree"""

        return all(abs(angle - 90) < ANGLE_TOLERANCE for angle in self.angles)


def importCrystal(path: Path) -> ImportedCrystal:
    """
    Imports a crystal file, the format is chosen by the file name

    :param path: path to file
    """

    name = path.name.lower()
    if name.endswith('.cif'):
        return importCif(path)
    if name.endswith('.vasp') or name.startswith('poscar') or name.startswith('contcar'):
        return importPoscar(path)
    raise CrystalImportError(f'Unknown file format of "{path.name}". Supported are CIF (*.cif) and VASP (POSCAR, CONTCAR, *.vasp) files')


def _number(value: str) -> float:
    """Converts a CIF number, e.g. "5.4310(2)", to float"""

    return float(sub(r'\(\d+\)', '', value))


def _elementFromLabel(label: str) -> str:
    """Returns the element symbol of a CIF type symbol or label, e.g. "Na1+" -> "Na", "O2" -> "O" """

    found = match(r'([A-Z][a-z]?)', label.strip())
    if found is None:
        raise CrystalImportError(f'Could not determine the element of "{label}"')
    return found.group(1)


def _wrap(position: np.ndarray) -> np.ndarray:
    """Returns relative coordinates in [0, 1)"""

    position = np.mod(position, 1.)
    position[np.isclose(position, 1., atol=POSITION_TOLERANCE)] = 0.
    position[np.isclose(position, 0., atol=POSITION_TOLERANCE)] = 0.
    return position


def _symmetryOperation(operation: str):
    """
    Returns a function that applies a symmetry operation like "-x+1/2, y, z" to relative coordinates

    :param operation: symmetry operation in xyz notation
    """

    parts = [part.strip().lower().replace(' ', '') for part in operation.split(',')]
    if len(parts) != 3:
        raise CrystalImportError(f'Could not read symmetry operation "{operation}"')

    matrix = np.zeros((3, 3))
    offset = np.zeros(3)
    for i, part in enumerate(parts):
        for sign, term in findall(r'([+-]?)([^+-]+)', part):
            factor = -1. if sign == '-' else 1.
            if term in 'xyz':
                matrix[i, 'xyz'.index(term)] += factor
            elif term[-1] in 'xyz' and term[:-1].replace('*', ''):
                matrix[i, 'xyz'.index(term[-1])] += factor * float(Fraction(term[:-1].replace('*', '')))
            else:
                offset[i] += factor * float(Fraction(term))

    return lambda position: matrix @ position + offset


def _cifTokens(path: Path) -> List[str]:
    """Returns the tokens of a CIF file (comments removed, multi-line texts skipped)"""

    tokens = []
    in_text = False
    with open(path, 'r', encoding='utf-8', errors='replace') as file:
        for line in file:
            if line.startswith(';'):
                in_text = not in_text
                continue
            if in_text:
                continue
            line = line.split('#', 1)[0].strip()
            if not line:
                continue
            try:
                tokens.extend(shlex.split(line, posix=True))
            except ValueError:
                tokens.extend(line.split())
    return tokens


def importCif(path: Path) -> ImportedCrystal:
    """
    Imports a CIF file. The first data block is used

    :param path: path to file
    """

    tokens = _cifTokens(path)
    values = {}
    loops = []
    name = path.stem
    i = 0
    while i < len(tokens):
        token = tokens[i]
        lower = token.lower()

        if lower.startswith('data_'):
            if loops or values:
                break
            name = token[5:] or name
            i += 1

        elif lower == 'loop_':
            i += 1
            headers = []
            while i < len(tokens) and tokens[i].startswith('_'):
                headers.append(tokens[i].lower())
                i += 1
            rows = []
            while i < len(tokens) and not tokens[i].startswith('_') and tokens[i].lower() not in ('loop_',) and not tokens[i].lower().startswith('data_'):
                rows.append(tokens[i:i + len(headers)])
                i += len(headers)
            loops.append((headers, [row for row in rows if len(row) == len(headers)]))

        elif token.startswith('_'):
            if i + 1 < len(tokens):
                values[lower] = tokens[i + 1]
            i += 2

        else:
            i += 1

    try:
        lengths = tuple(_number(values[f'_cell_length_{axis}']) for axis in 'abc')
        angles = tuple(_number(values.get(f'_cell_angle_{angle}', '90')) for angle in ('alpha', 'beta', 'gamma'))
    except (KeyError, ValueError) as error:
        raise CrystalImportError(f'Could not read the unit cell of "{path.name}": {error}')

    # atoms
    atoms = None
    for headers, rows in loops:
        if '_atom_site_fract_x' in headers:
            atoms = (headers, rows)
            break
    if atoms is None:
        raise CrystalImportError(f'"{path.name}" contains no atom positions with relative coordinates (_atom_site_fract_x)')

    headers, rows = atoms
    column_x, column_y, column_z = (headers.index(f'_atom_site_fract_{axis}') for axis in 'xyz')
    if '_atom_site_type_symbol' in headers:
        column_element = headers.index('_atom_site_type_symbol')
    elif '_atom_site_label' in headers:
        column_element = headers.index('_atom_site_label')
    else:
        raise CrystalImportError(f'"{path.name}" contains no element symbols of the atoms')
    column_occupancy = headers.index('_atom_site_occupancy') if '_atom_site_occupancy' in headers else None

    warnings = []
    asymmetric_atoms = []
    for row in rows:
        try:
            position = np.array([_number(row[column_x]), _number(row[column_y]), _number(row[column_z])])
        except ValueError as error:
            raise CrystalImportError(f'Could not read the position of atom "{row[column_element]}": {error}')
        if column_occupancy is not None and row[column_occupancy] not in ('.', '?'):
            if abs(_number(row[column_occupancy]) - 1) > 1e-3:
                warnings.append(f'Atom "{row[column_element]}" has a partial occupancy of {row[column_occupancy]}, it is treated as fully occupied')
        asymmetric_atoms.append((_elementFromLabel(row[column_element]), position))

    # symmetry operations
    operations = ['x, y, z']
    for headers, rows in loops:
        for key in ('_space_group_symop_operation_xyz', '_symmetry_equiv_pos_as_xyz'):
            if key in headers:
                column = headers.index(key)
                operations = [row[column] for row in rows]
                break
    symmetry_operations = [_symmetryOperation(operation) for operation in operations]

    # apply symmetry and remove duplicates
    elements = []
    positions = []
    for element, position in asymmetric_atoms:
        for operation in symmetry_operations:
            new_position = _wrap(operation(position))
            duplicate = False
            for other in positions:
                difference = np.abs(other - new_position)
                if np.all(np.minimum(difference, 1 - difference) < POSITION_TOLERANCE):
                    duplicate = True
                    break
            if not duplicate:
                positions.append(new_position)
                elements.append(element)

    return ImportedCrystal(
        name=name,
        lengths=lengths,
        angles=angles,
        positions=[tuple(float(round(value, 6)) for value in position) for position in positions],
        elements=elements,
        warnings=warnings
    )


def importPoscar(path: Path) -> ImportedCrystal:
    """
    Imports a VASP POSCAR/CONTCAR file (VASP 5 format with element symbols)

    :param path: path to file
    """

    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as file:
            lines = [line.strip() for line in file.read().splitlines()]

        name = lines[0] or path.stem
        scale = float(lines[1].split()[0])
        lattice = np.array([[float(value) for value in lines[i].split()[:3]] for i in (2, 3, 4)])
        if scale < 0:
            # negative scale is the volume of the cell
            scale = (-scale / abs(np.linalg.det(lattice))) ** (1 / 3)
        lattice *= scale

        symbols = lines[5].split()
        if all(symbol.isdigit() for symbol in symbols):
            raise CrystalImportError('The POSCAR file contains no element symbols (VASP 4 format), please add them in line 6')
        counts = [int(value) for value in lines[6].split()]
        index = 7
        if lines[index][:1].lower() == 's':
            index += 1
        cartesian = lines[index][:1].lower() in ('c', 'k')
        index += 1

        elements = []
        positions = []
        for symbol, count in zip(symbols, counts):
            for _ in range(count):
                position = np.array([float(value) for value in lines[index].split()[:3]])
                index += 1
                if cartesian:
                    position = np.linalg.solve(lattice.T, position * scale)
                positions.append(_wrap(position))
                elements.append(_elementFromLabel(symbol.split('/')[0].split('_')[0]))
    except (IndexError, ValueError) as error:
        raise CrystalImportError(f'Could not read "{path.name}": {error}')

    a, b, c = lattice
    lengths = tuple(float(np.linalg.norm(vector)) for vector in (a, b, c))

    def angle(u, v):
        return float(np.degrees(np.arccos(np.clip(u @ v / np.linalg.norm(u) / np.linalg.norm(v), -1, 1))))

    return ImportedCrystal(
        name=name.split()[0] if name.split() else path.stem,
        lengths=lengths,
        angles=(angle(b, c), angle(a, c), angle(a, b)),
        positions=[tuple(float(round(value, 6)) for value in position) for position in positions],
        elements=elements
    )
