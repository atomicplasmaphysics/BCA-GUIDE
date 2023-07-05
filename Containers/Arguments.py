# BCA-GUIDE - a graphical user interface for bca simulations to simulate sputtering, ion implantation and the
# dynamic effects of ion irradiation
#
# Copyright(C) 2022, Alexander Redl, Paul S.Szabo, David Weichselbaum, Herbert Biber, Christian Cupak, Andreas Mutzke,
# Wolfhard Möller, Richard A.Wilhelm, Friedrich Aumayr
#
# This program implements libraries of the Qt framework (https://www.qt.io/).
#
# This program is free software: you can redistribute it and / or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either version 3 of the License, or any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with this program. If not, see
# https://www.gnu.org/licenses/.


from typing import List, Union
from enum import Enum, auto
from json import dump, JSONEncoder, load
from json.decoder import JSONDecodeError
import logging

from Utility.Indexing import RunningIndex, DefaultAssumed

from Containers.Element import Element
from Containers.Compound import Compound


class ArgumentValues:
    """
    Collection of argument value names
    """

    class Mode(Enum):
        """Mode of simulation"""
        STATIC = auto()
        DYNAMIC = auto()
        STATIC_NO_RECOIL = auto()

    class KineticEnergy(Enum):
        """Choice of incident energy"""
        FIXED = auto()
        FILE = auto()
        SWEEP = auto()
        MAXWELLIAN_VELOCITY_DISTRIBUTION = auto()
        MAXWELLIAN_ENERGY_DISTRIBUTION = auto()
        FILE_ENERGY_ANGLE = auto()
        LINEAR_RAMP = auto()

    class Angle(Enum):
        """Choice of the angle of incidence"""
        FIXED = auto()
        FILE = auto()
        SWEEP = auto()
        RANDOM_DISTRIBUTION = auto()
        COS_DISTRIBUTION_1 = auto()
        COS_DISTRIBUTION_2 = auto()
        FILE_ENERGY_ANGLE = auto()
        GAUSSIAN_2D = auto()
        COS_2D = auto()
        PARABOLIC_1D = auto()

    class InelasticLossModel(Enum):
        """Inelastic loss model"""
        LINDHARD_SCHARFF = auto()
        OEN_ROBINSON = auto()
        LINDHARD_SCHARFF_AND_OEN_ROBINSON = auto()
        HYDROGEN = auto()
        HELIUM = auto()
        ZIEGLER = auto()
        LINDHARD_SCHARFF_AND_ZIEGLER = auto()

    class InteractionPotential(Enum):
        """Interaction potential"""
        KRC = auto()
        MOLIERE = auto()
        ZBL = auto()
        NAKAGAWA_YAMAMURA = auto()
        SI_SI = auto()
        POWER = auto()

    class IntegrationMethod(Enum):
        """Integration method"""
        MAGIC = auto()
        GAUSS_MEHLER = auto()
        GAUSS_LEGENDRE = auto()

    class SurfaceBindingModel(Enum):
        """Surface binding model"""
        ELEMENT_SPECIFIC = auto()
        AVERAGE = auto()
        ELEMENT_PAIRS = auto()
        SOLID_SOLID = auto()
        SOLID_GAS = auto()
        FILE = auto()
        ELECTRONEGATIVITY = auto()
        COMPOUNDS = auto()
        TABLE = auto()


class Arguments:
    """
    General container that stores information.
    The purpose of this container is to share simulation parameters across different simulations. Therefore, required
    parameters need to be set and can be accessed in other simulations. Optional parameters might be ignored by other
    simulations.
    """

    def __init__(self, **kwargs):
        self.optional = kwargs

    def get(self, argument: str):
        """
        Returns value of argument or None if not set

        :param argument: argument name
        """

        if hasattr(self, argument):
            return getattr(self, argument)
        return self.optional.get(argument)

    def __str__(self) -> str:
        """Returns itself as printable string"""

        return f'<"{self.__class__.__name__}" object {hex(id(self))}>\n  optional={self.optional}'


class GeneralBeamArguments(Arguments):
    """
    Container that stores information of general beam arguments

    :param kinetic_energy_mode: choice of incidence energy
    :param angle_mode: choice of incidence angle
    """

    def __init__(
        self,
        kinetic_energy_mode: ArgumentValues.KineticEnergy = ArgumentValues.KineticEnergy.FIXED,
        angle_mode: ArgumentValues.Angle = ArgumentValues.Angle.FIXED,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.kinetic_energy_mode = kinetic_energy_mode
        self.angle_mode = angle_mode

    def __str__(self) -> str:
        """Returns itself as printable string"""

        return f'<"{self.__class__.__name__}" object {hex(id(self))}>\n  kinetic_energy_mode={self.kinetic_energy_mode}\n  angle_mode={self.angle_mode}\n  optional={self.optional}'


class GeneralTargetArguments(Arguments):
    """
    Container that stores information of general target arguments

    :param thickness: total thickness of target
    :param segments: number of layers/segments of target
    """

    def __init__(
        self,
        thickness: float = 100.0,
        segments: int = 10,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.thickness = float(thickness)
        self.segments = int(segments)

    def __str__(self) -> str:
        """Returns itself as printable string"""

        return f'<"{self.__class__.__name__}" object {hex(id(self))}>\n  thickness={self.thickness}\n  segments={self.segments}\n  optional={self.optional}'


class GeneralArguments(Arguments):
    """
    Container that stores general information of the simulation

    :param title: title of the simulation
    :param comment: additional comment for the simulation
    :param mode: mode of simulation
    :param fluence: incident fluence in [atoms/A^2]
    :param threads: number of threads used by the simulation
    :param compounds: list of <Compound> containers
    """

    def __init__(
        self,
        title: str,
        comment: str = '',
        mode: ArgumentValues.Mode = ArgumentValues.Mode.STATIC,
        fluence: float = 1,
        threads: int = 0,
        compounds: List[Compound] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.title = str(title)
        self.comment = str(comment)
        self.mode = mode
        self.fluence = float(fluence)
        self.threads = int(threads)
        if compounds is None:
            compounds = []
        self.compounds = compounds

    def __str__(self) -> str:
        """Returns itself as printable string"""

        return f'<"{self.__class__.__name__}" object {hex(id(self))}>\n  title={self.title}\n  comment={self.comment}\n  mode={self.mode}\n  fluence={self.fluence}\n  threads={self.threads}\n  compounds={self.compounds}\n  optional={self.optional}'


class RowArguments(Arguments):
    """
    Container that stores information of each element row

    :param index: index of row
    :param symbol: element symbol of row
    :param element: (possibly modified) element of row
    :param abundance: fraction of row in beam/target (must sum to 1 over all <RowArguments> for beam and target respectively)
    :param max_atomic_fraction: maximum atomic fraction of row
    :param energy: incidence energy of row (beam only)
    :param angle: incidence angle of row (beam only)
    :param modified_element: if element is modified
    """

    def __init__(
        self,
        index: int,
        symbol: str,
        element: Element,
        abundance: float = 1,
        max_atomic_fraction: float = 1,
        energy: float = 0,
        angle: float = 0,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.index = int(index)
        self.symbol = str(symbol)
        self.element = element
        self.abundance = float(abundance)
        self.max_atomic_fraction = float(max_atomic_fraction)
        self.energy = float(energy)
        self.angle = float(angle)

    def __str__(self) -> str:
        """Returns itself as printable string"""

        return f'<"{self.__class__.__name__}" object {hex(id(self))}>\n  index={self.index}\n  symbol={self.symbol}\n  element={self.element}\n  abundance={self.abundance}\n  max_atomic_fraction={self.max_atomic_fraction}\n  energy={self.energy}\n  angle={self.angle}\n  optional={self.optional}'

    def __lt__(self, other):
        """Method used only for sorting (less)"""

        return self.index < other.index

    def __gt__(self, other):
        """Method used only for sorting (greater)"""

        return self.index > other.index

    def __le__(self, other):
        """Method used only for sorting (less or equal)"""

        return self.index <= other.index

    def __ge__(self, other):
        """Method used only for sorting (greater or equal)"""

        return self.index >= other.index

    def __eq__(self, other):
        """Method used only for sorting (equal)"""

        return self.index == other.index


class StructureArguments(Arguments):
    """
    Container that stores information of the structure

    :param name: name of layer
    :param segments: number of segments
    :param thickness: thickness in A
    :param abundances: list of abundances (must sum to 1)
    """

    def __init__(
        self,
        name: str,
        segments: int,
        thickness: float,
        abundances: List[float],
        **kwargs
    ):
        super().__init__(**kwargs)
        self.name = str(name)
        self.segments = int(segments)
        self.thickness = float(thickness)
        self.abundances = abundances

    def __str__(self) -> str:
        """Returns itself as printable string"""

        return f'<"{self.__class__.__name__}" object {hex(id(self))}>\n  name={self.name}\n  segments={self.segments}\n  thickness={self.thickness}\n  abundances={self.abundances}\n  optional={self.optional}'


class SimulationArguments(Arguments):
    """
    Container that stores all arguments specified in the simulation.
    Acts as a container to store all other Arguments-containers.

    :param simulation: name of simulation program
    :param beam_args: <GeneralBeamArguments> for beam settings
    :param beam_rows: list of <RowArguments> for beam
    :param target_args: <GeneralTargetArguments> for target settings
    :param target_rows: list of <RowArguments> for target
    :param structure: list of <StructureArguments> for layers
    :param settings: <GeneralArguments> for general settings
    :param additional: list of additional arguments for input file
    """

    def __init__(
        self,
        simulation: str,
        beam_args: GeneralBeamArguments,
        beam_rows: List[RowArguments],
        target_args: GeneralTargetArguments,
        target_rows: List[RowArguments],
        structure: List[StructureArguments],
        settings: GeneralArguments,
        additional: list,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.simulation = str(simulation)
        self.title = str(settings.title)
        self.beam_args = beam_args
        self.beam_rows = beam_rows
        self.target_args = target_args
        self.target_rows = target_rows
        self.structure = structure
        self.settings = settings
        self.additional = additional

    def get(self, argument: str):
        """
        Returns value of argument which could be in any sub container or None if not set

        :param argument: argument name
        """

        if hasattr(self, argument):
            return getattr(self, argument)
        for key, value in self.__dict__.items():
            if isinstance(value, list):
                for v in value:
                    if isinstance(v, Arguments):
                        res = v.get(argument)
                        if res is not None:
                            return res
            else:
                if isinstance(value, Arguments):
                    res = value.get(argument)
                    if res is not None:
                        return res
        return self.optional.get(argument)

    def __str__(self) -> str:
        """Returns itself as printable string"""

        return f'<"{self.__class__.__name__}" object {hex(id(self))}>\n  simulation={self.simulation}\n  beam_args={self.beam_args}\n  beam_rows={self.beam_rows}\n  target_args={self.target_args}\n  target_rows={self.target_rows}\n  structure={self.structure}\n  settings={self.settings}\n  additional={self.additional}\n  optional={self.optional}'


class ArgumentEncoderJSON(JSONEncoder):
    """Json encoder for <Arguments> classes"""

    def default(self, obj):
        obj_dict = obj.__dict__
        if obj_dict.get('optional') == {}:
            del obj_dict['optional']
        if isinstance(obj, Enum):
            return obj_dict.get('_name_')
        return obj_dict


def saveSimulationArguments(arguments: SimulationArguments, file: str):
    """
    Save all simulation arguments to file

    :param arguments: container of <SimulationArguments>
    :param file: path to save file
    """

    config = {
        'general': {
            'title': arguments.title,
            'simulation': arguments.simulation
        },
        'beam_arguments': arguments.beam_args,
        'beam_rows': [row for row in arguments.beam_rows],
        'target_arguments': arguments.target_args,
        'target_rows': [row for row in arguments.target_rows],
        'structure': [row for row in arguments.structure],
        'settings': arguments.settings,
        'additional': arguments.additional
    }

    with open(file, 'w', encoding='utf-8') as conf_file:
        dump(config, conf_file, indent=4, cls=ArgumentEncoderJSON)


def loadSimulationArguments(file: str) -> Union[bool, SimulationArguments]:
    """
    Load all simulation arguments from file

    :param file: path to save file
    :return: container of <SimulationArguments> or False
    """

    index = RunningIndex()
    assumed = DefaultAssumed()

    def getDict(possible_dict) -> dict:
        """Returns an empty dict if possible_dict is not a dict, otherwise possible_dict is returned"""

        if not isinstance(possible_dict, dict):
            return {}
        return possible_dict

    def getList(possible_list) -> list:
        """Returns an empty list if possible_list is not a list, otherwise possible_list is returned"""

        if not isinstance(possible_list, list):
            return []
        return possible_list

    def getValue(value, value_type: type, default_value, item=None, assumed_cls: DefaultAssumed = None):
        """Returns value if value has type value_type, otherwise return default_value"""

        if assumed_cls is None:
            assumed_cls = []
        if not isinstance(value, value_type):
            if item is not None:
                assumed_cls.assumed(item)
            return default_value
        return value

    def getValueCls(value, cls, default_value, item=None, assumed_cls: DefaultAssumed = None):
        """Returns class member with name value if is class member, otherwise return default_value"""

        if assumed_cls is None:
            assumed_cls = []
        if not isinstance(value, str):
            if item is not None:
                assumed_cls.assumed(item)
            return default_value
        if not hasattr(cls, value):
            if item is not None:
                assumed_cls.assumed(item)
            return default_value
        return getattr(cls, value, default_value)

    # Try to read from json file
    try:
        with open(file, 'r', encoding='utf-8', errors='replace') as conf_file:
            data = load(conf_file)
    except (FileNotFoundError, JSONDecodeError):
        logging.info(f'Could not open file "{file}"!')
        return False

    # general data
    data_general = getDict(data.get('general'))
    general_simulation = getValue(data_general.get('simulation'), str, 'undefined', 'simulation', assumed_cls=assumed)
    general_title = getValue(data_general.get('title'), str, 'undefined', 'title', assumed_cls=assumed)

    # beam_args data (<GeneralBeamArguments>)
    data_beam_args = getDict(data.get('beam_arguments'))
    beam_args_parameters = {
        'kinetic_energy_mode': getValueCls(data_beam_args.get('kinetic_energy_mode'), ArgumentValues.KineticEnergy, ArgumentValues.KineticEnergy.FIXED, 'kinetic_energy_mode', assumed_cls=assumed),
        'angle_mode': getValueCls(data_beam_args.get('angle_mode'), ArgumentValues.Angle, ArgumentValues.Angle.FIXED, 'angle_mode', assumed_cls=assumed)
    }
    beam_args_parameters.update(getDict(data_beam_args.get('optional')))
    beam_args = GeneralBeamArguments(**beam_args_parameters)

    # target_args data (<GeneralTargetArguments>)
    data_target_args = getDict(data.get('target_arguments'))
    target_args_parameters = {
        'thickness': getValue(data_target_args.get('thickness'), float, 2000.0, 'thickness', assumed_cls=assumed),
        'segments': getValue(data_target_args.get('segments'), int, 200, 'segments', assumed_cls=assumed)
    }
    target_args_parameters.update(getDict(data_target_args.get('optional')))
    target_args = GeneralTargetArguments(**target_args_parameters)

    def rowList(rows_list: dict, typ: str) -> List[RowArguments]:
        """Converts the rows_list into a list of <RowArguments>"""

        rows_list = getList(rows_list)
        rows = []
        for row_dict in [getDict(i) for i in rows_list]:
            # only accept rows with set symbols
            if not isinstance(row_dict.get('symbol'), str) or not isinstance(row_dict.get('element'), dict) or row_dict.get('element').get('symbol') is None:
                assumed.assumed(f'{typ} row not convertible')
                continue
            assumed_row = DefaultAssumed()
            row_index = row_dict.get('index')
            if row_index is None:
                row_index = 999
            row_parameters = {
                'index': row_index,
                'symbol': row_dict.get('symbol'),
                'element': Element(**getDict(row_dict.get('element'))),
                'abundance': getValue(row_dict.get('abundance'), float, 1.0, 'abundance', assumed_cls=assumed_row),
                'max_atomic_fraction': getValue(row_dict.get('max_atomic_fraction'), float, 1.0, 'max_atomic_fraction', assumed_cls=assumed_row)
            }
            if typ == 'beam':
                row_parameters.update({
                    'energy': getValue(row_dict.get('energy'), float, 0.0, 'energy', assumed_cls=assumed_row),
                    'angle': getValue(row_dict.get('angle'), float, 0.0, 'angle', assumed_cls=assumed_row)
                })
            optional = getDict(row_dict.get('optional'))
            if optional.get('inelastic_loss_model') is not None:
                optional['inelastic_loss_model'] = getValueCls(optional.get('inelastic_loss_model'), ArgumentValues.InelasticLossModel, ArgumentValues.InelasticLossModel.LINDHARD_SCHARFF_AND_OEN_ROBINSON, 'inelastic_loss_model_row', assumed_cls=assumed)
            row_parameters.update(optional)
            row_parameters.update({
                'assumed': assumed_row
            })
            rows.append(RowArguments(**row_parameters))
        return rows

    # beam_rows data (List[<RowArguments>])
    beam_rows = rowList(data.get('beam_rows'), 'beam')

    # target_rows data (List[<RowArguments>])
    target_rows = rowList(data.get('target_rows'), 'target')

    # force row indices are continuous and in order
    for _, row in sorted(zip([row.index for row in beam_rows + target_rows], beam_rows + target_rows)):
        row.index = index.get()

    # structure data (List[<StructureArguments>])
    structure_list = getList(data.get('structure'))
    structure = []
    for structure_dict in [getDict(i) for i in structure_list]:
        structure_parameters = {
            'name': getValue(structure_dict.get('name'), str, 'Layer', 'layer_name', assumed_cls=assumed),
            'segments': getValue(structure_dict.get('segments'), int, 200, 'layer_segments', assumed_cls=assumed),
            'thickness': getValue(structure_dict.get('thickness'), float, 2000.0, 'layer_thickness', assumed_cls=assumed),
            'abundances': getList(structure_dict.get('abundances'))
        }
        structure_parameters.update(getDict(structure_dict.get('optional')))
        structure.append(StructureArguments(**structure_parameters))

    if not structure:
        abundances = [target.abundance for target in target_rows]
        if not abundances:
            abundances = [1.0]
            assumed.assumed('layer_abundance')
        structure_parameters = {
            'name': 'Layer',
            'segments': target_args.segments,
            'thickness': target_args.thickness,
            'abundances': abundances
        }
        assumed.assumed('layer_name')
        structure = [StructureArguments(**structure_parameters)]

    # settings data (<GeneralArguments>)
    data_settings = getDict(data.get('settings'))
    settings_parameters = {
        'title': getValue(data_settings.get('title'), str, general_title, 'title', assumed_cls=assumed),
        'comment': getValue(data_settings.get('comment'), str, '', 'comment', assumed_cls=assumed),
        'mode': getValueCls(data_settings.get('mode'), ArgumentValues.Mode, ArgumentValues.Mode.STATIC, 'mode', assumed_cls=assumed),
        'fluence': getValue(data_settings.get('fluence'), float, 1.0, 'fluence', assumed_cls=assumed),
        'threads': getValue(data_settings.get('threads'), int, 0, 'threads', assumed_cls=assumed),
        'compounds': [Compound(**getDict(compound)) for compound in getList(data_settings.get('compounds'))]
    }
    optional_settings = data_settings.get('optional')
    if isinstance(optional_settings, dict):
        if optional_settings.get('interaction_potential') is not None:
            optional_settings['interaction_potential'] = getValueCls(optional_settings.get('interaction_potential'), ArgumentValues.InteractionPotential, ArgumentValues.InteractionPotential.KRC, 'interaction_potential', assumed_cls=assumed)
        if optional_settings.get('integration_method') is not None:
            optional_settings['integration_method'] = getValueCls(optional_settings.get('integration_method'), ArgumentValues.IntegrationMethod, ArgumentValues.IntegrationMethod.GAUSS_LEGENDRE, 'integration_method', assumed_cls=assumed)
        if optional_settings.get('surface_binding_model') is not None:
            optional_settings['surface_binding_model'] = getValueCls(optional_settings.get('surface_binding_model'), ArgumentValues.SurfaceBindingModel, ArgumentValues.SurfaceBindingModel.ELEMENT_SPECIFIC, 'surface_binding_model', assumed_cls=assumed)
        if optional_settings.get('inelastic_loss_model') is not None:
            optional_settings['inelastic_loss_model'] = getValueCls(optional_settings.get('inelastic_loss_model'), ArgumentValues.InelasticLossModel, ArgumentValues.InelasticLossModel.LINDHARD_SCHARFF_AND_OEN_ROBINSON, 'inelastic_loss_model', assumed_cls=assumed)
    settings_parameters.update(getDict(optional_settings))
    settings = GeneralArguments(**settings_parameters)

    # additional data (List)
    additional = getList(data.get('additional'))

    return SimulationArguments(
        simulation=general_simulation,
        beam_args=beam_args,
        beam_rows=beam_rows,
        target_args=target_args,
        target_rows=target_rows,
        structure=structure,
        settings=settings,
        additional=additional,
        assumed=assumed
    )
