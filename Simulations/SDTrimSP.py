from typing import Any, List, Union, Tuple, Optional, Dict, Callable, Literal
from itertools import zip_longest
from copy import deepcopy
from operator import itemgetter
from pathlib import Path
from re import findall, sub, split
import logging

import numpy as np
from matplotlib.artist import Artist
from matplotlib.cm import ScalarMappable
from matplotlib.collections import LineCollection
from matplotlib.colors import to_rgb, LogNorm, Normalize, ListedColormap, BoundaryNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QLabel, QSlider, QPushButton, QMessageBox, QMainWindow, QHBoxLayout, QVBoxLayout

from Utility.Layouts import (
    MplCanvas, InputHBoxLayout, InputHBoxLayouts, VBoxTitleLayout,
    setWidgetBackground, ListWidget, ListWidgetItem,
    SpinBox, DoubleSpinBox, SpinBoxRange, ComboBox, LineEdit
)
from Utility.Indexing import RunningIndex, DefaultAssumed, DeleteDict, ElementList
from Utility.Functions import dateStr, fileToNpArray, roundToStr, normalizeList, intSafe, floatSafe, SafeInt, readlines, pathToStr
from Utility.Dialogs import DownloadDialog, selectFileDialog
from Utility.Styles import layerHex, paletteColormap

from TableWidgets.CustomTable import CustomRowField
from TableWidgets.CompTable import CompRow
from Utility.Icons import getIcon
from Utility.Typing import notNone
from TableWidgets.DistributionEditor import (
    DistributionDialog, readDistributionFile, writeDistributionFile, readEnergyAngleFile, writeEnergyAngleFile
)

from Containers.MplCanvasSettings import MplCanvasSettings, OffscreenCanvas, AnimationExport
from Containers.Arguments import (
    ArgumentValues, GeneralBeamArguments, GeneralTargetArguments, GeneralCrystalArguments,
    GeneralArguments, RowArguments, CrystalRowArguments, SimulationArguments, StructureArguments
)
from Containers.Element import Element, Elements
from Containers.Compound import Compound
from Containers.Crystal import MillerIndex, BasisVector, Coordinate
from Containers.CrystalTableFile import CrystalTableFile, CrystalTableError, layerMillerError, layerMillerSuggestion
from Containers.Particle import Particle

from Simulations.Simulations import (
    SimulationsInput, SimulationsOutput, SimulationsAnalysis, HlGeneralBeamSettings,
    HlGeneralTargetSettings, VlGeneralSimulationSettings, HlGeneralPlot, GeneralDefaultValues
)


class Versions:
    V_601 = '6.01'
    V_606 = '6.06'  # inelastic loss model LZ7 (inel0 = 7) as default
    V_609 = '6.09'
    V_700 = '7.00, 7.01'  # introduction of crystal input files
    V_702 = '7.02, 7.05'  # introduction of global crystal files
    V_707 = '7.07'  # file of tabulated stopping power must be selected (tbsp_binary, tbsp_ascii)

    # versions in chronological order
    ORDER = [V_601, V_606, V_609, V_700, V_702, V_707]

    @staticmethod
    def atLeast(version: str, minimum: str) -> bool:
        """
        Returns True if version is equal to or newer than minimum

        :param version: version of simulation
        :param minimum: minimum version
        """

        if version not in Versions.ORDER or minimum not in Versions.ORDER:
            return False
        return Versions.ORDER.index(version) >= Versions.ORDER.index(minimum)


class CrystalTableLimits:
    """
    Limits of the crystal table "tables/table.crystal" of SDTrimSP (since version 7.02)

    :param version: version of simulation
    """

    # maximum number of crystal structures (tableread.F90: max_struc)
    max_structures = 10
    # maximum number of atoms in the unit cell (work.F90: max_atoms)
    max_atoms = 8
    # maximum length of the name of a crystal (tableread.F90: character(len=10) name_cryst)
    max_name_length = 10
    # tolerance for comparing relative coordinates of atoms
    coord_tolerance = 1e-4

    def __init__(self, version: str = ''):
        self.version = version

    # maximum number of crystals in the target (l_crystal1, l_crystal2, l_crystal3)
    max_crystals = 3


def tableCrystals(crystal_args: Optional[GeneralCrystalArguments]) -> List[dict]:
    """
    Returns the crystals from table.crystal that are used in the target (since 7.02) as list of {'name': str, 'miller': list}

    :param crystal_args: <GeneralCrystalArguments> container
    """

    if crystal_args is None:
        return []
    crystals = crystal_args.get('crystals')
    if isinstance(crystals, list) and crystals:
        return [
            {'name': str(crystal.get('name', '')), 'miller': list(crystal.get('miller', [0, 0, 0]))}
            for crystal in crystals[:CrystalTableLimits.max_crystals] if isinstance(crystal, dict)
        ]
    return [{'name': crystal_args.name, 'miller': list(crystal_args.miller_ind.vec)}]


def crystalLayers(arguments: SimulationArguments) -> List[dict]:
    """
    Returns for each layer of the target structure the fractions of the crystals and the miller index as list of
    {'fractions': list, 'miller': list}. Layers without information consist completely of the first crystal

    :param arguments: <SimulationArguments> container
    """

    crystals = tableCrystals(arguments.crystal_args)
    result = []
    for structure in arguments.structure:
        fractions = structure.get('crystal_fractions')
        fractions = [float(f) for f in fractions][:len(crystals)] if isinstance(fractions, list) else [1.0]
        fractions += [0.0] * (len(crystals) - len(fractions))
        miller = structure.get('miller')
        if not isinstance(miller, list) or len(miller) != 3:
            miller = crystals[0]['miller'] if crystals else [0, 0, 0]
        result.append({'fractions': fractions, 'miller': list(miller)})
    return result


def speciesList(arguments: SimulationArguments, group_elements: bool) -> List[Tuple[str, bool]]:
    """
    Returns the species in the order of the input file as list of (symbol, is projectile)

    :param arguments: <SimulationArguments> container
    :param group_elements: elements of beam and target are grouped
    """

    if group_elements:
        beam_rows = sorted([row for row in arguments.beam_rows if row.symbol])
        target_rows = sorted([row for row in arguments.target_rows if row.symbol])
        species = []
        used = []
        for target_row in target_rows:
            beam_row = next((row for row in beam_rows if row.symbol == target_row.symbol), None)
            if beam_row is not None:
                used.append(beam_row)
            species.append((target_row.symbol, beam_row is not None and beam_row.abundance > 0))
        for beam_row in beam_rows:
            if beam_row not in used:
                species.append((beam_row.symbol, beam_row.abundance > 0))
        return species

    rows = sorted([row for row in arguments.beam_rows + arguments.target_rows if row.symbol])
    return [(row.symbol, row in arguments.beam_rows and row.abundance > 0) for row in rows]


def distributionFileNames(arguments: SimulationArguments, version: str, group_elements: bool) -> Dict[str, List[Tuple[str, str]]]:
    """
    Returns the names of the files of the energy and angle distributions as
    {'energy': [(symbol, file name)], 'angle': [(symbol or 'all', file name)], 'energy_angle': [('all', 'ene_ang.inp')]}.
    The files depend on the selected modes (case_e0 = 1 or 6, case_alpha = 4) and the version:
    since 7.00 energy.inp, energy02.inp, ... for each species of the beam (number of the species),
    before energy.inp and energy2.inp for the first and second projectile;
    since 7.05 angle.inp, angle02.inp, ... for each species of the beam, before one angle.inp for all projectiles
    (7.02 and 7.05 share the settings, therefore angle.inp is additionally written with the first projectile for 7.02)

    :param arguments: <SimulationArguments> container
    :param version: version of simulation
    :param group_elements: elements of beam and target are grouped
    """

    case_e0 = arguments.beam_args.kinetic_energy_mode
    case_alpha = arguments.beam_args.angle_mode
    species = speciesList(arguments, group_elements)
    projectiles = [(index, symbol) for index, (symbol, beam) in enumerate(species, start=1) if beam]

    def numbered(name: str, index: int) -> str:
        return f'{name}.inp' if index == 1 else f'{name}{index:02d}.inp'

    result: Dict[str, List[Tuple[str, str]]] = {'energy': [], 'angle': [], 'energy_angle': []}
    if case_e0 == ArgumentValues.KineticEnergy.FILE:
        if Versions.atLeast(version, Versions.V_700):
            result['energy'] = [(symbol, numbered('energy', index)) for index, symbol in projectiles]
        else:
            result['energy'] = [(symbol, name) for (_, symbol), name in zip(projectiles, ['energy.inp', 'energy2.inp'])]
    if case_alpha == ArgumentValues.Angle.FILE:
        if Versions.atLeast(version, Versions.V_702):
            result['angle'] = [(symbol, numbered('angle', index)) for index, symbol in projectiles]
            if version == Versions.V_702 and projectiles and all(name != 'angle.inp' for _, name in result['angle']):
                result['angle'].append((projectiles[0][1], 'angle.inp'))
        else:
            result['angle'] = [('all', 'angle.inp')]
    if case_e0 == ArgumentValues.KineticEnergy.FILE_ENERGY_ANGLE:
        result['energy_angle'] = [('all', 'ene_ang.inp')]
    return result


def defaultInelasticLossModel(symbol: str, version: str, dict_lookup, default_values) -> str:
    """
    Returns the inelastic loss model that SDTrimSP uses if inel0 is not given in tri.inp:
    since 6.09 model 4 for H, D, T, model 5 for He, He3 and model 7 otherwise (tableread.F90), before the default of the version

    :param symbol: symbol of the element
    :param version: version of simulation
    :param dict_lookup: <DictLookup> of the version
    :param default_values: <DefaultValues> of the version
    """

    inel0 = default_values.inel0
    if Versions.atLeast(version, Versions.V_609):
        if symbol in ('H', 'D', 'T'):
            inel0 = 4
        elif symbol in ('He', 'He3'):
            inel0 = 5
    return next(key for key, value in dict_lookup.inel0.items() if value == inel0)


def readCrystalInp(path: Path) -> dict:
    """
    Reads crystal.inp (SDTrimSP 7.00 and 7.01) like SDTrimSP (init_all.F90): leading lines starting with "#" are comments,
    every value is read list-directed, i.e. a read continues on the next line if values are missing and the rest of a
    line is ignored ("1   lattice_id" reads 1)

    :param path: path of crystal.inp
    :return: {'name', 'lattice_id', 'species', 'basis_vectors' (3 lists of 3 floats), 'atoms' (list of (x, y, z, species index)),
              'p_max', 'beam_dy', 'beam_dz', 'matrix_id', 'lattice_constant' (from the comment "# lattice_constant = ...", 1 otherwise)}
    :raises OSError: if the file can not be read
    :raises ValueError, IndexError: if the file has an incorrect format
    """

    with open(path, 'r', encoding='utf-8', errors='replace') as file:
        lines = file.read().splitlines()

    lattice_constant = 1.
    start = 0
    while start < len(lines) and lines[start].strip().startswith('#'):
        if lines[start].strip().startswith('# lattice_constant'):
            lattice_constant = float(lines[start].split('=')[-1])
        start += 1
    lines = lines[start:]
    position = [0]

    def read(count: int) -> List[str]:
        """Reads count values starting at the next line"""
        values: List[str] = []
        while len(values) < count:
            line = lines[position[0]].split('!')[0]
            position[0] += 1
            values += [value.strip('"\'') for value in line.replace(',', ' ').split()]
        return values[:count]

    crystal: Dict[str, Any] = {'name': read(1)[0], 'lattice_id': int(float(read(1)[0]))}
    species_count = int(float(read(1)[0]))
    crystal['species'] = [read(1)[0] for _ in range(species_count)]
    crystal['basis_vectors'] = [[float(value) for value in read(3)] for _ in range(3)]
    atom_count = int(float(read(1)[0]))
    crystal['atoms'] = []
    for _ in range(atom_count):
        values = read(4)
        crystal['atoms'].append((float(values[0]), float(values[1]), float(values[2]), int(float(values[3]))))
    crystal['p_max'] = float(read(1)[0])
    crystal['beam_dy'], crystal['beam_dz'] = (float(value) for value in read(2))
    crystal['matrix_id'] = int(float(read(1)[0]))
    crystal['lattice_constant'] = lattice_constant
    return crystal


def layerTargetSpecies(layer_file: Path, ncp: int) -> List[float]:
    """
    Returns 1 for the species that occur in a layer of layer.inp (qu_1 = 1 - sum of the other species), otherwise 0

    :param layer_file: path of layer.inp
    :param ncp: number of species
    """

    maximum = [0.] * ncp
    try:
        with open(layer_file, 'r', encoding='utf-8', errors='replace') as file:
            for line in file:
                values = line.split('!')[0].split()
                if len(values) < ncp + 1 or line.lstrip().startswith(('!', '#')):
                    continue
                try:
                    count = int(values[0])
                    fractions = [float(value.replace('D', 'E').replace('d', 'e')) for value in values[2:ncp + 1]]
                except ValueError:
                    continue
                if count <= 0:
                    break
                for i, fraction in enumerate([1. - sum(fractions)] + fractions):
                    maximum[i] = max(maximum[i], fraction)
    except OSError:
        pass
    return [1. if fraction > 1e-9 else 0. for fraction in maximum]


def readTrajectoryFile(path: Path) -> List[dict]:
    """
    Reads the trajectories of trajec_all.dat (or trajec_stop_p.dat, ...), written with ltraj_p/ltraj_r.
    Each trajectory starts with a line of "i_traj ihist iproj parent ncoll species ibn termflag",
    followed by the points "k x y z ptime energy" (ptime in fs).
    Since SDTrimSP 6.09 "parent" is the generation of a recoil (0: projectile), until 6.06 it is the species of the parent.
    Since 6.09 the time of a recoil starts at 0, the absolute time is reconstructed from the trajectories of the
    previous generation (see trajectoryStartTimes)

    :param path: path of the file

    :return: list of trajectories {'projectile': (ihist, iproj), 'recoil': bool, 'generation': int or None if unknown,
             'species': index of species starting at 0, 'termflag': int, 'collisions': int,
             'points': array of (x, y, z, energy, absolute time)}
    """

    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as file:
            lines = file.read().splitlines()
    except OSError:
        return []

    header = lines[0] if lines else ''
    numbers = findall(r'\d+\.\d+', header)
    generation_known = not numbers or float(numbers[0]) >= 6.09

    trajectories: List[dict] = []
    current = None
    points: list = []
    expect_info = False

    def finish():
        if current is not None:
            current['points'] = np.array(points, dtype=float).reshape(-1, 5)
            trajectories.append(current)

    for line in lines[3:]:
        text = line.strip().lstrip('#').strip()
        if not text:
            continue
        if text.startswith('i_traj'):
            finish()
            current, points, expect_info = None, [], True
            continue
        if text.startswith('k ') or text.startswith('ende'):
            if text.startswith('ende'):
                finish()
                current = None
            continue
        values = text.split()
        if expect_info:
            expect_info = False
            try:
                _, ihist, iproj, parent, ncoll, species, _, termflag = (int(value) for value in values[:8])
            except ValueError:
                continue
            # termflag 1-3: stopped, backscattered, transmitted projectile; 4-6: the same for recoils
            recoil = termflag >= 4 if termflag > 0 else parent > 0
            current = {
                'projectile': (ihist, iproj),
                'recoil': recoil,
                'generation': (parent if recoil else 0) if generation_known else (1 if recoil else 0),
                'generation_known': generation_known,
                'species': species - 1,
                'termflag': termflag,
                'collisions': ncoll
            }
            continue
        if current is not None and len(values) >= 6:
            try:
                points.append([float(values[1]), float(values[2]), float(values[3]), float(values[5]), float(values[4])])
            except ValueError:
                pass
    finish()
    trajectoryStartTimes(trajectories)
    return trajectories


def trajectoryStartTimes(trajectories: List[dict]):
    """
    Changes the times of the recoils to absolute times (since the start of the projectile).
    Since SDTrimSP 6.09 the time of each recoil starts at 0. A recoil is created at a collision of a particle of the
    previous generation, its start time is the time of the nearest point of the trajectories of the previous generation
    of the same projectile. Until 6.06 the times are already absolute (and the generation is unknown)

    :param trajectories: trajectories of readTrajectoryFile (changed in place)
    """

    by_projectile: Dict[tuple, List[dict]] = {}
    for trajectory in trajectories:
        by_projectile.setdefault(trajectory['projectile'], []).append(trajectory)

    for group in by_projectile.values():
        if not all(trajectory.get('generation_known', True) for trajectory in group):
            continue
        for generation in sorted({trajectory['generation'] for trajectory in group if trajectory['generation'] > 0}):
            parents = [t['points'] for t in group if t['generation'] == generation - 1 and len(t['points'])]
            if not parents:
                continue
            parent_points = np.vstack(parents)
            for trajectory in group:
                points = trajectory['points']
                if trajectory['generation'] != generation or not len(points) or points[0, 4] > 0:
                    continue
                distances = np.sum((parent_points[:, :3] - points[0, :3]) ** 2, axis=1)
                points[:, 4] += parent_points[np.argmin(distances), 4]


def readLayers(save_folder: Path) -> List[Tuple[float, float, str]]:
    """
    Returns the layers of the target as (top, bottom, name) in [Å] from layer.inp or the target thickness from tri.inp

    :param save_folder: folder of the simulation
    """

    layers: List[Tuple[float, float, str]] = []
    try:
        with open(save_folder / 'layer.inp', 'r', encoding='utf-8', errors='replace') as file:
            depth = 0.
            for line in file:
                values = line.split('!')[0].split()
                if len(values) < 2 or line.lstrip().startswith(('!', '#')):
                    continue
                try:
                    count, thickness = int(values[0]), float(values[1].replace('D', 'E').replace('d', 'e'))
                except ValueError:
                    continue
                if count <= 0:
                    break
                name = values[-1] if not values[-1].replace('.', '').replace('E', '').replace('-', '').replace('+', '').isdigit() else f'Layer {len(layers) + 1}'
                layers.append((depth, depth + count * thickness, name))
                depth += count * thickness
    except OSError:
        pass
    if layers:
        return layers

    try:
        with open(save_folder / 'tri.inp', 'r', encoding='utf-8', errors='replace') as file:
            for line in file:
                values = line.split('!')[0].replace(' ', '').split('=')
                if len(values) == 2 and values[0].lower() == 'ttarget':
                    return [(0., float(values[1].replace('D', 'E').replace('d', 'e')), 'Target')]
    except (OSError, ValueError):
        pass
    return []


def joinValues(values: list) -> str:
    """Returns the values as comma separated list of a Fortran namelist"""

    return ', '.join(f'{value}' for value in values)


def numbersOfLine(line: str) -> List[float]:
    """
    Returns all numbers of a line or an empty list if the line contains other text.
    Fortran exponents with D are accepted, numbers without blank in between (e.g. "0.24525E-04-0.10110E-04") are separated
    """

    if findall(r'[a-cf-zA-CF-Z]', line):
        return []
    values = findall(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[EeDd][-+]?\d+)?', line)
    try:
        return [float(value.replace('D', 'E').replace('d', 'e')) for value in values]
    except ValueError:
        return []


def readEnergyDistribution(path: Path) -> Optional[dict]:
    """
    Reads a file of the energy distribution in the target (lenergy_distr: E_distr_all.dat, E_distr_stop.dat, E_distr_inel.dat,
    E_distr_nucl.dat). The file contains the edges of the intervals in x (depth), y and z and for each depth interval a matrix
    of nz lines with ny values. The number of z intervals in the header is wrong (ny is written twice), so the edges are used

    :param path: path of the file

    :return: {'x', 'y', 'z': edges of the intervals [Å], 'values': array (nx, ny, nz) in [eV/Å³/projectile], 'projectiles': number}
             or None if the file can not be read
    """

    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as file:
            lines = file.read().splitlines()
    except OSError:
        return None

    edges: Dict[str, List[float]] = {}
    blocks: List[List[List[float]]] = []
    projectiles = 0.
    delta = 0.
    normalized = False
    section = None
    for line in lines[2:]:
        text = line.strip().lower()
        if not text:
            continue
        if 'nh*nr_pproj' in text:
            numbers = numbersOfLine(text.split('nh')[0])
            projectiles = numbers[0] if numbers else 0.
            continue
        if 'dist_delta' in text and not blocks:
            numbers = numbersOfLine(text.split('dx')[0])
            delta = numbers[0] if numbers else 0.
            continue
        if text.startswith('intervals'):
            section = text.split()[1]
            edges[section] = []
            continue
        if 'depth-interval' in text:
            section = 'values'
            normalized = 'delta**3' in text
            blocks.append([])
            continue
        if text.startswith(('normalized', 'sum ')):
            section = None
            continue
        numbers = numbersOfLine(text)
        if not numbers:
            continue
        if section in ('x', 'y', 'z'):
            edges[section] += numbers
        elif section == 'values':
            blocks[-1].append(numbers)

    if any(len(edges.get(axis, [])) < 2 for axis in 'xyz') or not blocks:
        return None
    nx, ny, nz = len(edges['x']) - 1, len(edges['y']) - 1, len(edges['z']) - 1
    try:
        values = np.array([block[:nz] for block in blocks[:nx]], dtype=float)  # (nx, nz, ny)
    except ValueError:
        return None
    if values.shape != (nx, nz, ny):
        return None
    values = np.transpose(values, (0, 2, 1))

    # E_distr_stop/inel/nucl are written in eV, E_distr_all is normalized to [eV/delta**3/nh/nr_pproj]
    if not normalized and projectiles > 0 and delta > 0:
        values = values / (delta ** 3 * projectiles)
    return {'x': np.array(edges['x']), 'y': np.array(edges['y']), 'z': np.array(edges['z']), 'values': values, 'projectiles': projectiles}


def readEnergyDepthMatrix(path: Path) -> List[dict]:
    """
    Reads a matrix of counts over the energy and the depth (morigin_ex_bs.dat, morigin_ex_ts.dat: depth of origin of
    sputtered atoms, mpe_ex_p.dat: maximum penetration depth of backscattered projectiles)

    :param path: path of the file

    :return: list of {'species': name, 'energies': array, 'depths': array (centers), 'counts': array (energies, depths),
             'projectiles': number of projectiles}
    """

    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as file:
            lines = file.read().splitlines()
    except OSError:
        return []

    matrices: List[Dict[str, Any]] = []
    projectiles = 0.
    current: Optional[Dict[str, Any]] = None
    for line in lines[2:]:
        text = line.strip()
        lower = text.lower()
        if 'nproj' in lower or 'nh*nr' in lower:
            numbers = numbersOfLine(text.split()[0])
            projectiles = numbers[0] if numbers else projectiles
            continue
        if 'component(' in lower:
            name = text.split(':')[-1].strip() if ':' in text else f'Species {len(matrices) + 1}'
            current = {'species': name, 'energies': [], 'depths': None, 'counts': [], 'projectiles': projectiles, 'dimensions': None}
            matrices.append(current)
            continue
        if current is None or lower.startswith(('#', 'energy')):
            continue
        numbers = numbersOfLine(text)
        if not numbers:
            continue
        if current['dimensions'] is None:
            # line with the dimensions (energies, depths, logarithmic energies)
            current['dimensions'] = numbers
            continue
        if current['depths'] is None:
            # line with 0 and the depths
            if len(numbers) > 1:
                current['depths'] = numbers[1:]
            continue
        if numbers[0] == 0 and current['energies']:
            # sums of the columns
            continue
        if len(numbers) > len(current['depths']):
            current['energies'].append(numbers[0])
            current['counts'].append(numbers[1:1 + len(current['depths'])])

    result = []
    for matrix in matrices:
        if matrix['depths'] is None or not matrix['counts']:
            continue
        matrix['energies'] = np.array(matrix['energies'])
        matrix['depths'] = np.array(matrix['depths'])
        matrix['counts'] = np.array(matrix['counts'], dtype=float)
        if not matrix['projectiles']:
            matrix['projectiles'] = projectiles
        del matrix['dimensions']
        result.append(matrix)
    return result


def matrixSpecies(path: Path) -> List[str]:
    """Returns the names of the species of the matrices with linear energy intervals in a matrix file (e.g. meagb_p.dat)"""

    names: List[str] = []
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as file:
            previous = ''
            for line in file:
                if 'lin.energy' in line.lower() and 'COMPONENT(' in previous.upper():
                    names.append(previous.split(':')[-1].strip() if ':' in previous else f'Species {len(names) + 1}')
                previous = line
    except OSError:
        pass
    return names


def readEnergyAngleMatrix(path: Path) -> List[dict]:
    """
    Reads the matrix of the energy, azimuthal and polar angle of backscattered or transmitted particles (lmatrices:
    meagb_p.dat, meagb_s.dat, meagt_p.dat, meagt_s.dat). Only the matrices with linear energy intervals are read,
    the counts are summed over the azimuthal angle

    :param path: path of the file

    :return: list of {'species': name, 'energies': array, 'polar': array, 'counts': array (energies, polar angles), 'projectiles': number}
    """

    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as file:
            lines = file.read().splitlines()
    except OSError:
        return []

    matrices: List[Dict[str, Any]] = []
    i = 0
    while i < len(lines):
        text = lines[i].strip()
        if 'COMPONENT(' not in text.upper() or i + 2 >= len(lines) or 'lin.energy' not in lines[i + 1].lower():
            i += 1
            continue
        name = text.split(':')[-1].strip() if ':' in text else f'Species {len(matrices) + 1}'
        dimensions = numbersOfLine(lines[i + 2])
        if len(dimensions) < 3:
            i += 1
            continue
        n_energy, n_azimuth, n_polar = (int(value) for value in dimensions[:3])
        projectiles = dimensions[3] if len(dimensions) > 3 else 0.
        i += 3

        def readValues(label: str) -> List[float]:
            nonlocal i
            while i < len(lines) and label not in lines[i].upper():
                i += 1
            i += 1
            values = []
            while i < len(lines) and not lines[i].lstrip().startswith('#'):
                numbers = numbersOfLine(lines[i])
                if not numbers:
                    break
                values += numbers
                i += 1
                if len(values) >= (n_energy if label == 'ENERGY' else n_azimuth if label == 'AZIMUTHAL' else n_polar):
                    break
            return values

        energies = readValues('ENERGY')
        readValues('AZIMUTHAL')
        polar = readValues('POLAR')
        counts = np.zeros((n_energy, n_polar))
        for k in range(n_energy):
            # line with the polar angles, then one line per azimuthal angle
            i += 1
            block = []
            for _ in range(n_azimuth):
                if i >= len(lines):
                    break
                block.append(numbersOfLine(lines[i])[:n_polar])
                i += 1
            try:
                counts[k] = np.sum(np.array(block, dtype=float), axis=0)
            except ValueError:
                pass
        matrices.append({'species': name, 'energies': np.array(energies[:n_energy]), 'polar': np.array(polar[:n_polar]),
                         'counts': counts, 'projectiles': projectiles})

    # the number of projectiles is only written for the first species
    projectiles = max([matrix['projectiles'] for matrix in matrices], default=0.)
    for matrix in matrices:
        matrix['projectiles'] = matrix['projectiles'] or projectiles
    return matrices


MAX_ELEMENTS_CACHE: Dict[str, Optional[int]] = {}


def maxElements(folder: Optional[Path]) -> Optional[int]:
    """
    Returns the maximum number of elements (ncp) that an installation of SDTrimSP is compiled for or None if unknown.
    The number is taken from the parameter ncpm in the source code (src/param.F90), e.g. 3 for SDTrimSP 6.01 and 12 for
    7.00. More elements stop SDTrimSP with the error 'Cannot match namelist object name ...' while reading tri.inp

    :param folder: folder of the installation
    """

    if folder is None:
        return None
    key = str(folder)
    if key not in MAX_ELEMENTS_CACHE:
        value = None
        for source in sorted((folder / 'src').glob('*.[fF]90')) if (folder / 'src').is_dir() else []:
            try:
                text = source.read_text(encoding='utf-8', errors='replace')
            except OSError:
                continue
            numbers = findall(r'(?im)^\s*integer\s*,\s*parameter\s*::.*?\bncpm\s*=\s*(\d+)', text)
            if numbers:
                value = int(numbers[0])
                break
        MAX_ELEMENTS_CACHE[key] = value
    return MAX_ELEMENTS_CACHE[key]


STOPPING_TABLE_CACHE: Dict[str, Optional[set]] = {}


def stoppingTableSymbols(folder: Optional[Path], table: str) -> Optional[set]:
    """
    Returns the symbols of a table of an installation of SDTrimSP (e.g. "table3" with the coefficients of H, D and T
    stopping, "table4" of He stopping) or None if the table can not be read. Lines of a symbol start with the symbol and
    the atomic number, comment lines with "c"

    :param folder: folder of the installation
    :param table: name of the table in the folder "tables"
    """

    if folder is None:
        return None
    key = str(folder / 'tables' / table)
    if key not in STOPPING_TABLE_CACHE:
        symbols: Optional[set] = None
        try:
            symbols = set()
            for line in (folder / 'tables' / table).read_text(encoding='utf-8', errors='replace').splitlines():
                values = line.split()
                if len(values) > 2 and values[1].isdigit():
                    symbols.add(values[0])
        except OSError:
            symbols = None
        STOPPING_TABLE_CACHE[key] = symbols
    return STOPPING_TABLE_CACHE[key]


NAMELIST_CACHE: Dict[str, Optional[set]] = {}


def namelistParameters(folder: Optional[Path]) -> Optional[set]:
    """
    Returns the names (lower case) of the parameters of tri.inp that an installation of SDTrimSP accepts or None if unknown.
    The names are taken from the definition of the namelist TRI_INP in the source code (src/work.F90), otherwise from
    the list of variables in the documentation (doc/tri.inp.txt)

    :param folder: folder of the installation
    """

    if folder is None:
        return None
    key = str(folder)
    if key in NAMELIST_CACHE:
        return NAMELIST_CACHE[key]

    names = None
    for source in sorted((folder / 'src').glob('*.[fF]90')) if (folder / 'src').is_dir() else []:
        try:
            text = source.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        if not findall(r'(?i)namelist\s*/\s*tri_inp\s*/', text):
            continue
        # continuation lines end with "&", comments start with "!"
        lines = []
        started = False
        for line in text.splitlines():
            if not started:
                if findall(r'(?i)namelist\s*/\s*tri_inp\s*/', line):
                    started = True
                    line = line.split('/', 2)[-1]
                else:
                    continue
            code = line.split('!')[0]
            if not code.strip() and line.strip().startswith('!'):
                continue
            lines.append(code.replace('&', ' '))
            if not code.rstrip().endswith('&'):
                break
        names = {name.lower() for name in findall(r'[A-Za-z_][A-Za-z0-9_]*', ' '.join(lines))}
        break

    if names is None:
        try:
            text = (folder / 'doc' / 'tri.inp.txt').read_text(encoding='utf-8', errors='replace')
        except OSError:
            text = ''
        if 'variable in tri.inp' in text:
            names = set()
            for line in text.split('variable in tri.inp', 1)[1].splitlines():
                match = findall(r'^\s([a-z][a-z0-9_]*)', line)
                if match and not line.lstrip().startswith('!'):
                    names.add(match[0].lower())
            names = names or None

    NAMELIST_CACHE[key] = names
    return names


def electronicStopping(energy: float, z1: int, m1: float, z2: float) -> float:
    """
    Returns an estimate of the electronic stopping cross-section in [eV Å²]: Lindhard-Scharff at low energies, Bethe at high
    energies, combined as 1 / (1 / S_LS + 1 / S_Bethe)

    :param energy: energy of the projectile in [eV]
    :param z1: atomic number of the projectile
    :param m1: mass of the projectile in [amu]
    :param z2: (mean) atomic number of the target
    """

    lindhard = 1.212 * z1 ** (7 / 6) * z2 * np.sqrt(energy / m1) / (z1 ** (2 / 3) + z2 ** (2 / 3)) ** 1.5
    # Bethe: 4 pi e^4 Z1^2 Z2 / (m_e v^2) ln(2 m_e v^2 / I) with e^2 = 14.4 eV Å, m_e v^2 = 2 E m_e / M1, I = 10 Z2 eV
    electron_energy = 2 * energy * 5.4858e-4 / m1
    argument = 2 * electron_energy / (10 * z2)
    if argument <= np.e:
        return lindhard
    bethe = 4 * np.pi * 14.4 ** 2 * z1 ** 2 * z2 / electron_energy * np.log(argument)
    return 1 / (1 / lindhard + 1 / bethe)


def nuclearStopping(energy: float, z1: int, m1: float, z2: float, m2: float) -> float:
    """
    Returns the nuclear stopping cross-section of the universal ZBL potential in [eV Å²]

    :param energy: energy of the projectile in [eV]
    :param z1: atomic number of the projectile
    :param m1: mass of the projectile in [amu]
    :param z2: (mean) atomic number of the target
    :param m2: (mean) mass of the target in [amu]
    """

    screening = z1 ** 0.23 + z2 ** 0.23
    reduced = 32.53 * m2 * energy / 1000 / (z1 * z2 * (m1 + m2) * screening)
    if reduced <= 30:
        reduced_stopping = np.log(1 + 1.1383 * reduced) / (2 * (reduced + 0.01321 * reduced ** 0.21226 + 0.19593 * reduced ** 0.5))
    else:
        reduced_stopping = np.log(reduced) / (2 * reduced)
    return 84.62 * z1 * z2 * m1 * reduced_stopping / ((m1 + m2) * screening)


def estimateRange(energy: float, z1: int, m1: float, z2: float, m2: float, density: float) -> float:
    """
    Returns an estimate of the path length (upper limit of the projected range) of a projectile in [Å]

    :param energy: energy of the projectile in [eV]
    :param z1: atomic number of the projectile
    :param m1: mass of the projectile in [amu]
    :param z2: (mean) atomic number of the target
    :param m2: (mean) mass of the target in [amu]
    :param density: atomic density of the target in [atoms/Å³]
    """

    if energy <= 1 or density <= 0 or z1 <= 0 or z2 <= 0:
        return 0.
    energies = np.geomspace(1., energy, 400)
    stopping = np.array([density * (nuclearStopping(e, z1, m1, z2, m2) + electronicStopping(e, z1, m1, z2)) for e in energies])
    # numpy.trapz was renamed to numpy.trapezoid in numpy 2.0
    integrate = getattr(np, 'trapezoid', None) or getattr(np, 'trapz')
    return float(integrate(1 / stopping, energies))


def usesCrystalLayerFile(arguments: SimulationArguments, version: str) -> bool:
    """
    Returns True if crystals from table.crystal (since 7.02) are used in a way that needs the layer file layer.inp:
    more than one crystal, more than one layer or a layer that is not completely crystalline

    :param arguments: <SimulationArguments> container
    :param version: version of simulation
    """

    if not DefaultValues(version).crystal_table or not arguments.target_args.get('crystal_flag', False):
        return False
    crystal_args = arguments.crystal_args
    if crystal_args is None:
        return False
    crystals = tableCrystals(crystal_args)
    layers = crystalLayers(arguments)
    if len(crystals) > 1 or len(layers) > 1:
        return True
    return any(abs(fraction - 1) > 1e-9 for layer in layers for fraction in layer['fractions'])


class DefaultValues(GeneralDefaultValues):
    """
    Default values for this simulation

    :param version: version of simulation
    """

    # general beam settings
    case_e0 = 0
    case_alpha = 0
    number_calc = 18

    # general target settings
    ttarget = 2000
    nqx = 200
    globaldensity = False

    # general settings
    idrel = 1
    nh = 1000
    idout = 10
    nr_pproj = 100
    flc = 1.0
    ipot = 1
    iintegral = 2
    isbv = 1

    # beam/target row
    qubeam = 0
    e0 = 500
    alpha0 = 0
    qumax = 1
    dns0 = 0
    e_surfb = 0
    e_displ = 0
    inel0 = 3

    # group elements
    group_elements = True

    # output options
    lparticle_p = False
    lparticle_r = False
    lmatrices = False

    # compounds
    l_two_comp = False
    l_two_comp2 = False
    l_two_comp3 = False

    # tabulated stopping power file (since 7.07): 'binary' (tbsp.db) or 'ascii' (tbsp.ascii)
    tbsp_format = 'binary'

    # further parameters of beam and elements (-1: value from the tables or default of SDTrimSP)
    shth = 0.
    beta0 = 0.
    x0 = 0.
    charge = 0.
    e_cutoff = -1.
    e_bulkb = -1.
    deltahf = -1.
    isot = 0
    ck_elec = 1.

    # further settings
    irand = 1
    sfin = 0
    ltraj_p = False
    ltraj_r = False
    numb_hist = 20
    lenergy_distr = False
    dist_nx = 60
    dist_ny = 60
    dist_nz = 60
    dist_delta = 2.0

    # general crystal settings
    crystal_name = 'MyLittleCrystal'
    lattice_id = 1

    l_crystal = False
    l_crystal_dyn = False
    crystal_capable = False

    miller_ind = MillerIndex([0, 0, 0])

    basis_vec_a1 = BasisVector(direction=1)
    basis_vec_a2 = BasisVector(direction=2)
    basis_vec_a3 = BasisVector(direction=3)

    p_max = 3
    beam_dy = 0
    beam_dz = 0

    matrix_id = 3

    lattice_constant = 1

    def __init__(self, version: str):
        # defaults according to the documentation (doc/default_init.txt, doc/tri.inp.txt) of each version
        if Versions.atLeast(version, Versions.V_606):
            self.inel0 = 7
        if Versions.atLeast(version, Versions.V_609):
            self.isbv = 8

        # crystal input
        if Versions.atLeast(version, Versions.V_700):
            self.enable_crystal = True

        # since 7.02 crystals are selected from tables/table.crystal and crystal.inp is not used anymore
        self.crystal_table = Versions.atLeast(version, Versions.V_702)

        # since 7.07 the file of the tabulated stopping power (inel0=8) must be selected
        self.tbsp_file_selection = Versions.atLeast(version, Versions.V_707)

        # parameters that are not available in all versions
        self.supports_beta0 = Versions.atLeast(version, Versions.V_700)  # azimuthal angle
        self.supports_x0 = Versions.atLeast(version, Versions.V_609)  # starting depth (not in 6.06)
        self.supports_deltahf = Versions.atLeast(version, Versions.V_609)  # heat of formation per element (scalar before)
        # case_e0 = 6 (ene_ang.inp) is not implemented in 7.00 - 7.02 (7.02 shares the settings with 7.05, see SimulationInput.supportsEnergyAngleFile)
        self.supports_energy_angle_file = not Versions.atLeast(version, Versions.V_700) or Versions.atLeast(version, Versions.V_702)
        # sfin = 1 crashes the Windows binaries of 7.00 - 7.07 with an access violation (also without other changes)
        self.supports_sfin = not Versions.atLeast(version, Versions.V_700)


class DictLookup:
    """
    Class to store lookup dictionaries that link simulation values to meaningful values

    :param version: version of simulation
    """

    inel0 = {
        ArgumentValues.InelasticLossModel.LINDHARD_SCHARFF: 1,
        ArgumentValues.InelasticLossModel.OEN_ROBINSON: 2,
        ArgumentValues.InelasticLossModel.LINDHARD_SCHARFF_AND_OEN_ROBINSON: 3,
        ArgumentValues.InelasticLossModel.HYDROGEN: 4,
        ArgumentValues.InelasticLossModel.HELIUM: 5,
        ArgumentValues.InelasticLossModel.ZIEGLER: 6,
        ArgumentValues.InelasticLossModel.LINDHARD_SCHARFF_AND_ZIEGLER: 7
    }

    idrel = {
        ArgumentValues.Mode.STATIC_NO_RECOIL: -1,
        ArgumentValues.Mode.DYNAMIC: 0,
        ArgumentValues.Mode.STATIC: 1
    }

    ipot = {
        ArgumentValues.InteractionPotential.KRC: 1,
        ArgumentValues.InteractionPotential.MOLIERE: 2,
        ArgumentValues.InteractionPotential.ZBL: 3,
        ArgumentValues.InteractionPotential.NAKAGAWA_YAMAMURA: 4,
        ArgumentValues.InteractionPotential.SI_SI: 5,
        ArgumentValues.InteractionPotential.POWER: 6
    }

    iintegral = {
        ArgumentValues.IntegrationMethod.MAGIC: 0,
        ArgumentValues.IntegrationMethod.GAUSS_MEHLER: 1,
        ArgumentValues.IntegrationMethod.GAUSS_LEGENDRE: 2
    }

    isbv = {
        ArgumentValues.SurfaceBindingModel.ELEMENT_SPECIFIC: 1,
        ArgumentValues.SurfaceBindingModel.AVERAGE: 2,
        ArgumentValues.SurfaceBindingModel.ELEMENT_PAIRS: 3,
        ArgumentValues.SurfaceBindingModel.SOLID_SOLID: 4,
        ArgumentValues.SurfaceBindingModel.SOLID_GAS: 5,
        ArgumentValues.SurfaceBindingModel.FILE: 6,
        ArgumentValues.SurfaceBindingModel.ELECTRONEGATIVITY: 7
    }

    case_e0 = {
        ArgumentValues.KineticEnergy.FIXED: 0,
        ArgumentValues.KineticEnergy.FILE: 1,
        ArgumentValues.KineticEnergy.MAXWELLIAN_VELOCITY_DISTRIBUTION: 2,
        ArgumentValues.KineticEnergy.MAXWELLIAN_ENERGY_DISTRIBUTION: 3,
        ArgumentValues.KineticEnergy.SWEEP: 5,
        ArgumentValues.KineticEnergy.FILE_ENERGY_ANGLE: 6
    }

    case_alpha = {
        ArgumentValues.Angle.FIXED: 0,
        ArgumentValues.Angle.RANDOM_DISTRIBUTION: 1,
        ArgumentValues.Angle.COS_DISTRIBUTION_1: 2,
        ArgumentValues.Angle.COS_DISTRIBUTION_2: 3,
        ArgumentValues.Angle.FILE: 4,
        ArgumentValues.Angle.SWEEP: 5,
        ArgumentValues.Angle.FILE_ENERGY_ANGLE: 6
    }

    def __init__(self, version: str):
        # since 6.09: isbv=5 and isbv=7 do not work anymore, isbv=4 is used for compounds, isbv=8 is new
        if Versions.atLeast(version, Versions.V_609):
            self.isbv = {
                ArgumentValues.SurfaceBindingModel.ELEMENT_SPECIFIC: 1,
                ArgumentValues.SurfaceBindingModel.AVERAGE: 2,
                ArgumentValues.SurfaceBindingModel.ELEMENT_PAIRS: 3,
                ArgumentValues.SurfaceBindingModel.COMPOUNDS: 4,
                ArgumentValues.SurfaceBindingModel.FILE: 6,
                ArgumentValues.SurfaceBindingModel.TABLE: 8
            }

        # since 7.00: tabulated stopping power (inel0=8)
        if Versions.atLeast(version, Versions.V_700):
            self.inel0 = dict(DictLookup.inel0)
            self.inel0[ArgumentValues.InelasticLossModel.TABULATED] = 8


class HlBeamSettings(HlGeneralBeamSettings):
    """
    QHBoxLayout for general beam settings

    :param version: version of simulation
    """

    def __init__(self, version: str):
        self.default_values = DefaultValues(version)
        super().__init__(version, self.default_values)

        # kinetic energy mode
        self.kinetic_energy = ComboBox(
            default=self.default_values.case_e0,
            tooltips=[
                'The energy (in eV) for each element in the beam is constant and defined in the table below',
                'The energy distribution of the beam is read from the <i>energy.inp</i> file',
                'The energy for each element in the beam is defined in the table below as the temperature of a Maxwellian velocity distribution  (in eV)',
                'The energy for each element in the beam is defined in the table below as the temperature of a Maxwellian energy distribution  (in eV)',
                '',
                'A series of calculations at different energies, with energy steps defined for each element in the table',
                'The angle and energy distribution of the beam is read from the <i>ene_ang.inp</i> file'
            ],
            numbering=0,
            label_default=True,
            entries=[
                'constant',
                'energy.inp',
                'Maxwell velocity distr. temp.',
                'Maxwell energy distr. temp.',
                '(unused)',
                'energy sweep',
                'ene_ang.inp'
            ],
            entries_save=[
                ArgumentValues.KineticEnergy.FIXED,
                ArgumentValues.KineticEnergy.FILE,
                ArgumentValues.KineticEnergy.MAXWELLIAN_VELOCITY_DISTRIBUTION,
                ArgumentValues.KineticEnergy.MAXWELLIAN_ENERGY_DISTRIBUTION,
                -1,
                ArgumentValues.KineticEnergy.SWEEP,
                ArgumentValues.KineticEnergy.FILE_ENERGY_ANGLE
            ],
            disabled_list=[4] if self.default_values.supports_energy_angle_file else [4, 6]
        )
        self.layout_kinetic_energy = InputHBoxLayout(
            'Kinetic energy [eV]:',
            self.kinetic_energy,
            tooltip='<i>case_e0</i><br>How the energy of the projectiles in the beam is defined',
        )
        self.energy_previous = self.kinetic_energy.getValue(save=True)
        self.kinetic_energy.currentIndexChanged.connect(lambda _: self.changedEnergy())
        self.kinetic_energy.currentIndexChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_kinetic_energy)
        self.addSpacing(20)

        # angle mode
        self.angle = ComboBox(
            default=self.default_values.case_alpha,
            tooltips=[
                'The angle α (in °) for each element in the beam is constant and defined in the table below',
                'The angles α and φ are sampled from a random distribution',
                'The angles α and φ follow a cosine distribution (1st type)',
                'The angles α and φ follow a cosine distribution (2nd type)',
                'The angle distribution of the beam is read from the <i>angle.inp</i> file',
                'A series of calculations at different angles of incidence, with angle steps defined for each element in the table',
                'The angle and energy distribution of the beam is read from the <i>ene_ang.inp</i> file'
            ],
            numbering=0,
            label_default=True,
            entries=[
                'constant',
                'random distribution',
                'cosine distr. 1',
                'cosine distr. 2',
                'angle.inp',
                'angle sweep',
                'ene_ang.inp'
            ],
            entries_save=[
                ArgumentValues.Angle.FIXED,
                ArgumentValues.Angle.RANDOM_DISTRIBUTION,
                ArgumentValues.Angle.COS_DISTRIBUTION_1,
                ArgumentValues.Angle.COS_DISTRIBUTION_2,
                ArgumentValues.Angle.FILE,
                ArgumentValues.Angle.SWEEP,
                ArgumentValues.Angle.FILE_ENERGY_ANGLE
            ]
        )
        self.layout_angle = InputHBoxLayout(
            'Angle of incidence [°]:',
            self.angle,
            tooltip='<i>case_alpha</i><br>How the angle of incidence of the projectiles in the beam is defined'
        )
        self.angle_previous = self.angle.getValue(save=True)
        self.angle.currentIndexChanged.connect(lambda _: self.changedAngle())
        self.angle.currentIndexChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_angle)
        self.addSpacing(20)

        # number of sweeps
        self.sweep = SpinBox(
            default=self.default_values.number_calc,
            input_range=(0, 1e4)
        )
        self.layout_sweep = InputHBoxLayout(
            'Sweep steps:',
            self.sweep,
            tooltip='<i>number_calc</i><br>How many steps will be taken (<i>number_calc</i>), starting at 0 and incrementing by the energy or angle value given in the table. <b>Note, that the sweep feature is currently (6.01) not working as it is described in the documentation!</b>',
            hidden=True
        )
        self.sweep.valueChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_sweep)

        # distributions of energies and angles from files
        self.distributions: Dict[str, Any] = {}
        self.projectiles: Callable[[], List[str]] = lambda: []  # set by the page: symbols of the projectiles
        self.distribution_button = QPushButton(getIcon('file'), ' Distributions...')
        self.distribution_button.setAutoDefault(False)
        self.distribution_button.setToolTip(
            'Define the distributions of energies and/or angles of the projectiles.<br>'
            'They are written to <i>energy.inp</i>, <i>angle.inp</i> or <i>ene_ang.inp</i> when the settings are saved'
        )
        self.distribution_button.clicked.connect(self.editDistributions)
        self.distribution_button.setHidden(True)
        self.addWidget(self.distribution_button)

        # sheath potential (Maxwellian distributions)
        self.sheath_potential = DoubleSpinBox(default=self.default_values.shth, input_range=(0, 1e6), step_size=0.1)
        self.layout_sheath_potential = InputHBoxLayout(
            'Sheath potential [eV]:',
            self.sheath_potential,
            tooltip='<i>shth</i><br>Sheath potential (in [eV]) for Maxwellian distributions (plasma), usually 3·|e0|. '
                    'Must be larger than 0. The charge of the projectiles is set in the beam composition',
            hidden=True
        )
        self.sheath_potential.valueChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_sheath_potential)
        self.addStretch(1)

        self.changedEnergy()
        self.changedAngle()

    def usedDistributions(self) -> Tuple[bool, bool, bool]:
        """Returns if distributions of energies, angles and of energies and angles are read from files"""

        case_e0 = self.kinetic_energy.getValue(save=True)
        case_alpha = self.angle.getValue(save=True)
        return (
            case_e0 == ArgumentValues.KineticEnergy.FILE,
            case_alpha == ArgumentValues.Angle.FILE,
            case_e0 == ArgumentValues.KineticEnergy.FILE_ENERGY_ANGLE
        )

    def updateDistributionButton(self):
        """Shows the button for the distributions if a file mode is selected"""

        self.distribution_button.setHidden(not any(self.usedDistributions()))

    def editDistributions(self):
        """Opens the dialog to edit the distributions of energies and angles"""

        energy, angle, energy_angle = self.usedDistributions()
        projectiles = [symbol for symbol in self.projectiles() if symbol]
        if (energy or angle) and not projectiles:
            QMessageBox.warning(self.distribution_button, 'Warning!', 'Define the elements of the beam first')
            return
        dialog = DistributionDialog(
            self.distribution_button,
            projectiles,
            self.distributions,
            energy,
            angle,
            energy_angle,
            angle_per_projectile=Versions.atLeast(self.version, Versions.V_702),
            legacy_energy_angle=not Versions.atLeast(self.version, Versions.V_707)
        )
        if dialog.exec():
            self.distributions = dialog.distributionData()
            self.edited()

    def changedEnergy(self):
        """
        Enables/disables kinetic energy for beam rows depending on selected energy mode
        Synchronises and enables/disables angle mode if needed
        Popup for energy sweep
        """

        case_e0 = self.kinetic_energy.getValue(save=True)
        case_alpha = self.angle.getValue(save=True)
        self.layout_angle.setEnabled(True)

        self.updateDistributionButton()

        # the sheath potential is needed for Maxwellian distributions
        self.layout_sheath_potential.setHidden(case_e0 not in [
            ArgumentValues.KineticEnergy.MAXWELLIAN_VELOCITY_DISTRIBUTION,
            ArgumentValues.KineticEnergy.MAXWELLIAN_ENERGY_DISTRIBUTION
        ])

        changes = case_e0 != self.energy_previous
        if changes:
            self.energy_previous = case_e0

        if case_alpha != ArgumentValues.Angle.SWEEP:
            self.layout_sweep.setHidden(True)

        energy = True
        output_options = True
        if case_e0 in [
            ArgumentValues.KineticEnergy.FILE,
            ArgumentValues.KineticEnergy.FILE_ENERGY_ANGLE
        ]:
            energy = False

            if case_e0 == ArgumentValues.KineticEnergy.FILE_ENERGY_ANGLE and case_alpha != ArgumentValues.Angle.FILE_ENERGY_ANGLE:
                self.angle.setValue(ArgumentValues.Angle.FILE_ENERGY_ANGLE, from_entries_save=True)
                self.layout_angle.setEnabled(False)

        if case_e0 != ArgumentValues.KineticEnergy.FILE_ENERGY_ANGLE and case_alpha == ArgumentValues.Angle.FILE_ENERGY_ANGLE:
            self.angle.setValue(ArgumentValues.Angle.FIXED, from_entries_save=True)
            self.layout_angle.setEnabled(True)

        if case_e0 == ArgumentValues.KineticEnergy.SWEEP:
            self.angle.setValue(ArgumentValues.Angle.FIXED, from_entries_save=True)
            self.layout_angle.setEnabled(False)
            self.layout_sweep.setHidden(False)
            output_options = False

            if changes:
                self.emit({
                    'popup': True,
                    'popup_title': 'Energy sweep information',
                    'popup_text': 'The energy sweep feature is still in development and may result in unwanted behaviour. Be cautious!<br><br>Currently (up to SDTrimSP v.6.09) only the first defined element in the input file will have a proper energy sweep. Therefore, the "Group elements" option should be unchecked and only one element must be defined in the Beam composition for the energy sweep to work as intended.',
                    'popup_hide': 'energy_sweep',
                    'group_elements': False
                })

        self.emit({
            'energy': energy,
            'output_options': output_options
        })

    def changedAngle(self):
        """
        Enables/disables angle for beam rows depending on selected angle mode
        Synchronises and enables/disables energy mode if needed
        Popup for angle sweep
        """

        self.updateDistributionButton()

        case_e0 = self.kinetic_energy.getValue(save=True)
        case_alpha = self.angle.getValue(save=True)
        self.layout_kinetic_energy.setEnabled(True)

        changes = case_alpha != self.angle_previous
        if changes:
            self.angle_previous = case_alpha

        if case_e0 != ArgumentValues.KineticEnergy.SWEEP:
            self.layout_sweep.setHidden(True)

        angle = True
        output_options = True
        if case_alpha in [
            ArgumentValues.Angle.RANDOM_DISTRIBUTION,
            ArgumentValues.Angle.COS_DISTRIBUTION_1,
            ArgumentValues.Angle.COS_DISTRIBUTION_2,
            ArgumentValues.Angle.FILE,
            ArgumentValues.Angle.FILE_ENERGY_ANGLE
        ]:
            angle = False

            if case_alpha == ArgumentValues.Angle.FILE_ENERGY_ANGLE and case_e0 != ArgumentValues.KineticEnergy.FILE_ENERGY_ANGLE:
                self.kinetic_energy.setValue(ArgumentValues.KineticEnergy.FILE_ENERGY_ANGLE, from_entries_save=True)
                self.layout_kinetic_energy.setEnabled(False)

        if case_alpha != ArgumentValues.Angle.FILE_ENERGY_ANGLE and case_e0 == ArgumentValues.KineticEnergy.FILE_ENERGY_ANGLE:
            self.kinetic_energy.setValue(ArgumentValues.KineticEnergy.FIXED, from_entries_save=True)
            self.layout_kinetic_energy.setEnabled(True)

        if case_alpha == ArgumentValues.Angle.SWEEP:
            self.kinetic_energy.setValue(ArgumentValues.KineticEnergy.FIXED, from_entries_save=True)
            self.layout_kinetic_energy.setEnabled(False)
            self.layout_sweep.setHidden(False)
            output_options = False

            if changes:
                self.emit({
                    'popup': True,
                    'popup_title': 'Angle sweep information',
                    'popup_text': 'The angle sweep feature is still in development and may result in unwanted behaviour. Be cautious!<br><br>Currently (up to SDTrimSP v.6.09) only the first defined element in the input file will have a proper angle sweep. Therefore, the "Group elements" option should be unchecked and only one element must be defined in the Beam composition for the angle sweep to work as intended.',
                    'popup_hide': 'angle_sweep',
                    'group_elements': False
                })

        self.emit({
            'angle': angle,
            'output_options': output_options
        })

    def reset(self):
        """Resets all input fields"""

        self.layout_kinetic_energy.reset()
        self.layout_angle.reset()
        self.layout_sweep.reset()
        self.layout_sheath_potential.reset()
        self.distributions = {}

        self.changedEnergy()
        self.changedAngle()

    def getArguments(self) -> GeneralBeamArguments:
        """Returns <GeneralBeamArguments> container of parameters for beam settings"""

        return GeneralBeamArguments(
            kinetic_energy_mode=self.kinetic_energy.getValue(save=True),  # case_e0
            angle_mode=self.angle.getValue(save=True),  # case_alpha
            sweep=self.sweep.value(),  # number_calc
            sheath_potential=self.sheath_potential.value(),  # shth
            distributions=self.distributions  # energy.inp, angle.inp, ene_ang.inp
        )

    def loadArguments(self, arguments: SimulationArguments) -> list:
        """Loads <SimulationArguments> container. Returns list of not loadable parameters (default used)"""

        self.reset()
        beam_args = arguments.beam_args
        assumed = arguments.get('assumed')
        if not isinstance(assumed, list):
            assumed = []
        not_loadable = []

        # incident energy
        # TODO: also check beam row containers
        case_e0 = beam_args.kinetic_energy_mode
        if case_e0 not in [
            ArgumentValues.KineticEnergy.FIXED,
            ArgumentValues.KineticEnergy.FILE,
            ArgumentValues.KineticEnergy.SWEEP,
            ArgumentValues.KineticEnergy.MAXWELLIAN_VELOCITY_DISTRIBUTION,
            ArgumentValues.KineticEnergy.MAXWELLIAN_ENERGY_DISTRIBUTION,
            ArgumentValues.KineticEnergy.FILE_ENERGY_ANGLE
        ] or 'kinetic_energy_mode' in assumed:
            case_e0 = self.kinetic_energy.getDefaultSave()
            self.layout_kinetic_energy.mark()
            not_loadable.append('Mode of kinetic energy')
        self.kinetic_energy.setValue(case_e0, from_entries_save=True)

        # angle of incidence
        # TODO: also check beam row containers
        case_alpha = beam_args.angle_mode
        if case_alpha not in [
            ArgumentValues.Angle.FIXED,
            ArgumentValues.Angle.FILE,
            ArgumentValues.Angle.SWEEP,
            ArgumentValues.Angle.RANDOM_DISTRIBUTION,
            ArgumentValues.Angle.COS_DISTRIBUTION_1,
            ArgumentValues.Angle.COS_DISTRIBUTION_2,
            ArgumentValues.Angle.FILE_ENERGY_ANGLE
        ] or 'angle_mode' in assumed:
            case_alpha = self.angle.getDefaultSave()
            self.layout_angle.mark()
            not_loadable.append('Mode of incidence angle')
        self.angle.setValue(case_alpha, from_entries_save=True)

        # number of sweeps
        number_calc = beam_args.get('sweep')
        if not isinstance(number_calc, int):
            number_calc = self.default_values.number_calc
            self.layout_sweep.mark()
            not_loadable.append('Number of sweeps')
        self.sweep.setValue(number_calc)

        # distributions of energies and angles
        distributions = beam_args.get('distributions')
        self.distributions = distributions if isinstance(distributions, dict) else {}

        # sheath potential
        shth = beam_args.get('sheath_potential')
        self.sheath_potential.setValue(float(shth) if isinstance(shth, (int, float)) else self.default_values.shth)

        self.changedEnergy()
        self.changedAngle()

        return not_loadable


class HlTargetSettings(HlGeneralTargetSettings):
    """
    QHBoxLayout for general target settings

    :param version: version of simulation
    """

    def __init__(self, version: str):
        self.default_values = DefaultValues(version)
        super().__init__(version, self.default_values)

        # thickness
        self.thickness = DoubleSpinBox(
            default=self.default_values.ttarget,
            input_range=SpinBoxRange.ZERO_INF
        )
        self.layout_thickness = InputHBoxLayout(
            'Thickness [Å]:',
            self.thickness,
            tooltip='<i>ttarget</i><br>Thickness of the whole target'
        )
        self.thickness.valueChanged.connect(lambda _: self.updateSegmentThickness())
        self.thickness.valueChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_thickness)
        self.addSpacing(10)

        # segments
        self.segments = SpinBox(
            default=self.default_values.nqx,
            input_range=(1, 5e4)
        )
        self.layout_segments = InputHBoxLayout(
            'Target segments:',
            self.segments,
            tooltip='<i>nqx</i><br>The amount of discrete segments the target is divided into'
        )
        self.segments.valueChanged.connect(lambda _: self.updateSegmentThickness())
        self.segments.valueChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_segments)
        self.addSpacing(10)

        # segment thickness (automatically calculated)
        self.segment_thickness = DoubleSpinBox(
            default=self.default_values.ttarget/self.default_values.nqx,
            input_range=SpinBoxRange.INF_INF,
            decimals=4
        )
        self.layout_segment_thickness = InputHBoxLayout(
            'Segment thickness [Å]:',
            self.segment_thickness,
            tooltip='The resulting thickness of each segment. A value ≥10Å is recommended',
            disabled=True
        )
        self.addLayout(self.layout_segment_thickness)
        self.addSpacing(10)

        # global density
        self.global_density = DoubleSpinBox(
            default=self.default_values.globaldensity,
            input_range=(1e-8, 1e8),
            decimals=5
        )
        self.layout_global_density = InputHBoxLayout(
            'Global density [g/cm³]:',
            self.global_density,
            tooltip='<i>!globaldensity</i><br>Toggle a global density, which the individual target element densities will be calculated from.\nCan only be used if there is just one layer in the target composition',
            checkbox=False,
            disabled=True
        )

        self.layout_global_density.check.stateChanged.connect(lambda _: self.changedGlobDens())
        self.global_density.valueChanged.connect(lambda _: self.changedGlobDens())

        self.layout_global_density.check.stateChanged.connect(lambda _: self.edited())
        self.global_density.valueChanged.connect(lambda _: self.edited())

        self.addLayout(self.layout_global_density)

        if self.default_values.enable_crystal:
            self.insertCrystalCheckbox(
                checkbox=self.default_values.lmatrices,
                tooltip='<i>l_crystal</i><br>If checked the simulation uses the crystal structure of the target'
            )
        else:
            self.addStretch(1)

        self.updateSegmentThickness()
        self.changedGlobDens()

    def updateSegmentThickness(self):
        """Update value for segment thickness"""

        self.segment_thickness.setValue(self.thickness.value() / self.segments.value())
        self.emit({
            'thickness': self.thickness.value(),
            'segments': self.segments.value()
        })

    def changedGlobDens(self):
        """Detects when global density is changed"""

        global_density_state = self.layout_global_density.check.isChecked()
        global_density: Union[bool, float] = False
        if global_density_state:
            global_density = self.global_density.value()

        self.emit({
            'global_density': global_density,
            'enable_layer_table': not global_density_state
        })

    def reset(self):
        """Resets all input fields"""

        super().reset()

        self.layout_thickness.reset()
        self.layout_segments.reset()
        self.layout_global_density.reset()

        # loaded options of the layer file without input fields (iq0, qu), they are written again
        self.layer_file_options = {}

        self.updateSegmentThickness()
        self.changedGlobDens()

    def getArguments(self, miller_ind: Optional[MillerIndex] = None) -> GeneralTargetArguments:
        """
        Returns <GeneralTargetArguments> container of parameters for target settings

        :param miller_ind: (optional) MillerIndex
        """

        global_density: Union[bool, float] = False
        if self.layout_global_density.check.isChecked():
            global_density = self.global_density.value()

        crystal_flag = None
        if self.layout_crystal_file is not None:
            crystal_flag = self.layout_crystal_file.check.isChecked()

        return GeneralTargetArguments(
            thickness=self.thickness.value(),  # ttarget
            segments=self.segments.value(),  # nqx
            global_density=global_density,  # !globaldensity
            crystal_flag=crystal_flag,
            miller_ind=miller_ind,
            **getattr(self, 'layer_file_options', {})
        )

    def loadArguments(self, arguments: SimulationArguments) -> list:
        """Loads <SimulationArguments> container. Returns list of not loadable parameters (default used)"""

        self.reset()
        target_args = arguments.target_args
        self.layer_file_options = {
            name: target_args.get(name) for name in ('layer_file_flag', 'layer_file_qu') if target_args.get(name) is not None
        }
        assumed = arguments.get('assumed')
        if not isinstance(assumed, list):
            assumed = []
        not_loadable = []

        # thickness
        ttarget = target_args.thickness
        if 'thickness' in assumed:
            ttarget = self.default_values.ttarget
            self.layout_thickness.mark()
            not_loadable.append('Thickness of target')
        self.thickness.setValue(ttarget)

        # segments
        nqx = target_args.segments
        if 'segments' in assumed:
            nqx = self.default_values.nqx
            self.layout_segments.mark()
            not_loadable.append('Number of segments of target')
        self.segments.setValue(nqx)

        # global density
        global_density = target_args.get('global_density')
        if global_density is False:
            self.global_density.reset()
            self.layout_global_density.check.setChecked(False)
        elif isinstance(global_density, float):
            self.global_density.setValue(global_density)
            self.layout_global_density.check.setChecked(True)
        else:
            self.global_density.reset()
            self.layout_global_density.check.setChecked(False)
            self.layout_global_density.mark()
            not_loadable.append('Global density')

        # crystal
        crystal_flag = target_args.get('crystal_flag')
        if self.layout_crystal_file is not None:
            if isinstance(crystal_flag, bool):
                self.layout_crystal_file.check.setChecked(crystal_flag)

        self.changedGlobDens()

        return not_loadable

    def receive(self, value_dict: dict):
        """Receives other settingsChanged pyqtSignal -> dict"""

        layer_table_rows = value_dict.get('layer_table_rows')
        if layer_table_rows is not None:
            global_density = False
            if layer_table_rows == 1:
                global_density = True

            self.layout_global_density.setEnabled(global_density)
            if global_density and not self.layout_global_density.check.isChecked():
                self.global_density.setEnabled(False)


class VlSimulationSettings(VlGeneralSimulationSettings):
    """
    QVBoxLayout for general simulation settings

    :param version: version of simulation
    """

    def __init__(self, version: str):
        super().__init__(version)
        self.default_values = DefaultValues(self.version)
        self.dict_lookup = DictLookup(self.version)

        # title
        self.title = LineEdit(
            default=f'SDTrimSP - {dateStr()}',
            placeholder='Choose a title...'
        )
        self.layout_title = InputHBoxLayout(
            'Simulation Title:',
            self.title,
            split=20,
            tooltip='The first line of the <i>tri.inp</i> file (at most 80 characters, SDTrimSP reads only 80 characters)'
        )
        self.title.setMaxLength(80)
        self.title.textChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_title)

        # simulation method
        self.calculation_method = ComboBox(
            default=self.default_values.idrel,
            entries=[
                'static (no recoils)',
                'dynamic',
                'static'
            ],
            numbering=-1,
            label_default=True,
            entries_save=[
                ArgumentValues.Mode.STATIC_NO_RECOIL,
                ArgumentValues.Mode.DYNAMIC,
                ArgumentValues.Mode.STATIC
            ],
            tooltips=[
                'Suppression of dynamic relaxation and cascades; static calculation (TRIM); only projectiles (no recoils) are followed',
                'Full dynamic calculation (TRIDYN)',
                'Suppression of dynamic relaxation (TRIM); full static calculation'
            ],
        )
        self.layout_calculation_method = InputHBoxLayout(
            'Calculation method:',
            self.calculation_method,
            tooltip='<i>idrel</i>'
        )
        self.calculation_method.currentIndexChanged.connect(lambda _: self.changedMode())
        self.calculation_method.currentIndexChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_calculation_method)

        # number of histories
        self.histories_total = SpinBox(
            default=self.default_values.nh,
            input_range=SpinBoxRange.NEG_ONE_INF
        )
        self.layout_histories_total = InputHBoxLayout(
            'Histories',
            self.histories_total,
            tooltip='<i>nh</i><br>How many histories will be simulated'
        )
        self.histories_total.valueChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_histories_total)

        # number of histories between outputs
        self.histories_between = SpinBox(
            default=self.default_values.idout,
            input_range=SpinBoxRange.NEG_ONE_INF
        )
        self.layout_histories_between = InputHBoxLayout(
            'Histories between outputs:',
            self.histories_between,
            tooltip='<i>idout</i><br>How many histories are simulated between two outputs.\nSet to 0 to output only after the last fluence step'
        )
        self.histories_between.valueChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_histories_between)

        # limit histories
        self.layout_histories_limit = InputHBoxLayout(
            'Limit to a total of 100 outputs',
            None,
            checkbox=False,
            tooltip='Limits the histories'
        )
        self.addLayout(self.layout_histories_limit)
        self.histories_between_val = 0
        self.layout_histories_limit.check.toggled.connect(lambda state: self.changeHistoriesBetween(state))

        # number of projectiles per history
        self.projectiles = SpinBox(
            default=self.default_values.nr_pproj,
            input_range=SpinBoxRange.ONE_INF
        )
        self.layout_projectiles = InputHBoxLayout(
            'Projectiles per history:',
            self.projectiles,
            tooltip='<i>nr_pproj</i><br>How many projectiles will be simulated per history'
        )
        self.projectiles.valueChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_projectiles)

        # fluence
        self.fluence = DoubleSpinBox(
            default=self.default_values.flc,
            input_range=SpinBoxRange.ZERO_INF
        )
        self.layout_fluence = InputHBoxLayout(
            'Fluence [atoms/Å<sup>2</sup>]:',
            self.fluence,
            tooltip='<i>flc</i><br>Fluence of incident atoms. Can only be defined for dynamic calculations'
        )
        self.fluence.valueChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_fluence)

        # interaction potential
        self.potential = ComboBox(
            default=self.default_values.ipot,
            entries=[
                'KrC',
                'Moliere',
                'ZBL',
                'Na-Ya',
                'Si-Si',
                'power'
            ],
            numbering=1,
            label_default=True,
            entries_save=[
                ArgumentValues.InteractionPotential.KRC,
                ArgumentValues.InteractionPotential.MOLIERE,
                ArgumentValues.InteractionPotential.ZBL,
                ArgumentValues.InteractionPotential.NAKAGAWA_YAMAMURA,
                ArgumentValues.InteractionPotential.SI_SI,
                ArgumentValues.InteractionPotential.POWER
            ],
            tooltips=[
                '',
                '',
                '',
                'Nakagawa-Yamamura',
                '',
                ''
            ],
        )
        self.layout_potential = InputHBoxLayout(
            'Interaction potential:',
            self.potential,
            tooltip='<i>ipot</i>'
        )
        self.potential.currentIndexChanged.connect(lambda _: self.changedPotential())
        self.potential.currentIndexChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_potential)

        # integration method
        self.integration = ComboBox(
            default=self.default_values.iintegral,
            entries=[
                'Magic',
                'Gauss-Mehler',
                'Gauss-Legendre'
            ],
            numbering=0,
            label_default=True,
            entries_save=[
                ArgumentValues.IntegrationMethod.MAGIC,
                ArgumentValues.IntegrationMethod.GAUSS_MEHLER,
                ArgumentValues.IntegrationMethod.GAUSS_LEGENDRE
            ],
            tooltips=[
                'Only allowed with the following interaction potentials: KrC, Moliere, and ZBL',
                '',
                ''
            ]
        )
        self.layout_integration = InputHBoxLayout(
            'Integration method:',
            self.integration,
            tooltip='<i>iintegral</i>'
        )
        self.integration.currentIndexChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_integration)

        # surface binding model
        self.surface_binding_model_entries = [
            'element-specific',
            'average for all elements',
            'element-pair averages',
            'solid-solid compound enthalpies',
            'solid-gas compound enthalpies',
            'from mat_surfb.inp',
            'from electronegativity'
        ]
        # -1: entry that is not supported by the version
        self.surface_binding_model_entries_save: List[Union[ArgumentValues.SurfaceBindingModel, int]] = [
            ArgumentValues.SurfaceBindingModel.ELEMENT_SPECIFIC,
            ArgumentValues.SurfaceBindingModel.AVERAGE,
            ArgumentValues.SurfaceBindingModel.ELEMENT_PAIRS,
            ArgumentValues.SurfaceBindingModel.SOLID_SOLID,
            ArgumentValues.SurfaceBindingModel.SOLID_GAS,
            ArgumentValues.SurfaceBindingModel.FILE,
            ArgumentValues.SurfaceBindingModel.ELECTRONEGATIVITY
        ]
        self.surface_binding_model_entries_tooltips = [
            'sbv(ip,jp)=e_surfb(jp) for ip=jp',
            'sbv(ip,jp)=e_surfb(jp) for all ip, jp',
            'sbv(ip,jp)=0., if e_surfb(ip)=0 or e_surfb(jp)=0\nelse: sbv(ip,jp)=0.5*(e_surfb(ip)+e_surfb(jp))',
            'sbv(ip,jp)=f(e_surfb, qu, deltahf) for solid/solid compound',
            'sbv(ip,jp)=f(e_surfb, qu, deltahf, deltahd) for solid/gas compound',
            'input of given matrix of the surface-bindig-energy: "mat_surfb.inp"',
            'calculate according to "Kudriavtsev"'
        ]
        self.surface_binding_model_disabled_list = []

        # since 6.09: isbv=5 and isbv=7 do not work anymore
        if Versions.atLeast(self.version, Versions.V_609):
            self.surface_binding_model_entries = [
                'element-specific',
                'average for all elements',
                'element-pair averages',
                'compounds only',
                '(not supported)',
                'from mat_surfb.inp',
                '(not supported)',
                'from table1a'
            ]
            self.surface_binding_model_entries_save = [
                ArgumentValues.SurfaceBindingModel.ELEMENT_SPECIFIC,
                ArgumentValues.SurfaceBindingModel.AVERAGE,
                ArgumentValues.SurfaceBindingModel.ELEMENT_PAIRS,
                ArgumentValues.SurfaceBindingModel.COMPOUNDS,
                -1,
                ArgumentValues.SurfaceBindingModel.FILE,
                -1,
                ArgumentValues.SurfaceBindingModel.TABLE
            ]
            self.surface_binding_model_entries_tooltips = [
                'sbv(ip,jp)=e_surfb(jp) for ip=jp',
                'sbv(ip,jp)=e_surfb(jp) for all ip, jp',
                'sbv(ip,jp)=0., if e_surfb(ip)=0 or e_surfb(jp)=0\nelse: sbv(ip,jp)=0.5*(e_surfb(ip)+e_surfb(jp))',
                'e_bulkb(compound)=deltaH_f\nsbv(ip,jp)=e_surfb(jp) for ip=jp, =0 else',
                '',
                'input of given matrix of the surface-bindig-energy: "mat_surfb.inp"',
                '',
                'e_surfb=0, e_bulkb=Es, e_cutoff=Es/3\ne_bulkb(compound)=Es+deltaH_f'
            ]
            self.surface_binding_model_disabled_list = [4, 6]

        self.surface_binding_model = ComboBox(
            default=self.default_values.isbv,
            entries=self.surface_binding_model_entries,
            numbering=1,
            label_default=True,
            entries_save=self.surface_binding_model_entries_save,
            disabled_list=self.surface_binding_model_disabled_list,
            tooltips=self.surface_binding_model_entries_tooltips
        )
        self.layout_surface_binding_model = InputHBoxLayout(
            'Surface binding model:',
            self.surface_binding_model,
            tooltip='<i>isbv</i>'
        )
        self.surface_binding_model.currentIndexChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_surface_binding_model)

        # group elements
        self.layout_group_elements = InputHBoxLayout(
            'Group elements',
            None,
            checkbox=self.default_values.group_elements,
            tooltip='<i>Checked:</i> Elements that occur in beam and target will be treated as identical elements<br><i>Unchecked:</i> Elements in beam and target will be treated as different elements even if they are identical'
        )
        self.layout_group_elements.check.clicked.connect(lambda _: self.changedGroupElements())
        self.layout_group_elements.check.clicked.connect(lambda _: self.edited())
        self.addLayout(self.layout_group_elements)

        # additional output options
        self.addSpacing(10)
        self.addWidget(QLabel('<b>Additional output options</b>'))

        # two columns: particle distributions and matrices, trajectories
        output_columns = QHBoxLayout()
        output_left = QVBoxLayout()
        output_right = QVBoxLayout()
        output_columns.addLayout(output_left, 1)
        output_columns.addLayout(output_right, 1)

        # reflected projectiles
        self.layout_reflected = InputHBoxLayout(
            'Reflected projectiles',
            None,
            checkbox=self.default_values.lparticle_p,
            tooltip='<i>lparticle_p</i><br>Compute the angle and energy distributions of reflected projectiles and write them to output files'
        )
        self.layout_reflected.check.clicked.connect(lambda _: self.edited())
        output_left.addLayout(self.layout_reflected)

        # sputtered recoil atoms
        self.layout_sputtered = InputHBoxLayout(
            'Sputtered recoil atoms',
            None,
            checkbox=self.default_values.lparticle_r,
            tooltip='<i>lparticle_r</i><br>Compute the angle and energy distributions of sputtered recoil atoms and write them to output files'
        )
        self.layout_sputtered.check.clicked.connect(lambda _: self.edited())
        output_left.addLayout(self.layout_sputtered)

        # matrix files
        self.layout_matrix_files = InputHBoxLayout(
            'Matrix files',
            None,
            checkbox=self.default_values.lmatrices,
            tooltip='<i>lmatrices</i><br>Compute and write the pre-sorted secondary particle distributions to output files'
        )

        self.layout_matrix_files.check.clicked.connect(lambda _: self.edited())
        output_left.addLayout(self.layout_matrix_files)

        # trajectories
        self.layout_trajectories_p = InputHBoxLayout(
            'Projectile trajectories',
            None,
            checkbox=self.default_values.ltraj_p,
            tooltip='<i>ltraj_p</i><br>Write the trajectories of projectiles to output files'
        )
        self.layout_trajectories_r = InputHBoxLayout(
            'Recoil trajectories',
            None,
            checkbox=self.default_values.ltraj_r,
            tooltip='<i>ltraj_r</i><br>Write the trajectories of recoils to output files'
        )
        self.trajectories_number = SpinBox(default=self.default_values.numb_hist, input_range=(1, 1e6))
        self.layout_trajectories_number = InputHBoxLayout(
            'Traced trajectories:',
            self.trajectories_number,
            tooltip='<i>numb_hist</i><br>Number of traced trajectories of projectiles and recoils'
        )
        for layout in (self.layout_trajectories_p, self.layout_trajectories_r):
            layout.check.clicked.connect(lambda _: self.changedOutputs())
            output_right.addLayout(layout)
        output_right.addStretch(1)
        self.addLayout(output_columns)
        self.trajectories_number.valueChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_trajectories_number)

        # energy distribution in the target
        self.layout_energy_distribution = InputHBoxLayout(
            'Energy distribution in the target',
            None,
            checkbox=self.default_values.lenergy_distr,
            tooltip='<i>lenergy_distr</i><br>Write the distribution of stopped energy, electronic and nuclear losses in the target (E_distr_*.dat)'
        )
        self.layout_energy_distribution.check.clicked.connect(lambda _: self.changedOutputs())
        self.addLayout(self.layout_energy_distribution)

        self.distribution_grid: List[Union[SpinBox, DoubleSpinBox]] = [
            SpinBox(default=self.default_values.dist_nx, input_range=(1, 1e4)),
            SpinBox(default=self.default_values.dist_ny, input_range=(1, 1e4)),
            SpinBox(default=self.default_values.dist_nz, input_range=(1, 1e4)),
            DoubleSpinBox(default=self.default_values.dist_delta, input_range=(1e-3, 1e4), step_size=0.1)
        ]
        self.layout_distribution_grid = InputHBoxLayouts(
            'Grid:',
            self.distribution_grid,
            split=0,
            tooltip='<i>dist_nx, dist_ny, dist_nz, dist_delta</i><br>Size of the matrix of the energy distribution and distance (in [Å]) of its points',
            widgets_labels=['nx', 'ny', 'nz', 'Δ [Å]']
        )
        for widget in self.distribution_grid:
            widget.valueChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_distribution_grid)

        # other settings
        self.random_seed = SpinBox(default=self.default_values.irand, input_range=(1, 2147483647))
        self.layout_random_seed = InputHBoxLayout(
            'Random seed:',
            self.random_seed,
            tooltip='<i>irand</i><br>Random seed of the simulation'
        )
        self.random_seed.valueChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_random_seed)

        self.layout_inelastic_outside = InputHBoxLayout(
            'Inelastic energy loss outside the surface',
            None,
            checkbox=bool(self.default_values.sfin),
            tooltip='<i>sfin</i><br>Inelastic energy loss also outside the target surface (between surface potential and surface)'
        )
        self.layout_inelastic_outside.check.clicked.connect(lambda _: self.edited())
        if not self.default_values.supports_sfin:
            self.layout_inelastic_outside.check.setEnabled(False)
            self.layout_inelastic_outside.check.setToolTip(
                '<i>sfin</i><br>Inelastic energy loss also outside the target surface.<br>'
                '<b>Disabled for SDTrimSP 7.00 and newer: sfin = 1 lets the simulation crash (access violation)</b>'
            )
        self.addLayout(self.layout_inelastic_outside)

        # file of tabulated stopping power (since 7.07): tbsp.db (binary) and tbsp.ascii contain the same data, so the
        # selection is not shown and the binary file is always used (tbsp_binary = .true.)
        self.tbsp_format: Optional[ComboBox] = None
        self.layout_tbsp_format: Optional[InputHBoxLayout] = None
        # if self.default_values.tbsp_file_selection:
        #     self.tbsp_format = ComboBox(
        #         default=0,
        #         entries=['tbsp.db (binary)', 'tbsp.ascii (text)'],
        #         entries_save=['binary', 'ascii'],
        #         label_default=True
        #     )
        #     self.layout_tbsp_format = InputHBoxLayout(
        #         'Tabulated stopping power file:',
        #         self.tbsp_format,
        #         tooltip='<i>tbsp_binary, tbsp_ascii</i><br>File in the tables-directory that is used for the tabulated stopping power (inelastic loss model 8)'
        #     )
        #     self.tbsp_format.currentIndexChanged.connect(lambda _: self.edited())
        #     self.addLayout(self.layout_tbsp_format)

        self.changedPotential()
        self.changedMode()
        self.changedGroupElements()

    def changeHistoriesBetween(self, state):
        """Changes histories between value depending on if limit histories is checked"""

        if state:
            self.layout_histories_between.setEnabled(False)
            self.histories_between_val = self.histories_between.value()
            self.histories_between.setValue(-1)
        else:
            self.layout_histories_between.setEnabled(True)
            self.histories_between.setValue(self.histories_between_val)

    def changedPotential(self):
        """
        Updates integration method if potential has changed
            If potential = NAKAGAWA_YAMAMURA, SI_SI or POWER
            integration method must not be MAGIC
        """

        ipot = self.potential.getValue(save=True)
        disabled_list = []
        if ipot in [
            ArgumentValues.InteractionPotential.NAKAGAWA_YAMAMURA,
            ArgumentValues.InteractionPotential.SI_SI,
            ArgumentValues.InteractionPotential.POWER
        ]:
            disabled_list = [notNone(self.integration.entries_save).index(ArgumentValues.IntegrationMethod.MAGIC)]
            if self.integration.getValue(save=True) == ArgumentValues.IntegrationMethod.MAGIC:
                self.integration.reset()
        self.integration.updateDisabledList(disabled_list)

    def changedMode(self):
        """Disables fluence if mode is STATIC and emits signal for disable max. concentration in beam and target rows"""

        dynamic = True
        if self.calculation_method.getValue(save=True) in [
            ArgumentValues.Mode.STATIC,
            ArgumentValues.Mode.STATIC_NO_RECOIL
        ]:
            dynamic = False
        self.layout_matrix_files.setEnabled(not dynamic)
        if dynamic:
            self.layout_matrix_files.check.setChecked(False)
        self.fluence.setEnabled(dynamic)
        self.emit({
            'max_concentration': dynamic
        })

    def changedGroupElements(self):
        """Grouping of elements has changed"""

        self.emit({
            'group_elements': self.layout_group_elements.check.isChecked()
        })

    def reset(self):
        """Resets all input fields"""

        self.title.default = f'SDTrimSP - {dateStr()}'
        self.layout_title.reset()
        self.layout_calculation_method.reset()
        self.layout_histories_limit.check.setChecked(False)
        self.layout_histories_total.reset()
        self.layout_histories_between.reset()
        self.layout_projectiles.reset()
        self.layout_fluence.reset()
        self.layout_potential.reset()
        self.layout_integration.reset()
        self.layout_surface_binding_model.reset()
        self.layout_group_elements.reset()
        self.layout_reflected.reset()
        self.layout_sputtered.reset()
        self.layout_matrix_files.reset()
        if self.layout_tbsp_format is not None:
            self.layout_tbsp_format.reset()
        for layout in (self.layout_trajectories_p, self.layout_trajectories_r, self.layout_trajectories_number,
                       self.layout_energy_distribution, self.layout_distribution_grid, self.layout_random_seed, self.layout_inelastic_outside):
            layout.reset()
        self.changedOutputs()

        self.changedPotential()
        self.changedMode()

    def changedOutputs(self):
        """Enables the number of trajectories and the grid of the energy distribution if they are used"""

        self.layout_trajectories_number.setEnabled(
            self.layout_trajectories_p.check.isChecked() or self.layout_trajectories_r.check.isChecked()
        )
        self.layout_distribution_grid.setEnabled(self.layout_energy_distribution.check.isChecked())
        self.edited()

    def getArguments(self) -> GeneralArguments:
        """Returns <GeneralArguments> container of parameters for general simulation settings"""

        return GeneralArguments(
            title=self.title.text(),
            mode=self.calculation_method.getValue(save=True),  # idrel
            fluence=self.fluence.value(),  # flc
            histories=self.histories_total.value(),  # nh
            histories_between_out=self.histories_between.value(),  # idout
            projectiles=self.projectiles.value(),  # nr_pproj
            interaction_potential=self.potential.getValue(save=True),  # ipot
            integration_method=self.integration.getValue(save=True),  # iintegral
            surface_binding_model=self.surface_binding_model.getValue(save=True),  # isbv
            group_elements=self.layout_group_elements.check.isChecked(),
            log_reflected=self.layout_reflected.check.isChecked(),  # lparticle_p
            log_sputtered=self.layout_sputtered.check.isChecked(),  # lparticle_r
            log_matrix=self.layout_matrix_files.check.isChecked(),  # lmatrices
            tbsp_format=self.tbsp_format.getValue(save=True) if self.tbsp_format is not None else None,  # tbsp_binary, tbsp_ascii
            trajectories_projectiles=self.layout_trajectories_p.check.isChecked(),  # ltraj_p
            trajectories_recoils=self.layout_trajectories_r.check.isChecked(),  # ltraj_r
            trajectories_number=self.trajectories_number.value(),  # numb_hist
            energy_distribution=self.layout_energy_distribution.check.isChecked(),  # lenergy_distr
            distribution_grid=[widget.value() for widget in self.distribution_grid],  # dist_nx, dist_ny, dist_nz, dist_delta
            random_seed=self.random_seed.value(),  # irand
            inelastic_outside=self.layout_inelastic_outside.check.isChecked()  # sfin
        )

    def loadArguments(self, arguments: SimulationArguments) -> list:
        """Loads <SimulationArguments> container. Returns list of not loadable parameters (default used)"""

        self.reset()
        settings = arguments.settings
        assumed = arguments.get('assumed')
        if not isinstance(assumed, list):
            assumed = []
        not_loadable = []

        # simulation title
        title = settings.title
        if 'title' in assumed:
            title = f'SDTrimSP - {dateStr()}'
            self.layout_title.mark()
            not_loadable.append('Simulation title')
        comment = settings.comment
        if isinstance(comment, str) and comment.strip() != '':
            title = f'{title} {comment}'
        self.title.setText(title)

        # calculation method
        idrel = settings.mode
        if idrel not in self.dict_lookup.idrel or 'mode' in assumed:
            idrel = self.calculation_method.getDefaultSave()
            self.layout_calculation_method.mark()
            not_loadable.append('Calculation mode')
        self.calculation_method.setValue(idrel, from_entries_save=True)

        # histories between
        idout = settings.get('histories_between_out')
        if not isinstance(idout, int):
            idout = self.default_values.idout
            self.layout_histories_between.mark()
            not_loadable.append('Histories between outputs')
        if idout >= 0:
            self.layout_histories_limit.check.setChecked(False)
        else:
            idout = -1
            self.layout_histories_limit.check.setChecked(True)
        self.histories_between.setValue(idout)

        # projectiles
        nr_pproj = settings.get('projectiles')
        if not isinstance(nr_pproj, int):
            nr_pproj = self.default_values.nr_pproj
            self.layout_projectiles.mark()
            not_loadable.append('Projectiles')
        self.projectiles.setValue(nr_pproj)

        # total histories
        nh = settings.get('histories')
        if not isinstance(nh, int):
            nh = self.default_values.nh
            self.layout_histories_total.mark()
            not_loadable.append('Histories')
            self.projectiles.setValue(nr_pproj//nh)
        self.histories_total.setValue(nh)

        # fluence
        flc = settings.fluence
        if not isinstance(flc, float) or 'fluence' in assumed:
            flc = self.default_values.flc
            self.layout_fluence.mark()
            not_loadable.append('Fluence')
        self.fluence.setValue(flc)

        # interaction potential
        ipot = settings.get('interaction_potential')
        if ipot not in self.dict_lookup.ipot or 'interaction_potential' in assumed:
            ipot = self.potential.getDefaultSave()
            self.layout_potential.mark()
            not_loadable.append('Interaction Potential')
        self.potential.setValue(ipot, from_entries_save=True)

        # integration method
        iintegral = settings.get('integration_method')
        if iintegral not in self.dict_lookup.iintegral or 'integration_method' in assumed:
            iintegral = self.integration.getDefaultSave()
            self.layout_integration.mark()
            not_loadable.append('Integration Method')
        self.integration.setValue(iintegral, from_entries_save=True)

        # surface binding model
        isbv = settings.get('surface_binding_model')
        if isbv not in self.dict_lookup.isbv or 'surface_binding_model' in assumed:
            isbv = self.surface_binding_model.getDefaultSave()
            self.layout_surface_binding_model.mark()
            not_loadable.append('Surface binding model')
        self.surface_binding_model.setValue(isbv, from_entries_save=True)

        # group elements
        if arguments.beam_args.kinetic_energy_mode == ArgumentValues.KineticEnergy.SWEEP or arguments.beam_args.angle_mode == ArgumentValues.Angle.SWEEP:
            self.layout_group_elements.check.setChecked(False)
        else:
            group_elements = settings.get('group_elements')
            if not isinstance(group_elements, bool):
                group_elements = self.default_values.group_elements
            self.layout_group_elements.check.setChecked(group_elements)

        # output matrices (not relevant in not_loadable list)
        lparticle_p = settings.get('log_reflected')
        if not isinstance(lparticle_p, bool):
            lparticle_p = self.default_values.lparticle_p
        self.layout_reflected.check.setChecked(lparticle_p)

        lparticle_r = settings.get('log_sputtered')
        if not isinstance(lparticle_r, bool):
            lparticle_r = self.default_values.lparticle_r
        self.layout_sputtered.check.setChecked(lparticle_r)

        lmatrices = settings.get('log_matrix')
        if not isinstance(lmatrices, bool):
            lmatrices = self.default_values.lparticle_p
        self.layout_matrix_files.check.setChecked(lmatrices)

        # trajectories, energy distribution, random seed and inelastic loss outside the surface
        for key, layout, default in [
            ('trajectories_projectiles', self.layout_trajectories_p, self.default_values.ltraj_p),
            ('trajectories_recoils', self.layout_trajectories_r, self.default_values.ltraj_r),
            ('energy_distribution', self.layout_energy_distribution, self.default_values.lenergy_distr),
            ('inelastic_outside', self.layout_inelastic_outside, bool(self.default_values.sfin))
        ]:
            value = settings.get(key)
            layout.check.setChecked(value if isinstance(value, bool) else default)
        numb_hist = settings.get('trajectories_number')
        self.trajectories_number.setValue(numb_hist if isinstance(numb_hist, int) else self.default_values.numb_hist)
        grid = settings.get('distribution_grid')
        defaults = [self.default_values.dist_nx, self.default_values.dist_ny, self.default_values.dist_nz, self.default_values.dist_delta]
        if not isinstance(grid, list) or len(grid) != 4:
            grid = defaults
        for widget, value in zip(self.distribution_grid, grid):
            widget.setValue(value)
        irand = settings.get('random_seed')
        self.random_seed.setValue(irand if isinstance(irand, int) else self.default_values.irand)
        self.changedOutputs()

        if self.tbsp_format is not None:
            tbsp_format = settings.get('tbsp_format')
            if tbsp_format not in ('binary', 'ascii'):
                tbsp_format = self.default_values.tbsp_format
            self.tbsp_format.setValue(tbsp_format, from_entries_save=True)

        self.changedPotential()
        self.changedMode()

        return not_loadable

    def receive(self, value_dict: dict):
        """Receives other settingsChanged pyqtSignal -> dict"""

        output_options = value_dict.get('output_options')
        if output_options is not None:
            if bool(output_options):
                self.layout_reflected.setEnabled(True)
                self.layout_sputtered.setEnabled(True)
                if self.calculation_method.getValue(save=True) != ArgumentValues.Mode.DYNAMIC:
                    self.layout_matrix_files.setEnabled(True)
            else:
                self.layout_reflected.setEnabled(False)
                self.layout_reflected.check.setChecked(False)

                self.layout_sputtered.setEnabled(False)
                self.layout_sputtered.check.setChecked(False)

                if self.calculation_method.getValue(save=True) != ArgumentValues.Mode.DYNAMIC:
                    self.layout_matrix_files.setEnabled(False)
                    self.layout_matrix_files.check.setChecked(False)

        row_added = value_dict.get('row_added')
        if row_added is True:
            dynamic = True
            if self.calculation_method.getValue(save=True) in [
                ArgumentValues.Mode.STATIC,
                ArgumentValues.Mode.STATIC_NO_RECOIL
            ]:
                dynamic = False
            self.emit({
                'max_concentration': dynamic
            })

        group_elements = value_dict.get('group_elements')
        if group_elements is not None:
            self.layout_group_elements.check.setChecked(bool(group_elements))


class CompRowBeamSettings(CompRow):
    """
    CompRow for beam

    :param version: version of simulation
    """

    syncHint = '<br>If the element occurs in both the beam and the target, the value is defined in the target table.'
    modifyHint = '<br>A red highlight indicates a modified value. A negative number resets it back to the default one.'
    # all fields of the rows by their unique name, the order of the columns is given by rowFields
    allRowFields = {field.unique: field for field in [
        CustomRowField(
            unique='qubeam',
            label='Abundance',
            tooltip='<i>qubeam</i><br>How much each element contributes to the beam composition.<br>The abundances of all elements sum up to 1.',
            synced=False,
            limit=1
        ),
        CustomRowField(
            unique='e0',
            label='Kin. energy [eV]',
            tooltip='<i>e0</i><br>The kinetic energy (in [eV]) of the incoming ions.',
            synced=False
        ),
        CustomRowField(
            unique='alpha0',
            label='Angle [°]',
            tooltip='<i>alpha0</i><br>The angle of incidence (α) of the incoming ions, measured in degrees from the surface normal.',
            synced=False
        ),
        CustomRowField(
            unique='qumax',
            label='Max conc.',
            tooltip='<i>qumax</i><br>The maximum allowed concentration of each element in the target (only dynamic calculations).' + syncHint
        ),
        CustomRowField(
            unique='a_mass',
            label='Mass [amu]',
            tooltip='<i>a_mass</i><br>The atomic mass (in [amu]) of the element, fetched from table1.' + modifyHint + syncHint,
            reset_neg=True
        ),
        CustomRowField(
            unique='isot',
            label='Isotopes',
            tooltip='<i>isot</i><br>natural: mass of the natural isotope mixture (table1)<br>isotopes: isotope masses and natural abundances (table2)' + syncHint
        ),
        CustomRowField(
            unique='dns0',
            label='Dens. [1/Å³]',
            tooltip='<i>dns0</i><br>The atomic density (in [1/Å³]) of the element, fetched from table1.' + modifyHint + '<br>Modifying is disabled if a global density is defined.' + syncHint,
            reset_neg=True
        ),
        CustomRowField(
            unique='e_surfb',
            label='Surf. bind. energy [eV]',
            tooltip='<i>e_surfb</i><br>The surface binding energy (in [eV]) of this element, fetched from table1.' + modifyHint + syncHint,
            reset_neg=True
        ),
        CustomRowField(
            unique='e_displ',
            label='Displ. energy [eV]',
            tooltip='<i>e_displ</i><br>The displacement energy (in [eV]) of this element, fetched from table1.' + modifyHint + syncHint,
            reset_neg=True
        ),
        CustomRowField(
            unique='e_bulkb',
            label='Bulk bind. energy [eV]',
            tooltip='<i>e_bulkb</i><br>Bulk binding energy (in [eV]) that is subtracted from the transferred energy.<br>-1: value from the tables.' + syncHint
        ),
        CustomRowField(
            unique='e_cutoff',
            label='Cutoff energy [eV]',
            tooltip='<i>e_cutoff</i><br>Cutoff energy (in [eV]) below which particles are stopped.<br>-1: default of SDTrimSP (from the tables).' + syncHint
        ),
        CustomRowField(
            unique='deltahf',
            label='Heat of formation [eV]',
            tooltip='<i>deltahf</i><br>Heat of formation (in [eV]) of a molecular target (since SDTrimSP 6.09 per element).<br>-1: value from table.compound.' + syncHint
        ),
        CustomRowField(
            unique='inel0',
            label='Inelastic loss model',
            tooltip='<i>inel0</i><br>The inelastic loss model used for calculations.' + syncHint
        ),
        CustomRowField(
            unique='ck_elec',
            label='Inel. correction',
            tooltip='<i>ck_elec</i><br>Correction factor for the inelastic energy loss of this element as moving particle (default 1).' + syncHint
        ),
        CustomRowField(
            unique='beta0',
            label='Azimuth [°]',
            tooltip='<i>beta0</i><br>The azimuthal angle (β) of incidence of the incoming ions in degrees (since SDTrimSP 7.00).',
            synced=False
        ),
        CustomRowField(
            unique='x0',
            label='Start depth [Å]',
            tooltip='<i>x0</i><br>Starting position of the projectiles: ≤ 0 outside the surface, > 0 inside the solid (not in SDTrimSP 6.06).',
            synced=False
        ),
        CustomRowField(
            unique='charge',
            label='Charge',
            tooltip='<i>charge</i><br>Charge of the projectiles, used with the sheath potential (shth) for Maxwellian distributions.',
            synced=False
        )
    ]}
    # columns of the beam: abundance, energy and angle first, the charge next to the mass, the isotopes at the end
    rowFields = list(itemgetter(
        'qubeam', 'e0', 'alpha0', 'qumax', 'a_mass', 'charge', 'dns0', 'e_surfb', 'e_displ', 'e_bulkb', 'e_cutoff',
        'deltahf', 'inel0', 'ck_elec', 'beta0', 'x0', 'isot'
    )(allRowFields))

    def __init__(self, *args, version: str = '', **kwargs):
        super().__init__(*args, **kwargs)
        self.version = version
        self.default_values = DefaultValues(self.version)
        self.dict_lookup = DictLookup(self.version)
        self.max_concentration_field = self.allRowFields['qumax']

        # abundances
        self.abundance = DoubleSpinBox(
            input_range=(0, 1),
            step_size=0.01
        )
        self.abundance.valueChanged.connect(lambda: self.updateHighlightWidgetValue(self.abundance, 0))
        self.abundance.valueChanged.connect(self.contentChanged.emit)

        # kinetic energy
        self.kinetic_energy = DoubleSpinBox(
            default=self.default_values.e0,
            input_range=SpinBoxRange.ZERO_INF,
            step_size=0.01
        )
        self.kinetic_energy.valueChanged.connect(self.contentChanged.emit)

        # incident angle
        self.angle = DoubleSpinBox(
            default=self.default_values.alpha0,
            input_range=(-90, 90),
            step_size=0.01
        )
        self.angle.valueChanged.connect(self.contentChanged.emit)

        # maximum concentration
        self.maximum_concentration = DoubleSpinBox(
            default=1,
            input_range=(0, 1),
            decimals=4
        )
        self.maximum_concentration.valueChanged.connect(self.contentChanged.emit)

        self.element_precision = 6

        # atomic mass
        self.atomic_mass = DoubleSpinBox(
            input_range=(-1e3, 1e3),
            decimals=self.element_precision
        )
        self.atomic_mass.setMaximumWidth(100)
        self.atomic_mass.valueChanged.connect(
            lambda _: self.updateHighlightAndResetSpinbox(self.atomic_mass,
                                                          self.element.atomic_mass,
                                                          digits=self.element_precision)
        )
        self.atomic_mass.valueChanged.connect(self.contentChanged.emit)

        # atomic density
        self.atomic_density = DoubleSpinBox(
            input_range=(-1e3, 1e3),
            decimals=self.element_precision
        )
        self.atomic_density.setMaximumWidth(100)
        self.atomic_density.valueChanged.connect(
            lambda _: self.updateHighlightAndResetSpinbox(self.atomic_density,
                                                          self.element.atomic_density,
                                                          digits=self.element_precision)
        )
        self.atomic_density.valueChanged.connect(self.contentChanged.emit)

        # surface binding energy
        self.surface_binding_energy = DoubleSpinBox(
            input_range=(-1e3, 1e3),
            decimals=self.element_precision
        )
        self.surface_binding_energy.valueChanged.connect(
            lambda _: self.updateHighlightAndResetSpinbox(self.surface_binding_energy,
                                                          self.element.surface_binding_energy,
                                                          digits=self.element_precision)
        )
        self.surface_binding_energy.valueChanged.connect(self.contentChanged.emit)

        # displacement energy
        self.displacement_energy = DoubleSpinBox(
            input_range=(-1e3, 1e3),
            decimals=self.element_precision
        )
        self.displacement_energy.valueChanged.connect(
            lambda _: self.updateHighlightAndResetSpinbox(self.displacement_energy,
                                                          self.element.displacement_energy,
                                                          digits=self.element_precision)
        )
        self.displacement_energy.valueChanged.connect(self.contentChanged.emit)

        # inelastic loss model
        self.inelastic_loss_model_entries = [
            'Lindhard-Scharff',
            'Oen-Robinson',
            'average of (1) and (2)',
            'H, D, T',
            'He3, He4',
            'Ziegler-Biersack'
        ]
        self.inelastic_loss_model_entries_save = [
            ArgumentValues.InelasticLossModel.LINDHARD_SCHARFF,
            ArgumentValues.InelasticLossModel.OEN_ROBINSON,
            ArgumentValues.InelasticLossModel.LINDHARD_SCHARFF_AND_OEN_ROBINSON,
            ArgumentValues.InelasticLossModel.HYDROGEN,
            ArgumentValues.InelasticLossModel.HELIUM,
            ArgumentValues.InelasticLossModel.ZIEGLER
        ]
        self.inelastic_loss_model_tooltips = [
            'Necessary condition: E < 25 · Z^(4/3) · M (in keV) where E, Z, M are the energy, the atomic number and the atomic mass of the moving particle',
            'Necessary condition: E < 25 · Z^(4/3) · M (in keV)',
            'Equipartition of Lindhard-Scharff and Oen-Robinson',
            'High energy hydrogen (H, D, T) (energy > 25 keV), values taken from "table3"',
            'High energy helium (He3, He) (energy > 100 keV), values taken from "table4"',
            'Values are calculated for each element based on values taken from "table6a" and "table6b"'
        ]

        if Versions.atLeast(self.version, Versions.V_606):
            self.inelastic_loss_model_entries.append('LZ7')
            self.inelastic_loss_model_entries_save.append(ArgumentValues.InelasticLossModel.LINDHARD_SCHARFF_AND_ZIEGLER)
            self.inelastic_loss_model_tooltips.append('Combination of Lindhard-Scharff and Ziegler-Biersack with corretion')

        if Versions.atLeast(self.version, Versions.V_700):
            self.inelastic_loss_model_entries.append('tabulated')
            self.inelastic_loss_model_entries_save.append(ArgumentValues.InelasticLossModel.TABULATED)
            self.inelastic_loss_model_tooltips.append(
                'Manually tabulated stopping power from database "tbsp.db" in the tables-directory'
            )

        self.inelastic_loss_model = ComboBox(
            default=self.default_values.inel0,
            entries=self.inelastic_loss_model_entries,
            entries_save=self.inelastic_loss_model_entries_save,
            numbering=1,
            label_default=True,
            tooltips=self.inelastic_loss_model_tooltips
        )

        self.inelastic_loss_model.currentIndexChanged.connect(self.contentChanged.emit)
        self.inelastic_loss_model.mouseReleaseEvent = lambda _: setWidgetBackground(self.inelastic_loss_model, False)  # type: ignore[method-assign, assignment]  # replaces the event handler of this widget

        # azimuthal angle, starting depth and charge of projectiles
        self.azimuth = DoubleSpinBox(default=self.default_values.beta0, input_range=(-360, 360), step_size=0.01)
        self.start_depth = DoubleSpinBox(default=self.default_values.x0, input_range=(-1e6, 1e6), step_size=0.01)
        self.charge = DoubleSpinBox(default=self.default_values.charge, input_range=(0, 100), step_size=1)
        self.azimuth.setEnabled(self.default_values.supports_beta0)
        self.start_depth.setEnabled(self.default_values.supports_x0)

        # element parameters (-1: value from the tables)
        self.inelastic_correction = DoubleSpinBox(default=self.default_values.ck_elec, input_range=(0, 1e3), decimals=4)
        self.cutoff_energy = DoubleSpinBox(default=self.default_values.e_cutoff, input_range=(-1, 1e6), decimals=4)
        self.bulk_binding_energy = DoubleSpinBox(default=self.default_values.e_bulkb, input_range=(-1, 1e6), decimals=4)
        self.heat_of_formation = DoubleSpinBox(default=self.default_values.deltahf, input_range=(-1e3, 1e3), decimals=4)
        self.heat_of_formation.setEnabled(self.default_values.supports_deltahf)
        self.isotopes = ComboBox(default=0, entries=['natural', 'isotopes'], entries_save=[0, 1])

        for widget in (self.azimuth, self.start_depth, self.charge, self.inelastic_correction, self.cutoff_energy, self.bulk_binding_energy, self.heat_of_formation):
            widget.valueChanged.connect(self.contentChanged.emit)
        self.isotopes.currentIndexChanged.connect(self.contentChanged.emit)

        # widgets of the fields, in the order of the fields of the row (columns of the table)
        self.field_widgets = {
            'qubeam': self.abundance,
            'e0': self.kinetic_energy,
            'alpha0': self.angle,
            'qumax': self.maximum_concentration,
            'a_mass': self.atomic_mass,
            'isot': self.isotopes,
            'dns0': self.atomic_density,
            'e_surfb': self.surface_binding_energy,
            'e_displ': self.displacement_energy,
            'e_bulkb': self.bulk_binding_energy,
            'e_cutoff': self.cutoff_energy,
            'deltahf': self.heat_of_formation,
            'inel0': self.inelastic_loss_model,
            'ck_elec': self.inelastic_correction,
            'beta0': self.azimuth,
            'x0': self.start_depth,
            'charge': self.charge
        }
        self.row_widgets += [self.field_widgets[field.unique] for field in self.row_fields if field.unique in self.field_widgets]

        self.updateHighlightWidgetValue(self.abundance, 0)

        self.clearSpinboxButtons()

    def setElement(self, element: Element):
        """Sets rows element to element"""

        self.element = element

        self.atomic_mass.setValue(round(element.atomic_mass, self.element_precision))

        # Only set the element's density if it's not defined by the global density
        if self.atomic_density.isEnabled():
            self.atomic_density.setValue(round(element.atomic_density, self.element_precision))

        surface_binding_energy = element.surface_binding_energy
        if not isinstance(surface_binding_energy, float):
            surface_binding_energy = 0
        self.surface_binding_energy.setValue(round(surface_binding_energy, self.element_precision))

        displacement_energy = element.displacement_energy
        if not isinstance(displacement_energy, float):
            displacement_energy = 0
        self.displacement_energy.setValue(round(displacement_energy, self.element_precision))

        # set inelastic model if H,D,T or He3,He4 is set
        if self.element.symbol in ['H', 'H2', 'D', 'T']:
            self.inelastic_loss_model.setValue(ArgumentValues.InelasticLossModel.HYDROGEN, from_entries_save=True)
        elif self.element.symbol in ['He', 'He3']:
            self.inelastic_loss_model.setValue(ArgumentValues.InelasticLossModel.HELIUM, from_entries_save=True)

        # needs to happen after synced values are changed, since element-change-signal should be emitted last
        super().setElement(element)

    def adaptElement(self, element: Element):
        """Adapts element specific parameters"""

        self.atomic_mass.setValue(round(element.atomic_mass, self.element_precision))

        # Only set the element's density if it's not defined by the global density
        if self.atomic_density.isEnabled():
            self.atomic_density.setValue(round(element.atomic_density, self.element_precision))

        surface_binding_energy = element.surface_binding_energy
        if not isinstance(surface_binding_energy, float):
            surface_binding_energy = 0
        self.surface_binding_energy.setValue(round(surface_binding_energy, self.element_precision))

        displacement_energy = element.displacement_energy
        if not isinstance(displacement_energy, float):
            displacement_energy = 0
        self.displacement_energy.setValue(round(displacement_energy, self.element_precision))

    def getElement(self):
        """Returns new element with modified values"""

        new_element = self.element.copy()
        modified = False

        atomic_mass = self.atomic_mass.value()
        if atomic_mass != self.element.atomic_mass:
            modified = True
            new_element.atomic_mass = atomic_mass

        atomic_density = self.atomic_density.value()
        if atomic_density != self.element.atomic_density:
            modified = True
            new_element.atomic_density = atomic_density

        surface_binding_energy = self.surface_binding_energy.value()
        if surface_binding_energy != self.element.surface_binding_energy:
            modified = True
            new_element.surface_binding_energy = surface_binding_energy

        displacement_energy = self.displacement_energy.value()
        if displacement_energy != self.element.displacement_energy:
            modified = True
            new_element.displacement_energy = displacement_energy

        new_element.modified = modified

        return new_element

    def setEnabled(self, enabled: bool):
        """
        Set row disabled or enabled

        :param enabled: enable/disable
        """

        super().setEnabled(enabled)
        if enabled and not self.max_concentration_field.enabled:
            self.maximum_concentration.setEnabled(False)

        # parameters that are not supported by the version
        if not self.default_values.supports_beta0:
            self.azimuth.setEnabled(False)
        if not self.default_values.supports_x0:
            self.start_depth.setEnabled(False)
        if not self.default_values.supports_deltahf:
            self.heat_of_formation.setEnabled(False)

    def getArguments(self) -> RowArguments:
        """Returns <RowArguments> container of parameters for row"""

        return RowArguments(
            index=self.element_index.value(),
            symbol=self.element.symbol,  # symbol
            element=self.getElement(),
            abundance=self.abundance.value(),  # qubeam (beam) / qu (target)
            energy=self.kinetic_energy.value(),  # e0
            angle=self.angle.value(),  # alpha0
            max_atomic_fraction=self.maximum_concentration.value(),  # qumax
            inelastic_loss_model=self.inelastic_loss_model.getValue(save=True),  # inel0
            azimuth=self.azimuth.value(),  # beta0
            start_depth=self.start_depth.value(),  # x0
            charge=self.charge.value(),  # charge
            inelastic_correction=self.inelastic_correction.value(),  # ck_elec
            cutoff_energy=self.cutoff_energy.value(),  # e_cutoff
            bulk_binding_energy=self.bulk_binding_energy.value(),  # e_bulkb
            heat_of_formation=self.heat_of_formation.value(),  # deltahf
            isotopes=self.isotopes.getValue(save=True)  # isot
        )

    def setArguments(self, arguments: RowArguments, general_arguments: Union[SimulationArguments, GeneralArguments]):
        """Sets <RowArguments> container of parameters for row"""

        assumed = arguments.get('assumed')
        if not isinstance(assumed, list):
            assumed = []

        # element
        self.setElement(arguments.element)

        # abundance
        qubeam = arguments.abundance
        if 'abundance' in assumed:
            qubeam = self.default_values.qubeam
        self.abundance.setValue(qubeam)

        # maximum concentration
        qumax = arguments.max_atomic_fraction
        if 'max_atomic_fraction' in assumed:
            qumax = self.default_values.qumax
        self.maximum_concentration.setValue(qumax)

        # incidence energy
        e0 = arguments.energy
        if 'energy' in assumed:
            e0 = self.default_values.e0
        self.kinetic_energy.setValue(e0)

        # incidence angle
        alpha0 = arguments.angle
        if 'angle' in assumed:
            alpha0 = self.default_values.alpha0
        self.angle.setValue(alpha0)

        # further parameters (default if not given)
        for key, widget, default in [
            ('azimuth', self.azimuth, self.default_values.beta0),
            ('start_depth', self.start_depth, self.default_values.x0),
            ('charge', self.charge, self.default_values.charge),
            ('inelastic_correction', self.inelastic_correction, self.default_values.ck_elec),
            ('cutoff_energy', self.cutoff_energy, self.default_values.e_cutoff),
            ('bulk_binding_energy', self.bulk_binding_energy, self.default_values.e_bulkb),
            ('heat_of_formation', self.heat_of_formation, self.default_values.deltahf)
        ]:
            value = arguments.get(key)
            widget.setValue(float(value) if isinstance(value, (int, float)) else default)
        isot = arguments.get('isotopes')
        self.isotopes.setValue(isot if isot in (0, 1) else self.default_values.isot, from_entries_save=True)

        # inelastic loss model
        inel0 = arguments.get('inelastic_loss_model')
        if inel0 not in self.dict_lookup.inel0:
            inel0 = general_arguments.get('inelastic_loss_model')
        if inel0 not in self.dict_lookup.inel0:
            setWidgetBackground(self.inelastic_loss_model, True)
            self.inelastic_loss_model.reset()
        else:
            self.inelastic_loss_model.setValue(inel0, from_entries_save=True)

    def receive(self, value_dict: dict):
        """Receives other settingsChanged pyqtSignal -> dict"""

        max_concentration = value_dict.get('max_concentration')
        if max_concentration is not None:
            self.max_concentration_field.enabled = bool(max_concentration)
            if self.enabled:
                self.maximum_concentration.setEnabled(self.max_concentration_field.enabled)

        energy = value_dict.get('energy')
        if energy is not None:
            self.kinetic_energy.setEnabled(bool(energy))

        angle = value_dict.get('angle')
        if angle is not None:
            self.angle.setEnabled(bool(angle))


class CompRowTargetSettings(CompRowBeamSettings):
    """
    CompRow for target

    :param version: version of simulation
    """

    # without the fields of the beam only (abundance, energy, angles, start depth and charge), the isotopes at the end
    rowFields = list(itemgetter(
        'qumax', 'a_mass', 'dns0', 'e_surfb', 'e_displ', 'e_bulkb', 'e_cutoff', 'deltahf', 'inel0', 'ck_elec', 'isot'
    )(CompRowBeamSettings.allRowFields))

    def receive(self, value_dict: dict):
        """Receives other settingsChanged pyqtSignal -> dict"""

        super().receive(value_dict)
        density = value_dict.get('atomic_global_density')
        if isinstance(density, bool):
            self.atomic_density.setValue(self.element.original.atomic_density)
            if self.enabled:
                self.atomic_density.setEnabled(True)
        elif isinstance(density, float):
            self.atomic_density.setValue(density)
            self.atomic_density.setEnabled(False)


class HlPlot(HlGeneralPlot):
    """
    QHBoxLayout for general plot settings

    :param version: version of simulation
    """

    def __init__(self, version: str):
        super().__init__(version)

        # history step slider
        self.history_step_tooltip = 'The history step which will be plotted, from 0 to (number of histories)/(histories between outputs)'
        self.history_step = SpinBox(
            default=0
        )
        self.layout_history_step = InputHBoxLayout(
            'History step',
            self.history_step,
            tooltip=self.history_step_tooltip
        )
        self.layout_history_step.setHidden(True)
        self.addLayout(self.layout_history_step)

        self.history_spacer = QLabel()
        self.history_spacer.setHidden(True)
        self.addWidget(self.history_spacer)

        self.history_step_slider = QSlider(Qt.Orientation.Horizontal)
        self.history_step_slider.setMinimumWidth(200)
        self.history_step_slider.setMinimum(0)
        self.history_step_slider.setToolTip(self.history_step_tooltip)
        self.history_step_slider.hide()
        self.addWidget(self.history_step_slider)

        # connect history sliders
        self.history_step.valueChanged.connect(self.history_step_slider.setValue)
        self.history_step_slider.valueChanged.connect(self.history_step.setValue)
        self.history_step.valueChanged.connect(lambda val: self.emit({'history': val}))

        # polar energy
        self.polar_angle = DoubleSpinBox(
            default=0,
            input_range=(-90, 90),
            scroll=True
        )
        self.layout_polar_angle = InputHBoxLayout(
            'Polar angle',
            self.polar_angle,
            tooltip='Polar angle at which the energy will be displayed'
        )
        self.layout_polar_angle.setHidden(True)
        self.addLayout(self.layout_polar_angle)
        self.polar_angle.valueChanged.connect(self.emit_polar_angle)

        self.polar_angle_delta = DoubleSpinBox(
            default=0,
            input_range=(0, 180),
            scroll=True
        )
        self.layout_polar_angle_delta = InputHBoxLayout(
            'Polar angle delta',
            self.polar_angle_delta,
            tooltip='Delta polar angle at which the energy will be displayed'
        )
        self.layout_polar_angle_delta.setHidden(True)
        self.addLayout(self.layout_polar_angle_delta)
        self.polar_angle_delta.valueChanged.connect(self.emit_polar_angle)

        # trajectories
        self.trajectory_number = SpinBox(default=1, input_range=(1, 1), buttons=True, scroll=True)
        self.layout_trajectory_number = InputHBoxLayout(
            'Projectile',
            self.trajectory_number,
            tooltip='Number of the projectile whose trajectory (and the ones of its recoils) is shown.<br>'
                    'The number of traced projectiles is set in the simulation settings (numb_hist)'
        )
        self.trajectory_view = ComboBox(
            entries=['depth x – lateral y', 'depth x – lateral z', 'both lateral directions', 'top view (y – z)', '3D'],
            entries_save=['y', 'z', 'both', 'top', '3d']
        )
        self.layout_trajectory_view = InputHBoxLayout('View', self.trajectory_view, tooltip='Plane in which the trajectories are shown (the 3D view can be rotated)')
        self.trajectory_color = ComboBox(entries=['species and generation', 'energy', 'time'], entries_save=['species', 'energy', 'time'])
        self.layout_trajectory_color = InputHBoxLayout(
            'Color',
            self.trajectory_color,
            tooltip='Color of the trajectories:<br>'
                    '<b>species and generation</b>: each species has its own color, recoils of later generations of the cascade are darker<br>'
                    '<b>energy</b>: kinetic energy of the particle on its flight path<br>'
                    '<b>time</b>: time since the projectile entered the target'
        )
        self.trajectory_recoils = InputHBoxLayout('Recoils', None, checkbox=True, tooltip='Show the trajectories of the recoils')
        self.trajectory_layers = InputHBoxLayout('Layers', None, checkbox=True, tooltip='Show the layers of the target structure below the trajectories')

        # animation of the cascade: time slider (the maximum shows the whole cascade), play and export as GIF
        self.trajectory_time_steps = 200
        self.trajectory_time = QSlider(Qt.Orientation.Horizontal)
        self.trajectory_time.setRange(0, self.trajectory_time_steps)
        self.trajectory_time.setValue(self.trajectory_time_steps)
        self.trajectory_time.setMinimumWidth(100)
        self.layout_trajectory_time = InputHBoxLayout(
            'Time',
            self.trajectory_time,
            tooltip='Time in the collision cascade on a logarithmic scale (right end: the whole cascade)'
        )
        self.trajectory_play = QPushButton(getIcon('play'), '')
        self.trajectory_play.setCheckable(True)
        self.trajectory_play.setToolTip('Animate the collision cascade')
        self.trajectory_gif = QPushButton('GIF')
        self.trajectory_gif.setToolTip('Save the animation of the collision cascade with the current settings as GIF')
        self.layout_trajectory_time.addWidget(self.trajectory_play)
        self.layout_trajectory_time.addWidget(self.trajectory_gif)
        self.layout_trajectory_time.widgets_list += [self.trajectory_play, self.trajectory_gif]
        self.trajectory_timer = QTimer()
        self.trajectory_timer.setInterval(60)
        self.trajectory_timer.timeout.connect(self.animationStep)
        self.trajectory_play.toggled.connect(self.animate)
        self.trajectory_gif.clicked.connect(lambda: self.emit({'trajectory_gif': self.trajectoryArguments(animation=False)}))

        self.trajectory_layouts = [
            self.layout_trajectory_number, self.layout_trajectory_view, self.layout_trajectory_color, self.trajectory_recoils,
            self.trajectory_layers, self.layout_trajectory_time
        ]
        for layout in self.trajectory_layouts:
            layout.setHidden(True)
            self.addLayout(layout)
        self.trajectory_number.valueChanged.connect(self.emitTrajectories)
        self.trajectory_view.currentIndexChanged.connect(self.emitTrajectories)
        self.trajectory_color.currentIndexChanged.connect(self.emitTrajectories)
        self.trajectory_recoils.check.stateChanged.connect(self.emitTrajectories)
        self.trajectory_layers.check.stateChanged.connect(self.emitTrajectories)
        self.trajectory_time.valueChanged.connect(self.emitTrajectories)

        # energy distribution in the target
        self.energy_distribution_view = ComboBox(
            entries=['depth x – lateral y', 'depth x – lateral z', 'top view (y – z)', 'depth profile'],
            entries_save=['y', 'z', 'top', 'depth']
        )
        self.layout_energy_distribution_view = InputHBoxLayout(
            'View',
            self.energy_distribution_view,
            tooltip='Map of the energy summed over the third direction or depth profile summed over both lateral directions'
        )
        self.energy_distribution_log = InputHBoxLayout('Logarithmic scale', None, checkbox=False, tooltip='Logarithmic color scale')
        self.energy_distribution_layouts = [self.layout_energy_distribution_view, self.energy_distribution_log]
        for layout in self.energy_distribution_layouts:
            layout.setHidden(True)
            self.addLayout(layout)
        self.energy_distribution_view.currentIndexChanged.connect(self.emitEnergyDistribution)
        self.energy_distribution_log.check.stateChanged.connect(self.emitEnergyDistribution)

        self.addStretch(1)

    def emitEnergyDistribution(self):
        """Emits signal for the plot of the energy distribution in the target"""

        self.emit({
            'energy_distribution': {
                'view': self.energy_distribution_view.getValue(save=True),
                'log': self.energy_distribution_log.check.isChecked()
            }
        })

    def setEnergyDistributionHidden(self, hidden: bool):
        """Shows or hides the settings of the energy distribution plot"""

        for layout in self.energy_distribution_layouts:
            layout.setHidden(hidden)

    def trajectoryArguments(self, animation: bool = True) -> dict:
        """
        Returns the arguments of the trajectory plot

        :param animation: include the time of the animation
        """

        arguments = {
            'projectile': self.trajectory_number.value(),
            'view': self.trajectory_view.getValue(save=True),
            'color': self.trajectory_color.getValue(save=True),
            'recoils': self.trajectory_recoils.check.isChecked(),
            'layers': self.trajectory_layers.check.isChecked(),
        }
        if animation:
            value = self.trajectory_time.value()
            arguments['time_fraction'] = None if value >= self.trajectory_time_steps else value / self.trajectory_time_steps
        return arguments

    def emitTrajectories(self):
        """Emits signal for the trajectory plot"""

        self.emit({'trajectories': self.trajectoryArguments()})

    def animate(self, play: bool):
        """Starts or stops the animation of the collision cascade"""

        if play:
            if self.trajectory_time.value() >= self.trajectory_time_steps:
                self.trajectory_time.setValue(0)
            self.trajectory_play.setIcon(getIcon('pause'))
            self.trajectory_timer.start()
        else:
            self.trajectory_play.setIcon(getIcon('play'))
            self.trajectory_timer.stop()

    def animationStep(self):
        """Next step of the animation"""

        value = self.trajectory_time.value() + 1
        self.trajectory_time.setValue(value)
        if value >= self.trajectory_time_steps:
            self.trajectory_play.setChecked(False)

    def setTrajectoriesHidden(self, hidden: bool):
        """Shows or hides the settings of the trajectory plot"""

        for layout in self.trajectory_layouts:
            layout.setHidden(hidden)
        if hidden:
            self.trajectory_play.setChecked(False)

    def emit_polar_angle(self):
        """Emits signal for polar angle energy"""

        self.emit({
            'energy_polar': {
                'polar_angle': self.polar_angle.value(),
                'polar_angle_delta': self.polar_angle_delta.value(),
            }
        })

    def receive(self, value_dict: dict):
        """Receives pyqtSignal -> dict"""

        hide = value_dict.get('hide')
        if hide:
            self.layout_history_step.setHidden(hide)
            self.history_step_slider.setHidden(hide)
            self.history_spacer.setHidden(hide)
            self.layout_polar_angle.setHidden(hide)
            self.layout_polar_angle_delta.setHidden(hide)
            self.setTrajectoriesHidden(hide)
            self.setEnergyDistributionHidden(hide)

        # hide history buttons
        hide_history = value_dict.get('hide_history')
        if isinstance(hide_history, bool):
            self.layout_history_step.setHidden(hide_history)
            self.history_step_slider.setHidden(hide_history)
            self.history_spacer.setHidden(hide_history)
            if not hide_history:
                self.setTrajectoriesHidden(True)
                self.setEnergyDistributionHidden(True)

        # show trajectory settings (and hide the others)
        hide_trajectories = value_dict.get('hide_trajectories')
        if isinstance(hide_trajectories, bool):
            self.setTrajectoriesHidden(hide_trajectories)
            if not hide_trajectories:
                for widget in (self.layout_history_step, self.history_step_slider, self.history_spacer, self.layout_polar_angle, self.layout_polar_angle_delta):
                    widget.setHidden(True)
                self.setEnergyDistributionHidden(True)

        # show the settings of the energy distribution (and hide the others)
        hide_energy_distribution = value_dict.get('hide_energy_distribution')
        if isinstance(hide_energy_distribution, bool):
            self.setEnergyDistributionHidden(hide_energy_distribution)
            if not hide_energy_distribution:
                for widget in (self.layout_history_step, self.history_step_slider, self.history_spacer, self.layout_polar_angle, self.layout_polar_angle_delta):
                    widget.setHidden(True)
                self.setTrajectoriesHidden(True)

        max_trajectories = value_dict.get('max_trajectories')
        if max_trajectories is not None:
            self.trajectory_number.blockSignals(True)
            self.trajectory_number.setMaximum(max(1, int(max_trajectories)))
            self.trajectory_number.blockSignals(False)

        # set max history
        max_hist = value_dict.get('max_history')
        if max_hist is not None:
            max_hist = int(max_hist)
            self.history_step.setMaximum(max_hist)
            self.history_step_slider.setMaximum(max_hist)

        # set history
        hist = value_dict.get('history')
        if hist is not None:
            self.history_step_slider.setValue(int(hist))

        # hide polar angle buttons
        hide_polar_angle = value_dict.get('hide_polar_angle')
        if isinstance(hide_polar_angle, bool):
            self.layout_polar_angle.setHidden(hide_polar_angle)
            self.layout_polar_angle_delta.setHidden(hide_polar_angle)
            if not hide_polar_angle:
                self.setTrajectoriesHidden(True)

        # set polar angle
        polar_angle = value_dict.get('polar_angle')
        if polar_angle is not None:
            self.polar_angle.setValue(float(polar_angle))

        # set polar angle delta
        polar_angle_delta = value_dict.get('polar_angle_delta')
        if polar_angle_delta is not None:
            self.polar_angle_delta.setValue(float(polar_angle_delta))


class SimulationInput(SimulationsInput):
    """
    Class for SDTrimSP specific parameters
    """

    default_values: 'DefaultValues'

    # parameters should be different for each simulation class
    Name = 'SDTrimSP'
    Versions = [
        Versions.V_601,
        Versions.V_606,
        Versions.V_609,
        Versions.V_700,
        Versions.V_702,
        Versions.V_707,
    ]
    Description = '''
SDTrimSP is designed for atomic collisions in amorphous
targets. It calculates ranges, reflection coefficients and sputtering yields as
well as more detailed information like depth distributions of implanted and
energy distributions of backscattered and sputtered atoms. The program is
based on the binary collision approximation and uses the same physics as its
predecessors TRIM.SP and TRIDYN, but the structure of the new program
has been completely changed. It runs on all sequential and parallel platforms
with a F90 compiler. Table lookup is applied for all available atomic data
needed for input, and different integration schemes for several interaction
potentials are provided. Several examples are given to show the wide range
of possible applications.
'''
    Logo = ':/assets/aboutlogo_ipp.png'
    About = '''
Andreas Mutzke

<a href="https://www.ipp.mpg.de">https://www.ipp.mpg.de/</a>
    '''
    SaveFolder = 'SDTrimSP'
    BinaryKeywords = ['sdtrim']
    InputFilename = 'tri.inp'
    CrystalFilename = 'crystal.inp'
    LayerFilename = 'layer.inp'
    ExampleAdditionalSetting = 'e.g. ienergy_distr = .true.'
    SkipList = [InputFilename, LayerFilename, CrystalFilename, 'ausdat.dat']
    # e.g. a0_tdiff.inp and eact_tdiff.inp (diffusion), energy.inp, angle.inp, CH.data (chemical erosion)
    KeepFiles = ['*.inp', '*.data']
    OutputTooltips = {
        'output.dat': 'general standard output',
        'energy_analyse.dat': 'sum of all energy',
        'E0_31_target.dat': 'number particle, energy, atomic-fraction, moment, surface\nas function of fluence',
        'E0_33_sputt.dat': 'sputtered yield by generation',
        'E0_34_moments.dat': 'moment_energy, moment_depth_imp.',
        'layerinp.dat': 'depth profile, use to create (copy) inputfile: layer.inp\nread layer.inp: with switch iq0=-1',
        'depth_proj.dat': 'depth distributions projectiles',
        'depth_recoil.dat': 'depth distributions recoils',
        'mepb.dat': 'e-energy p - pathlength',
        'mept.dat': 'e-energy p - pathlength',
        'mpe_ex_p.dat': 'energy/xm - maximum penetration only backscattered',
        'morigin_ex_bs.dat': 'energy/depth of origin (come from which depth) only sputtered',
        'morigin_ex_ts.dat': 'energy/depth of origin (come from which depth) only sputtered',
        'partic_back_p.dat': 'first "ioutput_part(2)" back-scattered particle',
        'partic_back_r.dat': 'first "ioutput_part(5)" back-sputterd particle',
        'partic_stop_p.dat': 'first "ioutput_part(1)" implanted projectiles',
        'partic_stop_r.dat': 'first "ioutput_part(4)" moove/implamted recoils',
        'partic_tran_p.dat': 'first "ioutput_part(3)"',
        'partic_tran_r.dat': 'first "ioutput_part(6)" back-transmiissed recoils',
        'trajec_all.dat': 'first "numb_hist" complete trajectories',
        'trajec_back_p.dat': 'first "ioutput_hist(2)" back-scattered trajectories',
        'trajec_back_r.dat': 'first "ioutput_hist(5)" back-sputterd trajectories',
        'trajec_stop_p.dat': 'first "ioutput_hist(1)" stopped projectil trajectories',
        'trajec_stop_r.dat': 'first "ioutput_hist(4)" stopped recoil trajectories',
        'time.dat': 'output calculation time',
        'time_run.dat': 'output during the run',
        'ausdat.dat': 'temporary help file',
        'serie.dat': 'energy, alpha, refl.coeff, sputt.coeff (number_calc>1)',
        'meagb_p.dat': 'output of backscattered particles',
        'meagb_s.dat': 'output of all backsputtered particles',
        'meagt_p.dat': 'output of all transmitted scattered particles',
        'meagt_s.dat': 'output of all transmitted sputtered particles'
    }
    GroupElements = DefaultValues.group_elements

    # Reference to classes
    HlBeamSettings = HlBeamSettings
    HlTargetSettings = HlTargetSettings
    VlSimulationSettings = VlSimulationSettings
    CompRowBeamSettings = CompRowBeamSettings
    CompRowTargetSettings = CompRowTargetSettings

    # Maximum number of components
    MaxComponents = 8

    def __init__(self):
        super().__init__()

    @staticmethod
    def getVersionName(folder: Optional[Path], binary: Optional[Path]) -> Union[str, Literal[False]]:
        """
        Returns version of simulation depending on selected folder and binary or False if no version can be determined

        :param folder: main folder of simulation
        :param binary: binary of simulation
        """

        version = []

        if folder is not None:
            # checked on sourcecode or if 'src'-directory exists
            source_code = folder / 'src' / 'SDTrimSP.F90'  # check sourcecode
            try:
                with open(source_code, 'r', encoding='utf-8', errors='replace') as f:
                    for line in f:
                        if line.strip().startswith('avs0 ='):
                            version = [line.split('\'')[1]]  # save as array to we can ask its length
                            break
            except FileNotFoundError:
                logging.info(f'Could not open sourcecode file "{source_code}"!')
                pass
            if not version and (folder / 'src').is_dir():  # search path
                version = findall(r'\d+\.\d+', pathToStr(folder))
            if not version:  # search binary path
                version = findall(r'\d+\.\d+', pathToStr(binary))

        if not len(version) or not len(version[0]):
            return False

        return f'SDTrimSP v{version[0]}'

    @staticmethod
    def getDoc(folder: Path, binary: Path, version: str) -> Union[Path, bool]:
        """
        Returns path to documentation pdf-file

        :param folder: main folder of simulation
        :param binary: binary of simulation
        :param version: version of simulation

        :return: path to documentation pdf-file or
                 True if no documentation can be found but there is a possibility to download
                 False if no documentation can be found
        """

        if folder is None or not folder.is_dir():
            return False

        def pdfFiles(directory: Path) -> List[Path]:
            try:
                return sorted(file for file in directory.iterdir() if file.is_file() and file.suffix.lower() == '.pdf')
            except OSError:
                return []

        # check for pdf file in doc folder, then in main folder
        files = pdfFiles(folder / 'doc') + pdfFiles(folder)
        if files:
            return files[0]

        # newer versions (e.g. 7.05, 7.07) come without the pdf: the documentation of another installed version next to
        # this folder (the newest one, the folder names contain the version)
        try:
            siblings = sorted((path for path in folder.parent.iterdir() if path.is_dir() and path != folder), key=lambda path: path.name, reverse=True)
        except OSError:
            siblings = []
        for sibling in siblings:
            files = pdfFiles(sibling / 'doc') + pdfFiles(sibling)
            if files and (sibling / 'tables').is_dir():
                return files[0]

        # no pdf documentation found, but downloadDoc method is implemented
        return True

    @staticmethod
    def downloadDoc(parent, folder: Path, binary: Path, version: str):
        """
        Downloads documentation pdf-file and saves it in the default directory

        :param parent: parent widget
        :param folder: main folder of simulation
        :param binary: binary of simulation
        :param version: version of simulation
        """

        dialog = DownloadDialog(
            parent=parent,
            url='https://pure.mpg.de/pubman/item/item_3026474_4/component/file_3028154/IPP%202019-02.pdf',
            path=folder / 'doc',
            name='IPP_2019-02.pdf',
            expected_file_size=1250762
        )
        dialog.open()

    def update(self, folder: Path, binary: Path, version: str):
        """
        Updates on startup

        :param folder: folder of simulation
        :param binary: binary path of simulation
        :param version: version of simulation
        """

        # default values
        self.default_values = DefaultValues(version)
        self.simulation_folder = folder

        # get compounds
        # open compound file and read contents
        self.CompoundList = []
        if Versions.atLeast(version, Versions.V_700):
            compound_table2 = folder / 'tables' / 'table.compound'
            try:
                for line in readlines(compound_table2, 'r', comments=['', '!'], encoding='utf-8', errors='replace'):
                    content = line.split()

                    try:
                        self.CompoundList.append(Compound(
                            content[0],
                            elements={content[1]: int(content[9]), content[2]: int(content[10])}
                        ))
                    except (ValueError, IndexError):
                        logging.debug(f'Could not read compound "{line}"!')
            except FileNotFoundError:
                logging.info(f'Could not open compound table (2 elements) "{compound_table2}"!')

            compound_table3 = folder / 'tables' / 'table.compound3'
            try:
                for line in readlines(compound_table3, 'r', comments=['', '!'], encoding='utf-8', errors='replace'):
                    content = line.split()

                    try:
                        self.CompoundList.append(Compound(
                            content[0],
                            elements={content[6]: int(content[10]), content[7]: int(content[11]), content[8]: int(content[12])}
                        ))
                    except (ValueError, IndexError):
                        logging.debug(f'Could not read compound "{line}"!')

            except FileNotFoundError:
                logging.info(f'Could not open compound table (3 elements) "{compound_table3}"!')

        # update number of components: the installation is compiled for ncpm species (src/param.F90, e.g. 3 for 6.01,
        # 12 for 7.00), otherwise the documented number of the version
        self.MaxComponents = maxElements(folder) or (11 if Versions.atLeast(version, Versions.V_609) else 8)

        # update OutputTooltips
        # -> could be used, but is not: formatting in this file is bad for reading and there are spelling mistakes
        # -> not all files are described in output_files.txt, some are in Readme
        update_tooltips = False
        if update_tooltips:
            output_variables_doc = folder / 'doc' / 'output_files.txt'
            try:
                with open(output_variables_doc, 'r', encoding='utf-8', errors='replace') as file:
                    for line in file.readlines():
                        content = line.split('.dat')
                        if len(content) <= 1:
                            continue

                        output_file_name = f'{content[0].strip()}.dat'
                        self.OutputTooltips[output_file_name] = content[1].strip()
            except FileNotFoundError:
                logging.info(f'Could not open output variable documentation "{output_variables_doc}"!')
                pass

        # update possible input variables
        input_variables_doc = folder / 'doc' / 'tri.inp.txt'
        try:
            with open(input_variables_doc, 'r', encoding='utf-8', errors='replace') as file:
                while file.readline().strip() != 'variable in tri.inp:':
                    continue
                file.readline()

                while True:
                    line = file.readline().strip()
                    if not line:
                        break

                    content = [sp.strip() for sp in line.split(' ') if sp.strip()]
                    if not content:
                        continue

                    variable = sub(r'[^\w]', '', content[0])

                    data_type: type = str
                    try:
                        if content[1] in ['.true.', '.false.']:
                            data_type = bool

                        float(content[1])
                        data_type = float

                        int(content[1])
                        data_type = int
                    except (ValueError, IndexError):
                        pass

                    self.InputParameters.update({variable: data_type})

        except FileNotFoundError:
            logging.info(f'Could not open input variable documentation "{input_variables_doc}"!')
            pass

        # TODO: update available crystals
        if version == Versions.V_702:
            crystal_table = folder / 'tables' / 'table.crystal'
            try:
                lines = readlines(crystal_table, 'r', comments=['', '!'], encoding='utf-8', errors='replace')
                no_crystal_structures = int(lines[0].split()[0])
                crystal_structures = []
                j = 1
                for _ in range(no_crystal_structures):
                    no_coords = int(lines[j].split()[1])
                    coords = []
                    for i in range(no_coords):
                        coords.append(Coordinate([float(coord) for coord in lines[j + i].split()[:3]]))
                    crystal_structures.append(coords)

            except (FileNotFoundError, ValueError, IndexError):
                logging.info(f'Could not open or read crystal table "{crystal_table}"!')

    def updateElements(self, folder: Path, version: str) -> bool:
        """
        Updates list of <Element> for this simulation

        :param folder: main folder of simulation
        :param version: version of simulation
        """

        element_list: List[Element] = []
        table_path = folder / 'tables' / 'table1'

        try:
            # get table contents
            table_str = []
            with open(table_path, 'r', encoding='utf-8', errors='replace') as file:
                for line in file.readlines():
                    line = line.strip()

                    # skip commented lines
                    if not len(line) or line[0] == '!':
                        continue

                    # stop after element list
                    if line[0] == '-':
                        break

                    table_str.append(line)

            # no data in table
            if not table_str:
                super().loadDefaultElements(version)
                return False

            # divide table where a continuous column of whitespaces exists
            table: List[List[str]] = []
            divisions = []
            i = 0

            while True:
                break_flag = True
                division_flag = True

                for t in table_str:
                    if len(t) - 2 < i:
                        continue
                    break_flag = False
                    if t[i] != ' ' and t[i + 1] != ' ':
                        division_flag = False
                        break

                if break_flag:
                    break
                elif division_flag:
                    divisions.append(i)
                i += 1

            for i in range(len(divisions) - 1, 0, -1):
                if divisions[i] - 1 == divisions[i - 1]:
                    divisions.pop(i)
            divisions = [d + 1 for d in divisions]

            for t_str in table_str:
                columns = [t_str[:divisions[0]].strip()]
                for i in range(len(divisions) - 1):
                    columns.append(t_str[divisions[i]:divisions[i + 1]].strip())
                columns.append(t_str[divisions[-1]:].strip())
                table.append(columns)

            last_atomic_nr = 0
            group = 0
            period = 1
            period_increase = [3, 11, 19, 37, 55, 87]
            for element in table:

                symbol = element[0]
                atomic_nr = intSafe(element[1])

                # skip the weird elements
                if atomic_nr > last_atomic_nr + 1:
                    continue

                # some SDTrimSP versions contain bugs (e.g. v6.01, v6,06)
                # Francium is missing a decimal point in its vaporization energy
                if symbol == 'Fr' and len(divisions) == 17:
                    element[10] = '.'.join(element[10].split(' '))
                # Polonium and Astatine are missing a decimal point in their formation enthalpy
                elif symbol in ['Po', 'At'] and len(divisions) == 17:
                    element[11] = '.'.join(element[11].split(' '))

                name = element[-1]

                # build a nice name for versions 6.05 onward
                if '_' in name:
                    parts = name.split('_')
                    info = ' '.join(parts[2:])
                    if info:
                        info = f' ({info})'
                        parts[0] += info
                        parts[1] += info

                    name = f'{parts[0]}/{parts[1]}'

                name_en = name.lower()
                name_de = name.capitalize()

                name_list = name.split('/')
                if len(name_list) > 1:
                    name_en = name_list[1]
                    name_de = name_list[0].capitalize()

                names = {
                    'en': name_en,
                    'de': name_de
                }

                if atomic_nr != last_atomic_nr:
                    group += 1
                if atomic_nr in period_increase:
                    period += 1
                    group = 1

                # H -> He
                if atomic_nr == 2:
                    group = 18

                # Be/Mg -> B/Al
                elif atomic_nr in [5, 13]:
                    group = 13

                # show Lantha/Acti two rows down
                elif atomic_nr in [57, 89]:
                    period += 2

                # go back up after Lantha/Acti
                elif atomic_nr in [71, 103]:
                    period -= 2
                    group = 3

                last_atomic_nr = atomic_nr

                periodic_table_symbol = element[0].split('_')[0][:2]
                # charge = element[1]
                atomic_mass = floatSafe(element[2])
                atomic_density = floatSafe(element[4])

                energy_surfb = floatSafe(element[5])
                energy_disp = floatSafe(element[6])

                new_element = Element(
                    symbol=symbol,
                    name=names,
                    atomic_nr=atomic_nr,
                    period=period,
                    group=group,
                    atomic_mass=atomic_mass,
                    atomic_density=atomic_density,
                    surface_binding_energy=energy_surfb,
                    displacement_energy=energy_disp,
                    periodic_table_symbol=periodic_table_symbol
                )

                # Since He3 appears first, add He before it
                if symbol == 'He':
                    element_list.insert(-1, new_element)
                else:
                    element_list.append(new_element)

        except FileNotFoundError:
            logging.info(f'Could not open file "{table_path}"!')
            pass

        if not element_list:
            super().loadDefaultElements(version)
            return False

        self.element_data_default = False
        return self.element_data.updateElements(element_list)

    def makeInputFile(self, arguments: SimulationArguments, folder: Path, version: str) -> str:
        """
        Returns input file as string

        :param arguments: <SimulationArguments> container
        :param folder: folder of simulation
        :param version: version of simulation
        """

        default_values = DefaultValues(version)
        dict_lookup = DictLookup(version)

        group_elements = arguments.settings.get('group_elements')
        if not isinstance(group_elements, bool):
            group_elements = default_values.group_elements

        grouped_rows: List[list] = []  # pairs of beam row and target row (one of them can be None)
        if group_elements:
            beam_rows = sorted([row for row in arguments.beam_rows if row.symbol])
            target_rows = sorted([row for row in arguments.target_rows if row.symbol])
            used_beam_rows = []

            for target_row in target_rows:
                for beam_row in beam_rows:
                    if beam_row.symbol == target_row.symbol:
                        grouped_rows.append([beam_row, target_row])
                        used_beam_rows.append(beam_row)
                        break
                else:
                    grouped_rows.append([None, target_row])

            for beam_row in beam_rows:
                if beam_row not in used_beam_rows:
                    grouped_rows.append([beam_row, None])

        rows = arguments.beam_rows + arguments.target_rows
        rows = [row for row in rows if row.symbol]
        rows = sorted(rows)
        mask_beam = [1 if row in arguments.beam_rows else 0 for row in rows]

        abundances = [round(row.abundance, 2) for row in rows]

        if group_elements:
            elements = []
            original_elements = []
            for beam_row, target_row in grouped_rows:
                if beam_row is None:
                    elements.append(target_row.element)
                    original_elements.append(target_row.element.getOriginal())
                else:
                    elements.append(beam_row.element)
                    original_elements.append(beam_row.element.getOriginal())
        else:
            elements = [row.element for row in rows]
            original_elements = [row.element if not row.element.modified else row.element.getOriginal() for row in rows]
        changed_elements = any(element.modified for element in elements)

        # --- elements ---

        # SDTrimSP reads the title with format A80, in sweeps it appends the energy or angle (e.g. " e=" with f10.0),
        # longer titles stop the simulation
        sweep_modes = ArgumentValues.KineticEnergy.SWEEP, ArgumentValues.Angle.SWEEP
        is_sweep = arguments.beam_args.kinetic_energy_mode in sweep_modes or arguments.beam_args.angle_mode in sweep_modes
        title = arguments.settings.title[:65 if is_sweep else 80].rstrip()

        if group_elements:
            ncp = len(grouped_rows)
        else:
            ncp = len(rows)

        if group_elements:
            symbol = []
            for beam_row, target_row in grouped_rows:
                if beam_row is None:
                    symbol.append(target_row.symbol)
                else:
                    symbol.append(beam_row.symbol)
            symbol = ', '.join(f'"{sym}"' for sym in symbol)
        else:
            symbol = ', '.join([f'"{row.symbol}"' for row in rows])

        global_density = arguments.target_args.get('global_density')
        global_density = 'False, 0.0' if global_density is (None or False) else f'True, {global_density}'

        inel0 = arguments.settings.get('inelastic_loss_model')
        if inel0 is not None:
            inel0 = dict_lookup.inel0.get(inel0)
            if inel0 is None:
                inel0 = default_values.inel0
            inel0 = ', '.join([str(inel0)] * ncp)
        else:
            if group_elements:
                inel0 = []
                for beam_row, target_row in grouped_rows:
                    if beam_row is None:
                        inel0_i = target_row.get('inelastic_loss_model')
                    else:
                        inel0_i = beam_row.get('inelastic_loss_model')
                    if inel0_i is None:
                        inel0_i = default_values.inel0
                    inel0.append(inel0_i)
            else:
                inel0 = [row.get('inelastic_loss_model') for row in rows]
                inel0 = [i if i is not None else default_values.inel0 for i in inel0]

            inel0 = [dict_lookup.inel0.get(i) for i in inel0]
            inel0 = [str(i) if i is not None else str(default_values.inel0) for i in inel0]
            inel0 = ', '.join(inel0)

        e_surfb = []
        e_surfb_modified = False
        e_displ = []
        e_displ_modified = False
        dns0 = []
        dns0_modified = False
        a_mass = []
        a_mass_modified = False
        if changed_elements:
            for element, original_element in zip(elements, original_elements):
                e_surfb.append(element.surface_binding_energy)
                if element.surface_binding_energy != notNone(original_element).surface_binding_energy:
                    e_surfb_modified = True

                e_displ.append(element.displacement_energy)
                if element.displacement_energy != notNone(original_element).displacement_energy:
                    e_displ_modified = True

                dns0.append(element.atomic_density)
                if element.atomic_density != notNone(original_element).atomic_density:
                    dns0_modified = True

                a_mass.append(element.atomic_mass)
                if element.atomic_mass != notNone(original_element).atomic_mass:
                    a_mass_modified = True

        e_surfb = [f'{e}' for e in e_surfb]
        e_displ = [f'{e}' for e in e_displ]
        dns0 = [f'{e}' for e in dns0]
        a_mass = [f'{e}' for e in a_mass]

        def speciesValues(key: str, default, beam_only: bool = False) -> list:
            """Returns the value of a row parameter for all species (in the order of symbol)"""

            values = []
            if group_elements:
                for beam_row_i, target_row_i in grouped_rows:
                    row_i = beam_row_i if (beam_only or target_row_i is None) else target_row_i
                    value_i = row_i.get(key) if row_i is not None else None
                    values.append(default if value_i is None else value_i)
            else:
                for row_i in rows:
                    value_i = row_i.get(key) if (not beam_only or row_i in arguments.beam_rows) else None
                    values.append(default if value_i is None else value_i)
            return values

        # further parameters of the species, only written if they differ from the defaults
        species_settings = ''
        species_parameters = [
            ('beta0', 'azimuth', default_values.beta0, True, default_values.supports_beta0),
            ('x0', 'start_depth', default_values.x0, True, default_values.supports_x0),
            ('charge', 'charge', default_values.charge, True, True),
            ('e_cutoff', 'cutoff_energy', default_values.e_cutoff, False, True),
            ('e_bulkb', 'bulk_binding_energy', default_values.e_bulkb, False, True),
            ('deltahf', 'heat_of_formation', default_values.deltahf, False, default_values.supports_deltahf),
            ('isot', 'isotopes', default_values.isot, False, True),
        ]
        for name, key, default, beam_only, supported in species_parameters:
            values = speciesValues(key, default, beam_only)
            if supported and any(value != default for value in values):
                species_settings += f'    {name} = ' + ', '.join(f'{value}' for value in values) + '\n'

        # correction of the inelastic energy loss of species i (moving particle) in all species j: ck_elec(i, j)
        ck_elec = speciesValues('inelastic_correction', default_values.ck_elec)
        if any(value != default_values.ck_elec for value in ck_elec):
            # column major order of the matrix ck_elec(ncp, ncp)
            species_settings += '    ck_elec = ' + ', '.join(f'{ck_elec[i]}' for _ in ck_elec for i in range(len(ck_elec))) + '\n'

        modifications = ''
        if e_surfb_modified:
            modifications += '    e_surfb = ' + ', '.join(e_surfb) + '\n'
        if e_displ_modified:
            modifications += '    e_displ = ' + ', '.join(e_displ) + '\n'
        if dns0_modified:
            modifications += '    dns0 = ' + ', '.join(dns0) + '\n'
        if a_mass_modified:
            modifications += '    a_mass = ' + ', '.join(a_mass) + '\n'

        # --- general ---
        idrel = arguments.settings.mode
        idrel = dict_lookup.idrel.get(idrel)
        if idrel is None:
            idrel = default_values.idrel

        flc = arguments.settings.fluence

        nh = arguments.settings.get('histories')
        if nh is None:
            nh = default_values.nh

        idout = arguments.settings.get('histories_between_out')
        if idout is None:
            idout = default_values.idout

        nr_pproj = arguments.settings.get('projectiles')
        if nr_pproj is None:
            nr_pproj = default_values.nr_pproj

        ipot = arguments.settings.get('interaction_potential')
        if ipot is not None:
            ipot = dict_lookup.ipot.get(ipot)
        if ipot is None:
            ipot = default_values.ipot

        iintegral = arguments.settings.get('integration_method')
        if iintegral is not None:
            iintegral = dict_lookup.iintegral.get(iintegral)
        if iintegral is None:
            iintegral = default_values.iintegral

        isbv = arguments.settings.get('surface_binding_model')
        if isbv is not None:
            isbv = dict_lookup.isbv.get(isbv)
        if isbv is None:
            isbv = default_values.isbv

        # --- beam ---

        if group_elements:
            qubeam = [round(beam_row.abundance, 2) if beam_row is not None else 0.0 for beam_row, _ in grouped_rows]
        else:
            qubeam = [round(a, 2) if m == 1 else 0.0 for a, m in zip(abundances, mask_beam)]
        qubeam = normalizeList(qubeam)

        kinetic_energy_mode = arguments.beam_args.kinetic_energy_mode
        case_e0 = dict_lookup.case_e0.get(kinetic_energy_mode) if kinetic_energy_mode is not None else None
        if case_e0 is None:
            case_e0 = default_values.case_e0

        if group_elements:
            e0 = [beam_row.energy if beam_row is not None else 0.0 for beam_row, _ in grouped_rows]
        else:
            e0 = [row.energy for row in rows]

        angle_mode = arguments.beam_args.angle_mode
        case_alpha = dict_lookup.case_alpha.get(angle_mode) if angle_mode is not None else None
        if case_alpha is None:
            case_alpha = default_values.case_alpha

        if group_elements:
            alpha0 = [beam_row.angle if beam_row is not None else 0.0 for beam_row, _ in grouped_rows]
        else:
            alpha0 = [row.angle for row in rows]

        number_calc = arguments.beam_args.get('sweep')
        if number_calc is None:
            number_calc = default_values.number_calc
        if case_e0 != dict_lookup.case_e0.get(ArgumentValues.KineticEnergy.SWEEP) and case_alpha != dict_lookup.case_alpha.get(ArgumentValues.Angle.SWEEP):
            number_calc = ''
        else:
            number_calc = f'    number_calc = {number_calc}\n'

        # --- target ---

        # iq0 < 0: composition from layer.inp (-2 has a special meaning for chemical erosion, so the loaded value is kept)
        iq0 = 0
        if len(arguments.structure) > 1 or usesCrystalLayerFile(arguments, version):
            iq0 = arguments.target_args.get('layer_file_flag', -1)
            if not isinstance(iq0, int) or iq0 >= 0:
                iq0 = -1

        if group_elements:
            qu = [1.0 if target_row is not None else 0.0 for _, target_row in grouped_rows]
        else:
            qu = [1.0 - m for m in mask_beam]

        if iq0 == 0 and arguments.structure and len(arguments.structure[0].abundances) == sum(qu):
            j = 0
            abundance_list = arguments.structure[0].abundances
            for i, q in enumerate(qu):
                if q == 1:
                    qu[i] = abundance_list[j]
                    j += 1

        # with a layer file the loaded values of qu are kept, if the species did not change
        layer_file_qu = arguments.target_args.get('layer_file_qu')
        if iq0 < 0 and isinstance(layer_file_qu, dict):
            if group_elements:
                species = [(target_row or beam_row).symbol for beam_row, target_row in grouped_rows]
            else:
                species = [row.symbol for row in rows]
            target_species = {symbol for symbol, q in zip(species, qu) if q}
            if target_species and {symbol for symbol, q in layer_file_qu.items() if q} <= target_species:
                qu = [float(layer_file_qu.get(symbol, 0.)) if q else 0. for symbol, q in zip(species, qu)]
                if sum(qu) <= 0:
                    qu = [1.0 if symbol in target_species else 0. for symbol in species]

        qu = normalizeList(qu)

        if group_elements:
            # synced field: defined in the target table if the element is in the beam and the target (the beam row can
            # have qumax = 0 from a tri.inp with separate projectile and target species, SDTrimSP stops then)
            qumax = []
            for beam_row, target_row in grouped_rows:
                if target_row is None:
                    qumax.append(beam_row.max_atomic_fraction)
                else:
                    qumax.append(target_row.max_atomic_fraction)
        else:
            qumax = [row.max_atomic_fraction for row in rows]

        ttarget = arguments.target_args.thickness

        nqx = arguments.target_args.segments

        miller_ind = arguments.target_args.get('miller_ind')

        crystal_settings = ''
        crystal_flag = bool(arguments.target_args.get('crystal_flag', False))
        if self.default_values.enable_crystal and self.default_values.crystal_table:
            # since 7.02: crystal from tables/table.crystal (one crystal for the whole target)
            crystal_settings = '''
text = "--- crystal ---"
    l_crystal = .false.
'''
            crystal_args = arguments.crystal_args
            if crystal_flag and crystal_args is not None:
                crystals = tableCrystals(crystal_args)
                crystal_list = ''
                # with layer.inp the orientation of each layer is used, a polycrystal ((0 0 0)) is not possible: the orientation
                # of the first layer with the crystal is written
                layers = crystalLayers(arguments) if usesCrystalLayerFile(arguments, version) else []
                for i, crystal in enumerate(crystals, start=1):
                    crystal_miller = crystal['miller']
                    if layers and all(float(m) == 0 for m in crystal_miller):
                        crystal_miller = next(
                            (layer['miller'] for layer in layers if len(layer['fractions']) >= i and layer['fractions'][i - 1] > 0),
                            [1, 0, 0]
                        )
                    miller = ', '.join(f'{float(m):g}' for m in crystal_miller)
                    crystal_list += f'''
    name_cryst{i} = '{crystal['name']}'
    miller_ind{i} = {miller}'''
                crystal_settings = f'''
text = "--- crystal ---"
    l_crystal = .true.
    l_crystal_dyn = .{str(bool(crystal_args.get('crystal_dyn', False))).lower()}.
    l_crystal{len(crystals)} = .true.{crystal_list}
    dy_crystal_beam = {float(crystal_args.get('beam_dy', 0) or 0)}
    dz_crystal_beam = {float(crystal_args.get('beam_dz', 0) or 0)}
'''
        elif self.default_values.enable_crystal:
            crystal_settings = f'''
text = "--- crystal ---"
    l_crystal = .{str(crystal_flag).lower()}.
    miller_ind = {miller_ind.crystal_inp_str()}
'''

        # two-compound options
        cmpd = []
        comp_output = ''

        if arguments.settings.compounds:
            for compound in arguments.settings.compounds:
                cmpd.append(compound.name_save)

        cmpd_limit = 3
        if 0 < len(cmpd) <= cmpd_limit:
            comp_output = f'''
text = "--- compound ---"
    l_two_comp{len(cmpd) if len(cmpd) > 1 else ''} = .true.'''
            for i, c in enumerate(cmpd):
                comp_output += f'''
    two_comp{i + 1 if i > 0 else ''} = "{c}"'''
            comp_output += '\n'

        elif len(cmpd) > cmpd_limit:
            comp_output = '\ntext = "--- compound not more than 3 possible ---"\n'

        # --- output options ---
        lparticle_p = arguments.settings.get('log_reflected')
        if not isinstance(lparticle_p, bool):
            lparticle_p = default_values.lparticle_p
        lparticle_p_str = f'.{str(lparticle_p).lower()}.'
        if lparticle_p:
            lparticle_p_str += f'''
    ioutput_part(2) = {nh * nr_pproj}'''

        lparticle_r = arguments.settings.get('log_sputtered')
        if not isinstance(lparticle_r, bool):
            lparticle_r = default_values.lparticle_r
        lparticle_r_str = f'.{str(lparticle_r).lower()}.'
        if lparticle_r:
            lparticle_r_str += f'''
    ioutput_part(5) = {nh * nr_pproj * 100}'''

        lmatrices = arguments.settings.get('log_matrix')
        if not isinstance(lmatrices, bool):
            lmatrices = default_values.lmatrices

        # further settings, only written if they differ from the defaults
        extra_settings = ''
        if arguments.settings.get('trajectories_projectiles'):
            extra_settings += '\n    ltraj_p = .true.'
        if arguments.settings.get('trajectories_recoils'):
            extra_settings += '\n    ltraj_r = .true.'
        if arguments.settings.get('trajectories_projectiles') or arguments.settings.get('trajectories_recoils'):
            numb_hist = arguments.settings.get('trajectories_number')
            extra_settings += f'\n    numb_hist = {numb_hist if isinstance(numb_hist, int) else default_values.numb_hist}'
        if arguments.settings.get('energy_distribution'):
            grid = arguments.settings.get('distribution_grid')
            if not isinstance(grid, list) or len(grid) != 4:
                grid = [default_values.dist_nx, default_values.dist_ny, default_values.dist_nz, default_values.dist_delta]
            extra_settings += f'\n    lenergy_distr = .true.\n    dist_nx = {int(grid[0])}\n    dist_ny = {int(grid[1])}\n    dist_nz = {int(grid[2])}\n    dist_delta = {float(grid[3])}'
        irand = arguments.settings.get('random_seed')
        if isinstance(irand, int) and irand != default_values.irand:
            extra_settings += f'\n    irand = {irand}'
        if arguments.settings.get('inelastic_outside') and default_values.supports_sfin:
            extra_settings += '\n    sfin = 1'
        shth = arguments.beam_args.get('sheath_potential')
        if isinstance(shth, (int, float)) and shth > 0:
            extra_settings += f'\n    shth = {float(shth)}'

        # file of tabulated stopping power (since 7.07)
        tbsp_settings = ''
        if default_values.tbsp_file_selection:
            tbsp_ascii = arguments.settings.get('tbsp_format') == 'ascii'
            tbsp_settings = f'''
    tbsp_binary = .{str(not tbsp_ascii).lower()}.
    tbsp_ascii = .{str(tbsp_ascii).lower()}.'''

        # --- extra ---

        tableinp = pathToStr(folder / 'tables')
        additional = '\n    '.join(arguments.additional)
        out = f'''
{title}
&TRI_INP
text = "--- elements ---"
    ncp = {ncp}
    symbol = {symbol}
    !globaldensity = {global_density}
    inel0 = {inel0}
{modifications}{species_settings}
text = "--- general ---"
    idrel = {idrel}
    flc = {flc}
    nh = {nh}
    idout = {idout}
    nr_pproj = {nr_pproj}
    ipot = {ipot}
    iintegral = {iintegral}
    isbv = {isbv}

text = "--- beam ---"
    qubeam = {joinValues(qubeam)}
    case_e0 = {case_e0}
    e0 = {joinValues(e0)}
    case_alpha = {case_alpha}
    alpha0 = {joinValues(alpha0)}
{number_calc}
text = "--- target ---"
    qu = {joinValues(qu)}
    qumax = {joinValues(qumax)}
    ttarget = {ttarget}
    nqx = {nqx}
    iq0 = {iq0}
{comp_output}{crystal_settings}
text = "--- output options ---"
    lparticle_p = {lparticle_p_str}
    lparticle_r = {lparticle_r_str}
    lmatrices = .{str(lmatrices).lower()}.{tbsp_settings}{extra_settings}

text = "--- extra ---"
    tableinp = "{tableinp}"
    {additional}
/
'''
        return f'{out.strip()}\n'

    def exactVersion(self) -> Optional[float]:
        """Returns the version number of the simulation folder (e.g. 7.02) or None if unknown"""

        folder = getattr(self, 'simulation_folder', None)
        name = self.getVersionName(folder, None) if folder is not None else ''
        numbers = findall(r'\d+\.\d+', name) if isinstance(name, str) else []
        return float(numbers[0]) if numbers else None

    def supportsEnergyAngleFile(self, version: str) -> bool:
        """
        Returns True if the distribution of energies and angles from ene_ang.inp (case_e0 = 6) is implemented:
        until 6.09 and since 7.05 (7.02 shares the settings with 7.05, therefore the version of the folder is checked)

        :param version: version of simulation
        """

        if not DefaultValues(version).supports_energy_angle_file:
            return False
        if version == Versions.V_702:
            exact = self.exactVersion()
            return exact is None or exact >= 7.05
        return True

    def legacyEnergyAngleFormat(self, version: str) -> bool:
        """
        Returns True if ene_ang.inp has the format until 7.02 (the format changed with 7.05).
        7.02 and 7.05 share the settings, therefore the version of the simulation folder is checked

        :param version: version of simulation
        """

        if not Versions.atLeast(version, Versions.V_702):
            return True
        if version != Versions.V_702:
            return False
        exact = self.exactVersion()
        return exact is not None and exact < 7.05

    def makeDistributionFiles(self, arguments: SimulationArguments, version: str) -> Dict[str, str]:
        """
        Returns the files of the distributions of energies and angles (energy.inp, angle.inp, ene_ang.inp) as {file name: content}

        :param arguments: <SimulationArguments> container
        :param version: version of simulation
        """

        group_elements = arguments.settings.get('group_elements')
        if not isinstance(group_elements, bool):
            group_elements = DefaultValues(version).group_elements
        distributions = arguments.beam_args.get('distributions')
        if not isinstance(distributions, dict):
            distributions = {}

        files = {}
        names = distributionFileNames(arguments, version, group_elements)
        for symbol, name in names['energy']:
            rows = distributions.get('energy', {}).get(symbol)
            if rows:
                files[name] = writeDistributionFile(rows, f'! E [eV] distribution [-/dE] ({symbol}, created with BCA-GUIDE)')
        for symbol, name in names['angle']:
            rows = distributions.get('angle', {}).get(symbol)
            if rows is None and symbol == 'all':
                rows = next(iter(distributions.get('angle', {}).values()), None)
            if rows:
                files[name] = writeDistributionFile(rows, f'! alpha [degree] distribution [-/dalpha] ({symbol}, created with BCA-GUIDE)')
        for _, name in names['energy_angle']:
            data = distributions.get('energy_angle')
            if data:
                files[name] = writeEnergyAngleFile(data, legacy=self.legacyEnergyAngleFormat(version))
        return files

    @staticmethod
    def makeLayerFile(arguments: SimulationArguments, folder: Path, version: str) -> str:
        """
        Returns layer input file as string

        :param arguments: <SimulationArguments> container
        :param folder: folder of simulation
        :param version: version of simulation
        """

        structures = arguments.structure
        crystal_layer_file = usesCrystalLayerFile(arguments, version)
        if len(structures) < 2 and not crystal_layer_file:
            return ''

        default_values = DefaultValues(version)

        # crystals from table.crystal: additional columns for the atomic fractions of the crystal species and the miller index
        crystal_species = []
        crystal_layers = []
        if crystal_layer_file:
            try:
                table = CrystalTableFile(folder / 'tables' / 'table.crystal', CrystalTableLimits(version))
            except CrystalTableError:
                table = None
            for k, crystal in enumerate(tableCrystals(arguments.crystal_args), start=1):
                table_crystal = table.crystal(crystal['name']) if table is not None else None
                if table_crystal is None:
                    continue
                for element, count in table_crystal.composition().items():
                    crystal_species.append((k - 1, f'{element}_{k}', count / len(table_crystal.elements)))
            crystal_layers = crystalLayers(arguments)

        group_elements = arguments.settings.get('group_elements')
        if not isinstance(group_elements, bool):
            group_elements = default_values.group_elements

        grouped_rows: List[list] = []  # pairs of beam row and target row (one of them can be None)
        if group_elements:
            beam_rows = sorted([row for row in arguments.beam_rows if row.symbol])
            target_rows = sorted([row for row in arguments.target_rows if row.symbol])
            used_beam_rows = []

            for target_row in target_rows:
                for beam_row in beam_rows:
                    if beam_row.symbol == target_row.symbol:
                        grouped_rows.append([beam_row, target_row])
                        used_beam_rows.append(beam_row)
                        break
                else:
                    grouped_rows.append([None, target_row])

            for beam_row in beam_rows:
                if beam_row not in used_beam_rows:
                    grouped_rows.append([beam_row, None])

        rows = arguments.beam_rows + arguments.target_rows
        rows = [row for row in rows if row.symbol]
        rows = sorted(rows)

        if group_elements:
            rows_len = len(grouped_rows)
            mask_target = [1 if target_row is not None else 0 for _, target_row in grouped_rows]
        else:
            rows_len = len(rows)
            mask_target = [0 if row in arguments.beam_rows else 1 for row in rows]

        abundances = rows_len - 1
        layer_info_total = []
        for layer_index, structure in enumerate(structures):
            if structure.segments == 0:
                continue
            layer_info = f'{structure.segments:>6} {structure.thickness / structure.segments:>12.5E}  '
            abundance_list = [0.0] * rows_len
            if arguments.structure and len(arguments.structure[0].abundances) == sum(mask_target):
                j = 0
                for i, m in enumerate(mask_target):
                    if m == 1:
                        abundance_list[i] = structure.abundances[j]
                        j += 1

            if crystal_layer_file:
                # amorphous part of the layer and crystal species (stoichiometric fractions of the crystal)
                fractions = crystal_layers[layer_index]['fractions']
                amorphous = max(0., 1 - sum(fractions))
                abundance_list = [abundance * amorphous for abundance in abundance_list]
                abundance_list += [fractions[k] * stoichiometry for k, _, stoichiometry in crystal_species]
                layer_info += '  '.join([f'{abundance:>13.5E}' for abundance in abundance_list[1:]])
                # SDTrimSP checks the miller index of all layers, amorphous layers get [1, 0, 0]
                miller = crystal_layers[layer_index]['miller'] if sum(fractions) > 0 else [1, 0, 0]
                layer_info += '   ' + '  '.join(f'{float(m):5.2f}' for m in miller)
            else:
                layer_info += '  '.join([f'{abundance:>13.5E}' for abundance in abundance_list[1:]])
            layer_info += f'    {structure.name}'
            layer_info_total.append(layer_info)
        layer_info_total = '\n'.join(layer_info_total)

        if crystal_layer_file:
            labels = [f'qu_{i + 2}' for i in range(abundances)] + [name for _, name, _ in crystal_species]
            out = f'''
! number of    thick-    target composition 2...ncp (crystal species: element_crystal)    miller index    name of layer
! layers       ness      {'           '.join(labels)}    h  k  l
{layer_info_total}
     0            0    {'    '.join(['          0' for _ in labels])}    0  0  0    end
'''
            return f'{out.strip()}\n'

        # since 7.07 both header lines must start with "!" or "#"
        out = f'''
! number of    thick-    target composition 2...ncp    name of layer
! layers       ness      {'           '.join([f'qu_{i + 2}' for i in range(abundances)])}
{layer_info_total}
     0            0    {'    '.join(['          0' for _ in range(abundances)])}    end
'''
        return f'{out.strip()}\n'

    @staticmethod
    def makeCrystalFile(arguments: SimulationArguments, folder: Path, version: str) -> str:
        """
        Returns input file as string

        :param arguments: <SimulationArguments> container
        :param folder: folder of simulation
        :param version: version of simulation
        """

        title = arguments.settings.title
        crystal = arguments.crystal_args
        if not crystal:
            return ''

        # since 7.02 crystals are defined in tables/table.crystal, there is no crystal.inp
        if DefaultValues(version).crystal_table:
            return ''

        name = crystal.name
        lattice_id = crystal.lattice_id

        a1 = crystal.basis_vec_a1
        a2 = crystal.basis_vec_a2
        a3 = crystal.basis_vec_a3

        miller_ind = crystal.miller_ind

        lattice_constant = crystal.get('lattice_constant')
        p_max = crystal.get('p_max')
        beam_dy = crystal.get('beam_dy')
        beam_dz = crystal.get('beam_dz')
        matrix_id = crystal.get('matrix_id')
        crystal_rows = arguments.crystal_rows
        if not crystal_rows:
            number_of_atoms = 0
        else:
            number_of_atoms = len(crystal_rows)

        species = []
        if crystal_rows:
            coordinate_str = ''
            for crystal_row in crystal_rows:
                element = crystal_row.symbol
                if element not in species:
                    species.append(element)
                coordinate_str += f'{crystal_row.coord.crystal_inp_str()} {(species.index(element) + 1)} x,y,z Number of species\n'
            coordinate_str.strip()
        else:
            coordinate_str = 'No coordinates defined'

        species_str = 'No elements in species list'
        if species:
            species_str = ''
            for element in species:
                species_str += f'"{element}"\n'
            species_str.strip()

        if not arguments.target_args.get('crystal_flag'):
            return ''

        out = f'''
#{title}
#&Crystal_INP
# name of Cristal(surface: dy,dz) (text)
# lattice_id (integer)
# number of spezies (integer)
# species_1 (element name: character, len(2))
# species_2 (element name: character, len(2))
# a1 : first basis vector of lattice cell (x1,y1,z1) :real, dimension(3)
# a2 : second basis vector of lattice cell (x2,y2,z2):real, dimension(3)
# a3 : third basis vector of lattice cell (x3,y3,z3) :real, dimension(3)
# number of atoms (integer)
# x(depth), y(back), z(right) position and number(=type) of species : real, dimension(3), integer
# p_max of crystal if known (default 0.0)
# dy_beam dz_beam  surface of beam
# matrix_id 3x3x3 ...3 
# matrix_id 5x5x5 ...5
# miller_ind = {miller_ind}
# lattice_constant = {lattice_constant}
#--------------------------------------------
        
{name}                  name
{lattice_id}            lattice_id
{len(species)}          number of species
{species_str}
{a1[0] * lattice_constant} {a1[1] * lattice_constant} {a1[2] * lattice_constant}    a1: dx, dy, dz [Å]
{a2[0] * lattice_constant} {a2[1] * lattice_constant} {a2[2] * lattice_constant}    a2: dx, dy, dz [Å]
{a3[0] * lattice_constant} {a3[1] * lattice_constant} {a3[2] * lattice_constant}    a3: dx, dy, dz [Å]
{number_of_atoms}           number of atoms in cell
{coordinate_str} 
{p_max}                 p_max (Impact parameter)
{beam_dy} {beam_dz}     surface of beam ( beam_dy beam_dz)
{matrix_id}             matrix_id = 5 => 5x5x5 , matrix_id = 3 => 3x3x3
'''

        return f'{out.strip()}\\n'

    def loadFiles(self, folder: Path, version: str) -> Union[Tuple[SimulationArguments, list], str, Literal[False]]:
        """
        Returns Tuple of <SimulationArguments> container if it can load input files from folder and list of errors while loading
        Returns string of error if input file can not be opened
        Returns False if not implemented

        :param folder: folder of input files
        :param version: version of simulation

        :return: Tuple(<SimulationArguments>, list), str or False
        """

        default_values = DefaultValues(version)
        dict_lookup = DictLookup(version)

        input_file = folder / self.InputFilename
        layer_file = folder / self.LayerFilename
        crystal_file = folder / self.CrystalFilename

        contents = DeleteDict()

        # get all contents from input file
        try:
            with open(input_file, 'r', encoding='utf-8', errors='replace') as file:
                contents['title'] = file.readline().strip()
                for line in file.readlines():
                    line = line.strip()

                    # strip off comments
                    comment_positions = [line.index(c) for c in ['!', '#'] if c in line]
                    comment_offset = min(comment_positions) if comment_positions else -1
                    if comment_offset > 0:
                        line = line[:comment_offset]

                    # split into key and value
                    content = [p.strip() for p in line.split('=')]
                    if len(content) != 2 or content[0] == 'text':
                        continue
                    contents[content[0]] = content[1]

        except FileNotFoundError:
            logging.info(f'Could not open file "{input_file}"!')
            return False

        assumed = DefaultAssumed()
        error_list = []

        def getValue(value: str, value_type: type, default_value, item=None, assumed_cls: Optional[DefaultAssumed] = None):
            """Returns value if value has type value_type, otherwise return default_value"""

            if assumed_cls is None:
                assumed_cls = DefaultAssumed()
            # a single value may end with a separator in Fortran namelists (e.g. "ncp = 2,")
            if isinstance(value, str) and value_type is not str:
                value = value.strip().rstrip(',').strip()
            try:
                value = value_type(value)
                return value
            except (ValueError, TypeError):
                if item is not None:
                    assumed_cls.assumed(item)
                return default_value

        def getValueBool(value: str, default_value) -> bool:
            """Returns a boolean representation of the value, or default value if it can not be converted"""

            if not isinstance(value, str):
                return default_value
            return 'true' in value

        def getValueBoolInt(value: str) -> Union[bool, float]:
            """Returns the integer of value or False"""

            if value is None:
                return False
            if 'False' in value:
                return False
            try:
                return float(value.split(',')[1].strip())
            except ValueError:
                return False

        def getValueDict(value: str, lookup_dict: dict, default_value, item=None, assumed_cls: Optional[DefaultAssumed] = None):
            """Returns class member with name value if is class member, otherwise return default_value"""

            if assumed_cls is None:
                assumed_cls = DefaultAssumed()
            try:
                return [k for k, v in lookup_dict.items() if v == int(value)][0]
            except (ValueError, IndexError, TypeError):
                if item is not None:
                    assumed_cls.assumed(item)
                return [k for k, v in lookup_dict.items() if v == default_value][0]

        def getValueList(value: str, value_type, default_value, item=None, lookup_dict=None, split_str: str = ',', assumed_cls: Optional[DefaultAssumed] = None) -> list:
            """Returns list of values converted to value_type. If conversion of list element is not successful, it is replaced by default_value"""

            if assumed_cls is None:
                assumed_cls = DefaultAssumed()
            if not isinstance(value, str):
                if item is not None:
                    assumed_cls.assumed(item)
                value = ''
            value = value.replace('\"', ' ').replace('\'', ' ')
            # the values of Fortran namelists are separated by commas and/or blanks (e.g. symbol = "C_g" "W")
            if split_str == ',':
                values = [part for part in split(r'[\s,]+', value.strip()) if part] or ['']
            else:
                values = value.split(split_str)
            values_out = []
            if lookup_dict is None:
                lookup_dict = {}
            for value in values:
                if isinstance(value_type, type):
                    try:
                        value = value_type(value.strip())
                    except ValueError:
                        if item is not None:
                            assumed_cls.assumed(item)
                        value = default_value
                # value_type() is a function
                else:
                    value = value_type(value.strip(), lookup_dict, default_value, item=item, assumed_cls=assumed_cls)

                values_out.append(value)
            return values_out

        # extract variables from contents dict
        title = getValue(contents.get('title'), str, f'SDTrimSP - {dateStr()}', 'title', assumed_cls=assumed)
        idrel = getValueDict(contents.get('idrel'), dict_lookup.idrel, default_values.idrel, 'mode', assumed_cls=assumed)
        flc = getValue(contents.get('flc'), float, default_values.flc, 'fluence', assumed_cls=assumed)
        nh = getValue(contents.get('nh'), int, default_values.nh, 'number_of_histories', assumed_cls=assumed)
        idout = getValue(contents.get('idout'), int, default_values.idout, 'histories_between_outputs', assumed_cls=assumed)
        nr_pproj = getValue(contents.get('nr_pproj'), int, default_values.nr_pproj, 'projectiles_per_history', assumed_cls=assumed)
        ipot = getValueDict(contents.get('ipot'), dict_lookup.ipot, default_values.ipot, 'interaction_potential', assumed_cls=assumed)
        iintegral = getValueDict(contents.get('iintegral'), dict_lookup.iintegral, default_values.iintegral, 'integration_method', assumed_cls=assumed)
        isbv = getValueDict(contents.get('isbv'), dict_lookup.isbv, default_values.isbv, 'surface_binding_model', assumed_cls=assumed)
        lparticle_p = getValueBool(contents.get('lparticle_p'), default_values.lparticle_p)
        lparticle_r = getValueBool(contents.get('lparticle_r'), default_values.lparticle_r)
        lmatrices = getValueBool(contents.get('lmatrices'), default_values.lmatrices)
        tbsp_format = default_values.tbsp_format
        if default_values.tbsp_file_selection:
            contents.get('tbsp_binary')
            if getValueBool(contents.get('tbsp_ascii'), False):
                tbsp_format = 'ascii'
        globaldensity = getValueBoolInt(contents.get('!globaldensity'))
        case_e0 = getValueDict(contents.get('case_e0'), dict_lookup.case_e0, default_values.case_e0, 'kinetic_energy_mode', assumed_cls=assumed)
        case_alpha = getValueDict(contents.get('case_alpha'), dict_lookup.case_alpha, default_values.case_alpha, 'angle_mode', assumed_cls=assumed)
        number_calc = int(getValue(contents.get('number_calc'), float, default_values.number_calc, 'sweeps', assumed_cls=assumed))
        iq0 = getValue(contents.get('iq0'), int, 0, 'composition_profile', assumed_cls=assumed)
        nqx = getValue(contents.get('nqx'), int, default_values.nqx, 'segments', assumed_cls=assumed)
        ttarget = getValue(contents.get('ttarget'), float, default_values.ttarget, 'thickness', assumed_cls=assumed)
        symbol = getValueList(contents.get('symbol'), str, 'H', 'symbol', assumed_cls=assumed)
        # without inel0 the default of SDTrimSP is used for each species (see defaultInelasticLossModel)
        inel0_text = contents.get('inel0')
        inel0 = getValueList(inel0_text, getValueDict, default_values.inel0, 'inelastic_loss_model', dict_lookup.inel0, assumed_cls=assumed) if isinstance(inel0_text, str) else []
        qubeam = getValueList(contents.get('qubeam'), float, default_values.qubeam, 'abundance', assumed_cls=assumed)
        qu_text = contents.get('qu')
        qu = getValueList(qu_text, float, default_values.qubeam, 'abundance', assumed_cls=assumed)
        qumax = getValueList(contents.get('qumax'), float, default_values.qumax, 'max_atomic_fraction', assumed_cls=assumed)
        e0 = getValueList(contents.get('e0'), float, default_values.e0, 'energy', assumed_cls=assumed)
        alpha0 = getValueList(contents.get('alpha0'), float, default_values.alpha0, 'angle', assumed_cls=assumed)
        ncp = getValue(contents.get('ncp'), int, -1, assumed_cls=assumed)
        e_surfb = getValueList(contents.get('e_surfb'), float, -1.0, assumed_cls=assumed)

        # further parameters of the species
        def optionalList(name: str, value_type, default) -> list:
            """Returns list of values of a parameter (empty if not given)"""
            value = contents.get(name)
            if not isinstance(value, str):
                return []
            return getValueList(value, value_type, default)

        beta0 = optionalList('beta0', float, default_values.beta0)
        x0 = optionalList('x0', float, default_values.x0)
        charge = optionalList('charge', float, default_values.charge)
        e_cutoff = optionalList('e_cutoff', float, default_values.e_cutoff)
        e_bulkb = optionalList('e_bulkb', float, default_values.e_bulkb)
        deltahf = optionalList('deltahf', float, default_values.deltahf)
        isot = optionalList('isot', SafeInt, default_values.isot)
        ck_elec_matrix = optionalList('ck_elec', float, default_values.ck_elec)

        # further settings
        ltraj_p = getValueBool(contents.get('ltraj_p'), default_values.ltraj_p)
        ltraj_r = getValueBool(contents.get('ltraj_r'), default_values.ltraj_r)
        numb_hist = getValue(contents.get('numb_hist'), SafeInt, default_values.numb_hist)
        lenergy_distr = getValueBool(contents.get('lenergy_distr'), default_values.lenergy_distr)
        distribution_grid = [
            getValue(contents.get('dist_nx'), SafeInt, default_values.dist_nx),
            getValue(contents.get('dist_ny'), SafeInt, default_values.dist_ny),
            getValue(contents.get('dist_nz'), SafeInt, default_values.dist_nz),
            getValue(contents.get('dist_delta'), float, default_values.dist_delta)
        ]
        irand = getValue(contents.get('irand'), SafeInt, default_values.irand)
        sfin = getValue(contents.get('sfin'), SafeInt, default_values.sfin)
        shth = getValue(contents.get('shth'), float, default_values.shth)
        e_displ = getValueList(contents.get('e_displ'), float, -1.0, assumed_cls=assumed)
        dns0 = getValueList(contents.get('dns0'), float, -1.0, assumed_cls=assumed)
        a_mass = getValueList(contents.get('a_mass'), float, -1.0, assumed_cls=assumed)

        miller_ind = None
        l_crystal = False

        if default_values.enable_crystal:
            l_crystal = getValueBool(contents.get('l_crystal'), default_values.l_crystal)

        table_crystal: Optional[Dict[str, Any]] = None
        if l_crystal and default_values.crystal_table:
            # since 7.02: up to three crystals from tables/table.crystal (l_crystal1, l_crystal2 or l_crystal3)
            crystal_count = 1
            for i in range(1, CrystalTableLimits.max_crystals + 1):
                if getValueBool(contents.get(f'l_crystal{i}'), False):
                    crystal_count = i
            crystals: List[Dict[str, Any]] = []
            for i in range(1, CrystalTableLimits.max_crystals + 1):
                name = str(contents.get(f'name_cryst{i}') or '').strip().strip('"\'')
                miller = getValueList(contents.get(f'miller_ind{i}'), float, 0, 'miller_indices_list' if i <= crystal_count else None, assumed_cls=assumed)
                if i <= crystal_count:
                    crystals.append({'name': name, 'miller': [SafeInt(m) if float(m).is_integer() else m for m in miller]})
            miller_ind = MillerIndex(list(crystals[0]['miller']))
            table_crystal = {
                'name': crystals[0]['name'],
                'crystals': crystals,
                'crystal_dyn': getValueBool(contents.get('l_crystal_dyn'), default_values.l_crystal_dyn),
                'beam_dy': getValue(contents.get('dy_crystal_beam'), float, default_values.beam_dy, 'beam_dy', assumed_cls=assumed),
                'beam_dz': getValue(contents.get('dz_crystal_beam'), float, default_values.beam_dz, 'beam_dz', assumed_cls=assumed),
            }
            if not table_crystal['name']:
                assumed.assumed('name')

        # 7.00 and 7.01: the GUI also writes miller_ind without crystal, it is no additional setting then
        elif l_crystal or (default_values.enable_crystal and not default_values.crystal_table and 'miller_ind' in contents):
            miller_ind = MillerIndex(getValueList(contents.get('miller_ind'), SafeInt, 0, 'miller_indices_list', assumed_cls=assumed))

        # tables of the simulation (needed for the crystals in the layer file), 'tableinp' is not loaded otherwise
        tables_folder = None
        if getattr(self, 'simulation_folder', None) is not None:
            tables_folder = self.simulation_folder / 'tables'
        tableinp = str(contents.get('tableinp') or '').strip().strip('"\'')
        if tables_folder is None and tableinp and Path(tableinp).is_dir():
            tables_folder = Path(tableinp)

        # the GUI writes 'ioutput_part(2)' (nh * nr_pproj) and 'ioutput_part(5)' (100 * nh * nr_pproj), other values are
        # kept in the additional settings (they are written after the ones of the GUI and are used by SDTrimSP)
        particle_outputs = []
        for index, factor in ((2, 1), (5, 100)):
            value = contents.get(f'ioutput_part({index})')
            if value is not None and getValue(value, int, -1) != int(nh) * int(nr_pproj) * factor:
                particle_outputs.append(f'ioutput_part({index}) = {str(value).strip()}')

        additional = []

        for add_key, add_val in contents.items():
            additional.append(f'{add_key} = {add_val}')
        additional += particle_outputs

        # with a layer file SDTrimSP uses qu only to estimate the depth of the dynamic relaxation, the loaded values are kept
        layer_file_qu = None
        if iq0 < 0 and isinstance(qu_text, str) and len(qu) == ncp == len(symbol):
            layer_file_qu = {str(s): float(q) for s, q in zip(symbol, qu)}

        # with a layer file (iq0 < 0) qu is not needed, the target species are the ones that occur in the layers
        # (also projectiles with qu = 0 that form a layer)
        if iq0 < 0 and ncp > 0:
            layer_species = layerTargetSpecies(layer_file, ncp)
            if not isinstance(qu_text, str):
                qu = layer_species
            elif len(qu) == ncp and any(layer_species):
                qu = [q if q else in_layer for q, in_layer in zip(qu, layer_species)]

        if not len(symbol) == len(qubeam) == len(qu) == ncp:
            return f'Length of lists "symbol({len(symbol)})", "qubeam({len(qubeam)})", "qu({len(qu)})" and "ncp={ncp}" are different.'

        row_index = RunningIndex()

        def rowList(qu_list: list, typ: str) -> List[RowArguments]:
            """Converts the qu_list into a list of <RowArguments>"""

            row_arguments: List[RowArguments] = []
            for qu_i, symbol_i, qumax_i, e0_i, alpha0_i, inel0_i, e_surfb_i, e_displ_i, dns0_i, a_mass_i in zip_longest(qu_list, symbol, qumax, e0, alpha0, inel0, e_surfb, e_displ, dns0, a_mass):
                if not qu_i:
                    continue

                assumed_row = DefaultAssumed()

                element_i = self.element_data.elementFromSymbol(symbol_i)
                if element_i is None:
                    element_i = Element()
                    error_list.append(f'Element "{symbol_i}" unknown, left empty')
                    symbol_i = ''

                # check if element is modified
                else:
                    if e_surfb_i is not None and e_surfb_i != -1.0:
                        element_i.surface_binding_energy = e_surfb_i
                        element_i.modified = True
                    if e_displ_i is not None and e_displ_i != -1.0:
                        element_i.displacement_energy = e_displ_i
                        element_i.modified = True
                    if dns0_i is not None and dns0_i != -1.0:
                        element_i.atomic_density = dns0_i
                        element_i.modified = True
                    if a_mass_i is not None and a_mass_i != -1.0:
                        element_i.atomic_mass = a_mass_i
                        element_i.modified = True

                if qumax_i is None:
                    qumax_i = default_values.qumax
                    assumed_row.assumed('max_atomic_fraction')
                if inel0_i is None:
                    inel0_i = defaultInelasticLossModel(symbol_i, version, dict_lookup, default_values)
                    assumed_row.assumed('inelastic_loss_model_row')

                row_parameters = {
                    'index': row_index.get(),
                    'symbol': symbol_i,
                    'element': element_i,
                    'abundance': qu_i,
                    'inelastic_loss_model': inel0_i,
                    'max_atomic_fraction': qumax_i
                }

                # further parameters of the species
                species_index = symbol.index(symbol_i) if symbol_i in symbol else -1
                for key, values in [
                    ('azimuth', beta0), ('start_depth', x0), ('charge', charge), ('cutoff_energy', e_cutoff),
                    ('bulk_binding_energy', e_bulkb), ('heat_of_formation', deltahf), ('isotopes', isot)
                ]:
                    if 0 <= species_index < len(values):
                        row_parameters[key] = values[species_index]
                # ck_elec(i, j) in column major order, the value for species i is taken from j = 1
                if 0 <= species_index < len(ck_elec_matrix):
                    row_parameters['inelastic_correction'] = ck_elec_matrix[species_index]

                if typ == 'beam':
                    if e0_i is None:
                        e0_i = default_values.e0
                        assumed_row.assumed('energy')
                    if alpha0_i is None:
                        alpha0_i = default_values.alpha0
                        assumed_row.assumed('angle')

                    row_parameters.update({
                        'energy': e0_i,
                        'angle': alpha0_i
                    })

                row_parameters.update({
                    'assumed': assumed_row
                })
                row_arguments.append(RowArguments(**row_parameters))
            return row_arguments

        # beam_rows data (List[<RowArguments>])
        # crystal species in layer.inp (since 7.02): (crystal index, stoichiometric fraction) of each additional column
        crystal_species = []
        crystal_layers = []
        crystal_elements = set()
        if iq0 < 0 and table_crystal is not None:
            try:
                if tables_folder is None:
                    raise CrystalTableError('the simulation folder is unknown')
                table = CrystalTableFile(tables_folder / 'table.crystal', CrystalTableLimits(version))
                for k, crystal in enumerate(table_crystal['crystals']):
                    table_entry = table.crystal(crystal['name'])
                    if table_entry is None:
                        raise CrystalTableError(f'crystal "{crystal["name"]}" not found')
                    for element, count in table_entry.composition().items():
                        crystal_species.append((k, count / len(table_entry.elements)))
                        crystal_elements.add(element)
            except CrystalTableError as table_error:
                error_list.append(f'Could not read the crystals of the layer file from table.crystal: {table_error}')
                crystal_species = []

        beam_rows = rowList(qubeam, 'beam')

        # target_rows data (List[<RowArguments>])
        # elements that are only part of crystals in the layer file have qu = 0, but are target elements
        if crystal_elements:
            qu = [q if q or s not in crystal_elements or b else 1.0 for q, s, b in zip(qu, symbol, qubeam)]
        # elements that are only part of the crystal of crystal.inp (7.00, 7.01) have qu = 0, but are target elements
        if l_crystal and table_crystal is None:
            try:
                crystal_inp_species = set(readCrystalInp(crystal_file)['species'])
            except (OSError, ValueError, IndexError):
                crystal_inp_species = set()
            qu = [q if q or s not in crystal_inp_species or b else 1.0 for q, s, b in zip(qu, symbol, qubeam)]
        target_rows = rowList(qu, 'target')

        # beam_args data (<GeneralBeamArguments>)
        # distributions of energies and angles from files
        distributions: Dict[str, Any] = {}
        projectiles = [(number, symbol_i) for number, (symbol_i, qubeam_i) in enumerate(zip(symbol, qubeam), start=1) if qubeam_i and qubeam_i > 0]

        def numbered(name: str, index: int) -> str:
            return f'{name}.inp' if index == 1 else f'{name}{index:02d}.inp'

        if case_e0 == ArgumentValues.KineticEnergy.FILE:
            if Versions.atLeast(version, Versions.V_700):
                energy_files = [(symbol_i, numbered('energy', index)) for index, symbol_i in projectiles]
            else:
                energy_files = [(symbol_i, name) for (_, symbol_i), name in zip(projectiles, ['energy.inp', 'energy2.inp'])]
            for symbol_i, name in energy_files:
                if (folder / name).is_file():
                    distributions.setdefault('energy', {})[symbol_i] = readDistributionFile(folder / name)
                else:
                    error_list.append(f'Energy distribution "{name}" not found')
        if case_alpha == ArgumentValues.Angle.FILE:
            if Versions.atLeast(version, Versions.V_702):
                angle_files = [(symbol_i, numbered('angle', index)) for index, symbol_i in projectiles]
                # 7.02 reads only angle.inp
                if version == Versions.V_702 and projectiles and all(name != 'angle.inp' for _, name in angle_files):
                    angle_files.append((projectiles[0][1], 'angle.inp'))
            else:
                angle_files = [('all', 'angle.inp')]
            for symbol_i, name in angle_files:
                if (folder / name).is_file() and symbol_i not in distributions.get('angle', {}):
                    distributions.setdefault('angle', {})[symbol_i] = readDistributionFile(folder / name)
            if not distributions.get('angle'):
                error_list.append(f'Angle distribution "{angle_files[0][1] if angle_files else "angle.inp"}" not found')
        # ene_ang.inp is loaded whenever it exists (it does not depend on the projectiles)
        energy_angle = readEnergyAngleFile(folder / 'ene_ang.inp') if (folder / 'ene_ang.inp').is_file() else None
        if energy_angle is not None:
            distributions['energy_angle'] = energy_angle
        elif case_e0 == ArgumentValues.KineticEnergy.FILE_ENERGY_ANGLE:
            error_list.append('Distribution of energies and angles "ene_ang.inp" not found or not readable')

        # the order of the species in tri.inp is kept (it changes the random numbers and therefore the results):
        # grouped are the target species first and then the projectiles that are not in the target (every species once),
        # not grouped are all projectiles first and then all target species
        beam_symbols = [row.symbol for row in beam_rows]
        target_symbols = [row.symbol for row in target_rows]
        file_symbols = [symbol_i for symbol_i, qu_i, qubeam_i in zip(symbol, qu, qubeam) if qu_i or qubeam_i]
        shared = bool(set(beam_symbols) & set(target_symbols))
        # a species that is projectile and target atom at the same time is only possible with grouped elements, the same
        # element as separate projectile and target species (e.g. "Cu", "Cu" in case Cu_Cu_crystal) is kept separate
        shared_species = any(qu_i and qubeam_i for qu_i, qubeam_i in zip(qu, qubeam))
        grouped_symbols = target_symbols + [symbol_i for symbol_i in beam_symbols if symbol_i not in target_symbols]
        if not shared_species and file_symbols == beam_symbols + target_symbols:
            group_elements = False
        elif file_symbols == grouped_symbols:
            group_elements = True
        else:
            group_elements = shared
            error_list.append('The order of the elements is changed (beam and target elements are grouped)' if shared else
                              'The order of the elements is changed (beam elements first)')

        beam_args = GeneralBeamArguments(
            kinetic_energy_mode=case_e0,
            angle_mode=case_alpha,
            sweep=number_calc,
            sheath_potential=shth,
            distributions=distributions
        )

        # target_args data (<GeneralTargetArguments>)
        target_args = GeneralTargetArguments(
            thickness=ttarget,
            segments=nqx,
            global_density=globaldensity,
            crystal_flag=l_crystal,
            layer_file_flag=iq0 if iq0 < 0 else -1,
            **({'layer_file_qu': layer_file_qu} if layer_file_qu is not None else {})
        )

        # settings data (<GeneralArguments>)
        settings = GeneralArguments(
            title=title,
            mode=idrel,
            fluence=flc,
            histories=nh,
            histories_between_out=idout,
            projectiles=nr_pproj,
            interaction_potential=ipot,
            integration_method=iintegral,
            surface_binding_model=isbv,
            log_reflected=lparticle_p,
            log_sputtered=lparticle_r,
            log_matrix=lmatrices,
            tbsp_format=tbsp_format,
            trajectories_projectiles=ltraj_p,
            trajectories_recoils=ltraj_r,
            trajectories_number=int(numb_hist),
            energy_distribution=lenergy_distr,
            distribution_grid=distribution_grid,
            random_seed=int(irand),
            inelastic_outside=bool(sfin),
            group_elements=group_elements
        )

        layer_counter = RunningIndex()
        structure = []
        if iq0 < 0:
            error_layer = 'Layer file has incorrect format.'

            try:
                # get all contents from layer file
                with open(layer_file, 'r', encoding='utf-8', errors='replace') as file:
                    for line in file.readlines():
                        line = line.strip()
                        if not line:
                            continue
                        if not line[0].isdigit() and line[0] != '.':
                            continue

                        content = [p.strip() for p in line.replace(',', ' ').split(' ') if p.strip()]
                        if not content:
                            continue
                        # the layers end with a line with 0 segments ("end"), SDTrimSP does not read further
                        if content[-1] == 'end' or content[0] == '0':
                            break
                        if len(content) < 1 + ncp:
                            if error_layer not in error_list:
                                error_list.append(error_layer)
                            continue

                        # crystal species and miller index after the amorphous species
                        crystal_columns = len(crystal_species)
                        if crystal_columns:
                            try:
                                crystal_values = [float(value) for value in content[ncp + 1:ncp + 1 + crystal_columns]]
                                miller = [float(value) for value in content[ncp + 1 + crystal_columns:ncp + 4 + crystal_columns]]
                                if len(crystal_values) != crystal_columns or len(miller) != 3:
                                    raise ValueError
                            except ValueError:
                                if error_layer not in error_list:
                                    error_list.append(error_layer)
                                continue
                            fractions = [0.] * len(notNone(table_crystal)['crystals'])
                            for (k, stoichiometry), value in zip(crystal_species, crystal_values):
                                fractions[k] += value
                            crystal_layers.append({'fractions': fractions, 'miller': miller})
                            content = content[:ncp + 1] + content[ncp + 4 + crystal_columns:]

                        name = f'Layer{layer_counter.get()}'
                        abundance_texts = content[2:ncp + 1]
                        if len(content) > 1 + ncp:
                            name = content[ncp + 1]

                        try:
                            abundances = [float(a) for a in abundance_texts]
                            abundances.insert(0, 1 - sum(abundances) - (sum(crystal_layers[-1]['fractions']) if crystal_columns else 0))
                            # abundances of the amorphous part are normalized
                            if crystal_columns and sum(abundances) > 1e-12:
                                abundances = [a / sum(abundances) for a in abundances]
                        except ValueError:
                            if error_layer not in error_list:
                                error_list.append(error_layer)
                            continue

                        abundances = [a for (a, q) in zip(abundances, qu) if q]

                        segments = getValue(content[0], int, default_values.nqx, 'layer_segments')
                        thickness_per_segment = getValue(content[1], float, default_values.ttarget, 'layer_thickness')

                        crystal_arguments = {}
                        if crystal_columns:
                            crystal_arguments = {'crystal_fractions': crystal_layers[-1]['fractions'], 'miller': crystal_layers[-1]['miller']}
                        structure.append(StructureArguments(
                            name=name,
                            segments=segments,
                            thickness=segments * thickness_per_segment,
                            abundances=abundances,
                            **crystal_arguments
                        ))

            except FileNotFoundError:
                error_list.append('No known layer files in this directory, assuming no layer file.')

        # SDTrimSP uses the first nqx segments of the layer file with their thicknesses (ttarget is not used then)
        if structure and iq0 < 0 and sum(layer.segments for layer in structure) > nqx:
            remaining = nqx
            trimmed = []
            for layer in structure:
                if remaining <= 0:
                    break
                if layer.segments > remaining:
                    layer.thickness = layer.thickness / layer.segments * remaining
                    layer.segments = remaining
                trimmed.append(layer)
                remaining -= layer.segments
            structure = trimmed
            target_args.thickness = sum(layer.thickness for layer in structure)

        # layer files with less than nqx segments: SDTrimSP repeats all segments of the layer file (starting with the first
        # layer) until nqx segments are reached
        elif structure and iq0 < 0 and 0 < sum(layer.segments for layer in structure) < nqx:
            original = list(structure)
            remaining = nqx - sum(layer.segments for layer in structure)
            layer_index = 0
            while remaining > 0:
                layer = deepcopy(original[layer_index % len(original)])
                if layer.segments > remaining:
                    layer.thickness = layer.thickness / layer.segments * remaining
                    layer.segments = remaining
                structure.append(layer)
                remaining -= layer.segments
                layer_index += 1
            target_args.thickness = sum(layer.thickness for layer in structure)

        if not structure:
            abundances = [target.abundance for target in target_rows]
            if not abundances:
                abundances = [1.0]
            structure = [StructureArguments(
                name='Layer',
                segments=target_args.segments,
                thickness=target_args.thickness,
                abundances=abundances
            )]

        crystal_args = None
        crystal_rows = None

        if table_crystal is not None:
            crystal_args = GeneralCrystalArguments(
                name=table_crystal['name'],
                lattice_id=default_values.lattice_id,
                lattice_constant=default_values.lattice_constant,
                basis_vec_a1=default_values.basis_vec_a1,
                basis_vec_a2=default_values.basis_vec_a2,
                basis_vec_a3=default_values.basis_vec_a3,
                miller_ind=notNone(miller_ind),
                beam_dy=table_crystal['beam_dy'],
                beam_dz=table_crystal['beam_dz'],
                crystal_dyn=table_crystal['crystal_dyn'],
                crystals=table_crystal['crystals'],
                table_crystal=True
            )

        elif l_crystal:
            """
            open file
            get rid of lines starting with # and skip empty lines
            
            read file: name -> name
            read file: lattice_id -> lattice_id
            
            read file: k -> number of species
            if ( k > ncp )then 'ERROR: number of spezies in crystal.inp > ncp in tri.inp'
            do i=1,k: read file: name -> species
            read file: lattice % base_vectors0(1) % p -> basis vec 1
            read file: lattice % base_vectors0(2) % p -> basis vec 2
            read file: lattice % base_vectors0(3) % p -> basis vec 3
            
            read file: k
            do i=1, k: read file: lattice%base_atom0(i)%p,it -> position, species
            read file: pmax_crystal -> pmax_crystal
            read file: dy_crystal_beam, dz_crystal_beam -> dy_beam, dz_beam
            read file: matrix_id -> matrix_id
            """

            crystal_args = GeneralCrystalArguments(
                name=default_values.crystal_name,
                lattice_id=default_values.lattice_id,
                lattice_constant=default_values.lattice_constant,
                basis_vec_a1=default_values.basis_vec_a1,
                basis_vec_a2=default_values.basis_vec_a2,
                basis_vec_a3=default_values.basis_vec_a3,
                miller_ind=default_values.miller_ind,
                p_max=default_values.p_max,
                beam_dy=default_values.beam_dy,
                beam_dz=default_values.beam_dz,
                matrix_id=default_values.matrix_id
            )

            try:
                crystal = readCrystalInp(crystal_file)
                lattice_constant = crystal['lattice_constant']
                species = crystal['species']
                if not species:
                    assumed.assumed('species')
                crystal_rows = [
                    CrystalRowArguments(index=i, symbol=species[atom[3] - 1], coord=Coordinate(list(atom[:3])))
                    for i, atom in enumerate(crystal['atoms'])
                ]

                # crystal_args data (<GeneralTargetArguments>)
                crystal_args = GeneralCrystalArguments(
                    name=crystal['name'],
                    lattice_id=crystal['lattice_id'],
                    number_of_species=len(species),
                    species=species,
                    lattice_constant=lattice_constant,
                    basis_vec_a1=BasisVector(crystal['basis_vectors'][0]) / lattice_constant,
                    basis_vec_a2=BasisVector(crystal['basis_vectors'][1]) / lattice_constant,
                    basis_vec_a3=BasisVector(crystal['basis_vectors'][2]) / lattice_constant,
                    miller_ind=notNone(miller_ind),
                    p_max=crystal['p_max'],
                    beam_dy=crystal['beam_dy'],
                    beam_dz=crystal['beam_dz'],
                    matrix_id=crystal['matrix_id']
                )

            except OSError:
                error_list.append('Could not open crystal file.')

            except (IndexError, ValueError):
                error_list.append('Crystal file has incorrect format.')

        simulation = SimulationArguments(
            simulation=self.Name,
            beam_args=beam_args,
            beam_rows=beam_rows,
            target_args=target_args,
            target_rows=target_rows,
            structure=structure,
            settings=settings,
            additional=additional,
            assumed=assumed,
            crystal_args=crystal_args,
            crystal_rows=crystal_rows
        )

        return simulation, error_list

    def checkWarnings(self, arguments: SimulationArguments, version: str) -> List[str]:
        """
        Returns warnings about parameters that SDTrimSP accepts, but that might give wrong results, fail or create very large
        files (the user decides whether the simulation is run)

        :param arguments: <SimulationArguments> container
        :param version: version of simulation
        """

        warnings = []
        default_values = DefaultValues(version)
        dict_lookup = DictLookup(version)
        beam_rows = [row for row in arguments.beam_rows if row.symbol and row.element is not None and row.abundance > 0]
        target_rows = [row for row in arguments.target_rows if row.symbol and row.element is not None]
        names = {
            1: 'Lindhard-Scharff', 2: 'Oen-Robinson', 3: 'Lindhard-Scharff and Oen-Robinson'
        }

        def inelasticModel(row) -> int:
            model = row.get('inelastic_loss_model')
            return dict_lookup.inel0.get(model, default_values.inel0) if model is not None else default_values.inel0

        def validityLimit(row) -> float:
            """Upper energy limit (in eV) of the models of Lindhard-Scharff and Oen-Robinson: E < 25 Z^(4/3) M keV"""
            return 25e3 * row.element.atomic_nr ** (4 / 3) * row.element.atomic_mass

        # 1) Lindhard-Scharff and Oen-Robinson are only valid below 25 Z^(4/3) M keV (projectiles and the recoils they create)
        for row in beam_rows:
            model = inelasticModel(row)
            if model in names and row.energy > validityLimit(row):
                warnings.append(
                    f'{row.symbol}: the inelastic loss model {model} ({names[model]}) is only valid for energies below '
                    f'25 · Z^(4/3) · M = {validityLimit(row) / 1e3:.4g} keV, the energy is {row.energy / 1e3:.4g} keV. '
                    f'The high energy models (4: H, D, T; 5: He; 6: Ziegler-Biersack{"; 7: LZ7" if Versions.atLeast(version, Versions.V_606) else ""}) suit better'
                )
        max_energy = max([row.energy for row in beam_rows], default=0.)
        for row in target_rows:
            model = inelasticModel(row)
            if model not in names:
                continue
            # maximum energy transfer to the target atoms
            transfer = max([
                4 * beam.element.atomic_mass * row.element.atomic_mass / (beam.element.atomic_mass + row.element.atomic_mass) ** 2 * beam.energy
                for beam in beam_rows
            ], default=0.)
            if transfer > validityLimit(row):
                warnings.append(
                    f'{row.symbol} (target): the recoils can get up to {transfer / 1e3:.4g} keV, the inelastic loss model {model} '
                    f'({names[model]}) is only valid below {validityLimit(row) / 1e3:.4g} keV'
                )

        # 0) the installation is compiled for a maximum number of elements (ncpm in src/param.F90)
        max_elements = maxElements(getattr(self, 'simulation_folder', None))
        group_elements = arguments.settings.get('group_elements')
        if group_elements is None:
            group_elements = default_values.group_elements
        elements = len(speciesList(arguments, group_elements))
        if max_elements is not None and elements > max_elements:
            warnings.append(
                f'The simulation has {elements} elements, but this installation of SDTrimSP is compiled for at most '
                f'{max_elements} (ncpm in src/param.F90). SDTrimSP stops with "Cannot match namelist object name" while '
                f'reading tri.inp: use fewer elements, a newer version or compile SDTrimSP with a larger ncpm'
            )

        # 0b) the high energy models of H, D, T (4, table3) and He (5, table4) read the coefficients of all species, SDTrimSP
        # stops with "Bad real number" in tableread.F90 if one is missing (e.g. C_a before 7.02, B10 in 6.09)
        all_rows = [row for row in arguments.beam_rows + arguments.target_rows if row.symbol]
        for model, table, projectiles in ((4, 'table3', 'H, D, T'), (5, 'table4', 'He')):
            if not any(inelasticModel(row) == model for row in all_rows):
                continue
            table_symbols = stoppingTableSymbols(getattr(self, 'simulation_folder', None), table)
            if table_symbols is None:
                continue
            missing = sorted({row.symbol for row in all_rows if row.symbol not in table_symbols})
            if missing:
                warnings.append(
                    f'The inelastic loss model {model} ({projectiles}) needs the coefficients of all elements in tables/{table}, '
                    f'{", ".join(missing)} {"is" if len(missing) == 1 else "are"} missing in this installation: SDTrimSP stops '
                    f'with "Bad real number" while reading the table. Use another inelastic loss model or a newer version'
                )

        # mean target composition (first layer)
        abundances = arguments.structure[0].abundances if arguments.structure else []
        if len(abundances) != len(target_rows):
            abundances = [row.abundance for row in target_rows]
        total = sum(abundances)
        thickness = arguments.target_args.thickness
        if target_rows and total > 0:
            fractions = [a / total for a in abundances]
            z2 = sum(f * row.element.atomic_nr for f, row in zip(fractions, target_rows))
            m2 = sum(f * row.element.atomic_mass for f, row in zip(fractions, target_rows))
            densities = [row.get('atomic_density') or row.element.atomic_density for row in target_rows]
            density = sum(f * float(d or 0) for f, d in zip(fractions, densities))

            # 2) SDTrimSP 7.00 and 7.01 abort if projectiles leave the target at the bottom
            if version == Versions.V_700:
                for row in beam_rows:
                    path = estimateRange(row.energy, row.element.atomic_nr, row.element.atomic_mass, z2, m2, density)
                    if path > 0.8 * thickness:
                        warnings.append(
                            f'{row.symbol}: the estimated path length of the projectiles ({path:.4g} Å) is not much smaller than the '
                            f'thickness of the target ({thickness:.4g} Å). SDTrimSP 7.00 and 7.01 abort with "invalid case for flag" '
                            f'if projectiles are transmitted: use a thicker target or SDTrimSP 7.02 or newer'
                        )

        # 3) the energy distribution in the target crashes SDTrimSP in sweeps ("allocatable array is already allocated")
        sweep = ArgumentValues.KineticEnergy.SWEEP, ArgumentValues.Angle.SWEEP
        if arguments.settings.get('energy_distribution') and (
            arguments.beam_args.kinetic_energy_mode in sweep or arguments.beam_args.angle_mode in sweep
        ) and int(arguments.beam_args.get('sweep') or 1) > 1:
            warnings.append('The energy distribution in the target (lenergy_distr) crashes SDTrimSP in energy and angle sweeps '
                            '("allocatable array is already allocated"), switch it off')

        # 4) large output files
        projectiles = int(arguments.settings.get('histories', 0) or 0) * int(arguments.settings.get('projectiles', 0) or 0)
        if arguments.settings.get('trajectories_projectiles') or arguments.settings.get('trajectories_recoils'):
            traced = int(arguments.settings.get('trajectories_number', default_values.numb_hist) or 0)
            # about 70 bytes per eV of the projectile for the cascade of recoils (trajec_all.dat), a few kB without recoils
            per_projectile = 70 * max_energy if arguments.settings.get('trajectories_recoils') else 5e3
            size = 2 * traced * per_projectile
            if size > 200e6:
                warnings.append(f'The trajectory files (trajec_*.dat) might become about {size / 1e9:.2g} GB large ({traced} traced trajectories)')
        if arguments.settings.get('log_matrix'):
            projectile_species = len(beam_rows)
            species = len({row.symbol for row in beam_rows + target_rows})
            size = 6e6 * (2 * projectile_species + 2 * species)
            if size > 100e6:
                warnings.append(f'The matrix files (meagb_*.dat, meagt_*.dat) will be about {size / 1e6:.0f} MB large')
        if arguments.settings.get('log_sputtered') and projectiles > 2e6:
            warnings.append(
                f'The files of the sputtered recoils (partic_*_r.dat) might become very large ({projectiles:.3g} projectiles, '
                f'about 150 bytes per sputtered atom)'
            )
        return warnings

    def checkArguments(self, arguments: SimulationArguments, version: str) -> List[str]:
        """
        Checks combinations of parameters that SDTrimSP does not accept and returns list of errors

        :param arguments: <SimulationArguments> container
        :param version: version of simulation
        """

        errors = []

        # crystals from table.crystal in the layers
        if DefaultValues(version).crystal_table and arguments.target_args.get('crystal_flag', False) and arguments.crystal_args is not None:
            layers = crystalLayers(arguments)
            for structure, layer in zip(arguments.structure, layers):
                if sum(layer['fractions']) > 1 + 1e-6:
                    errors.append(f'The crystal fractions of layer "{structure.name}" are larger than 1')
            if layers and not any(fraction > 0 for layer in layers for fraction in layer['fractions']):
                errors.append('No layer of the target structure contains a crystal')
            if usesCrystalLayerFile(arguments, version):
                # layer.inp: each layer with crystal has its own orientation, polycrystals ((0 0 0)) are not possible
                for structure, layer in zip(arguments.structure, layers):
                    error = layerMillerError(layer['miller'])
                    if sum(layer['fractions']) > 0 and error is not None:
                        miller = ' '.join(f'{float(m):g}' for m in layer['miller'])
                        if all(float(m) == 0 for m in layer['miller']):
                            errors.append(
                                f'Layer "{structure.name}": {error}. With several layers each layer with crystal needs an '
                                f'orientation of the form [1, 0...1, 0...1], e.g. (1 0 0)'
                            )
                            continue
                        suggestion = ' '.join(f'{m:g}' for m in layerMillerSuggestion(layer['miller']))
                        errors.append(
                            f'The miller index ({miller}) of layer "{structure.name}" is not accepted by SDTrimSP in layer.inp: {error}. '
                            f'Only the form [1, 0...1, 0...1] is allowed (h >= k, h >= l), e.g. ({suggestion}) '
                            f'which is equivalent for cubic crystals'
                        )
            else:
                # polycrystal ((0 0 0) in tri.inp): only the first crystal and not with the surface binding model 4
                crystals = tableCrystals(arguments.crystal_args)
                for i, crystal in enumerate(crystals):
                    if all(float(m) == 0 for m in crystal['miller']):
                        if i > 0:
                            errors.append(f'Crystal "{crystal["name"]}": only the first crystal can be a polycrystal (miller index (0 0 0))')
                        elif DictLookup(version).isbv.get(arguments.settings.get('surface_binding_model')) == 4:
                            errors.append('A polycrystal (miller index (0 0 0)) is not possible with the surface binding model 4')

        # distributions of energies and angles from files must be defined
        group_elements = arguments.settings.get('group_elements')
        if not isinstance(group_elements, bool):
            group_elements = DefaultValues(version).group_elements
        names = distributionFileNames(arguments, version, group_elements)
        distributions = arguments.beam_args.get('distributions')
        if not isinstance(distributions, dict):
            distributions = {}
        for symbol, name in names['energy']:
            if not distributions.get('energy', {}).get(symbol):
                errors.append(f'The energy distribution of {symbol} ({name}) is not defined, use the "Distributions..." button')
        for symbol, name in names['angle']:
            angles = distributions.get('angle', {})
            if not (angles.get(symbol) or (symbol == 'all' and any(angles.values()))):
                errors.append(f'The angle distribution{"" if symbol == "all" else " of " + symbol} ({name}) is not defined, use the "Distributions..." button')
        if names['energy_angle'] and not self.supportsEnergyAngleFile(version):
            errors.append('The distribution of energies and angles from ene_ang.inp (case_e0 = 6) is not implemented in SDTrimSP 7.00 - 7.02')
        elif names['energy_angle'] and not distributions.get('energy_angle'):
            errors.append('The distribution of energies and angles (ene_ang.inp) is not defined, use the "Distributions..." button')
        if not Versions.atLeast(version, Versions.V_700) and arguments.beam_args.kinetic_energy_mode == ArgumentValues.KineticEnergy.FILE:
            if sum(1 for _, beam in speciesList(arguments, group_elements) if beam) > 2:
                errors.append(f'SDTrimSP {version} reads energy distributions (energy.inp, energy2.inp) for at most two projectiles')

        # SDTrimSP.F90: inel0 = 2 or 3 is only allowed for the KrC potential (ipot = 1)
        ipot = arguments.settings.get('interaction_potential')
        if ipot is not None and ipot != ArgumentValues.InteractionPotential.KRC:
            models = [arguments.settings.get('inelastic_loss_model')]
            models += [row.get('inelastic_loss_model') for row in arguments.beam_rows + arguments.target_rows if row.symbol]
            not_allowed = (ArgumentValues.InelasticLossModel.OEN_ROBINSON, ArgumentValues.InelasticLossModel.LINDHARD_SCHARFF_AND_OEN_ROBINSON)
            if any(model in not_allowed for model in models):
                errors.append('The inelastic loss models "Oen-Robinson" (2) and "average of (1) and (2)" (3) are only allowed for the KrC interaction potential')

        return errors

    def runFailed(self, save_folder: Optional[Path], log: str, exit_code: int, version: str) -> Optional[str]:
        """
        Returns a description of the problem if the finished simulation failed, otherwise None.
        SDTrimSP sometimes terminates with exit code 0 after an error, so the log and the output files are checked as well

        :param save_folder: folder of the simulation
        :param log: output of the simulation process
        :param exit_code: exit code of the simulation process
        :param version: version of simulation
        """

        if 'stop from subroutine' in log or exit_code == 66:
            return 'the simulation stopped because of an error, see the log'
        # 7.00 and 7.01 leave the collision loop without a result if a projectile is already below the target
        # (projectile.F90, "ix_var is not properly set"), this was fixed in 7.02
        if 'invalid case for flag' in log and 'ix_var is not properly set' in log:
            return ('a projectile passed through the target (transmission), which SDTrimSP 7.00 and 7.01 cannot handle. '
                    'Use a thicker target, a lower energy or SDTrimSP 7.02 or newer')
        if 'allocatable array is already allocated' in log:
            return ('SDTrimSP crashed ("allocatable array is already allocated"), this happens e.g. with the energy distribution '
                    'in the target (lenergy_distr) in energy or angle sweeps')
        if 'code terminates' in log:
            return 'the simulation terminated because of an error, see the log'
        if exit_code != 0:
            return f'exit code {exit_code}'
        if save_folder is not None and save_folder.is_dir() and not any(save_folder.glob('output*.dat')):
            return 'the simulation finished without writing the results (output.dat), see the log'
        return None

    def checkAdditional(self, settings: str, version: str) -> List[str]:
        """
        Checks the user defined additional settings and returns list of errors

        :param settings: provided additional settings
        :param version: version of simulation

        :return: list of errors
        """

        if not settings:
            return []

        # parameters that the installation accepts (namelist TRI_INP in the source code or the documentation)
        known = namelistParameters(getattr(self, 'simulation_folder', None))

        errors = []
        for i, setting in enumerate(settings.split('\n')):
            setting = setting.strip()
            if not setting:
                continue
            if setting.startswith('!'):
                continue

            content = [sp.strip() for sp in setting.split('=')]

            if len(content) != 2:
                errors.append(f'Line {i + 1}: Missing or too many "="')
                continue

            name = content[0].split('(')[0].strip()
            parameter_type = self.InputParameters.get(name)
            if known is not None and name.lower() not in known:
                errors.append(f'Line {i + 1}: Unknown variable "{name}", SDTrimSP {version} does not read it (namelist TRI_INP in src/work.F90)')
            elif known is None and parameter_type is None:
                errors.append(f'Line {i + 1}: Unknown variable "{content[0]}"')

            if content[0].count('(') != content[0].count(')'):
                errors.append(f'Line {i + 1}: Parentheses do not match')

            data_type: type = str
            try:
                if content[1] in ['.true.', '.false.']:
                    data_type = bool

                float(content[1])
                data_type = float

                int(content[1])
                data_type = int

            except (ValueError, IndexError):
                pass

            if not content[1]:
                errors.append(f'Line {i + 1}: variable "{content[0]}" has no value')
            elif parameter_type != data_type and not (parameter_type is None or parameter_type is str):
                if not (parameter_type is float and data_type is int):
                    errors.append(f'Line {i + 1}: variable "{content[0]}" has wrong type (should be {parameter_type})')

        return errors

    def getProgress(self, save_folder: Path, process_log: str, version: str) -> float:
        """
        Returns progress in % of running simulation.
        Negative return value indicates some error.

        :param save_folder: folder for output files
        :param process_log: most recent output of process
        :param version: version of simulation
        """

        log_file = 'time_run.dat'

        if not (save_folder / log_file).is_file():
            process_log_packages = process_log.split('%')
            if len(process_log_packages) < 2:
                return -1
            percentage = ''
            for char in process_log_packages[-2].strip()[::-1]:
                if char.isnumeric():
                    percentage += char
                else:
                    break
            try:
                return int(percentage[::-1])
            except ValueError:
                return -1

        percent: float = -1
        try:
            with open(save_folder / log_file, 'r', encoding='utf-8', errors='replace') as file:
                for line in reversed(file.readlines()):
                    data = line.split(' %')
                    if len(data) == 2 and data[0][0] not in ['I', 'W']:
                        try:
                            percent = float(data[0][-3:])
                            break
                        except (ValueError, IndexError):
                            pass

        except FileNotFoundError:
            return -1

        # single run
        if not any('001' in file.name for file in save_folder.iterdir() if file.is_file()) or percent < 0:
            return percent

        # sweep run
        else:
            current_sweep = sum('output.' in file.name for file in save_folder.iterdir() if file.is_file())
            if not (save_folder / self.InputFilename).is_file():
                return -1
            sweeps = DefaultValues(version).number_calc
            try:
                with open(save_folder / self.InputFilename, 'r', encoding='utf-8', errors='replace') as file:
                    for line in file.readlines():
                        if not line.strip().startswith('number_calc'):
                            continue
                        try:
                            sweeps = int(line.split(' = ')[1])
                            break
                        except ValueError:
                            pass

            except FileNotFoundError:
                return -1

            return (100 * current_sweep + percent) / sweeps


class SimulationOutput(SimulationsOutput):
    """
    Class for displaying SDTrimSP specific parameters and plots
    """

    # References to classes
    HlPlot = HlPlot

    analysis: 'SimulationAnalysis'

    def __init__(self, plot: MplCanvas, element_data: Elements, title_label: VBoxTitleLayout):
        self.analysis = SimulationAnalysis(element_data)
        super().__init__(plot, element_data, title_label)

        # settings of the trajectory plot, changed in HlPlot
        self.trajectory_args = {'projectile': 1, 'view': 'y', 'color': 'species', 'recoils': True, 'layers': True, 'time_fraction': None}

        # settings of the plot of the energy distribution in the target, changed in HlPlot
        self.energy_distribution_args = {'kind': 'all', 'view': 'y', 'log': False}

        # export of the animation of the collision cascade as GIF (in a background thread)
        self.animation_export: Optional[AnimationExport] = None

    def receive(self, value_dict: dict):
        """Receives pyqtSignal -> dict"""

        trajectories = value_dict.get('trajectories')
        if isinstance(trajectories, dict):
            self.trajectory_args.update(trajectories)
            self.analyse('plotTrajectories', dict(self.trajectory_args), hide=False)

        trajectory_gif = value_dict.get('trajectory_gif')
        if isinstance(trajectory_gif, dict):
            self.saveTrajectoryAnimation(trajectory_gif)

        energy_distribution = value_dict.get('energy_distribution')
        if isinstance(energy_distribution, dict):
            self.energy_distribution_args.update(energy_distribution)
            self.analyse('plotEnergyDistribution', dict(self.energy_distribution_args), hide=False)

        histories = value_dict.get('history')
        if histories is not None:
            self.analyse('plotDepthConcentration', {'history_step': int(histories)}, hide=False)

        energy_polar = value_dict.get('energy_polar')
        if energy_polar is not None:
            self.analyse('plotParticlesEnergyPolar', energy_polar, hide=False)

    def showEnergyDistribution(self, kind: str, text: str = ''):
        """
        Shows the energy distribution in the target of a kind (see SimulationAnalysis.EnergyDistributions)

        :param kind: kind of the energy distribution
        :param text: text of the analysis
        """

        self.energy_distribution_args['kind'] = kind
        self.analyse('plotEnergyDistribution', dict(self.energy_distribution_args), hide=False, text=text)

    def listDistributions(self, save_folder: Path, list_widget: ListWidget):
        """
        Adds the plots of the energy distribution in the target (lenergy_distr), the depth distributions of the matrices
        (maximum penetration depth, depth of origin) and the energy-angle matrices (lmatrices) to the list

        :param save_folder: folder for output files
        :param list_widget: ListWidget that is written to
        """

        def nonEmpty(name: str) -> bool:
            path = save_folder / name
            return path.is_file() and path.stat().st_size > 0

        items = []
        for kind, (name, title) in self.analysis.EnergyDistributions.items():
            if nonEmpty(name):
                items.append(ListWidgetItem(title, indent=1, function=self.showEnergyDistribution, function_args={'kind': kind}))
        for name, (title, _) in self.analysis.EnergyDepthMatrices.items():
            # the matrices are always written, often without particles (e.g. depth of origin of sputtered target atoms in 7.07)
            if nonEmpty(name) and any(np.sum(matrix['counts']) > 0 for matrix in readEnergyDepthMatrix(save_folder / name)):
                items.append(ListWidgetItem(title, indent=1, function=self.analyse,
                                            function_args={'plot': 'plotEnergyDepthMatrix', 'plot_args': {'name': name}}))
        for name, title in self.analysis.EnergyAngleMatrices.items():
            if not nonEmpty(name):
                continue
            for i, species in enumerate(matrixSpecies(save_folder / name)):
                items.append(ListWidgetItem(f'Energy and polar angle of {title} ({species})', indent=1, function=self.analyse,
                                            function_args={'plot': 'plotEnergyAngleMatrix', 'plot_args': {'name': name, 'species': i}}))

        if items:
            list_widget.addItem(ListWidgetItem('Plot distributions in the target and output matrices:', bold=True))
            for item in items:
                list_widget.addItem(item)
        else:
            list_widget.addItem(ListWidgetItem('Plot distributions in the target (only with energy distribution or matrix output)', bold=True, grey=True))
        list_widget.addItemEmpty()

    def saveTrajectoryAnimation(self, arguments: dict, path: Optional[Path] = None, frames: int = 60, frame_duration: int = 80) -> Optional[Path]:
        """
        Saves the animation of the collision cascade as GIF in a background thread (self.animation_export) and returns its
        path. The frames are created first, then they are drawn and saved in the background: the GUI stays usable and the
        status bar shows the progress

        :param arguments: arguments of the trajectory plot (see SimulationAnalysis.plotTrajectories)
        :param path: (optional) path of the GIF, otherwise a file dialog asks for it
        :param frames: number of frames (the last frame shows the whole cascade)
        :param frame_duration: duration of a frame in ms
        """

        # the status bar of the main window shows the progress
        main_window = self.plot.window()
        status_bar = main_window.statusBar() if isinstance(main_window, QMainWindow) else None

        def showStatus(message: str, timeout: int = 0):
            try:
                if status_bar is not None:
                    status_bar.showMessage(message, timeout)
            except RuntimeError:
                # the window was closed in the meantime
                pass

        if self.animation_export is not None and self.animation_export.isRunning():
            showStatus('An animation is already being saved, please wait until it is finished', 5000)
            return None

        save_folder = self.analysis.save_folder
        if save_folder is None:
            return None
        if path is None:
            path = selectFileDialog(
                self.plot,
                True,
                'Save animation of the collision cascade as...',
                save_folder / f'trajectories_projectile_{arguments.get("projectile", 1)}.gif',
                'GIF files (*.gif)'
            )
            if path is None:
                return None

        # settings of the frames (fast, the data of the simulation is read here), they are drawn in the background
        settings: List[MplCanvasSettings] = []
        for frame in range(frames + 1):
            result = self.analysis.plotTrajectories(**dict(arguments, time_fraction=frame / frames))
            if result is None or result[0] is None:
                break
            settings.append(result[1])
        if not settings:
            showStatus('The animation could not be saved (no trajectories)', 5000)
            return None

        # canvas with the size of the plot, a 3D plot keeps its current view
        width, height = self.plot.fig.get_size_inches()
        canvas = OffscreenCanvas(max(width, 4), max(height, 3), self.plot.fig.dpi, projection='3d' if arguments.get('view') == '3d' else None)
        plot_axes: Any = self.plot.axes
        if arguments.get('view') == '3d' and getattr(plot_axes, 'name', '') == '3d':
            canvas.axes.view_init(plot_axes.elev, plot_axes.azim)

        durations = [frame_duration] * (len(settings) - 1) + [frame_duration * 25]
        export = AnimationExport(settings, canvas, path, durations)
        name = path.name
        export.progress.connect(lambda frame, number: showStatus(f'Saving the animation as GIF in the background: frame {frame} of {number} ({name})...'))

        def finished(saved: str, error: str):
            if saved:
                showStatus(f'Animation saved as {saved}', 8000)
            else:
                showStatus(f'The animation could not be saved ({error})', 8000)

        export.finished.connect(finished)
        self.animation_export = export
        showStatus(f'Saving the animation as GIF in the background ({name})...')
        export.start()
        return path

    def listParameters(self, save_folder: Path, list_widget: ListWidget):
        """
        Builds ListWidget from files in save folder

        :param save_folder: folder for output files
        :param list_widget: empty ListWidget (extension of QListWidget) that should be written to
        """

        info_file = 'E0_31_target.dat'
        if not (save_folder / info_file).is_file():
            info_file = 'E0_31_target001.dat'
            if not (save_folder / info_file).is_file():
                list_widget.addItem(ListWidgetItem('Corrupted input files', bold=True))
                return

        self.analysis.updateData(save_folder, info_file)

        # dynamic
        if self.analysis.is_dynamic:
            list_widget.addItem(ListWidgetItem('Results overview (only for finished static Simulations)', bold=True, grey=True))
            list_widget.addItemEmpty()

        # static
        elif (save_folder / 'output.dat').is_file():
            list_widget.addItem(ListWidgetItem('Results overview:', bold=True))

            output_data = self.analysis.getOutputFileData()
            if output_data is None:
                list_widget.addItem(ListWidgetItem('Corrupted input file', indent=1))
                return

            (sputter_yields,
             total_sputter_yield,
             amu_sputter_yield,
             reflection_coefficients,

             implantation_depth,
             energy_loss_nuclear,
             energy_loss_electron,

             transmission_sputter_yields,
             total_transmission_sputter_yield,
             amu_transmission_sputter_yield,
             transmission_coefficients) = output_data

            energy_loss_total = energy_loss_nuclear + energy_loss_electron
            transmission_happening = transmission_coefficients.any() or transmission_sputter_yields.any()

            # sputtering yields
            list_widget.addItem(ListWidgetItem('Sputtering yields:', indent=1))

            for i, element in enumerate(self.analysis.elements):
                if sputter_yields[i]:
                    list_widget.addItem(ListWidgetItem(f'{element}\t{roundToStr(sputter_yields[i])} atoms/ion', indent=2))

            if not total_sputter_yield:
                list_widget.addItem(ListWidgetItem('No sputtering occurred.', indent=2))

            else:
                list_widget.addItemEmpty()
                list_widget.addItem(ListWidgetItem(f'Total\t{roundToStr(float(total_sputter_yield))} atoms/ion', indent=2))
                list_widget.addItem(ListWidgetItem(f'\t{roundToStr(float(amu_sputter_yield))} amu/ion', indent=2))

            # transmission sputtering yields
            if transmission_happening:
                list_widget.addItemEmpty()
                list_widget.addItem(ListWidgetItem('Transmission sputtering yields:', indent=1))

                for i, element in enumerate(self.analysis.elements):
                    if transmission_sputter_yields[i]:
                        list_widget.addItem(ListWidgetItem(f'{element}\t{roundToStr(transmission_sputter_yields[i])} atoms/ion', indent=2))

                if not total_transmission_sputter_yield:
                    list_widget.addItem(ListWidgetItem('No transmission sputtering occurred.', indent=2))

                else:
                    list_widget.addItemEmpty()
                    list_widget.addItem(ListWidgetItem(f'Total\t{roundToStr(float(total_transmission_sputter_yield))} atoms/ion', indent=2))
                    list_widget.addItem(ListWidgetItem(f'\t{roundToStr(float(amu_transmission_sputter_yield))} amu/ion', indent=2))

            # reflection coefficients
            list_widget.addItemEmpty()
            list_widget.addItem(ListWidgetItem('Reflection coefficients:', indent=1))

            for i, element in enumerate(self.analysis.elements):
                if reflection_coefficients[i]:
                    list_widget.addItem(ListWidgetItem(f'{element}\t{roundToStr(reflection_coefficients[i])}', indent=2))

            if not np.sum(reflection_coefficients):
                list_widget.addItem(ListWidgetItem('No projectile reflection occurred.', indent=2))

            # transmission coefficients
            if transmission_happening:
                list_widget.addItemEmpty()
                list_widget.addItem(ListWidgetItem('Transmission coefficients:', indent=1))

                for i, element in enumerate(self.analysis.elements):
                    if transmission_coefficients[i]:
                        list_widget.addItem(ListWidgetItem(f'{element}\t{roundToStr(transmission_coefficients[i])}', indent=2))

                if not np.sum(transmission_coefficients):
                    list_widget.addItem(ListWidgetItem('No transmission effects occurred.', indent=2))

            # implantation depth
            list_widget.addItemEmpty()
            list_widget.addItem(ListWidgetItem('Mean implantation depth:', indent=1))

            for i, element in enumerate(self.analysis.elements):
                if implantation_depth[i]:
                    list_widget.addItem(ListWidgetItem(f'{element}\t{implantation_depth[i]:.3f} Å', indent=2))

            if not np.sum(implantation_depth):
                list_widget.addItem(ListWidgetItem('No projectile implantation occurred.', indent=2))

            # energy loss
            list_widget.addItemEmpty()
            list_widget.addItem(ListWidgetItem('Mean projectile energy loss:', indent=1))
            list_widget.addItem(ListWidgetItem('\tNuclear\tElectronic\tTotal', indent=2))

            for i, element in enumerate(self.analysis.elements):
                if energy_loss_total[i]:
                    list_widget.addItem(ListWidgetItem(f'{element}\t{energy_loss_nuclear[i]:.3f} eV\t{energy_loss_electron[i]:.3f} eV\t{energy_loss_total[i]:.3f} eV', indent=2))

            list_widget.addItemEmpty()

        # depth statistic
        depth_proj_exists = (save_folder / 'depth_proj.dat').is_file()
        depth_recoil_exists = (save_folder / 'depth_recoil.dat').is_file()
        depth_damage_exists = (save_folder / 'depth_damage.dat').is_file()

        if depth_proj_exists or depth_recoil_exists or depth_damage_exists:
            list_widget.addItem(ListWidgetItem('Plot depth statistic:', bold=True))

            if depth_proj_exists:
                list_widget.addItem(ListWidgetItem('Implantation depth',
                                                   indent=1,
                                                   function=self.analyse,
                                                   function_args={'plot': 'plotImplantationDepth'}))
                list_widget.addItem(ListWidgetItem('Projectile energy loss',
                                                   indent=1,
                                                   function=self.analyse,
                                                   function_args={'plot': 'plotEnergyLossDepth'}))

            if depth_recoil_exists or depth_damage_exists:
                list_widget.addItem(ListWidgetItem('Ion-induced damages',
                                                   indent=1,
                                                   function=self.analyse,
                                                   function_args={'plot': 'plotVacanciesDepth'}))

        else:
            list_widget.addItem(ListWidgetItem('Plot depth statistics (only for finished static Simulations)', bold=True, grey=True))

        list_widget.addItemEmpty()

        # fluence dependent quantities
        if self.analysis.is_dynamic:
            list_widget.addItem(ListWidgetItem('Plot over fluence:', bold=True))

            list_widget.addItem(ListWidgetItem('Sputtering yields',
                                               indent=1,
                                               function=self.analyse,
                                               function_args={'plot': 'plotSputterYields'}))
            list_widget.addItem(ListWidgetItem('Total sputtering yield (atoms/ion)',
                                               indent=1,
                                               function=self.analyse,
                                               function_args={'plot': 'plotSputterYieldsTotal'}))
            list_widget.addItem(ListWidgetItem('Net mass removal (amu/ion)',
                                               indent=1,
                                               function=self.analyse,
                                               function_args={'plot': 'plotSputterYieldsTotalAmu'}))
            list_widget.addItem(ListWidgetItem('Reflection coefficients',
                                               indent=1,
                                               function=self.analyse,
                                               function_args={'plot': 'plotReflectionCoefficients'}))
            list_widget.addItem(ListWidgetItem('Reemission coefficients',
                                               indent=1,
                                               function=self.analyse,
                                               function_args={'plot': 'plotReemissionCoefficients'}))
            list_widget.addItem(ListWidgetItem('Surface concentrations',
                                               indent=1,
                                               function=self.analyse,
                                               function_args={'plot': 'plotSurfaceConcentrations'}))
            list_widget.addItem(ListWidgetItem('Surface level',
                                               indent=1,
                                               function=self.analyse,
                                               function_args={'plot': 'plotSurfaceLevel'}))
            list_widget.addItem(ListWidgetItem('Concentrations over depth',
                                               indent=1,
                                               function=self.analyse,
                                               function_args={'plot': 'updateDepthConcentration',
                                                              'plot_args': {'set_to_max': True},
                                                              'hide': False}))

        else:
            list_widget.addItem(ListWidgetItem('Plot over fluence (only for dynamic Simulations)', bold=True, grey=True))

        list_widget.addItemEmpty()

        # angular dependence
        nr_energies = 0
        nr_angles = 0
        series_data = self.analysis.getSerieFileData()

        if series_data is not None:
            (ncp,
             ncp_proj,
             elements,
             elements_projectiles,
             masses,

             nr_energies,
             nr_angles,
             nr_total,

             energies,
             angles,
             mean_depth,
             refl_coefficients,
             energ_refl_coefficients,
             sputt_coefficients,
             energ_sputt_coefficients,
             ii) = series_data

        if nr_angles > 1:
            list_widget.addItem(ListWidgetItem('Plot angular dependence:', bold=True))
            list_widget.addItem(ListWidgetItem('Angular dependence of sputtering yields (atoms/ion)',
                                               indent=1,
                                               function=self.analyse,
                                               function_args={'plot': 'plotAngularSputterYields'}))
            list_widget.addItem(ListWidgetItem('Angular dependence of sputtered mass (amu/ion)',
                                               indent=1,
                                               function=self.analyse,
                                               function_args={'plot': 'plotAngularMassYields'}))
            list_widget.addItem(ListWidgetItem('Angular dependence of reflection coefficients',
                                               indent=1,
                                               function=self.analyse,
                                               function_args={'plot': 'plotAngularReflection'}))
            list_widget.addItem(ListWidgetItem('Angular dependence of implantation depth',
                                               indent=1,
                                               function=self.analyse,
                                               function_args={'plot': 'plotAngularMeanDepth'}))
        else:
            list_widget.addItem(ListWidgetItem('Plot angular dependence (only for "angle sweep")', bold=True, grey=True))
        list_widget.addItemEmpty()

        if nr_energies > 1:
            list_widget.addItem(ListWidgetItem('Plot energy dependence:', bold=True))
            list_widget.addItem(ListWidgetItem('Energy dependence of sputtering yields (atoms/ion)',
                                               indent=1,
                                               function=self.analyse,
                                               function_args={'plot': 'plotEnergySputterYields'}))
            list_widget.addItem(ListWidgetItem('Energy dependence of sputtered mass (amu/ion)',
                                               indent=1,
                                               function=self.analyse,
                                               function_args={'plot': 'plotEnergyMassYields'}))
            list_widget.addItem(ListWidgetItem('Energy dependence of reflection coefficients',
                                               indent=1,
                                               function=self.analyse,
                                               function_args={'plot': 'plotEnergyReflection'}))
            list_widget.addItem(ListWidgetItem('Energy dependence of implantation depth',
                                               indent=1,
                                               function=self.analyse,
                                               function_args={'plot': 'plotEnergyMeanDepth'}))
        else:
            list_widget.addItem(ListWidgetItem('Plot energy dependence (only for "energy sweep")', bold=True, grey=True))
        list_widget.addItemEmpty()

        # trajectories
        trajectories_file = save_folder / 'trajec_all.dat'
        if trajectories_file.is_file() and trajectories_file.stat().st_size > 0:
            list_widget.addItem(ListWidgetItem('Plot particle trajectories:', bold=True))
            list_widget.addItem(ListWidgetItem('Trajectories of projectiles and recoils',
                                               indent=1,
                                               function=self.analyse,
                                               function_args={'plot': 'plotTrajectories',
                                                              'plot_args': self.trajectory_args,
                                                              'hide': False}))
        else:
            list_widget.addItem(ListWidgetItem('Plot particle trajectories (only with trajectory output)', bold=True, grey=True))
        list_widget.addItemEmpty()

        # distributions in the target and matrices of the output
        self.listDistributions(save_folder, list_widget)

        # reflected projectiles and sputtered recoils
        back_p_exists = (save_folder / 'partic_back_p.dat').is_file()
        back_r_exists = (save_folder / 'partic_back_r.dat').is_file()

        if back_p_exists or back_r_exists:
            list_widget.addItem(ListWidgetItem('Plot secondary particle distributions:', bold=True))

            for i, element in enumerate(self.analysis.elements):
                if back_p_exists:
                    list_widget.addItem(ListWidgetItem(f'Backscattered {element} ions',
                                                       indent=1,
                                                       function=self.analyse,
                                                       function_args={'plot': 'plotPolar',
                                                                      'plot_args': {'element': i, 'particle': Particle.Projectile}}))
                if back_r_exists:
                    list_widget.addItem(ListWidgetItem(f'Backsputtered {element} recoil atoms',
                                                       indent=1,
                                                       function=self.analyse,
                                                       function_args={'plot': 'plotPolar',
                                                                      'plot_args': {'element': i, 'particle': Particle.Recoil}}))
            list_widget.addItemEmpty()

            if back_p_exists:
                list_widget.addItem(ListWidgetItem('Polar angles of backscattered ions',
                                                   indent=1,
                                                   function=self.analyse,
                                                   function_args={'plot': 'plotParticlesPolarP'}))
            if back_r_exists:
                list_widget.addItem(ListWidgetItem('Polar angles of backsputtered recoils',
                                                   indent=1,
                                                   function=self.analyse,
                                                   function_args={'plot': 'plotParticlesPolarR'}))
            list_widget.addItemEmpty()

            if back_p_exists:
                list_widget.addItem(ListWidgetItem('Energy of backscattered ions',
                                                   indent=1,
                                                   function=self.analyse,
                                                   function_args={'plot': 'plotParticlesEnergyP',
                                                                  'hide': False}))
            if back_r_exists:
                list_widget.addItem(ListWidgetItem('Energy of backsputtered recoils',
                                                   indent=1,
                                                   function=self.analyse,
                                                   function_args={'plot': 'plotParticlesEnergyR',
                                                                  'hide': False}))
            list_widget.addItemEmpty()

        else:
            list_widget.addItem(ListWidgetItem('Plot secondary particle distributions (only with additional output options)', bold=True, grey=True))


class SimulationAnalysis(SimulationsAnalysis):
    """
    Class for calculating SDTrimSP specific parameters and plots
    """

    # plots that can be compared between several simulations
    ComparablePlots = {
        'plotImplantationDepth': 'Implantation depth',
        'plotEnergyLossDepth': 'Projectile energy loss',
        'plotVacanciesDepth': 'Ion-induced damages',
        'plotParticlesEnergyP': 'Energy of backscattered ions',
        'plotParticlesEnergyR': 'Energy of backsputtered recoils',
        'plotParticlesPolarP': 'Polar angles of backscattered ions',
        'plotParticlesPolarR': 'Polar angles of backsputtered recoils',
        'plotSputterYields': 'Sputter yields over fluence (dynamic)',
        'plotSputterYieldsTotal': 'Total sputter yield over fluence (dynamic)',
        'plotSurfaceLevel': 'Surface level over fluence (dynamic)',
        'plotReflectionCoefficients': 'Reflection coefficients over fluence (dynamic)',
        'plotAngularSputterYields': 'Sputter yields over the angle (angle sweep)',
        'plotEnergySputterYields': 'Sputter yields over the energy (energy sweep)',
    }

    def loadFolder(self, save_folder: Path) -> bool:
        """Reads the general information of the output in a folder (E0_31_target.dat)"""

        self.reset()
        for info_file in ('E0_31_target.dat', 'E0_31_target001.dat'):
            if (save_folder / info_file).is_file():
                self.updateData(save_folder, info_file)
                return bool(self.elements)
        self.save_folder = save_folder
        return False

    def summary(self) -> Dict[str, Dict[str, float]]:
        """
        Returns the main results of the simulation in the folder of loadFolder as {quantity: {species or "total": value}}.
        Static simulations: yields, coefficients, depths and energy losses; dynamic simulations: the values at the end
        """

        result: Dict[str, Dict[str, float]] = {}

        def add(quantity: str, values, total=None, skip_zero: bool = True):
            entries = {}
            for element, value in zip(self.elements, values):
                if not skip_zero or value:
                    entries[str(element)] = float(value)
            if total is not None:
                entries['total'] = float(total)
            if entries:
                result[quantity] = entries

        if not self.is_dynamic and self.save_folder is not None and (self.save_folder / 'output.dat').is_file():
            data = self.getOutputFileData()
            if data is None:
                return result
            (sputter_yields, total_sputter_yield, amu_sputter_yield, reflection_coefficients, implantation_depth,
             energy_loss_nuclear, energy_loss_electron, transmission_sputter_yields, total_transmission_sputter_yield,
             amu_transmission_sputter_yield, transmission_coefficients) = data
            add('Sputter yield [atoms/ion]', sputter_yields, total_sputter_yield)
            add('Mass sputter yield [amu/ion]', [], amu_sputter_yield)
            add('Reflection coefficient', reflection_coefficients)
            add('Mean implantation depth [Å]', implantation_depth)
            add('Nuclear energy loss [eV]', energy_loss_nuclear)
            add('Electronic energy loss [eV]', energy_loss_electron)
            if np.any(transmission_coefficients) or np.any(transmission_sputter_yields):
                add('Transmission coefficient', transmission_coefficients)
                add('Transmission sputter yield [atoms/ion]', transmission_sputter_yields, total_transmission_sputter_yield)
            return result

        data = self.getE031TargetData()
        if data is not None:
            fluence_array, sputtered_yield, amu_yield, reflected_yield, reemitted_yield, surface_conc, surface, _, _ = data
            if len(fluence_array) > 1:
                add('Sputter yield [atoms/ion]', sputtered_yield[-1], np.sum(sputtered_yield[-1]))
                add('Mass sputter yield [amu/ion]', [], amu_yield[-1])
                add('Reflection coefficient', reflected_yield[-1])
                add('Surface atomic fraction', surface_conc[-1], skip_zero=False)
                result['Surface level [Å]'] = {'total': float(surface[-1])}
                result['Fluence [10^20 ions/m²]'] = {'total': float(fluence_array[-1])}
        return result
    
    def __init__(self, element_data: Elements):
        super().__init__(element_data)

        self.is_dynamic = False

        self.particle_back_p_data = np.array([])
        self.particle_back_r_data = np.array([])

        self.fluence_array: Optional[np.ndarray] = None
        self.depth_array: Optional[np.ndarray] = None
        self.conc_array: Optional[np.ndarray] = None

        # TODO: move this to general <Simulations.py>
        self.particle: Particle = Particle.Projectile
        self.particle_data: Optional[List[np.ndarray]] = None

        # trajectories (cached with the modification time of the file)
        self.trajectories: List[dict] = []
        self.trajectories_file: Optional[Tuple[Path, float]] = None
        
    def reset(self):
        """Reset class"""

        super().reset()

        self.is_dynamic = False

        self.particle_back_p_data = np.array([])
        self.particle_back_r_data = np.array([])

        self.fluence_array = None
        self.depth_array = None
        self.conc_array = None
        
    def updateData(self, save_folder: Path, file: str):
        """
        Update evaluation data from file

        :param save_folder: path to save folder
        :param file: target file
        """

        target = save_folder / file

        # data from target file
        self.save_folder = save_folder
        try:
            with open(target, 'r', encoding='utf-8', errors='replace') as target_file:
                for i in range(4):
                    target_file.readline()
                contents = target_file.readline().split()
                ncp = int(contents[2])
                self.is_dynamic = int(contents[-1]) == 0
                elements_raw = target_file.readline().split()

        except FileNotFoundError:
            logging.info(f'Could not open file "{target}"!')
            return

        # check if both are equal
        if ncp != len(elements_raw):
            return

        elements = []
        for element in elements_raw:
            split = element.split('_')
            if len(split) == 1 or not split[-1].isnumeric():
                elements.append(element)
                continue
            elements.append('_'.join(element.split('_')[:-1]))

        self.elements = ElementList()
        for element in elements:
            self.elements.append(element)

        self.masses = np.array([self.elementMass(element) for element in elements])

    # masses of the isotopes of hydrogen [amu], which are not in the default elements (without the tables of SDTrimSP)
    ISOTOPE_MASSES = {'D': 2.014102, 'T': 3.016049}

    def elementMass(self, symbol: str) -> float:
        """Returns the atomic mass of an element (NaN if unknown, e.g. without the tables of SDTrimSP)"""

        element = self.element_data.elementFromSymbol(symbol)
        if element is not None:
            return element.atomic_mass
        return self.ISOTOPE_MASSES.get(symbol, float('nan'))

    def getElementIndex(self, element: str) -> int:
        """Returns index of element"""
        if element not in self.elements:
            return 0
        return self.elements.index(element)
    
    def getOutputFileData(self) -> Optional[tuple]:
        """
        Return the output.dat file data

        :return: Tuple(
                    sputter_yields,
                    total_sputter_yield,
                    amu_sputter_yield,
                    reflection_coefficients,

                    implantation_depth,
                    energy_loss_nuclear,
                    energy_loss_electron,

                    transmission_sputter_yields,
                    total_transmission_sputter_yield,
                    amu_transmission_sputter_yield,
                    transmission_coefficients
                 )
                 or None
        """

        if not self.save_folder:
            return None

        output = self.save_folder / 'output.dat'

        try:
            with open(output, 'r', encoding='utf-8', errors='replace') as file:
                content = [line.strip('# ').lower() for line in file.readlines()]

        except FileNotFoundError:
            logging.info(f'Could not open file "{output}"!')
            return None

        # simulation results
        ncp = len(self.elements)
        nr_calc_total = 1
        masses = np.zeros(ncp)
        beam_comp = np.ones(ncp) / ncp
        sputter_yields = np.zeros(ncp)
        energy_loss_nuclear = np.zeros(ncp)
        energy_loss_electron = np.zeros(ncp)
        implantation_depth = np.zeros(ncp)
        reflection_coefficients = np.zeros(ncp)
        transmission_coefficients = np.zeros(ncp)
        transmission_sputter_yields = np.zeros(ncp)

        # flags for faster loop
        flag_done_masses = False
        flag_done_particles = False
        flag_done_ratios = False
        flag_done_energy_loss = False
        flag_done_implantation = False
        flag_done_reflection = False
        flag_done_yields = False
        flag_done_transmission = False
        flag_done_transmission_yields = False

        # get data from content
        for i, line in enumerate(content):
            if not line:
                continue

            # masses
            if not flag_done_masses:
                if line.startswith('cpt ') and 'a-mass' in line:
                    for j in range(ncp):
                        try:
                            masses[j] = float(content[i + j + 1].split()[3])
                        except (ValueError, IndexError):
                            pass

                    flag_done_masses = True

            # number of particles
            if not flag_done_particles:
                if line.startswith('nh '):
                    try:
                        line_content = content[i + 1].split()
                        nr_calc_total = int(line_content[0]) * int(line_content[1])
                    except (ValueError, IndexError):
                        pass

                    flag_done_particles = True

            # ratios of elements
            if not flag_done_ratios:
                if line.startswith('cpt ') and 'q-beam' in line:
                    for j in range(ncp):
                        try:
                            beam_comp[j] = float(content[i + j + 1].split()[2])
                        except (ValueError, IndexError):
                            pass

                    flag_done_ratios = True

            # projectile energy loss
            # (needs to be modified afterwards, since it depends on nr_calc_total and beam_comp)
            if not flag_done_energy_loss:
                if line.startswith('energy losses (projectiles:'):
                    for j in range(ncp):
                        if not content[i + j + 3]:
                            break

                        try:
                            line_content = content[i + j + 3].split()
                            energy_loss_nuclear[j] = float(line_content[1])
                            energy_loss_electron[j] = float(line_content[2])
                        except (ValueError, IndexError):
                            pass

                    flag_done_energy_loss = True

            # projectile implantation depth
            if not flag_done_implantation:
                if line.startswith('implantation data (projectiles'):
                    for j in range(ncp):
                        if not content[i + j + 4]:
                            break

                        try:
                            implantation_depth[j] = float(content[i + j + 4].split()[1])
                        except (ValueError, IndexError):
                            pass

                    flag_done_implantation = True

            # reflection coefficients
            if not flag_done_reflection:
                if line.startswith('reflection data (backsc'):
                    for j in range(ncp):
                        if not content[i + j + 4] or content[i + j + 4].startswith('all'):
                            break

                        try:
                            reflection_coefficients[j] = float(content[i + j + 4].split()[1])
                        except (ValueError, IndexError):
                            pass
                    flag_done_reflection = True

            # sputtering yields
            if not flag_done_yields:
                if line.startswith('sputtering'):
                    if not content[i + 1].startswith('no'):
                        for j in range(ncp):
                            try:
                                sputter_yields[j] = float(content[i + j + 4].split()[1])
                            # except also leaved sputter_yields[j] set to 0 if 'no backward sputtering'
                            except (ValueError, IndexError):
                                pass

                    flag_done_yields = True

            # transmission coefficients
            if not flag_done_transmission:
                if line.startswith('transmission data'):
                    if not content[i + 1].startswith('no'):
                        for j in range(ncp):
                            if not content[i + j + 4] or content[i + j + 4].startswith('all'):
                                break

                            try:
                                transmission_coefficients[j] = float(content[i + j + 4].split()[1])
                            except (ValueError, IndexError):
                                pass

                    flag_done_transmission = True

            # transmission sputtering yields
            if not flag_done_transmission_yields:
                if line.startswith('transmission sputtering'):
                    if not content[i + 1].startswith('no'):
                        for j in range(ncp):
                            try:
                                transmission_sputter_yields[j] = float(content[i + j + 4].split()[1])
                            # except also leaved transmission_sputter_yields[j] set to 0 if 'no backward sputtering'
                            except (ValueError, IndexError):
                                pass

                    flag_done_transmission_yields = True

        # modify projectile energy loss
        for j in range(ncp):
            if not beam_comp[j]:
                energy_loss_nuclear[j] = 0
                energy_loss_electron[j] = 0

            else:
                factor = nr_calc_total * beam_comp[j]
                energy_loss_nuclear[j] /= factor
                energy_loss_electron[j] /= factor

        # additional calculations
        total_sputter_yield = np.sum(sputter_yields)
        total_transmission_sputter_yield = np.sum(transmission_sputter_yields)
        amu_sputter_yield = np.dot(masses, sputter_yields)
        amu_transmission_sputter_yield = np.dot(masses, transmission_sputter_yields)

        self.masses = masses

        return (
            sputter_yields,
            total_sputter_yield,
            amu_sputter_yield,
            reflection_coefficients,

            implantation_depth,
            energy_loss_nuclear,
            energy_loss_electron,

            transmission_sputter_yields,
            total_transmission_sputter_yield,
            amu_transmission_sputter_yield,
            transmission_coefficients
        )

    def getSerieFileData(self) -> Optional[Tuple[int, int, List[str], List[str], np.ndarray, int, int, int, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]]:
        """
        Return the serie.dat file data

        :return: Tuple(
                    ncp,
                    ncp_proj,
                    elements,
                    elements_projectiles,
                    masses,

                    nr_energies,
                    nr_angles,
                    nr_total,

                    energies,
                    angles,
                    mean_depth,
                    refl_coefficients,
                    energ_refl_coefficients,
                    sputt_coefficients,
                    energ_sputt_coefficients,
                    i
                 )
                 or None
        """

        if not self.save_folder:
            return None

        serie = self.save_folder / 'serie.dat'

        try:
            with open(serie, 'r', encoding='utf-8', errors='replace') as file:
                file.readline()

                # line 2: ncp and ncp_proj
                line_content = file.readline().strip('#').split()
                ncp = int(line_content[0])
                ncp_proj = int(line_content[1])

                # line 4: elements (wrapped to the next lines for many elements, e.g. 11), up to the header "CPT A-Z A-MASS ..."
                # (with "#" since 7.00)
                element_text = ''
                line = file.readline()
                while line and not line.strip().lstrip('#').strip().upper().startswith('CPT'):
                    if 'elements:' in line:
                        element_text = line.split('elements:', 1)[1]
                    elif element_text:
                        element_text += ' ' + line.strip('#')
                    line = file.readline()
                elements = element_text.split()[-ncp:]

                # ncp lines of element data
                masses = np.zeros(ncp)
                for i in range(ncp):
                    masses[i] = float(file.readline().split()[2])

                # skip lines starting with '!'
                line = file.readline()
                while line.strip().startswith('!') or line.strip().startswith('#'):
                    line = file.readline()

                # line (6+ncp+offset)+0 / +1: number energies / number angles
                nr_energies = int(line.split()[0])
                nr_angles = int(file.readline().split()[0])
                nr_total = nr_angles * nr_energies

                for _ in range(4):
                    file.readline()

                # line (6+ncp+offset)+6: elements list
                elements_projectiles = []
                line_elements = file.readline().strip('#').split()
                for i in range(ncp_proj):
                    elements_projectiles.append(line_elements[2 * i])

                energies = np.zeros(nr_total)
                angles = np.zeros(nr_total)
                mean_depth = np.zeros(nr_total)
                refl_coefficients = np.zeros((nr_total, ncp_proj))
                energ_refl_coefficients = np.zeros((nr_total, ncp_proj))
                sputt_coefficients = np.zeros((nr_total, ncp))
                energ_sputt_coefficients = np.zeros((nr_total, ncp))

                expected_line_elements = 3 + 2 * ncp_proj + 2 * ncp

                for i in range(nr_total):
                    values = file.readline().split()

                    if not values:
                        break

                    while len(values) < expected_line_elements:
                        values.extend(file.readline().split())

                    energies[i] = values[0]
                    angles[i] = values[1]
                    mean_depth[i] = values[2]

                    for j in range(ncp_proj):
                        refl_coefficients[i, j] = floatSafe(values[3 + 2 * j], 0)
                        energ_refl_coefficients[i, j] = floatSafe(values[3 + 2 * j + 1], 0)
                    for j in range(ncp):
                        sputt_coefficients[i, j] = floatSafe(values[3 + 2 * ncp_proj + 2 * j], 0)
                        energ_sputt_coefficients[i, j] = floatSafe(values[3 + 2 * ncp_proj + 2 * j + 1], 0)

        except FileNotFoundError:
            logging.info(f'Could not open file "{serie}"!')
            return None

        return (
            ncp,
            ncp_proj,
            elements,
            elements_projectiles,
            masses,

            nr_energies,
            nr_angles,
            nr_total,

            energies,
            angles,
            mean_depth,
            refl_coefficients,
            energ_refl_coefficients,
            sputt_coefficients,
            energ_sputt_coefficients,
            i
        )

    def getDepthFileData(self, filename: str) -> Optional[Tuple[int, List[str], np.ndarray, int, np.ndarray, np.ndarray]]:
        """
        Returns content from the specified depth file

        :param filename: file name of depth file

        :return: Tuple(
                    ncp,
                    file_elements,
                    nr_of_depth_steps,
                    max_nr_depth_steps,
                    nr_of_projectiles,
                    depth_data
                 )

                 or None
        """

        if not self.save_folder:
            return None

        depth_file = self.save_folder / filename

        try:
            with open(depth_file, 'r', encoding='utf-8', errors='replace') as file:
                content = [line.strip('# ').lower() for line in file.readlines() if line.strip()]

        except FileNotFoundError:
            logging.info(f'Could not open file "{depth_file}"!')
            return None

        # number of elements
        ncp = int(content[2].split()[0])

        nr_of_depth_steps = np.zeros(ncp, dtype=int)
        nr_of_projectiles = np.zeros(ncp, dtype=int)
        data_start_line = np.zeros(ncp, dtype=int)
        file_elements = []

        j = 0
        for i in range(ncp):
            while not content[j].startswith('depth distribution'):
                j += 1
            file_elements.append(content[j].split()[-1].capitalize())
            data_start_line[i] = j + 4
            line_content = content[j + 1].split()
            nr_of_depth_steps[i] = int(line_content[0])
            nr_of_projectiles[i] = int(float(line_content[1]))
            j += 1

        max_nr_depth_steps = np.max(nr_of_depth_steps)
        nr_of_columns = len(content[data_start_line[0]].split())
        depth_data = np.zeros((ncp, max_nr_depth_steps, nr_of_columns))

        for i in range(ncp):
            for j in range(nr_of_depth_steps[i]):
                line = content[data_start_line[i] + j].split()
                for k in range(nr_of_columns):
                    depth_data[i, j, k] = float(line[k])

        return (
            ncp,
            file_elements,
            nr_of_depth_steps,
            max_nr_depth_steps,
            nr_of_projectiles,
            depth_data
        )

    def getDamageDepthFileData(self, filename: str) -> Optional[Tuple[int, List[str], np.ndarray, int, int, np.ndarray]]:
        """
        Returns content from the specified depth damage file

        :param filename: file name of depth damage file

        :return: Tuple(
                    ncp,
                    file_elements,
                    nr_of_depth_steps,
                    max_nr_depth_steps,
                    nr_of_projectiles,
                    depth_data
                 )

                 or None
        """


        if not self.save_folder:
            return None

        damage_file = self.save_folder / filename

        try:
            with open(damage_file, 'r', encoding='utf-8', errors='replace') as file:
                content = []
                depth_step_index = []
                for i, line in enumerate(file.readlines()):
                    content.append(line.strip('# ').lower())
                    if content[i].endswith('number of depth\n'):
                        depth_step_index.append(i)

        except FileNotFoundError:
            logging.info(f'Could not open file "{filename}"!')
            return None

        try:
            line_content = content[2].split()
            ncp = int(line_content[0])
            nr_of_projectiles = int(float(line_content[1]))

            nr_of_depth_steps = np.zeros(ncp, dtype=int)
            data_start_line = np.zeros(ncp, dtype=int)

            for i in range(ncp):
                data_start_line[i] = depth_step_index[i] + 3

                if '->' in content[data_start_line[i]]:
                    data_start_line[i] = data_start_line[i] + 1

                nr_of_depth_steps[i] = int(content[depth_step_index[i]].split()[0])

            file_elements = []
            for i in range(ncp):
                element_line_index = data_start_line[i] + nr_of_depth_steps[i] + 2
                #element_line_index = 2 + i * (4 + 1 + 5) + int(np.sum(nr_of_depth_steps[:i])) + 1
                file_elements.append(content[element_line_index].split()[-1].capitalize())

            max_nr_depth_steps = np.max(nr_of_depth_steps)
            nr_of_columns = len(content[data_start_line[0]].split())
            depth_data = np.zeros((ncp, max_nr_depth_steps, nr_of_columns))

            for i in range(ncp):
                for j in range(nr_of_depth_steps[i]):
                    line_content = content[data_start_line[i] + j].split()
                    for k in range(nr_of_columns):
                        depth_data[i, j, k] = float(line_content[k])

            return (
                ncp,
                file_elements,
                nr_of_depth_steps,
                max_nr_depth_steps,
                nr_of_projectiles,
                depth_data
            )

        except (IndexError, ValueError):
            logging.warning(f'Could not process file "{filename}"!')
            return None

    def getTrajectories(self) -> List[dict]:
        """Returns the trajectories of trajec_all.dat in the save folder (see readTrajectoryFile)"""

        if self.save_folder is None:
            return []
        path = self.save_folder / 'trajec_all.dat'
        try:
            key = (path, path.stat().st_mtime)
        except OSError:
            return []
        if key != self.trajectories_file:
            self.trajectories = readTrajectoryFile(path)
            self.trajectories_file = key
        return self.trajectories

    def plotTrajectories(
        self,
        projectile: int = 1,
        view: str = 'y',
        color: str = 'species',
        recoils: bool = True,
        layers: bool = True,
        time_fraction: Optional[float] = None,
        **_
    ) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """
        Plot and return the trajectories of one projectile and its recoils.
        Each species has its own color, recoils of later generations of the collision cascade are darker.
        Alternatively the trajectories are colored by the energy or the time

        :param projectile: number of the projectile (starting at 1)
        :param view: 'y' (depth - lateral y), 'z' (depth - lateral z), 'both' (both side by side), 'top' (lateral y - lateral z) or '3d'
        :param color: 'species' (species and generation), 'energy' or 'time'
        :param recoils: show the recoils
        :param layers: show the layers of the target
        :param time_fraction: (optional) show the cascade until this time (animation) between 0 (start) and 1 (end), None shows
                              everything. The time scale is logarithmic, as the slow recoils at the end of a cascade take much longer
                              than the fast particles at the beginning
        """

        mpl_settings = MplCanvasSettings()
        trajectories = self.getTrajectories()
        projectiles = list(dict.fromkeys(trajectory['projectile'] for trajectory in trajectories))
        self.emit({
            'hide_trajectories': False,
            'max_trajectories': max(1, len(projectiles))
        })
        if not projectiles:
            mpl_settings.axes.set_title('No trajectories found')
            return None, mpl_settings

        projectile = max(1, min(int(projectile), len(projectiles)))
        selected = projectiles[projectile - 1]
        shown = [
            trajectory for trajectory in trajectories
            if trajectory['projectile'] == selected and len(trajectory['points']) and (recoils or not trajectory['recoil'])
        ]
        generation_known = all(trajectory.get('generation_known', True) for trajectory in shown)
        max_generation = max([trajectory['generation'] for trajectory in shown if trajectory['recoil']], default=0)
        all_points = np.vstack([trajectory['points'] for trajectory in shown])

        # time of the animation frame (logarithmic from the first collision to the end of the cascade)
        end_time = float(np.max(all_points[:, 4]))
        time = None
        if time_fraction is not None and float(time_fraction) < 1:
            positive_times = all_points[:, 4][all_points[:, 4] > 0]
            start_time = max(float(positive_times.min()) if positive_times.size else end_time, end_time * 1e-6, 1e-12)
            time = 0. if float(time_fraction) <= 0 else start_time * (max(end_time, start_time) / start_time) ** float(time_fraction)

        # visible part of each trajectory at this time and the current positions of the moving particles
        parts: List[Tuple[dict, np.ndarray]] = []
        heads: List[Tuple[dict, np.ndarray]] = []
        for trajectory in shown:
            points = trajectory['points']
            if time is not None:
                if points[0, 4] > time:
                    continue
                visible = points[points[:, 4] <= time]
                if len(visible) < len(points):
                    previous, following = visible[-1], points[len(visible)]
                    duration = following[4] - previous[4]
                    head = previous + ((time - previous[4]) / duration if duration > 0 else 1.) * (following - previous)
                    visible = np.vstack([visible, head])
                    heads.append((trajectory, head))
                points = visible
            parts.append((trajectory, points))

        def speciesName(species: int) -> str:
            return str(self.elements[species]) if 0 <= species < len(self.elements) else f'Species {species + 1}'

        # colors: species (projectiles and recoils), later generations are darker
        def shade(generation: int) -> float:
            return 0.6 * (generation - 1) / (max_generation - 1) if max_generation > 1 else 0.

        def trajectoryColor(trajectory: dict) -> np.ndarray:
            base = np.array(to_rgb(self.colors[trajectory['species']]))
            if not trajectory['recoil'] or not generation_known:
                return base
            return base * (1 - shade(trajectory['generation']))

        # colors: energy or time
        value_column = {'energy': 3, 'time': 4}.get(color)
        norm: Optional[Normalize] = None
        colormap, value_label = None, ''
        if value_column == 3:
            energies = all_points[:, 3][all_points[:, 3] > 0]
            vmax = float(energies.max()) if energies.size else 1.
            vmin = max(float(energies.min()) if energies.size else 1e-2, vmax * 1e-5)
            norm = LogNorm(vmin=vmin, vmax=max(vmax, vmin * 10))
            colormap, value_label = paletteColormap(), 'Energy [eV]'
        elif value_column == 4:
            norm = Normalize(vmin=0, vmax=max(end_time, 1e-9))
            colormap, value_label = paletteColormap(), 'Time [fs]'

        def segmentValues(points: np.ndarray) -> np.ndarray:
            values = points[:-1, value_column]
            return np.clip(values, notNone(norm).vmin, None) if value_column == 3 else values

        # ranges of all trajectories (constant during the animation), the layers are only drawn in the depth range
        margin = 0.05 * max(float(np.max(np.ptp(all_points[:, :3], axis=0))), 1.)
        lower = np.minimum(all_points[:, :3].min(axis=0), [0., 0., 0.]) - margin
        upper = all_points[:, :3].max(axis=0) + margin
        layer_list = [
            (max(top, lower[0]), min(bottom, upper[0]), name)
            for top, bottom, name in (readLayers(notNone(self.save_folder)) if layers and view != 'top' else [])
            if bottom > lower[0] and top < upper[0]
        ]
        layer_names = list(dict.fromkeys(name for _, _, name in layer_list))

        def layerColor(name: str) -> str:
            return layerHex(layer_names.index(name))

        axis_labels = ['Depth x [Å]', 'Lateral position y [Å]', 'Lateral position z [Å]']

        def draw2d(axes, horizontal: int, vertical: int):
            if vertical == 0:
                for top, bottom, name in layer_list:
                    axes.axhspan(top, bottom, color=layerColor(name), alpha=0.2, linewidth=0, zorder=0)
                axes.axhline(0, color='#7f7f7f', linewidth=1, zorder=1)

            if value_column is None:
                # all trajectories of a species and generation in one line, separated by nan
                groups: Dict[tuple, List[np.ndarray]] = {}
                for trajectory, points in parts:
                    key = (trajectory['generation'], trajectory['species'])
                    groups.setdefault(key, []).append(np.vstack([points[:, [horizontal, vertical]], [np.nan, np.nan]]))
                for (generation, species), segments in sorted(groups.items()):
                    trajectory = next(t for t, _ in parts if t['generation'] == generation and t['species'] == species)
                    lines = np.vstack(segments)
                    axes.plot(lines[:, 0], lines[:, 1], color=trajectoryColor(trajectory), linewidth=1.6 if generation == 0 else 0.9,
                              zorder=3 - generation / (max_generation + 1))
            else:
                segments, values, widths = [], [], []
                for trajectory, points in parts:
                    if len(points) < 2:
                        continue
                    xy = points[:, [horizontal, vertical]]
                    segments += list(np.stack([xy[:-1], xy[1:]], axis=1))
                    values += list(segmentValues(points))
                    widths += [1.6 if not trajectory['recoil'] else 0.9] * (len(points) - 1)
                if segments:
                    collection = LineCollection(segments, cmap=colormap, norm=norm, linewidths=widths, zorder=2)
                    collection.set_array(np.array(values))
                    axes.add_collection(collection)

            if heads:
                axes.scatter([head[horizontal] for _, head in heads], [head[vertical] for _, head in heads],
                             color=[trajectoryColor(t) for t, _ in heads], s=14, zorder=5, edgecolors='none')

            axes.set_xlim(lower[horizontal], upper[horizontal])
            axes.set_ylim(upper[vertical], lower[vertical]) if vertical == 0 else axes.set_ylim(lower[vertical], upper[vertical])
            axes.set_xlabel(axis_labels[horizontal])
            axes.set_ylabel(axis_labels[vertical])
            axes.set_aspect('equal', adjustable='box')

        def draw3d(axes):
            for top, bottom, name in layer_list:
                for depth in (top, bottom):
                    corners = [(lower[1], lower[2], depth), (upper[1], lower[2], depth), (upper[1], upper[2], depth), (lower[1], upper[2], depth)]
                    axes.add_collection3d(Poly3DCollection([corners], facecolor=layerColor(name), alpha=0.12, edgecolor='none'))

            if value_column is None:
                for trajectory, points in parts:
                    axes.plot(points[:, 1], points[:, 2], points[:, 0], color=trajectoryColor(trajectory),
                              linewidth=1.6 if not trajectory['recoil'] else 0.9)
            else:
                segments, values = [], []
                for trajectory, points in parts:
                    if len(points) < 2:
                        continue
                    xyz = points[:, [1, 2, 0]]
                    segments += list(np.stack([xyz[:-1], xyz[1:]], axis=1))
                    values += list(segmentValues(points))
                if segments:
                    collection = Line3DCollection(segments, cmap=colormap, norm=norm, linewidths=1)
                    collection.set_array(np.array(values))
                    axes.add_collection3d(collection)

            if heads:
                axes.scatter([head[1] for _, head in heads], [head[2] for _, head in heads], [head[0] for _, head in heads],
                             color=[trajectoryColor(t) for t, _ in heads], s=14, depthshade=False)

            axes.set_xlim(lower[1], upper[1])
            axes.set_ylim(lower[2], upper[2])
            axes.set_zlim(upper[0], lower[0])
            ranges = np.maximum(upper - lower, 1e-9)
            ranges = np.maximum(ranges, 0.15 * ranges.max())
            axes.set_box_aspect((ranges[1], ranges[2], ranges[0]))
            axes.set_xlabel(axis_labels[1])
            axes.set_ylabel(axis_labels[2])
            axes.set_zlabel(axis_labels[0])

        legend_axes = mpl_settings.axes
        if view == '3d':
            mpl_settings.fig.add_subplot(projection='3d')
            draw3d(mpl_settings.axes)
        elif view == 'both':
            mpl_settings.fig.add_subplot(1, 2, 1)
            draw2d(mpl_settings.axes, 1, 0)
            legend_axes = mpl_settings.addAxes(1, 2, 2)
            draw2d(legend_axes, 2, 0)
        elif view == 'top':
            draw2d(mpl_settings.axes, 1, 2)
        else:
            draw2d(mpl_settings.axes, 2 if view == 'z' else 1, 0)
        colorbar_axes = 1 if view == 'both' else 0

        # legend: species of the projectile and the recoils, layers
        handles: List[Artist] = []
        if value_column is None:
            for recoil in (False, True):
                for species in sorted({t['species'] for t, _ in parts if t['recoil'] == recoil}):
                    handles.append(Line2D([], [], color=to_rgb(self.colors[species]), linewidth=1.6 if not recoil else 0.9,
                                          label=f'{speciesName(species)} {"recoils" if recoil else "projectile"}'))
        for name in layer_names:
            handles.append(Patch(facecolor=layerColor(name), alpha=0.3 if view != '3d' else 0.2, label=name))
        if handles:
            legend_axes.legend(handles=handles, fontsize='small')

        # colorbar: generation (white to black as the recoils get darker), energy or time
        if value_column is not None:
            mpl_settings.colorbar(ScalarMappable(norm=norm, cmap=colormap), axes_index=colorbar_axes, label=value_label, shrink=0.8)
        elif max_generation > 0 and generation_known:
            grays = [(1 - shade(generation),) * 3 for generation in range(1, max_generation + 1)]
            generation_norm = BoundaryNorm(np.arange(0.5, max_generation + 1.5), max_generation)
            mpl_settings.colorbar(
                ScalarMappable(norm=generation_norm, cmap=ListedColormap(grays)),
                axes_index=colorbar_axes,
                label='Recoil generation',
                ticks=MaxNLocator(integer=True, nbins=min(max_generation, 10)),
                shrink=0.8
            )

        title = f'Trajectories of projectile {projectile} of {len(projectiles)}'
        if time is not None:
            title += f', t = {time:.4g} fs'
        if view == 'both':
            mpl_settings.fig.suptitle(title)
        else:
            mpl_settings.axes.set_title(title)

        # export: all points of the shown trajectories
        data_columns: List[list] = [[] for _ in range(9)]
        for number, (trajectory, points) in enumerate(parts, start=1):
            for column, value in enumerate([number, trajectory['generation'], trajectory['species'] + 1, int(trajectory['recoil'])]):
                data_columns[column] += [value] * len(points)
            for column, index in enumerate([0, 1, 2, 3, 4], start=4):
                data_columns[column] += list(points[:, index])
        labels = ['Trajectory', 'Generation', 'Species', 'Recoil', 'x [Å]', 'y [Å]', 'z [Å]', 'Energy [eV]', 'Time [fs]']
        return ([np.array(column, dtype=float) for column in data_columns], labels), mpl_settings

    # kinds of the energy distribution in the target (lenergy_distr): file name and title
    EnergyDistributions = {
        'all': ('E_distr_all.dat', 'Deposited energy (stopped particles, electronic and nuclear losses)'),
        'stop': ('E_distr_stop.dat', 'Energy of the stopped particles'),
        'inel': ('E_distr_inel.dat', 'Electronic energy loss'),
        'nucl': ('E_distr_nucl.dat', 'Nuclear energy loss')
    }

    # matrices over energy and depth: file name and (title, label of the depth)
    EnergyDepthMatrices = {
        'mpe_ex_p.dat': ('Maximum penetration depth of backscattered projectiles', 'Maximum penetration depth [Å]'),
        'morigin_ex_bs.dat': ('Depth of origin of backsputtered atoms', 'Depth of origin [Å]'),
        'morigin_ex_ts.dat': ('Depth of origin of transmission sputtered atoms', 'Depth of origin [Å]')
    }

    # matrices over energy and angles (lmatrices): file name and title
    EnergyAngleMatrices = {
        'meagb_p.dat': 'backscattered projectiles',
        'meagb_s.dat': 'backsputtered atoms',
        'meagt_p.dat': 'transmitted projectiles',
        'meagt_s.dat': 'transmission sputtered atoms'
    }

    def readCached(self, name: str, reader: Callable):
        """Returns the content of a file in the save folder read with reader, cached by the modification time"""

        if self.save_folder is None:
            return None
        path = self.save_folder / name
        try:
            key = (path, path.stat().st_mtime)
        except OSError:
            return None
        cache = self.__dict__.setdefault('file_cache', {})
        if cache.get(name, (None, None))[0] != key:
            cache[name] = (key, reader(path))
        return cache[name][1]

    def plotEnergyDistribution(self, kind: str = 'all', view: str = 'y', log: bool = False, **_) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """
        Plot and return the energy distribution in the target (lenergy_distr)

        :param kind: 'all' (deposited energy), 'stop' (energy of stopped particles), 'inel' (electronic loss) or 'nucl' (nuclear loss)
        :param view: 'y' (map over depth and lateral y, summed over z), 'z' (depth and z), 'top' (y and z, summed over the depth)
                     or 'depth' (depth profile, summed over y and z)
        :param log: logarithmic color scale
        """

        mpl_settings = MplCanvasSettings()
        self.emit({'hide_energy_distribution': False})
        name, title = self.EnergyDistributions.get(kind, self.EnergyDistributions['all'])
        distribution = self.readCached(name, readEnergyDistribution)
        if distribution is None:
            mpl_settings.axes.set_title(f'No data found ({name})')
            return None, mpl_settings

        edges = {axis: distribution[axis] for axis in 'xyz'}
        widths = {axis: np.diff(edges[axis]) for axis in 'xyz'}
        centers = {axis: edges[axis][:-1] + widths[axis] / 2 for axis in 'xyz'}
        values = distribution['values']  # (x, y, z) in [eV/Å³/projectile]
        labels = {'x': 'Depth x [Å]', 'y': 'Lateral position y [Å]', 'z': 'Lateral position z [Å]'}

        if view == 'depth':
            profile = np.sum(values * widths['y'][None, :, None] * widths['z'][None, None, :], axis=(1, 2))
            mpl_settings.axes.stairs(profile, edges['x'], color=self.first_color, linewidth=self.line_width)
            mpl_settings.axes.set_xlabel(labels['x'])
            mpl_settings.axes.set_ylabel('Energy [eV/Å/projectile]')
            if log and np.any(profile > 0):
                mpl_settings.axes.set_yscale('log')
            mpl_settings.axes.set_title(title)
            return ([centers['x'], profile], [labels['x'], f'{title} [eV/Å/projectile]']), mpl_settings

        # 2D map: sum over the third axis
        horizontal, vertical, summed = {'y': ('y', 'x', 2), 'z': ('z', 'x', 1), 'top': ('y', 'z', 0)}.get(view, ('y', 'x', 2))
        summed_axis = 'xyz'[summed]
        shape = [1, 1, 1]
        shape[summed] = -1
        mapped = np.sum(values * widths[summed_axis].reshape(shape), axis=summed)
        # mapped has the remaining axes in the order x, y, z
        if 'xyz'.index(horizontal) < 'xyz'.index(vertical):
            mapped = mapped.T
        # mapped: (vertical, horizontal)
        norm = None
        if log and np.any(mapped > 0):
            positive = mapped[mapped > 0]
            norm = LogNorm(vmin=max(float(positive.min()), float(positive.max()) * 1e-6), vmax=float(positive.max()))
            mapped = np.where(mapped > 0, mapped, np.nan)
        mpl_settings.axes.pcolormesh(edges[horizontal], edges[vertical], mapped, cmap=paletteColormap(), norm=norm, shading='flat')
        mpl_settings.axes.pcolormesh_label('Energy [eV/Å²/projectile]')
        if vertical == 'x':
            mpl_settings.axes.set_ylim(edges['x'][-1], edges['x'][0])
        mpl_settings.axes.set_aspect('equal', adjustable='box')
        mpl_settings.axes.set_xlabel(labels[horizontal])
        mpl_settings.axes.set_ylabel(labels[vertical])
        mpl_settings.axes.set_title(f'{title}, summed over {"the depth" if summed_axis == "x" else summed_axis}')

        horizontal_grid, vertical_grid = np.meshgrid(centers[horizontal], centers[vertical])
        return (
            [vertical_grid.ravel(), horizontal_grid.ravel(), np.nan_to_num(mapped).ravel()],
            [labels[vertical], labels[horizontal], 'Energy [eV/Å²/projectile]']
        ), mpl_settings

    def plotEnergyDepthMatrix(self, name: str = 'mpe_ex_p.dat') -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """
        Plot and return the distribution of the depth (summed over the energy) of a matrix over energy and depth
        (mpe_ex_p.dat: maximum penetration depth of backscattered projectiles, morigin_ex_bs.dat, morigin_ex_ts.dat: depth of
        origin of sputtered atoms)

        :param name: name of the file
        """

        mpl_settings = MplCanvasSettings()
        title, depth_label = self.EnergyDepthMatrices.get(name, ('Depth distribution', 'Depth [Å]'))
        matrices = [matrix for matrix in (self.readCached(name, readEnergyDepthMatrix) or []) if np.sum(matrix['counts']) > 0]
        if not matrices:
            mpl_settings.axes.set_title(f'No particles in {name}')
            return None, mpl_settings

        data, labels = [], []
        for i, matrix in enumerate(matrices):
            counts = np.sum(matrix['counts'], axis=0) / max(matrix['projectiles'], 1.)
            # edges of the depth intervals from their centers
            depths = matrix['depths']
            middles = (depths[1:] + depths[:-1]) / 2
            first = depths[0] - (middles[0] - depths[0]) if len(depths) > 1 else depths[0] - 0.5
            last = depths[-1] + (depths[-1] - middles[-1]) if len(depths) > 1 else depths[0] + 0.5
            edges = np.concatenate([[max(first, 0.)], middles, [last]])
            mpl_settings.axes.stairs(counts, edges, color=self.colors[i], linewidth=self.line_width, label=matrix['species'])
            data += [matrix['depths'], counts]
            labels += [f'{depth_label} ({matrix["species"]})', f'Particles per projectile ({matrix["species"]})']
        mpl_settings.axes.set_xlabel(depth_label)
        mpl_settings.axes.set_ylabel('Particles per projectile')
        mpl_settings.axes.set_xlim(left=0)
        mpl_settings.axes.legend()
        mpl_settings.axes.set_title(title)
        return (data, labels), mpl_settings

    def plotEnergyAngleMatrix(self, name: str = 'meagb_p.dat', species: int = 0, log: bool = True) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """
        Plot and return the energy and the polar angle (summed over the azimuthal angle) of backscattered or transmitted
        particles (lmatrices: meagb_p.dat, meagb_s.dat, meagt_p.dat, meagt_s.dat)

        :param name: name of the file
        :param species: index of the species in the file
        :param log: logarithmic color scale
        """

        mpl_settings = MplCanvasSettings()
        matrices = self.readCached(name, readEnergyAngleMatrix) or []
        if not 0 <= species < len(matrices) or np.sum(matrices[species]['counts']) <= 0:
            mpl_settings.axes.set_title(f'No particles in {name}')
            return None, mpl_settings

        matrix = matrices[species]
        counts = matrix['counts'] / max(matrix['projectiles'], 1.)
        # the values in the file are the upper edges of the intervals
        energy_edges = np.concatenate([[0.], matrix['energies']])
        polar_edges = np.concatenate([[0.], matrix['polar']])
        norm = None
        if log:
            positive = counts[counts > 0]
            norm = LogNorm(vmin=float(positive.min()), vmax=float(positive.max()))
            counts = np.where(counts > 0, counts, np.nan)
        mpl_settings.axes.pcolormesh(polar_edges, energy_edges, counts, cmap=paletteColormap(), norm=norm, shading='flat')
        mpl_settings.axes.pcolormesh_label('Particles per projectile')
        mpl_settings.axes.set_xlabel('Polar angle [°]')
        mpl_settings.axes.set_ylabel('Energy [eV]')
        mpl_settings.axes.set_title(f'Energy and polar angle of {self.EnergyAngleMatrices.get(name, name)} ({matrix["species"]})')

        polar_grid, energy_grid = np.meshgrid(matrix['polar'], matrix['energies'])
        return (
            [energy_grid.ravel(), polar_grid.ravel(), np.nan_to_num(counts).ravel()],
            ['Energy (upper edge) [eV]', 'Polar angle (upper edge) [°]', 'Particles per projectile']
        ), mpl_settings

    def getParticleData(self, particle: Particle) -> Optional[List[np.ndarray]]:
        """
        Returns content from particle files

        :param particle: particle to identify if projectile of recoil data should be used

        :return: list of file data per element [species, cosp, cosa, end-energy]
                 or None
        """


        if not self.save_folder:
            return None

        letter_file_name = 'p' if particle == Particle.Projectile else 'r'
        file_path = self.save_folder / f'partic_back_{letter_file_name}.dat'

        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
                for _ in range(4):
                    file.readline()
                line_content = file.readline().strip('#').split()
                if not all(column in line_content for column in ['cosp', 'cosa', 'end-energy']):
                    return None
                cosp_idx = line_content.index('cosp')
                cosa_idx = line_content.index('cosa')
                end_energy_idx = line_content.index('end-energy')

        except FileNotFoundError:
            logging.info(f'Could not open file "{file_path}"!')
            return None

        old_data_len = len(self.particle_back_p_data) if particle == Particle.Projectile else len(self.particle_back_r_data)

        try:
            new_particle_file_data = fileToNpArray(file_path,
                                                   skip_header=5 + old_data_len,
                                                   skip_footer=2,
                                                   usecols=(0, cosp_idx, cosa_idx, end_energy_idx))
        except FileNotFoundError:
            logging.info(f'Could not open file "{file_path}"!')
            return None

        if new_particle_file_data.size:
            # Fix the data shape if just a single line was read
            if new_particle_file_data.ndim == 1:
                new_particle_file_data = new_particle_file_data[np.newaxis, ...]

            if particle == Particle.Projectile:
                if self.particle_back_p_data.size:
                    self.particle_back_p_data = np.append(self.particle_back_p_data, new_particle_file_data, axis=0)
                else:
                    self.particle_back_p_data = new_particle_file_data

            else:
                if self.particle_back_r_data.size:
                    self.particle_back_r_data = np.append(self.particle_back_r_data, new_particle_file_data, axis=0)
                else:
                    self.particle_back_r_data = new_particle_file_data

        particle_file_data = self.particle_back_p_data if particle == Particle.Projectile else self.particle_back_r_data
        if not particle_file_data.size:
            return None

        particle_file_data_per_element = []
        for number in range(len(self.elements)):
            mask = particle_file_data[:, 0] == number + 1
            species_data = particle_file_data[mask, :]
            particle_file_data_per_element.append(species_data[:, 1:])

        return particle_file_data_per_element

    def getE031TargetData(self) -> Optional[Tuple[np.ndarray, ...]]:
        """
        Returns content from E031target

        :return: Tuple(
                    fluence_array,
                    sputtered_yield,
                    amu_yield,
                    reflected_yield,
                    reemitted_yield,
                    surface_conc,
                    surface,
                    depth_array,
                    conc_array
                 )

                 or None
        """

        if not self.save_folder:
            return None

        file_path = self.save_folder / 'E0_31_target.dat'

        if not self.masses.size:
            self.getOutputFileData()

        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
                # skip version header and name of simulation
                for _ in range(2):
                    file.readline()

                # read global parameter headers
                while 'nh ' not in file.readline():
                    pass

                global_pars = file.readline().split()
                maxhist = int(global_pars[0])
                nqx = int(global_pars[1])
                ncp = int(global_pars[2])
                ihist_out = int(global_pars[3])

                # skip element symbols and history step headers
                for _ in range(17):
                    file.readline()

                # for loop over history steps, set up variables that will be plotted
                max_hist_step = int(maxhist / ihist_out) + 1

                fluence_array = np.zeros(max_hist_step)
                surface = np.zeros(max_hist_step)  # surface minimum
                surface_conc = np.zeros((max_hist_step, ncp))
                nr_projectiles_array = np.zeros(max_hist_step)  # number of projectiles
                nr_projectiles_array_per_element = np.zeros((max_hist_step, ncp))  # number of projectiles per element
                nr_reflected = np.zeros((max_hist_step, ncp))  # number of reflected
                nr_sputtered = np.zeros((max_hist_step, ncp))  # number of backsputtered
                nr_reemitted = np.zeros((max_hist_step, ncp))  # number of reemitted projectiles
                conc_array = np.zeros((max_hist_step, ncp, nqx))  # concentration over depth of each element for each history step

                for hist_counter in range(max_hist_step):
                    # read fluence, surface_min, surface_max
                    hist_pars = file.readline().split()[0:2]

                    if not hist_pars:
                        max_hist_step = hist_counter  # adjust max_hist_step
                        # cut arrays for plotting
                        fluence_array = fluence_array[:max_hist_step]
                        surface = surface[:max_hist_step]
                        surface_conc = surface_conc[:max_hist_step]
                        conc_array = conc_array[:max_hist_step]
                        break

                    fluence_array[hist_counter] = float(hist_pars[0])
                    surface[hist_counter] = float(hist_pars[1])

                    # read surface atomic fractions
                    surface_conc[hist_counter, :] = np.array(file.readline().split()[0:ncp]).astype(np.float64)
                    if np.sum(surface_conc[hist_counter]) < 1.:
                        surface_conc[hist_counter, 0] = 1. - np.sum(surface_conc[hist_counter])

                    # skip Momente and areal densitites
                    for _ in range(2):
                        file.readline()

                    # read number of projectiles
                    nr_projectiles_array_per_element[hist_counter, :] = np.array(file.readline().split()[0:ncp]).astype(np.float64)
                    nr_projectiles_array[hist_counter] = np.sum(nr_projectiles_array_per_element[hist_counter, :])

                    # read number of backscattered particles
                    nr_reflected[hist_counter, :] = np.array(file.readline().split()[0:ncp]).astype(np.float64)

                    # skip energy of backscattered particles, and number and energy of transmitted projectiles
                    for _ in range(3):
                        file.readline()

                    # read number of backsputtered particles
                    nr_sputtered[hist_counter, :] = np.array(file.readline().split()[0:ncp]).astype(np.float64)

                    # skip energy of backsputtered particles , and number, energy of transmitted sputtered particles, energy of all projectiles
                    for _ in range(4):
                        file.readline()

                    # read number of reemitted atoms
                    nr_reemitted[hist_counter, :] = np.array(file.readline().split()[0:ncp]).astype(np.float64)

                    # chemical erosion --> not recorded further
                    file.readline()

                    # read two header lines + depth dependent concentrations
                    if not hist_counter:
                        for _ in range(2):
                            file.readline()

                    depth_array = np.zeros(nqx)

                    for i in range(nqx):
                        # f.readline()
                        layer_line = np.array(file.readline().split()).astype(np.float64)
                        depth_array[i] = layer_line[0]
                        # read layer concentrations for all ncp elements
                        for j in range(ncp):
                            conc_array[hist_counter, j, i] = layer_line[j + 2]

        except FileNotFoundError:
            logging.info(f'Could not open file "{file_path}"!')
            return None

        # calculate yields
        reflected_yield = np.zeros((max_hist_step, ncp))  # number of reflected
        sputtered_yield = np.zeros((max_hist_step, ncp))  # number of backsputtered
        reemitted_yield = np.zeros((max_hist_step, ncp))  # number of backsputtered
        projectile_yield = np.zeros((max_hist_step, ncp))  # number of backsputtered
        amu_yield = np.zeros(max_hist_step)  # mass change per ion over fluence

        for i in range(1, max_hist_step):
            for j in range(ncp):
                if nr_projectiles_array_per_element[i, j] != nr_projectiles_array_per_element[i - 1, j]:
                    reflected_yield[i, j] = (nr_reflected[i, j] - nr_reflected[i - 1, j]) / (
                        nr_projectiles_array_per_element[i, j] - nr_projectiles_array_per_element[i - 1, j])

            sputtered_yield[i, :] = (nr_sputtered[i, :] - nr_sputtered[i - 1, :]) / (nr_projectiles_array[i] - nr_projectiles_array[i - 1])
            reemitted_yield[i, :] = (nr_reemitted[i, :] - nr_reemitted[i - 1, :]) / (nr_projectiles_array[i] - nr_projectiles_array[i - 1])
            projectile_yield[i, :] = (nr_projectiles_array_per_element[i, :] - nr_projectiles_array_per_element[i - 1, :]) / (nr_projectiles_array[i] - nr_projectiles_array[i - 1])

            for j in range(ncp):
                amu_yield[i] += self.masses[j] * (sputtered_yield[i, j] + reemitted_yield[i, j] + reflected_yield[i, j] * projectile_yield[i, j] - projectile_yield[i, j])

        return (
            fluence_array,
            sputtered_yield,
            amu_yield,
            reflected_yield,
            reemitted_yield,
            surface_conc,
            surface,
            depth_array,
            conc_array
        )
    
    @staticmethod
    def depthIntervals(depth_x_values: np.ndarray) -> np.ndarray:
        """
        Returns the width of the depth intervals of each species from the centers of the intervals (depth_*.dat).
        With only one depth interval (nqx = 1) the first interval starts at the surface, so its width is twice its center
        """

        if depth_x_values.shape[1] >= 2:
            delta = depth_x_values[:, 1] - depth_x_values[:, 0]
        else:
            delta = 2 * depth_x_values[:, 0]
        return np.where(delta > 0, delta, 1.)

    def plotImplantationDepth(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return projectile stops over depth"""

        depth_data = self.getDepthFileData('depth_proj.dat')

        if depth_data is None:
            return None

        (ncp,
         file_elements,
         nr_of_depth_steps,
         max_nr_depth_steps,
         nr_of_projectiles,
         depth_data) = depth_data

        mpl_settings = MplCanvasSettings()

        depth_x_values = depth_data[:, :, 0]
        depth_delta = self.depthIntervals(depth_x_values)
        stops = depth_data[:, :, 1]

        data = []
        plot_labels = []
        flag_plots = False

        for k in range(ncp):
            if np.max(stops[k]) > 0 and nr_of_projectiles[k]:
                mpl_settings.axes.plot(depth_x_values[k, :nr_of_depth_steps[k]],
                                       stops[k, :nr_of_depth_steps[k]] / np.sum(stops[k, :nr_of_depth_steps[k]]) / depth_delta[k],
                                       label=file_elements[k],
                                       linewidth=self.line_width,
                                       color=self.colors[self.getElementIndex(file_elements[k])])
                data.append(depth_x_values[k, :])
                data.append(stops[k, :] / np.sum(stops[k, :nr_of_depth_steps[k]]) / depth_delta[k])
                plot_labels.append(f'Depth ({self.elements[k]}) [Angs]')
                plot_labels.append(f'Stopping probability ({self.elements[k]}) [1/Angs]')
                flag_plots = True

        if not flag_plots:
            return None

        mpl_settings.axes.set_xlim(xmin=0.0)
        mpl_settings.axes.set_ylim(ymin=0.0)
        mpl_settings.axes.legend()
        mpl_settings.axes.set_ylabel('Stopping Probability [1/Å]')
        mpl_settings.axes.set_xlabel('Depth [Å]')

        return (data, plot_labels), mpl_settings

    def plotEnergyLossDepth(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return projectile energy loss over depth"""

        depth_data = self.getDepthFileData('depth_proj.dat')

        if depth_data is None:
            return None

        (ncp,
         file_elements,
         nr_of_depth_steps,
         max_nr_depth_steps,
         nr_of_projectiles,
         depth_data) = depth_data

        mpl_settings = MplCanvasSettings()

        depth_x_values = depth_data[:, :, 0]
        depth_delta = self.depthIntervals(depth_x_values)
        nuclear_loss = depth_data[:, :, 3] * 1e6  # convert from MeV to eV
        electron_loss = depth_data[:, :, 4] * 1e6  # convert from MeV to eV
        total_loss = nuclear_loss + electron_loss

        data = []
        plot_labels = []
        flag_plots = False

        for k in range(ncp):
            if (np.max(nuclear_loss[k]) + np.max(electron_loss[k])) > 0 and nr_of_projectiles[k]:
                color = self.colors[self.getElementIndex(file_elements[k])]
                mpl_settings.axes.plot(depth_x_values[k, :nr_of_depth_steps[k]],
                                       nuclear_loss[k, :nr_of_depth_steps[k]] / nr_of_projectiles[k] / depth_delta[k],
                                       label=f'{file_elements[k]} (nuclear)',
                                       linestyle='--',
                                       linewidth=self.line_width,
                                       color=color)
                mpl_settings.axes.plot(depth_x_values[k, :nr_of_depth_steps[k]],
                                       electron_loss[k, :nr_of_depth_steps[k]] / nr_of_projectiles[k] / depth_delta[k],
                                       label=f'{file_elements[k]} (electronic)',
                                       linestyle=':',
                                       linewidth=self.line_width,
                                       color=color)
                mpl_settings.axes.plot(depth_x_values[k, :nr_of_depth_steps[k]],
                                       total_loss[k, :nr_of_depth_steps[k]] / nr_of_projectiles[k] / depth_delta[k],
                                       label=f'{file_elements[k]} (total)',
                                       linestyle='-',
                                       linewidth=self.line_width,
                                       color=color)
                data.append(depth_x_values[k, :])
                data.append(nuclear_loss[k, :] / nr_of_projectiles[k] / depth_delta[k])
                data.append(electron_loss[k, :] / nr_of_projectiles[k] / depth_delta[k])
                data.append(total_loss[k, :] / nr_of_projectiles[k] / depth_delta[k])
                plot_labels.append(f'Depth ({self.elements[k]}) [Angs]')
                plot_labels.append(f'Energy Loss (normalized) ({self.elements[k]}, nuclear) [eV/Angs]')
                plot_labels.append(f'Energy Loss (normalized) ({self.elements[k]}, electronic) [eV/Angs]')
                plot_labels.append(f'Energy Loss (normalized) ({self.elements[k]}, total) [eV/Angs]')
                flag_plots = True

        if not flag_plots:
            return None

        mpl_settings.axes.set_ylim(ymin=0.0)
        mpl_settings.axes.set_xlim(xmin=0.0)
        mpl_settings.axes.legend()
        mpl_settings.axes.set_ylabel('Energy Loss (normalized) [eV/Å]')
        mpl_settings.axes.set_xlabel('Depth [Å]')

        return (data, plot_labels), mpl_settings

    def plotVacanciesDepth(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return vacancies over depth"""

        if not self.save_folder:
            return None

        use_depth_damage = (self.save_folder / 'depth_damage.dat').is_file()

        # number of projectiles: int (depth_damage.dat) or array (depth_recoil.dat)
        file_data: Optional[Tuple[int, List[str], np.ndarray, int, Any, np.ndarray]]
        if use_depth_damage:
            file_data = self.getDamageDepthFileData('depth_damage.dat')
        else:
            file_data = self.getDepthFileData('depth_recoil.dat')

        if file_data is None:
            return None

        (ncp,
         file_elements,
         nr_of_depth_steps,
         max_nr_depth_steps,
         nr_of_projectiles,
         depth_data) = file_data

        mpl_settings = MplCanvasSettings()

        depth_x_values = depth_data[:, :, 0]
        depth_delta = self.depthIntervals(depth_x_values)
        if use_depth_damage:
            vacancies = depth_data[:, :, -1]
        else:
            vacancies = depth_data[:, :, 7]
            nr_of_projectiles = np.asarray(nr_of_projectiles)[0]

        data = []
        plot_labels = []
        nr_of_plots = 0

        for k in range(ncp):
            if np.max(vacancies[k]) > 0:
                mpl_settings.axes.plot(depth_x_values[k, :nr_of_depth_steps[k]],
                                       vacancies[k, :nr_of_depth_steps[k]] / nr_of_projectiles / depth_delta[k],
                                       label=file_elements[k],
                                       linewidth=self.line_width,
                                       color=self.colors[self.getElementIndex(file_elements[k])])
                data.append(depth_x_values[k, :])
                data.append(vacancies[k, :] / nr_of_projectiles / depth_delta[k])
                plot_labels.append(f'Depth ({self.elements[k]}) [Angs]')
                plot_labels.append(f'Vacancies ({self.elements[k]}) [1/Angs/ion]')

                nr_of_plots += 1

        if not nr_of_plots:
            return None

        if nr_of_plots > 1 and all(x == depth_delta[0] for x in depth_delta):
            mpl_settings.axes.plot(depth_x_values[np.argmax(nr_of_depth_steps), :max_nr_depth_steps],
                                   np.sum(vacancies[:, :max_nr_depth_steps], axis=0) / nr_of_projectiles / depth_delta[0],
                                   label='Total',
                                   linewidth=self.line_width,
                                   color=self.first_color)

            data.append(depth_x_values[np.argmax(nr_of_depth_steps), :])
            data.append(np.sum(vacancies[:, :max_nr_depth_steps], axis=0) / nr_of_projectiles / depth_delta[0])
            plot_labels.append('Depth (Total) [Angs]')
            plot_labels.append('Vacancies (Total) [1/Angs/ion]')

        mpl_settings.axes.set_ylim(ymin=0.0)
        mpl_settings.axes.set_xlim(xmin=0.0)
        mpl_settings.axes.legend()
        mpl_settings.axes.set_ylabel('Vacancies [1/Å/ion]')
        mpl_settings.axes.set_xlabel('Depth [Å]')
        mpl_settings.axes.set_title(f'Total Vacancies: {np.round(np.sum(vacancies) / nr_of_projectiles, 2)} / Ion')

        return (data, plot_labels), mpl_settings

    def plotAngularSputterYields(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return angular dependent sputter yields"""

        serie_data = self.getSerieFileData()

        if serie_data is None:
            return None

        (ncp,
         ncp_proj,
         elements,
         elements_projectiles,
         masses,

         nr_energies,
         nr_angles,
         nr_total,

         energies,
         angles,
         mean_depth,
         refl_coefficients,
         energ_refl_coefficients,
         sputt_coefficients,
         energ_sputt_coefficients,
         last_index) = serie_data

        if last_index > nr_total:
            last_index = nr_total

        mpl_settings = MplCanvasSettings()

        total_yield = np.sum(sputt_coefficients, axis=1)
        angle_distance_weights = np.ones(nr_total)

        # fit total yield with Eckstein formula
        fit_params_string = ''
        if last_index >= 5:
            for i in range(last_index - 1):
                angle_distance_weights[i] = 1. / (angles[i + 1] - angles[i])

            from scipy.optimize import curve_fit  # imported when needed (slow import, start time of the GUI)
            popt, pcov = curve_fit(self.ecksteinAngleFit,
                                   angles[:last_index],
                                   total_yield[:last_index],
                                   p0=[total_yield[0], 90., 1., 1., 1.6],
                                   sigma=angle_distance_weights[:last_index],
                                   bounds=(0., [np.max(total_yield), 90., 10., 1., 10.]))

            angles_fit = np.arange(0., 90., 0.1)
            mpl_settings.axes.plot(angles_fit,
                                   self.ecksteinAngleFit(angles_fit, *popt),
                                   label='Eckstein Fit',
                                   linestyle='--',
                                   linewidth=1,
                                   color='black')

            mpl_settings.axes.set_title(f'Fit: Y$_0$ = {np.round(popt[0], 3)} atoms/ion, $\\alpha_0$ = {np.round(popt[1], 3)}°, b = {np.round(popt[2], 3)}, c = {np.round(popt[3], 3)}, f = {np.round(popt[4], 3)}')
            fit_params_string = f'Fit: Y0 = {np.round(popt[0], 3)} atoms/ion, alpha0 = {np.round(popt[1], 3)}°, b = {np.round(popt[2], 3)}, c = {np.round(popt[3], 3)}, f = {np.round(popt[4], 3)}'

        data = []
        plot_labels = []

        plot_counter = 0
        for i, element in enumerate(elements):
            if np.max(sputt_coefficients[:, i]) > 0.:
                mpl_settings.axes.plot(angles[:last_index],
                                       sputt_coefficients[:last_index, i],
                                       label=element,
                                       marker='o',
                                       linestyle='',
                                       color=self.colors[self.getElementIndex(element)])

                if not plot_counter:
                    data.append(angles[:last_index])
                    plot_labels.append('Angle of Incidence [°]')
                data.append(sputt_coefficients[:last_index, i])
                plot_labels.append(element)

                plot_counter += 1

        if not plot_counter:
            return None

        elif plot_counter > 1:
            mpl_settings.axes.plot(angles[:last_index],
                                   total_yield[:last_index],
                                   label='Total',
                                   marker='o',
                                   linestyle='',
                                   color=self.first_color)

            data.append(total_yield[:last_index])
            plot_labels.append('Total')
            plot_labels.append(fit_params_string)

        mpl_settings.axes.set_xlabel('Angle of Incidence $\\alpha$ [°]')
        mpl_settings.axes.set_ylabel('Sputtering Yield Y [atoms/ion]')
        mpl_settings.axes.set_ylim(ymin=0.)
        mpl_settings.axes.set_xlim(xmin=-5., xmax=90.)
        mpl_settings.axes.legend()

        return (data, plot_labels), mpl_settings

    def plotAngularMassYields(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return angular dependant mass yields"""

        serie_data = self.getSerieFileData()

        if serie_data is None:
            return None

        (ncp,
         ncp_proj,
         elements,
         elements_projectiles,
         masses,

         nr_energies,
         nr_angles,
         nr_total,

         energies,
         angles,
         mean_depth,
         refl_coefficients,
         energ_refl_coefficients,
         sputt_coefficients,
         energ_sputt_coefficients,
         last_index) = serie_data

        if last_index > nr_total:
            last_index = nr_total

        mpl_settings = MplCanvasSettings()

        amu_yield = np.dot(sputt_coefficients, masses)

        fit_params_string = ''
        if last_index >= 5:
            angle_distance_weights = np.ones(nr_total)
            for i in range(last_index - 1):
                angle_distance_weights[i] = 1. / (angles[i + 1] - angles[i])

            from scipy.optimize import curve_fit  # imported when needed (slow import, start time of the GUI)
            popt, pcov = curve_fit(self.ecksteinAngleFit,
                                   angles[:last_index],
                                   amu_yield[:last_index],
                                   sigma=angle_distance_weights[:last_index],
                                   p0=[amu_yield[0], 90., 1., 1., 1.6],
                                   bounds=(0., [np.max(amu_yield), 90., 10., 1., 10.]))

            angles_fit = np.arange(0., 90., 0.1)
            mpl_settings.axes.plot(angles_fit,
                                   self.ecksteinAngleFit(angles_fit, *popt),
                                   label='Eckstein Fit',
                                   linestyle='--',
                                   linewidth=1,
                                   color='black')
            mpl_settings.axes.set_title(f'Fit: Y$_0$ = {np.round(popt[0], 3)} amu/ion, $\\alpha_0$ = {np.round(popt[1], 3)}°, b = {np.round(popt[2], 3)}, c = {np.round(popt[3], 3)}, f = {np.round(popt[4], 3)}')
            fit_params_string = f'Fit: Y0 = {np.round(popt[0], 3)} amu/ion, alpha0 = {np.round(popt[1], 3)}°, b = {np.round(popt[2], 3)}, c = {np.round(popt[3], 3)}, f = {np.round(popt[4], 3)}'

        mpl_settings.axes.plot(angles[:last_index],
                               amu_yield[:last_index],
                               label='SDTrimSP',
                               marker='o',
                               linestyle='',
                               color=self.first_color)

        data = []
        plot_labels = []

        if last_index > 0:
            data.append(angles[:last_index])
            data.append(amu_yield[:last_index])
            plot_labels.append('Angle of Incidence [°]')
            plot_labels.append('y [amu/ion]')
            plot_labels.append(fit_params_string)

        mpl_settings.axes.set_xlabel('Angle of Incidence $\\alpha$ [°]')
        mpl_settings.axes.set_ylabel('Sputtering Yield y [amu/ion]')
        mpl_settings.axes.set_ylim(ymin=0.)
        mpl_settings.axes.set_xlim(xmin=-5., xmax=90.)
        mpl_settings.axes.legend()

        return (data, plot_labels), mpl_settings

    def plotAngularReflection(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return angular dependent reflection coefficients"""

        serie_data = self.getSerieFileData()

        if serie_data is None:
            return None

        (ncp,
         ncp_proj,
         elements,
         elements_projectiles,
         masses,

         nr_energies,
         nr_angles,
         nr_total,

         energies,
         angles,
         mean_depth,
         refl_coefficients,
         energ_refl_coefficients,
         sputt_coefficients,
         energ_sputt_coefficients,
         last_index) = serie_data

        if last_index > nr_total:
            last_index = nr_total

        mpl_settings = MplCanvasSettings()

        total_yield = np.sum(refl_coefficients, axis=1)

        data = []
        plot_labels = []

        plot_counter = 0
        for i, element in enumerate(elements_projectiles):
            if np.max(refl_coefficients[:, i]) > 0.:
                mpl_settings.axes.plot(angles[:last_index],
                                       refl_coefficients[:last_index, i],
                                       label=element,
                                       marker='o',
                                       linestyle='',
                                       color=self.colors[self.getElementIndex(element)])

                if not plot_counter:
                    data.append(angles[:last_index])
                    plot_labels.append('Angle of Incidence [°]')

                data.append(refl_coefficients[:last_index, i])
                plot_labels.append(element)

                plot_counter += 1

        if not plot_counter:
            return None

        elif plot_counter > 1:
            mpl_settings.axes.plot(angles[:last_index],
                                   total_yield[:last_index],
                                   label='Total',
                                   marker='o',
                                   linestyle='',
                                   color=self.first_color)

        mpl_settings.axes.set_xlabel('Angle of Incidence $\\alpha$ [°]')
        mpl_settings.axes.set_ylabel('Reflection Coefficient R')
        mpl_settings.axes.set_ylim(ymin=0.)
        mpl_settings.axes.set_xlim(xmin=-5., xmax=90.)
        mpl_settings.axes.legend()

        return (data, plot_labels), mpl_settings

    def plotAngularMeanDepth(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return angular dependent mean depth"""

        serie_data = self.getSerieFileData()

        if serie_data is None:
            return None

        (ncp,
         ncp_proj,
         elements,
         elements_projectiles,
         masses,

         nr_energies,
         nr_angles,
         nr_total,

         energies,
         angles,
         mean_depth,
         refl_coefficients,
         energ_refl_coefficients,
         sputt_coefficients,
         energ_sputt_coefficients,
         last_index) = serie_data

        if last_index > nr_total:
            last_index = nr_total

        mpl_settings = MplCanvasSettings()

        mpl_settings.axes.plot(angles[:last_index],
                               mean_depth[:last_index],
                               label='Implantation Depth',
                               marker='o',
                               linestyle='',
                               color=self.first_color)

        data = []
        plot_labels = []

        if last_index > 0:
            data.append(angles[:last_index])
            data.append(mean_depth[:last_index])
            plot_labels.append('Angle of Incidence [°]')
            plot_labels.append('Implantation Depth [Angs]')

        mpl_settings.axes.set_xlabel('Angle of Incidence $\\alpha$ [°]')
        mpl_settings.axes.set_ylabel('Implantation Depth [Å]')
        mpl_settings.axes.set_ylim(ymin=0.)
        mpl_settings.axes.set_xlim(xmin=-5., xmax=90.)

        return (data, plot_labels), mpl_settings

    def plotEnergySputterYields(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return energy dependent sputter yields"""

        serie_data = self.getSerieFileData()

        if serie_data is None:
            return None

        (ncp,
         ncp_proj,
         elements,
         elements_projectiles,
         masses,

         nr_energies,
         nr_angles,
         nr_total,

         energies,
         angles,
         mean_depth,
         refl_coefficients,
         energ_refl_coefficients,
         sputt_coefficients,
         energ_sputt_coefficients,
         last_index) = serie_data

        if last_index > nr_total:
            last_index = nr_total

        mpl_settings = MplCanvasSettings()

        total_yield = np.sum(sputt_coefficients, axis=1)

        # possibly Eckstein energy fit here

        data = []
        plot_labels = []

        plot_counter = 0
        for i, element in enumerate(elements):
            if np.max(sputt_coefficients[:, i]) > 0.:
                mpl_settings.axes.plot(energies[:last_index],
                                       sputt_coefficients[:last_index, i],
                                       label=element,
                                       marker='o',
                                       linestyle='',
                                       color=self.colors[self.getElementIndex(element)])

                if not plot_counter:
                    data.append(energies[:last_index])
                    plot_labels.append('Kinetic Energy [eV]')

                data.append(sputt_coefficients[:last_index, i])
                plot_labels.append(element)

                plot_counter += 1

        if not plot_counter:
            return None

        elif plot_counter > 1:
            mpl_settings.axes.plot(energies[:last_index],
                                   total_yield[:last_index],
                                   label='Total',
                                   marker='o',
                                   linestyle='',
                                   color=self.first_color)
            data.append(total_yield[:last_index])
            plot_labels.append('Total')

        mpl_settings.axes.set_xlabel('Kinetic Energy E [eV]')
        mpl_settings.axes.set_ylabel('Sputtering Yield Y [atoms/ion]')
        mpl_settings.axes.set_yscale('log')
        mpl_settings.axes.set_xscale('log')
        mpl_settings.axes.legend()

        return (data, plot_labels), mpl_settings

    def plotEnergyMassYields(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return energy dependent mass yields"""

        serie_data = self.getSerieFileData()

        if serie_data is None:
            return None

        (ncp,
         ncp_proj,
         elements,
         elements_projectiles,
         masses,

         nr_energies,
         nr_angles,
         nr_total,

         energies,
         angles,
         mean_depth,
         refl_coefficients,
         energ_refl_coefficients,
         sputt_coefficients,
         energ_sputt_coefficients,
         last_index) = serie_data

        if last_index > nr_total:
            last_index = nr_total

        mpl_settings = MplCanvasSettings()

        amu_yield = np.dot(sputt_coefficients, masses)

        mpl_settings.axes.plot(energies[:last_index],
                               amu_yield[:last_index],
                               label='SDTrimSP',
                               marker='o',
                               linestyle='',
                               color=self.first_color)

        # possibly Eckstein energy fit here

        data = []
        plot_labels = []

        if last_index > 0:
            data.append(energies[:last_index])
            data.append(amu_yield[:last_index])
            plot_labels.append('Kinetic Energy [eV]')
            plot_labels.append('y [amu/ion]')

        mpl_settings.axes.set_xlabel('Kinetic Energy E [eV]')
        mpl_settings.axes.set_ylabel('Sputtering Yield y [amu/ion]')
        mpl_settings.axes.set_yscale('log')
        mpl_settings.axes.set_xscale('log')
        mpl_settings.axes.legend()

        return (data, plot_labels), mpl_settings

    def plotEnergyReflection(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return energy dependent reflection coefficients"""

        serie_data = self.getSerieFileData()

        if serie_data is None:
            return None

        (ncp,
         ncp_proj,
         elements,
         elements_projectiles,
         masses,

         nr_energies,
         nr_angles,
         nr_total,

         energies,
         angles,
         mean_depth,
         refl_coefficients,
         energ_refl_coefficients,
         sputt_coefficients,
         energ_sputt_coefficients,
         last_index) = serie_data

        if last_index > nr_total:
            last_index = nr_total

        mpl_settings = MplCanvasSettings()

        total_yield = np.sum(refl_coefficients, axis=1)

        data = []
        plot_labels = []

        plot_counter = 0
        for i, element in enumerate(elements_projectiles):
            if np.max(refl_coefficients[:, i]) > 0.:
                mpl_settings.axes.plot(energies[:last_index],
                                       refl_coefficients[:last_index, i],
                                       label=element,
                                       marker='o',
                                       linestyle='',
                                       color=self.colors[self.getElementIndex(element)])

                if not plot_counter:
                    data.append(energies[:last_index])
                    plot_labels.append('Kinetic Energy [eV]')
                data.append(refl_coefficients[:last_index, i])
                plot_labels.append(element)

                plot_counter += 1

        if not plot_counter:
            return None

        elif plot_counter > 1:
            mpl_settings.axes.plot(energies[:last_index],
                                   total_yield[:last_index],
                                   label='Total',
                                   marker='o',
                                   linestyle='',
                                   color=self.first_color)

        mpl_settings.axes.set_xlabel('Kinetic Energy E [eV]')
        mpl_settings.axes.set_ylabel('Reflection Coefficient R')
        mpl_settings.axes.set_yscale('log')
        mpl_settings.axes.set_xscale('log')
        mpl_settings.axes.legend()

        return (data, plot_labels), mpl_settings

    def plotEnergyMeanDepth(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return energy dependent mean depth"""

        serie_data = self.getSerieFileData()

        if serie_data is None:
            return None

        (ncp,
         ncp_proj,
         elements,
         elements_projectiles,
         masses,

         nr_energies,
         nr_angles,
         nr_total,

         energies,
         angles,
         mean_depth,
         refl_coefficients,
         energ_refl_coefficients,
         sputt_coefficients,
         energ_sputt_coefficients,
         last_index) = serie_data

        if last_index > nr_total:
            last_index = nr_total

        mpl_settings = MplCanvasSettings()

        mpl_settings.axes.plot(energies[:last_index],
                               mean_depth[:last_index],
                               label='Implantation Depth',
                               marker='o',
                               linestyle='',
                               color=self.first_color)

        data = []
        plot_labels = []

        if last_index > 0:
            data.append(energies[:last_index])
            data.append(mean_depth[:last_index])
            plot_labels.append('Kinetic Energy [eV]')
            plot_labels.append('Implantation Depth [Angs]')

        mpl_settings.axes.set_xlabel('Kinetic Energy E [eV]')
        mpl_settings.axes.set_ylabel('Implantation Depth [Å]')
        mpl_settings.axes.set_yscale('log')
        mpl_settings.axes.set_xscale('log')

        return (data, plot_labels), mpl_settings

    def plotParticlesPolar(self, particle: Optional[Particle] = None) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return angle data of backscattered particles"""

        if particle is None:
            particle = self.particle
        particle_data = self.getParticleData(particle)
        self.particle = particle

        mpl_settings = MplCanvasSettings()
        mpl_settings.fig.add_subplot(projection='polar')

        if particle_data is None or not particle_data:
            mpl_settings.axes.set_title('No data found')
            return None, mpl_settings

        data = []
        plot_labels = []

        plot_counter = 0
        for i, element in enumerate(self.elements):
            plot_data = particle_data[i]
            cos_polar = plot_data[:, 0]
            cos_azimuth = plot_data[:, 1]
            polar_angles = np.arccos(np.asarray(cos_polar)) * np.sign(cos_azimuth)

            if not cos_polar.size:
                continue

            hist, bin_edges = np.histogram(polar_angles, bins=72, range=(-np.pi / 2, np.pi / 2))
            bin_edges_new = 0.5 * (bin_edges[:-1] + bin_edges[1:])
            polar_plot_norm = np.absolute(np.cos(bin_edges[:-1]) - np.cos(bin_edges[1:])) / np.sum(np.absolute(np.cos(bin_edges[:-1]) - np.cos(bin_edges[1:])))
            # 0.5 ... normalization because both + and - polar angle are shown, np.pi/180. for conversion from 1/rad to 1/deg
            plot_data = 0.5 * np.pi / 180. * np.divide(hist, np.absolute(polar_plot_norm))
            mpl_settings.axes.plot(bin_edges_new,
                                   plot_data,
                                   label=element,
                                   linewidth=self.line_width,
                                   color=self.colors[i])

            if not plot_counter:
                data.append(bin_edges_new / np.pi * 180.)
                plot_labels.append('Polar Angle [°]')

            data.append(plot_data)
            plot_labels.append(f'Probability ({element}) [1/°]')

            plot_counter += 1

        if not plot_counter:
            mpl_settings.axes.set_title('No data found')
            return None, mpl_settings

        if particle == Particle.Projectile:
            mpl_settings.axes.set_title('Backscattered projectiles over polar angle')
        else:
            mpl_settings.axes.set_title('Sputtered recoils over polar angle')

        mpl_settings.axes.set_xlabel('Probability [1/°]')
        mpl_settings.axes.grid(True)
        mpl_settings.axes.set_thetagrids(tuple([i * 10 for i in range(-9, 10)]))
        mpl_settings.axes.set_thetamin(-90)
        mpl_settings.axes.set_thetamax(90)
        mpl_settings.axes.set_theta_offset(np.pi / 2)
        mpl_settings.axes.set_theta_direction(-1)
        mpl_settings.axes.tick_params(
            axis='y',
            labelrotation=45,
            pad=4,
            labelsize=8)
        mpl_settings.axes.legend()

        return (data, plot_labels), mpl_settings

    def plotParticlesPolarP(self) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return angle data of backscattered projectiles"""

        return self.plotParticlesPolar(Particle.Projectile)

    def plotParticlesPolarR(self) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return angle data of backscattered recoils"""

        return self.plotParticlesPolar(Particle.Recoil)

    def plotParticlesEnergy(self, particle: Optional[Particle] = None) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return energy of backscattered particles"""

        if particle is None:
            particle = self.particle
        particle_data = self.getParticleData(particle)
        self.particle = particle

        mpl_settings = MplCanvasSettings()

        if particle_data is None or not particle_data:
            mpl_settings.axes.set_title('No data found')
            return None, mpl_settings

        data = []
        plot_labels = []

        plot_counter = 0
        for i, element in enumerate(self.elements):
            plot_data = particle_data[i]
            energies = plot_data[:, 2]

            if not energies.size:
                continue

            if particle == Particle.Projectile:
                hist, bin_edges = np.histogram(energies, bins=100)

            # use very fine resolution in binning for sputtered atoms because lower energies are of more interest
            else:
                hist, bin_edges = np.histogram(energies, bins=max(1, int(np.max(energies) / 0.2)))

            bin_edges_new = 0.5 * (bin_edges[:-1] + bin_edges[1:])
            mpl_settings.axes.plot(bin_edges_new,
                                   hist,
                                   label=element,
                                   linewidth=self.line_width,
                                   color=self.colors[i])

            data.append(bin_edges_new)
            plot_labels.append(f'Energy ({element}) [eV]')
            data.append(hist)
            plot_labels.append(f'Probability ({element}) [1/eV]')

            plot_counter += 1

        if not plot_counter:
            return None, mpl_settings

        mpl_settings.axes.set_xlabel('Energy [eV]')
        if particle == Particle.Projectile:
            mpl_settings.axes.set_ylabel('Reflected ions [1/eV]')
        else:
            mpl_settings.axes.set_ylabel('Sputtered atoms [1/eV]')
        mpl_settings.axes.set_ylim(ymin=0.)
        mpl_settings.axes.set_xlim(xmin=0.)
        mpl_settings.axes.legend()

        return (data, plot_labels), mpl_settings

    def plotParticlesEnergyP(self) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return energy of backscattered projectiles"""

        return self.updateParticlesEnergyPolar(Particle.Projectile, 0, 90)

    def plotParticlesEnergyR(self) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return energy of backscattered recoils"""

        return self.updateParticlesEnergyPolar(Particle.Recoil, 0, 90)

    def plotParticlesEnergyPolar(self, polar_angle: float, polar_angle_delta: float) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return angle and energy data of backscattered particles"""

        mpl_settings = MplCanvasSettings()

        if self.particle_data is None or not self.particle_data:
            mpl_settings.axes.set_title('No data found')
            return None, mpl_settings

        data = []
        plot_labels = []

        plot_counter = 0
        for i, element in enumerate(self.elements):
            plot_data = self.particle_data[i]
            cos_polar = plot_data[:, 0]
            cos_azimuth = plot_data[:, 1]
            energies = plot_data[:, 2]
            polar_angles = np.arccos(np.asarray(cos_polar)) * np.sign(cos_azimuth)

            if not cos_polar.size or not energies.size:
                continue

            polar_angle_filter = np.logical_and(
                polar_angles < (polar_angle + polar_angle_delta) * np.pi / 180,
                polar_angles > (polar_angle - polar_angle_delta) * np.pi / 180
            )
            energies = energies[polar_angle_filter]

            if self.particle == Particle.Projectile:
                hist, bin_edges = np.histogram(energies, bins=100)

            # use very fine resolution in binning for sputtered atoms because lower energies are of more interest
            else:
                hist, bin_edges = np.histogram(energies, bins=max(1, int(np.max(energies) / 0.2)))

            bin_edges_new = 0.5 * (bin_edges[:-1] + bin_edges[1:])
            mpl_settings.axes.plot(bin_edges_new,
                                   hist,
                                   label=element,
                                   linewidth=self.line_width,
                                   color=self.colors[i])

            data.append(bin_edges_new)
            plot_labels.append(f'Energy ({element}) [eV]')
            data.append(hist)
            plot_labels.append(f'Probability ({element}) [1/eV]')

            plot_counter += 1

        if not plot_counter:
            return None, mpl_settings

        mpl_settings.axes.set_xlabel('Energy [eV]')
        if self.particle == Particle.Projectile:
            mpl_settings.axes.set_ylabel('Reflected ions [1/eV]')
        else:
            mpl_settings.axes.set_ylabel('Sputtered atoms [1/eV]')
        mpl_settings.axes.set_ylim(ymin=0.)
        mpl_settings.axes.set_xlim(xmin=0.)
        mpl_settings.axes.legend()

        return (data, plot_labels), mpl_settings

    def updateParticlesEnergyPolar(self, particle: Particle, polar_angle: float, polar_angle_delta: float) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Updates te plot and data of the angle and energy of backscattered particles"""

        self.particle = particle
        self.particle_data = self.getParticleData(particle)
        result = self.plotParticlesEnergyPolar(polar_angle, polar_angle_delta)

        # emit signal for HlPlot Layout
        self.emit({
            'hide_polar_angle': False,
            'polar_angle': polar_angle,
            'polar_angle_delta': polar_angle_delta
        })

        return result

    def plotPolar(self, element: int, particle: Particle, n_bins: int = 30) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return backscattered particles of element"""

        if element not in range(len(self.elements)):
            return None

        particle_data = self.getParticleData(particle)

        mpl_settings = MplCanvasSettings()
        mpl_settings.fig.add_subplot(projection='polar')

        if particle_data is None or not particle_data:
            mpl_settings.axes.set_title('No data found')
            return None, mpl_settings

        data = []
        plot_labels = []

        plot_data = particle_data[element]
        if len(plot_data) == 0:
            mpl_settings.axes.set_title('No data found')
            return None, mpl_settings

        phi_intermed = np.arccos(plot_data[:, 1])
        phi_intermed_neg = -phi_intermed
        phi = np.hstack((phi_intermed, phi_intermed_neg))

        theta_intermed = np.arccos(plot_data[:, 0])
        theta = np.hstack((theta_intermed, theta_intermed))

        lowerlimit = 0

        spacing = np.arange(lowerlimit, n_bins + 1)
        rbins = np.arccos(1 - spacing / n_bins)
        abins = np.linspace(-np.pi, np.pi, 4 * n_bins)

        hist, _, _ = np.histogram2d(phi, theta, bins=(abins, rbins))
        # 0.5 corrects for the extension to the full 2*pi azimuthal space, so that particles are not counted twice
        hist *= 0.5
        hist /= np.sum(hist)

        total_nr_of_bins = hist.size
        bin_area = np.pi * 2. / total_nr_of_bins
        hist /= bin_area

        a, r = np.meshgrid(abins, rbins)

        mpl_settings.axes.set_thetamin(0)
        mpl_settings.axes.set_thetamax(360)
        mpl_settings.axes.set_theta_direction(-1)
        mpl_settings.axes.set_theta_zero_location('E')
        mpl_settings.axes.set_yticklabels([])
        mpl_settings.axes.pcolormesh(a, r, hist.T, cmap=paletteColormap(), zorder=-1, vmin=0.)
        mpl_settings.axes.pcolormesh_label('Distribution of Particles [1/sr]', rotation=90)  # colorbar.set_label()

        plot_labels.append('Rows: polar angles [°], columns: azimuthal angles [°], distribution of particles in [1/sr], first row/column gives the respective angle (center of the bin of the histogram), polar bins are chosen so that all bins have the same solid angle')

        delta_rbins = rbins[1:] - rbins[:-1]
        rbins_center = rbins[:-1] + 0.5 * delta_rbins

        delta_abins = abins[1:] - abins[:-1]
        abins_center = abins[:-1] + 0.5 * delta_abins

        data.append(np.append(0., np.round(rbins_center / np.pi * 180., 2)))
        for i in range(len(hist)):
            if abins_center[i] < 0:
                continue
            data.append(np.append(np.mod(np.round(abins_center[i] / np.pi * 180., 2), 360.), hist[i]))

        for i in range(len(hist)):
            if abins_center[i] > 0:
                continue
            data.append(np.append(np.mod(np.round(abins_center[i] / np.pi * 180., 2), 360.), hist[i]))

        if particle == Particle.Projectile:
            title = f'Angular distribution of backscattered {self.elements[element]} projectiles'
        else:
            title = f'Angular distribution of backsputtered {self.elements[element]} recoil atoms'
        mpl_settings.axes.set_title(title)

        return (data, plot_labels), mpl_settings

    def plotSputterYields(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return sputter yields"""

        e031_data = self.getE031TargetData()

        if e031_data is None:
            return None

        (fluence_array,
         sputtered_yield,
         amu_yield,
         reflected_yield,
         reemitted_yield,
         surface_conc,
         surface,
         depth_array,
         conc_array) = e031_data

        mpl_settings = MplCanvasSettings()

        data = [fluence_array[1:]]
        plot_labels = ['Fluence[10^20 ions/m^2]']

        for i, element in enumerate(self.elements):
            mpl_settings.axes.plot(fluence_array[1:],
                                   sputtered_yield[1:, i],
                                   label=element,
                                   color=self.colors[i])

            data.append(sputtered_yield[1:, i])
            plot_labels.append(element)

        mpl_settings.axes.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.axes.set_ylabel('Sputtering Yield Y [atoms/ion]')
        mpl_settings.axes.set_ylim(ymin=0.)
        mpl_settings.axes.legend()

        return (data, plot_labels), mpl_settings

    def plotSputterYieldsTotal(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return total sputter yields"""

        e031_data = self.getE031TargetData()

        if e031_data is None:
            return None

        (fluence_array,
         sputtered_yield,
         amu_yield,
         reflected_yield,
         reemitted_yield,
         surface_conc,
         surface,
         depth_array,
         conc_array) = e031_data

        mpl_settings = MplCanvasSettings()

        mpl_settings.axes.plot(fluence_array[1:],
                               np.sum(sputtered_yield[1:, :], axis=1),
                               color=self.first_color)

        mpl_settings.axes.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.axes.set_ylabel('Sputtering Yield Y [atoms/ion]')
        mpl_settings.axes.set_ylim(ymin=0.)

        return ([fluence_array[1:], np.sum(sputtered_yield[1:, :], axis=1)], ['Fluence[10^20 ions/m^2]', 'Y [atoms/ion]']), mpl_settings

    def plotSputterYieldsTotalAmu(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return total sputter yields amu"""

        e031_data = self.getE031TargetData()

        if e031_data is None:
            return None

        (fluence_array,
         sputtered_yield,
         amu_yield,
         reflected_yield,
         reemitted_yield,
         surface_conc,
         surface,
         depth_array,
         conc_array) = e031_data

        mpl_settings = MplCanvasSettings()

        mpl_settings.axes.plot(fluence_array[1:],
                               amu_yield[1:],
                               color=self.first_color)

        mpl_settings.axes.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.axes.set_ylabel('Net Mass Removal y [amu/ion]')

        return ([fluence_array[1:], amu_yield[1:]], ['Fluence[10^20 ions/m^2]', 'y [amu/ion]']), mpl_settings

    def plotReflectionCoefficients(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return reflection coefficients"""

        e031_data = self.getE031TargetData()

        if e031_data is None:
            return None

        (fluence_array,
         sputtered_yield,
         amu_yield,
         reflected_yield,
         reemitted_yield,
         surface_conc,
         surface,
         depth_array,
         conc_array) = e031_data

        mpl_settings = MplCanvasSettings()

        data = [fluence_array[1:]]
        plot_labels = ['Fluence[10^20 ions/m^2]']

        for i, element in enumerate(self.elements):
            mpl_settings.axes.plot(fluence_array[1:],
                                   reflected_yield[1:, i],
                                   label=element,
                                   color=self.colors[i])

            data.append(reflected_yield[1:, i])
            plot_labels.append(element)

        mpl_settings.axes.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.axes.set_ylabel('Reflection Coefficient R [atoms/ion]')
        mpl_settings.axes.set_ylim(ymin=0., ymax=1.)
        mpl_settings.axes.legend()

        return (data, plot_labels), mpl_settings

    def plotReemissionCoefficients(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return reemission coefficients"""

        e031_data = self.getE031TargetData()

        if e031_data is None:
            return None

        (fluence_array,
         sputtered_yield,
         amu_yield,
         reflected_yield,
         reemitted_yield,
         surface_conc,
         surface,
         depth_array,
         conc_array) = e031_data

        mpl_settings = MplCanvasSettings()

        data = [fluence_array[1:]]
        plot_labels = ['Fluence[10^20 ions/m^2]']

        for i, element in enumerate(self.elements):
            mpl_settings.axes.plot(fluence_array[1:],
                                   reemitted_yield[1:, i],
                                   label=element,
                                   color=self.colors[i])

            data.append(reemitted_yield[1:, i])
            plot_labels.append(element)

        mpl_settings.axes.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.axes.set_ylabel('Reemission Coefficient [atoms/ion]')
        mpl_settings.axes.set_ylim(ymin=0., ymax=1.)
        mpl_settings.axes.legend()

        return (data, plot_labels), mpl_settings

    def plotSurfaceConcentrations(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return surface concentrations"""

        e031_data = self.getE031TargetData()

        if e031_data is None:
            return None

        (fluence_array,
         sputtered_yield,
         amu_yield,
         reflected_yield,
         reemitted_yield,
         surface_conc,
         surface,
         depth_array,
         conc_array) = e031_data

        mpl_settings = MplCanvasSettings()

        data = [fluence_array[1:]]
        plot_labels = ['Fluence[10^20 ions/m^2]']

        for i, element in enumerate(self.elements):
            mpl_settings.axes.plot(fluence_array[1:],
                                   surface_conc[1:, i],
                                   label=element,
                                   color=self.colors[i])

            data.append(surface_conc[1:, i])
            plot_labels.append(element)

        mpl_settings.axes.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.axes.set_ylabel('Surface Concentration')
        mpl_settings.axes.set_ylim(ymin=0., ymax=1.)
        mpl_settings.axes.legend()

        return (data, plot_labels), mpl_settings

    def plotSurfaceLevel(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return surface levels"""

        e031_data = self.getE031TargetData()

        if e031_data is None:
            return None

        (fluence_array,
         sputtered_yield,
         amu_yield,
         reflected_yield,
         reemitted_yield,
         surface_conc,
         surface,
         depth_array,
         conc_array) = e031_data

        mpl_settings = MplCanvasSettings()

        mpl_settings.axes.plot(fluence_array[1:],
                               surface[1:],
                               color=self.first_color)

        mpl_settings.axes.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.axes.set_ylabel('Surface Erosion [Å]')

        return ([fluence_array[1:], surface[1:]], ['Fluence[10^20 ions/m^2]', 'Surface Erosion [Angs]']), mpl_settings

    def plotDepthConcentration(self, history_step: int = 0) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return the depth concentration"""

        if self.depth_array is None or self.conc_array is None or self.fluence_array is None:
            return None

        mpl_settings = MplCanvasSettings()

        data = [self.depth_array]
        plot_labels = ['Depth [Angs]']

        for i, element in enumerate(self.elements):
            mpl_settings.axes.plot(self.depth_array,
                                   self.conc_array[history_step, i, :],
                                   label=element,
                                   linewidth=2,
                                   color=self.colors[i])

            data.append(self.conc_array[history_step, i, :])
            plot_labels.append(element)

        mpl_settings.axes.set_ylim(ymin=0.0, ymax=1.0)
        mpl_settings.axes.legend()
        mpl_settings.axes.set_xlabel('Depth [Å]')
        mpl_settings.axes.set_ylabel('Concentrations')
        mpl_settings.axes.set_title(f'Fluence: {self.fluence_array[history_step]:.2f}$\\times 10^{{20}}$/m$^2$')

        return (data, plot_labels), mpl_settings

    def updateDepthConcentration(self, set_to_max: bool = False) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Updates the plot and data of the depth concentration"""

        e031_data = self.getE031TargetData()

        if e031_data is None:
            return None

        (fluence_array,
         sputtered_yield,
         amu_yield,
         reflected_yield,
         reemitted_yield,
         surface_conc,
         surface,
         depth_array,
         conc_array) = e031_data

        max_hist = conc_array.shape[0] - 1
        if max_hist < 0:
            return None

        self.fluence_array = fluence_array
        self.depth_array = depth_array
        self.conc_array = conc_array

        history_step = 0
        if set_to_max:
            history_step = max_hist
        result = self.plotDepthConcentration(history_step=history_step)

        # emit signal for HlPlot Layout
        self.emit({
            'hide_history': False,
            'max_history': max_hist,
            'history': max_hist
        })

        return result
