from __future__ import annotations
from typing import List, Tuple, Dict
from dataclasses import dataclass, field
from pathlib import Path
from re import sub, findall, match
from fractions import Fraction
import shlex


import numpy as np


class CrystalImportError(Exception):
    """Error while importing a crystal file"""


@dataclass
class ImportedCrystal:
    """
    Crystal structure read from a file (SDTrimSP only supports orthogonal unit cells)

    :param name: suggested name
    :param lengths: lattice constants (a, b, c) in Angstrom
    :param angles: lattice angles (alpha, beta, gamma) in degree
    :param positions: relative coordinates of all atoms in the unit cell
    :param elements: element symbol of each atom
    :param warnings: problems that do not prevent the import
    """

    # tolerances of angles in degree and of relative coordinates
    angle_tolerance = 1e-3
    position_tolerance = 1e-4

    name: str
    lengths: Tuple[float, float, float]
    angles: Tuple[float, float, float] = (90., 90., 90.)
    positions: List[Tuple[float, float, float]] = field(default_factory=list)
    elements: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def isOrthogonal(self) -> bool:
        """Returns if all lattice angles are 90 degree"""

        return all(abs(angle - 90) < self.angle_tolerance for angle in self.angles)


def triple(values) -> Tuple[float, float, float]:
    """
    Returns first three values as tuple of floats

    :param values: list of values
    """

    return float(values[0]), float(values[1]), float(values[2])


def importCrystal(path: Path) -> ImportedCrystal:
    """
    Imports a CIF (*.cif) or VASP (POSCAR, CONTCAR, *.vasp) file, the format is chosen by the file name

    :param path: path to file
    """

    name = path.name.lower()
    try:
        if name.endswith('.cif'):
            return importCif(path)
        if name.endswith('.vasp') or name.startswith('poscar') or name.startswith('contcar'):
            return importPoscar(path)
    except CrystalImportError:
        raise
    except (OSError, ValueError, IndexError, KeyError, TypeError, ZeroDivisionError, OverflowError) as error:
        raise CrystalImportError(f'Could not read "{path.name}": {error}') from error
    raise CrystalImportError(f'Unknown file format of "{path.name}". Supported are CIF (*.cif) and VASP (POSCAR, CONTCAR, *.vasp) files')


def cifNumber(value: str) -> float:
    """
    Returns number of CIF file as float

    :param value: CIF number, e.g. "5.4310(2)"
    """

    return float(sub(r'\(\d+\)', '', value))


def elementFromLabel(label: str) -> str:
    """
    Returns element symbol of a CIF type symbol or label

    :param label: type symbol or label, e.g. "Na1+" -> "Na", "O2" -> "O"
    """

    found = match(r'([A-Z][a-z]?)', label.strip())
    if found is None:
        raise CrystalImportError(f'Could not determine the element of "{label}"')
    return found.group(1)


def wrapPosition(position: np.ndarray) -> np.ndarray:
    """
    Returns relative coordinates in [0, 1)

    :param position: relative coordinates
    """

    position = np.mod(position, 1.)
    position[np.isclose(position, 1., atol=ImportedCrystal.position_tolerance)] = 0.
    position[np.isclose(position, 0., atol=ImportedCrystal.position_tolerance)] = 0.
    return position


def symmetryOperation(operation: str):
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


def cifTokens(path: Path) -> List[str]:
    """
    Returns tokens of a CIF file (without comments and multi-line texts)

    :param path: path to file
    """

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


def isCifKeyword(token: str) -> bool:
    """
    Returns if token of a CIF file is a tag, loop or data block and no value

    :param token: token of CIF file
    """

    lower = token.lower()
    return token.startswith('_') or lower == 'loop_' or lower.startswith('data_')


def importCif(path: Path) -> ImportedCrystal:
    """
    Imports a CIF file (first data block), symmetry operations are applied to get all atoms of the unit cell

    :param path: path to file
    """

    tokens = cifTokens(path)
    values: Dict[str, str] = {}
    loops: List[Tuple[List[str], List[List[str]]]] = []
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
            # a loop without headers (damaged file) would never advance
            while headers and i < len(tokens) and not isCifKeyword(tokens[i]):
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
        lengths = triple([cifNumber(values[f'_cell_length_{axis}']) for axis in 'abc'])
        angles = triple([cifNumber(values.get(f'_cell_angle_{angle}', '90')) for angle in ('alpha', 'beta', 'gamma')])
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
            position = np.array([cifNumber(row[column_x]), cifNumber(row[column_y]), cifNumber(row[column_z])])
        except ValueError as error:
            raise CrystalImportError(f'Could not read the position of atom "{row[column_element]}": {error}')
        if column_occupancy is not None and row[column_occupancy] not in ('.', '?'):
            if abs(cifNumber(row[column_occupancy]) - 1) > 1e-3:
                warnings.append(f'Atom "{row[column_element]}" has a partial occupancy of {row[column_occupancy]}, it is treated as fully occupied')
        asymmetric_atoms.append((elementFromLabel(row[column_element]), position))

    # symmetry operations
    operations = ['x, y, z']
    for headers, rows in loops:
        for key in ('_space_group_symop_operation_xyz', '_symmetry_equiv_pos_as_xyz'):
            if key in headers:
                column = headers.index(key)
                operations = [row[column] for row in rows]
                break
    symmetry_operations = [symmetryOperation(operation) for operation in operations]

    # apply symmetry and remove duplicates
    elements = []
    positions: List[np.ndarray] = []
    for element, position in asymmetric_atoms:
        for operation in symmetry_operations:
            new_position = wrapPosition(operation(position))
            duplicate = False
            for other in positions:
                difference = np.abs(other - new_position)
                if np.all(np.minimum(difference, 1 - difference) < ImportedCrystal.position_tolerance):
                    duplicate = True
                    break
            if not duplicate:
                positions.append(new_position)
                elements.append(element)

    return ImportedCrystal(
        name=name,
        lengths=lengths,
        angles=angles,
        positions=[triple([float(round(value, 6)) for value in position]) for position in positions],
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
                positions.append(wrapPosition(position))
                elements.append(elementFromLabel(symbol.split('/')[0].split('_')[0]))
    except (IndexError, ValueError) as error:
        raise CrystalImportError(f'Could not read "{path.name}": {error}')

    a, b, c = lattice
    lengths = triple([float(np.linalg.norm(vector)) for vector in (a, b, c)])

    def angle(u: np.ndarray, v: np.ndarray) -> float:
        """
        Returns angle between two vectors in degree

        :param u: first vector
        :param v: second vector
        """

        cos_angle = u @ v / np.linalg.norm(u) / np.linalg.norm(v)
        return float(np.degrees(np.arccos(np.clip(cos_angle, -1, 1))))

    return ImportedCrystal(
        name=name.split()[0] if name.split() else path.stem,
        lengths=lengths,
        angles=(angle(b, c), angle(a, c), angle(a, b)),
        positions=[triple([float(round(value, 6)) for value in position]) for position in positions],
        elements=elements
    )
