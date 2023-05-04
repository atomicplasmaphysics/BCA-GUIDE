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


from typing import List, Union, Tuple, Optional, Callable
from itertools import zip_longest
from os import path, listdir
from re import findall, sub

import numpy as np
from scipy.optimize import curve_fit

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QSlider

from Utility.Layouts import (
    MplCanvas, MplCanvasSettings, InputHBoxLayout,
    setWidgetBackground, ListWidget, ListWidgetItem,
    SpinBox, DoubleSpinBox, SpinBoxRange, ComboBox, LineEdit
)
from Utility.Indexing import RunningIndex, DefaultAssumed, DeleteDict, ElementList
from Utility.Functions import dateStr, fileToNpArray, roundToStr, normalizeList, intSafe, floatSafe
from Utility.Dialogs import DownloadDialog

from TableWidgets.CustomTable import CustomRowField
from TableWidgets.CompTable import CompRow

from Containers.Arguments import (
    ArgumentValues, GeneralBeamArguments, GeneralTargetArguments,
    GeneralArguments, RowArguments, SimulationArguments, StructureArguments
)
from Containers.Element import Element, Elements

from Simulations.Simulations import (
    SimulationsInput, SimulationsOutput, HlGeneralBeamSettings,
    HlGeneralTargetSettings, VlGeneralSimulationSettings, HlGeneralPlot
)


class DefaultValues:
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

    def __init__(self, version: str):
        if version == '6.09':
            self.isbv = 8
            self.inel0 = 7


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
        ArgumentValues.InelasticLossModel.ZIEGLER: 6
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
        if version == '6.09':
            self.isbv = {
                ArgumentValues.SurfaceBindingModel.ELEMENT_SPECIFIC: 1,
                ArgumentValues.SurfaceBindingModel.AVERAGE: 2,
                ArgumentValues.SurfaceBindingModel.ELEMENT_PAIRS: 3,
                ArgumentValues.SurfaceBindingModel.COMPOUNDS: 5,
                ArgumentValues.SurfaceBindingModel.FILE: 6,
                ArgumentValues.SurfaceBindingModel.ELECTRONEGATIVITY: 7,
                ArgumentValues.SurfaceBindingModel.TABLE: 8
            }


class HlBeamSettings(HlGeneralBeamSettings):
    """
    QHBoxLayout for general beam settings

    :param version: version of simulation
    """

    def __init__(self, version: str):
        super().__init__(version)
        self.default_values = DefaultValues(self.version)

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
            disabled_list=[4]
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
        self.addStretch(1)

        self.changedEnergy()
        self.changedAngle()

    def changedEnergy(self):
        """
        Enables/disables kinetic energy for beam rows depending on selected energy mode
        Synchronises and enables/disables angle mode if needed
        Popup for energy sweep
        """

        case_e0 = self.kinetic_energy.getValue(save=True)
        case_alpha = self.angle.getValue(save=True)
        self.layout_angle.setEnabled(True)

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

        self.changedEnergy()
        self.changedAngle()

    def getArguments(self) -> GeneralBeamArguments:
        """Returns <GeneralBeamArguments> container of parameters for beam settings"""

        return GeneralBeamArguments(
            kinetic_energy_mode=self.kinetic_energy.getValue(save=True),  # case_e0
            angle_mode=self.angle.getValue(save=True),  # case_alpha
            sweep=self.sweep.value()  # number_calc
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

        self.changedEnergy()
        self.changedAngle()

        return not_loadable


class HlTargetSettings(HlGeneralTargetSettings):
    """
    QHBoxLayout for general target settings

    :param version: version of simulation
    """

    def __init__(self, version: str):
        super().__init__(version)
        self.default_values = DefaultValues(self.version)

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
        self.layout_global_density.checkbox.stateChanged.connect(lambda _: self.changedGlobDens())
        self.global_density.valueChanged.connect(lambda _: self.changedGlobDens())
        self.layout_global_density.checkbox.stateChanged.connect(lambda _: self.edited())
        self.global_density.valueChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_global_density)
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

        global_density_state = self.layout_global_density.checkbox.isChecked()
        global_density = False
        if global_density_state:
            global_density = self.global_density.value()

        self.emit({
            'global_density': global_density,
            'enable_layer_table': not global_density_state
        })

    def reset(self):
        """Resets all input fields"""

        self.layout_thickness.reset()
        self.layout_segments.reset()
        self.layout_global_density.reset()

        self.updateSegmentThickness()
        self.changedGlobDens()

    def getArguments(self) -> GeneralTargetArguments:
        """Returns <GeneralTargetArguments> container of parameters for target settings"""

        global_density = False
        if self.layout_global_density.checkbox.isChecked():
            global_density = self.global_density.value()

        return GeneralTargetArguments(
            thickness=self.thickness.value(),  # ttarget
            segments=self.segments.value(),  # nqx
            global_density=global_density  # !globaldensity
        )

    def loadArguments(self, arguments: SimulationArguments) -> list:
        """Loads <SimulationArguments> container. Returns list of not loadable parameters (default used)"""

        self.reset()
        target_args = arguments.target_args
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
            self.layout_global_density.checkbox.setChecked(False)
        elif isinstance(global_density, float):
            self.global_density.setValue(global_density)
            self.layout_global_density.checkbox.setChecked(True)
        else:
            self.global_density.reset()
            self.layout_global_density.checkbox.setChecked(False)
            self.layout_global_density.mark()
            not_loadable.append('Global density')

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
            if global_density and not self.layout_global_density.checkbox.isChecked():
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
            tooltip='The first line of the <i>tri.inp</i> file'
        )
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
        self.layout_histories_limit.checkbox.toggled.connect(lambda state: self.changeHistoriesBetween(state))

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
        self.surface_binding_model_entries_save = [
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

        if self.version == '6.09':
            self.surface_binding_model_entries = [
                'element-specific',
                'average for all elements',
                'element-pair averages',
                'compounds only',
                '(not supported)',
                'from mat_surfb.inp',
                'from electronegativity',
                'from table1a'
            ]
            self.surface_binding_model_entries_save = [
                ArgumentValues.SurfaceBindingModel.ELEMENT_SPECIFIC,
                ArgumentValues.SurfaceBindingModel.AVERAGE,
                ArgumentValues.SurfaceBindingModel.ELEMENT_PAIRS,
                ArgumentValues.SurfaceBindingModel.COMPOUNDS,
                -1,
                ArgumentValues.SurfaceBindingModel.FILE,
                ArgumentValues.SurfaceBindingModel.ELECTRONEGATIVITY,
                ArgumentValues.SurfaceBindingModel.TABLE
            ]
            self.surface_binding_model_entries_tooltips = [
                'sbv(ip,jp)=e_surfb(jp) for ip=jp',
                'sbv(ip,jp)=e_surfb(jp) for all ip, jp',
                'sbv(ip,jp)=0., if e_surfb(ip)=0 or e_surfb(jp)=0\nelse: sbv(ip,jp)=0.5*(e_surfb(ip)+e_surfb(jp))',
                'e_bulkb(compound)=deltaH_f\nsbv(ip,jp)=e_surfb(jp) for ip=jp, =0 else',
                '',
                'input of given matrix of the surface-bindig-energy: "mat_surfb.inp"',
                'calculate according to "Kudriavtsev"',
                'e_surfb=0, e_bulkb=Es, e_cutoff=Es/3\ne_bulkb(compound)=Es+deltaH_f'
            ]
            self.surface_binding_model_disabled_list = [4]

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
        self.layout_group_elements.checkbox.clicked.connect(lambda _: self.changedGroupElements())
        self.layout_group_elements.checkbox.clicked.connect(lambda _: self.edited())
        self.addLayout(self.layout_group_elements)

        # additional output options
        self.addSpacing(10)
        self.addWidget(QLabel('<b>Additional output options</b>'))

        # reflected projectiles
        self.layout_reflected = InputHBoxLayout(
            'Reflected projectiles',
            None,
            checkbox=self.default_values.lparticle_p,
            tooltip='<i>lparticle_p</i><br>Compute the angle and energy distributions of reflected projectiles and write them to output files'
        )
        self.layout_reflected.checkbox.clicked.connect(lambda _: self.edited())
        self.addLayout(self.layout_reflected)

        # sputtered recoil atoms
        self.layout_sputtered = InputHBoxLayout(
            'Sputtered recoil atoms',
            None,
            checkbox=self.default_values.lparticle_r,
            tooltip='<i>lparticle_r</i><br>Compute the angle and energy distributions of sputtered recoil atoms and write them to output files'
        )
        self.layout_sputtered.checkbox.clicked.connect(lambda _: self.edited())
        self.addLayout(self.layout_sputtered)

        # matrix files
        self.layout_matrix_files = InputHBoxLayout(
            'Matrix files',
            None,
            checkbox=self.default_values.lmatrices,
            tooltip='<i>lmatrices</i><br>Compute and write the pre-sorted secondary particle distributions to output files'
        )
        self.layout_matrix_files.checkbox.clicked.connect(lambda _: self.edited())
        self.addLayout(self.layout_matrix_files)

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
            disabled_list = [self.integration.entries_save.index(ArgumentValues.IntegrationMethod.MAGIC)]
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
            self.layout_matrix_files.checkbox.setChecked(False)
        self.fluence.setEnabled(dynamic)
        self.emit({
            'max_concentration': dynamic
        })

    def changedGroupElements(self):
        """Grouping of elements has changed"""

        self.emit({
            'group_elements': self.layout_group_elements.checkbox.isChecked()
        })

    def reset(self):
        """Resets all input fields"""

        self.title.default = f'SDTrimSP - {dateStr()}'
        self.layout_title.reset()
        self.layout_calculation_method.reset()
        self.layout_histories_limit.checkbox.setChecked(False)
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

        self.changedPotential()
        self.changedMode()

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
            group_elements=self.layout_group_elements.checkbox.isChecked(),
            log_reflected=self.layout_reflected.checkbox.isChecked(),  # lparticle_p
            log_sputtered=self.layout_sputtered.checkbox.isChecked(),  # lparticle_r
            log_matrix=self.layout_matrix_files.checkbox.isChecked()  # lmatrices
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
            self.layout_histories_limit.checkbox.setChecked(False)
        else:
            idout = -1
            self.layout_histories_limit.checkbox.setChecked(True)
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
            self.layout_group_elements.checkbox.setChecked(False)
        else:
            group_elements = settings.get('group_elements')
            if not isinstance(group_elements, bool):
                group_elements = self.default_values.group_elements
            self.layout_group_elements.checkbox.setChecked(group_elements)

        # output matrices (not relevant in not_loadable list)
        lparticle_p = settings.get('log_reflected')
        if not isinstance(lparticle_p, bool):
            lparticle_p = self.default_values.lparticle_p
        self.layout_reflected.checkbox.setChecked(lparticle_p)

        lparticle_r = settings.get('log_sputtered')
        if not isinstance(lparticle_r, bool):
            lparticle_r = self.default_values.lparticle_r
        self.layout_sputtered.checkbox.setChecked(lparticle_r)

        lmatrices = settings.get('log_matrix')
        if not isinstance(lmatrices, bool):
            lmatrices = self.default_values.lparticle_p
        self.layout_matrix_files.checkbox.setChecked(lmatrices)

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
                self.layout_reflected.checkbox.setChecked(False)

                self.layout_sputtered.setEnabled(False)
                self.layout_sputtered.checkbox.setChecked(False)

                if self.calculation_method.getValue(save=True) != ArgumentValues.Mode.DYNAMIC:
                    self.layout_matrix_files.setEnabled(False)
                    self.layout_matrix_files.checkbox.setChecked(False)

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
            self.layout_group_elements.checkbox.setChecked(bool(group_elements))


class CompRowBeamSettings(CompRow):
    """
    CompRow for beam

    :param version: version of simulation
    """

    syncHint = '<br>If the element occurs in both the beam and the target, the value is defined in the target table.'
    modifyHint = '<br>A red highlight indicates a modified value. A negative number resets it back to the default one.'
    rowFields = [
        CustomRowField(
            unique='qubeam',
            label='Abundance',
            tooltip='<i>qubeam</i><br>How much each element contributes to the beam composition.<br>The abundances of all elements sum up to 1.',
            synced=False,
            limit=1
        ),
        CustomRowField(
            unique='e0',
            label='Energy [eV]',
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
            unique='inel0',
            label='Inelastic loss model',
            tooltip='<i>inel0</i><br>The inelastic loss model used for calculations.' + syncHint
        )
    ]

    def __init__(self, *args, version: str = '', **kwargs):
        super().__init__(*args, **kwargs)
        self.version = version
        self.default_values = DefaultValues(self.version)
        self.dict_lookup = DictLookup(self.version)

        self.max_concentration_field = self.rowFields[3]

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
        if self.version == '6.09':
            self.inelastic_loss_model_entries.append('LZ7')
            self.inelastic_loss_model_entries_save.append(ArgumentValues.InelasticLossModel.LINDHARD_SCHARFF_AND_ZIEGLER)
            self.inelastic_loss_model_tooltips.append('Combination of Lindhard-Scharff and Ziegler-Biersack with corretion')

        self.inelastic_loss_model = ComboBox(
            default=self.default_values.inel0,
            entries=self.inelastic_loss_model_entries,
            entries_save=self.inelastic_loss_model_entries_save,
            numbering=1,
            label_default=True,
            tooltips=self.inelastic_loss_model_tooltips
        )

        self.inelastic_loss_model.currentIndexChanged.connect(self.contentChanged.emit)
        self.inelastic_loss_model.mouseReleaseEvent = lambda _: setWidgetBackground(self.inelastic_loss_model, False)

        self.row_widgets += [
            self.abundance,
            self.kinetic_energy,
            self.angle,
            self.maximum_concentration,
            self.atomic_mass,
            self.atomic_density,
            self.surface_binding_energy,
            self.displacement_energy,
            self.inelastic_loss_model
        ]

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
            self.inelastic_loss_model.setValue(ArgumentValues.InelasticLossModel.HYDROGEN, True)
        elif self.element.symbol in ['He', 'He3']:
            self.inelastic_loss_model.setValue(ArgumentValues.InelasticLossModel.HELIUM, True)

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
            inelastic_loss_model=self.inelastic_loss_model.getValue(save=True)  # inel0
        )

    def setArguments(self, arguments: RowArguments, general_arguments: SimulationArguments):
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

    rowFields = CompRowBeamSettings.rowFields[3:]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.row_widgets = self.row_widgets[0:3] + self.row_widgets[6:]

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
        self.history_step_slider = QSlider(Qt.Horizontal)
        self.history_step_slider.setMinimumWidth(200)
        self.history_step_slider.setMinimum(0)
        self.history_step_slider.setToolTip(self.history_step_tooltip)
        self.history_step_slider.hide()
        self.addWidget(QLabel())
        self.addWidget(self.history_step_slider)
        self.addStretch(1)

        # connect history sliders
        self.history_step.valueChanged.connect(self.history_step_slider.setValue)
        self.history_step_slider.valueChanged.connect(self.history_step.setValue)
        self.history_step.valueChanged.connect(lambda val: self.emit({'history': val}))

    def receive(self, value_dict: dict):
        """Receives pyqtSignal -> dict"""

        # hide buttons
        hide = value_dict.get('hide')
        if isinstance(hide, bool):
            self.layout_history_step.setHidden(hide)
            self.history_step_slider.setHidden(hide)

        # set max history
        max_hist = value_dict.get('max_history')
        if max_hist is not None:
            max_hist = int(max_hist)
            self.history_step.setMaximum(max_hist)
            self.history_step_slider.setMaximum(max_hist)

        # set history
        hist = value_dict.get('history')
        if hist is not None:
            hist = int(hist)
            self.history_step_slider.setValue(hist)


class SimulationInput(SimulationsInput):
    """
    Class for SDTrimSP specific parameters
    """

    # parameters should be different for each simulation class
    Name = 'SDTrimSP'
    Versions = [
        '6.01, 6.06',
        '6.09'
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
    Logo = ':icons/aboutlogo_ipp.png'
    About = '''
Andreas Mutzke

<a href="https://www.ipp.mpg.de">https://www.ipp.mpg.de/</a>
    '''
    SaveFolder = 'SDTrimSP'
    InputFilename = 'tri.inp'
    LayerFilename = 'layer.inp'
    ExampleAdditionalSetting = 'e.g. ienergy_distr = .true.'
    SkipList = [InputFilename, LayerFilename, 'ausdat.dat']
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
    def getVersionName(folder: str, binary: str) -> Union[str, bool]:
        """
        Returns version of simulation depending on selected folder and binary or False if no version can be determined

        :param folder: main folder of simulation
        :param binary: binary of simulation
        """

        version = []
        # checked on sourcecode or if 'src'-directory exists
        source_code = f'{folder}/src/SDTrimSP.F90'  # check sourcecode
        if path.exists(source_code):
            with open(source_code, 'r') as f:
                for line in f:
                    if line.strip().startswith('avs0 ='):
                        version = [line.split('\'')[1]]  # save as array to we can ask its length
                        break
        if not version and path.exists(f'{folder}/src'):  # search path
            version = findall(r'\d+\.\d+', folder)
        if not version:  # search binary path
            version = findall(r'\d+\.\d+', binary)

        if not len(version) or not len(version[0]):
            return False

        return f'SDTrimSP v{version[0]}'

    @staticmethod
    def getDoc(folder: str, binary: str, version: str) -> Union[str, bool]:
        """
        Returns path to documentation pdf-file

        :param folder: main folder of simulation
        :param binary: binary of simulation
        :param version: version of simulation

        :return: path to documentation pdf-file or
                 True if no documentation can be found but there is a possibility to download
                 False if no documentation can be found
        """

        # check for pdf file in doc folder
        doc_folder = f'{folder}/doc'
        if path.exists(doc_folder):
            files = [file for file in listdir(doc_folder) if path.isfile(f'{doc_folder}/{file}') and path.splitext(f'{doc_folder}/{file}')[1].lower() == '.pdf']
            if files:
                return f'{doc_folder}/{files[0]}'

        # check for pdf files in main folder
        files = [file for file in listdir(folder) if path.isfile(f'{folder}/{file}') and path.splitext(f'{folder}/{file}')[1].lower() == '.pdf']
        if files:
            return f'{folder}/{files[0]}'

        # no pdf documentation found, but downloadDoc method is implemented
        return True

    @staticmethod
    def downloadDoc(parent, folder: str, binary: str, version: str):
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
            path=f'{folder}/doc',
            name='IPP_2019-02.pdf',
            expected_file_size=1250762
        )
        dialog.open()

    def update(self, folder: str, binary: str, version: str):
        """
        Updates on startup

        :param folder: folder of simulation
        :param binary: binary path of simulation
        :param version: version of simulation
        """

        # update number of components
        if version == '6.09':
            self.MaxComponents = 11

        # update OutputTooltips
        # -> could be used, but is not: formatting in this file is bad for reading and there are spelling mistakes
        # -> not all files are described in output_files.txt, some are in Readme
        update_tooltips = False
        if update_tooltips:
            output_variables_doc = f'{folder}/doc/output_files.txt'
            if path.exists(output_variables_doc):
                with open(output_variables_doc, 'r') as file:
                    for line in file.readlines():
                        content = line.split('.dat')
                        if len(content) <= 1:
                            continue

                        output_file_name = f'{content[0].strip()}.dat'
                        self.OutputTooltips[output_file_name] = content[1].strip()

        # update possible input variables
        input_variables_doc = f'{folder}/doc/tri.inp.txt'
        if path.exists(input_variables_doc):
            with open(input_variables_doc, 'r') as file:
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

                    data_type = str
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

    def updateElements(self, folder: str, version: str) -> bool:
        """
        Updates list of <Element> for this simulation

        :param folder: main folder of simulation
        :param version: version of simulation
        """

        element_list = []
        table_path = f'{folder}/tables/table1'
        if path.exists(table_path):

            # get table contents
            table_str = []
            with open(table_path, 'r', encoding='cp1250') as file:
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
            table = []
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
                t = [t_str[:divisions[0]].strip()]
                for i in range(len(divisions) - 1):
                    t.append(t_str[divisions[i]:divisions[i + 1]].strip())
                t.append(t_str[divisions[-1]:].strip())
                table.append(t)

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

                name = {
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

                element = Element(
                    symbol=symbol,
                    name=name,
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
                    element_list.insert(-1, element)
                else:
                    element_list.append(element)

        if not element_list:
            super().loadDefaultElements(version)
            return False

        self.element_data_default = False
        return self.element_data.updateElements(element_list)

    def makeInputFile(self, arguments: SimulationArguments, folder: str, version: str) -> str:
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

        grouped_rows = []
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

        title = arguments.settings.title

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
                if element.surface_binding_energy != original_element.surface_binding_energy:
                    e_surfb_modified = True

                e_displ.append(element.displacement_energy)
                if element.displacement_energy != original_element.displacement_energy:
                    e_displ_modified = True

                dns0.append(element.atomic_density)
                if element.atomic_density != original_element.atomic_density:
                    dns0_modified = True

                a_mass.append(element.atomic_mass)
                if element.atomic_mass != original_element.atomic_mass:
                    a_mass_modified = True

        e_surfb = [f'{e}' for e in e_surfb]
        e_displ = [f'{e}' for e in e_displ]
        dns0 = [f'{e}' for e in dns0]
        a_mass = [f'{e}' for e in a_mass]

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
        qubeam = [f'{q}' for q in qubeam]
        qubeam = ', '.join(qubeam)

        case_e0 = arguments.beam_args.kinetic_energy_mode
        if case_e0 is not None:
            case_e0 = dict_lookup.case_e0.get(case_e0)
        if case_e0 is None:
            case_e0 = default_values.case_e0

        if group_elements:
            e0 = [beam_row.energy if beam_row is not None else 0.0 for beam_row, _ in grouped_rows]
        else:
            e0 = [row.energy for row in rows]
        e0 = [f'{e}' for e in e0]
        e0 = ', '.join(e0)

        case_alpha = arguments.beam_args.angle_mode
        if case_alpha is not None:
            case_alpha = dict_lookup.case_alpha.get(case_alpha)
        if case_alpha is None:
            case_alpha = default_values.case_alpha

        if group_elements:
            alpha0 = [beam_row.angle if beam_row is not None else 0.0 for beam_row, _ in grouped_rows]
        else:
            alpha0 = [row.angle for row in rows]
        alpha0 = [f'{a}' for a in alpha0]
        alpha0 = ', '.join(alpha0)

        number_calc = arguments.beam_args.get('sweep')
        if number_calc is None:
            number_calc = default_values.number_calc
        if case_e0 != dict_lookup.case_e0.get(ArgumentValues.KineticEnergy.SWEEP) and case_alpha != dict_lookup.case_alpha.get(ArgumentValues.Angle.SWEEP):
            number_calc = ''
        else:
            number_calc = f'    number_calc = {number_calc}\n'

        # --- target ---

        iq0 = 1 - len(arguments.structure)

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

        qu = normalizeList(qu)
        qu = [f'{q}' for q in qu]
        qu = ', '.join(qu)

        if group_elements:
            qumax = []
            for beam_row, target_row in grouped_rows:
                if beam_row is None:
                    qumax.append(target_row.max_atomic_fraction)
                else:
                    qumax.append(beam_row.max_atomic_fraction)
        else:
            qumax = [row.max_atomic_fraction for row in rows]
        qumax = [f'{q}' for q in qumax]
        qumax = ', '.join(qumax)

        ttarget = arguments.target_args.thickness

        nqx = arguments.target_args.segments

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

        # --- extra ---

        tableinp = f'{folder}/tables'
        additional = '\n    '.join(arguments.additional)

        out = f'''
{title}
&TRI_INP
text = "--- elements ---"
    ncp = {ncp}
    symbol = {symbol}
    !globaldensity = {global_density}
    inel0 = {inel0}
{modifications}
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
    qubeam = {qubeam}
    case_e0 = {case_e0}
    e0 = {e0}
    case_alpha = {case_alpha}
    alpha0 = {alpha0}
{number_calc}
text = "--- target ---"
    qu = {qu}
    qumax = {qumax}
    ttarget = {ttarget}
    nqx = {nqx}
    iq0 = {iq0}

text = "--- output options ---"
    lparticle_p = {lparticle_p_str}
    lparticle_r = {lparticle_r_str}
    lmatrices = .{str(lmatrices).lower()}.

text = "--- extra ---"
    tableinp = "{tableinp}"
    {additional}
/
'''
        return f'{out.strip()}\n'

    @staticmethod
    def makeLayerFile(arguments: SimulationArguments, folder: str, version: str) -> str:
        """
        Returns layer input file as string

        :param arguments: <SimulationArguments> container
        :param folder: folder of simulation
        :param version: version of simulation
        """

        structures = arguments.structure
        if len(structures) < 2:
            return ''

        default_values = DefaultValues(version)

        group_elements = arguments.settings.get('group_elements')
        if not isinstance(group_elements, bool):
            group_elements = default_values.group_elements

        grouped_rows = []
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
        for structure in structures:
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
            layer_info += '  '.join([f'{abundance:>13.5E}' for abundance in abundance_list[1:]])
            layer_info += f'    {structure.name}'
            layer_info_total.append(layer_info)
        layer_info_total = '\n'.join(layer_info_total)
        out = f'''
number of    thick-    target composition 2...ncp    name of layer
layers       ness      {'           '.join([f'qu_{i + 2}' for i in range(abundances)])}
{layer_info_total}
     0            0    {'    '.join(['          0' for _ in range(abundances)])}    end
'''
        return f'{out.strip()}\n'

    def loadFiles(self, folder: str, version: str) -> Union[Tuple[SimulationArguments, list], str, bool]:
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

        input_file = f'{folder}/{self.InputFilename}'
        layer_file = f'{folder}/{self.LayerFilename}'

        if not path.exists(input_file):
            return False

        contents = DeleteDict()

        # get all contents from input file
        with open(input_file, 'r') as file:
            contents['title'] = file.readline().strip()
            for line in file.readlines():
                content = [p.strip() for p in line.strip().split('=')]
                if len(content) != 2 or content[0] == 'text':
                    continue
                contents[content[0]] = content[1]

        assumed = DefaultAssumed()
        error_list = []

        def getValue(value: str, value_type: type, default_value, item=None, assumed_cls: DefaultAssumed = None):
            """Returns value if value has type value_type, otherwise return default_value"""

            if assumed_cls is None:
                assumed_cls = []
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

            if 'False' in value:
                return False
            try:
                return float(value.split(',')[1].strip())
            except ValueError:
                return False

        def getValueDict(value: str, lookup_dict: dict, default_value, item=None, assumed_cls: DefaultAssumed = None):
            """Returns class member with name value if is class member, otherwise return default_value"""

            if assumed_cls is None:
                assumed_cls = []
            try:
                return [k for k, v in lookup_dict.items() if v == int(value)][0]
            except (ValueError, IndexError):
                if item is not None:
                    assumed_cls.assumed(item)
                return [k for k, v in lookup_dict.items() if v == default_value][0]

        def getValueList(value: str, value_type, default_value, item=None, lookup_dict=None, assumed_cls: DefaultAssumed = None) -> list:
            """Returns list of values converted to value_type. If conversion of list element is not successful, it is replaced by default_value"""

            if assumed_cls is None:
                assumed_cls = []
            if not isinstance(value, str):
                if item is not None:
                    assumed_cls.assumed(item)
                value = ''
            values = value.replace('\"', '').replace('\'', '').split(',')
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
        idrel = getValueDict(contents.get('idrel'), dict_lookup.idrel, default_values.idrel + 1, 'mode', assumed_cls=assumed)
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
        globaldensity = getValueBoolInt(contents.get('!globaldensity'))
        case_e0 = getValueDict(contents.get('case_e0'), dict_lookup.case_e0, default_values.case_e0, 'kinetic_energy_mode', assumed_cls=assumed)
        case_alpha = getValueDict(contents.get('case_alpha'), dict_lookup.case_alpha, default_values.case_alpha, 'angle_mode', assumed_cls=assumed)
        number_calc = getValue(contents.get('number_calc'), float, default_values.number_calc, 'sweeps', assumed_cls=assumed)
        iq0 = getValue(contents.get('iq0'), int, 0, 'composition_profile', assumed_cls=assumed)
        nqx = getValue(contents.get('nqx'), int, default_values.nqx, 'segments', assumed_cls=assumed)
        ttarget = getValue(contents.get('ttarget'), float, default_values.ttarget, 'thickness', assumed_cls=assumed)
        symbol = getValueList(contents.get('symbol'), str, 'H', 'symbol', assumed_cls=assumed)
        inel0 = getValueList(contents.get('inel0'), getValueDict, default_values.inel0, 'inelastic_loss_model', dict_lookup.inel0, assumed_cls=assumed)
        qubeam = getValueList(contents.get('qubeam'), float, default_values.qubeam, 'abundance', assumed_cls=assumed)
        qu = getValueList(contents.get('qu'), float, default_values.qubeam, 'abundance', assumed_cls=assumed)
        qumax = getValueList(contents.get('qumax'), float, default_values.qumax, 'max_atomic_fraction', assumed_cls=assumed)
        e0 = getValueList(contents.get('e0'), float, default_values.e0, 'energy', assumed_cls=assumed)
        alpha0 = getValueList(contents.get('alpha0'), float, default_values.alpha0, 'angle', assumed_cls=assumed)
        ncp = getValue(contents.get('ncp'), int, -1, assumed_cls=assumed)
        e_surfb = getValueList(contents.get('e_surfb'), float, -1.0, assumed_cls=assumed)
        e_displ = getValueList(contents.get('e_displ'), float, -1.0, assumed_cls=assumed)
        dns0 = getValueList(contents.get('dns0'), float, -1.0, assumed_cls=assumed)
        a_mass = getValueList(contents.get('a_mass'), float, -1.0, assumed_cls=assumed)

        # get rid of 'tableinp' since it is not used
        contents.get('tableinp')

        # get rid of 'ioutput_part(x)'
        contents.get('ioutput_part(2)')
        contents.get('ioutput_part(5)')

        additional = []

        for add_key, add_val in contents.items():
            additional.append(f'{add_key} = {add_val}')

        if not len(symbol) == len(qubeam) == len(qu) == ncp:
            return f'Length of lists "symbol({len(symbol)})", "qubeam({len(qubeam)})", "qu({len(qu)})" and "ncp={ncp}" are different.'

        index = RunningIndex()

        def rowList(qu_list: list, typ: str) -> List[RowArguments]:
            """Converts the qu_list into a list of <RowArguments>"""

            rows: List[RowArguments] = []
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
                    inel0_i = [k for k, v in dict_lookup.inel0.items() if v == default_values.inel0][0]
                    assumed_row.assumed('inelastic_loss_model_row')

                row_parameters = {
                    'index': index.get(),
                    'symbol': symbol_i,
                    'element': element_i,
                    'abundance': qu_i,
                    'inelastic_loss_model': inel0_i,
                    'max_atomic_fraction': qumax_i
                }

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
                rows.append(RowArguments(**row_parameters))
            return rows

        # beam_rows data (List[<RowArguments>])
        beam_rows = rowList(qubeam, 'beam')

        # target_rows data (List[<RowArguments>])
        target_rows = rowList(qu, 'target')

        # beam_args data (<GeneralBeamArguments>)
        beam_args = GeneralBeamArguments(
            kinetic_energy_mode=case_e0,
            angle_mode=case_alpha,
            sweep=number_calc
        )

        # target_args data (<GeneralTargetArguments>)
        target_args = GeneralTargetArguments(
            thickness=ttarget,
            segments=nqx,
            global_density=globaldensity
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
            log_matrix=lmatrices
        )

        layer_counter = RunningIndex()
        structure = []
        if iq0 < 0:
            error_layer = 'Layer file has incorrect format.'
            if not path.exists(layer_file):
                error_list.append('No known layer files in this directory, assuming no layer file.')
            else:
                # get all contents from layer file
                with open(layer_file, 'r') as file:
                    for line in file.readlines():
                        line = line.strip()
                        if not line:
                            continue
                        if not line[0].isdigit() and line[0] != '.':
                            continue

                        content = [p.strip() for p in line.split(' ') if p.strip()]
                        if not content or content[-1] == 'end' or all(v == 0 for v in content[:-1]):
                            continue
                        if len(content) < 1 + ncp:
                            if error_layer not in error_list:
                                error_list.append(error_layer)
                            continue

                        name = f'Layer{layer_counter.get()}'
                        abundances = content[2:ncp + 1]
                        if len(content) > 1 + ncp:
                            name = content[ncp + 1]

                        try:
                            abundances = [float(a) for a in abundances]
                            abundances.insert(0, 1 - sum(abundances))
                        except ValueError:
                            if error_layer not in error_list:
                                error_list.append(error_layer)
                            continue

                        abundances = [a for (a, q) in zip(abundances, qu) if q]

                        segments = getValue(content[0], int, default_values.nqx, 'layer_segments')
                        thickness_per_segment = getValue(content[1], float, default_values.ttarget, 'layer_thickness')

                        structure.append(StructureArguments(
                            name=name,
                            segments=segments,
                            thickness=segments * thickness_per_segment,
                            abundances=abundances
                        ))

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

        simulation = SimulationArguments(
            simulation=self.Name,
            beam_args=beam_args,
            beam_rows=beam_rows,
            target_args=target_args,
            target_rows=target_rows,
            structure=structure,
            settings=settings,
            additional=additional,
            assumed=assumed
        )

        return simulation, error_list

    def checkAdditional(self, settings: str, version: str) -> List[str]:
        """
        Checks the user defined additional settings and returns list of errors

        :param settings: provided additional settings
        :param version: version of simulation

        :return: list of errors
        """

        if not settings:
            return []

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

            parameter_type = self.InputParameters.get(content[0].split('(')[0].strip())
            if parameter_type is None:
                errors.append(f'Line {i + 1}: Unknown variable "{content[0]}"')

            if content[0].count('(') != content[0].count(')'):
                errors.append(f'Line {i + 1}: Parentheses do not match')

            data_type = str
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
                if not (parameter_type == float and data_type == int):
                    errors.append(f'Line {i + 1}: variable "{content[0]}" has wrong type (should be {parameter_type})')

        return errors

    def getProgress(self, save_folder: str, process_log: str, version: str) -> int:
        """
        Returns progress in % of running simulation.
        Negative return value indicates some error.

        :param save_folder: folder for output files
        :param process_log: most recent output of process
        :param version: version of simulation
        """

        files = listdir(save_folder)
        log_file = 'time_run.dat'

        if log_file not in files:
            return -1

        percent = -1
        with open(f'{save_folder}/{log_file}', 'r') as file:
            for line in reversed(file.readlines()):
                data = line.split(' %')
                if len(data) == 2 and data[0][0] not in ['I', 'W']:
                    try:
                        percent = int(data[0][-3:])
                        break
                    except (ValueError, IndexError):
                        pass

        # single run
        if not any('001' in file for file in files) or percent < 0:
            return percent

        # sweep run
        else:
            current_sweep = len([None for file in files if 'output.' in file])
            if self.InputFilename not in files:
                return -1
            sweeps = DefaultValues(version).number_calc
            with open(f'{save_folder}/{self.InputFilename}', 'r') as file:
                for line in file.readlines():
                    if not line.strip().startswith('number_calc'):
                        continue
                    try:
                        sweeps = int(line.split(' = ')[1])
                        break
                    except ValueError:
                        pass

            return round((100 * current_sweep + percent) / sweeps)


class SimulationOutput(SimulationsOutput):
    """
    Class for displaying SDTrimSP specific parameters and plots
    """

    # References to classes
    HlPlot = HlPlot

    def __init__(self, plot: MplCanvas, element_data: Elements):
        super().__init__(plot, element_data)

        self.is_dynamic = False

        self.particle_back_p_data = np.array([])
        self.particle_back_r_data = np.array([])

        self.fluence_array = None
        self.depth_array = None
        self.conc_array = None

    def receive(self, value_dict: dict):
        """Receives pyqtSignal -> dict"""

        histories = value_dict.get('history')
        if histories is not None:
            result = self.plotDepthConcentration(history_step=int(histories))
            if result is None:
                self.data = None
            else:
                self.data, plot_settings = result
                plot_settings.apply(self.plot)

    def reset(self):
        """Reset class"""

        super().reset()

        self.is_dynamic = False

        self.particle_back_p_data = np.array([])
        self.particle_back_r_data = np.array([])

        self.fluence_array = None
        self.depth_array = None
        self.conc_array = None

    @staticmethod
    def ecksteinAngleFit(angles, y0, alpha0, b, c, f):
        """Eckstein fit function"""

        out_value = np.zeros(len(angles))

        for i, alpha in enumerate(angles):
            if alpha == 0.:
                out_value[i] = y0

            else:
                cos = np.cos((alpha / alpha0 * np.pi / 2) ** c)
                out_value[i] = y0 * np.power(cos, -f) * np.exp(b * (1 - 1 / cos))

        return out_value

    def updateData(self, save_folder: str, file: str):
        """
        Update evaluation data from file

        :param save_folder: path to save folder
        :param file: target file
        """

        target = f'{save_folder}/{file}'
        if not path.exists(target):
            return

        # data from target file
        self.save_folder = save_folder
        with open(target, 'r') as file:
            for i in range(4):
                file.readline()
            contents = file.readline().split()
            ncp = int(contents[2])
            self.is_dynamic = int(contents[-1]) == 0
            elements = file.readline().split()

        # check if both are equal
        if ncp != len(elements):
            return

        self.elements = ElementList()
        for element in elements:
            self.elements.append(element)

        # get masses
        self.masses = np.array([self.element_data.elementFromSymbol(element).atomic_mass for element in elements])

    def getElementIndex(self, element: str) -> int:
        """Returns index of element"""
        if element not in self.elements:
            return 0
        return self.elements.index(element)

    def getOutputFileData(self) -> Optional[Tuple[np.ndarray, ...]]:
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

        output = f'{self.save_folder}/output.dat'
        if not path.exists(output):
            return

        with open(output, 'r') as file:
            content = [line.strip().lower() for line in file.readlines()]

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

        serie = f'{self.save_folder}/serie.dat'
        if not path.exists(serie):
            return

        with open(serie, 'r') as file:
            file.readline()

            # line 2: ncp and ncp_proj
            line_content = file.readline().split()
            ncp = int(line_content[0])
            ncp_proj = int(line_content[1])

            file.readline()

            # line 4: elements
            elements = file.readline().split()[-ncp:]

            file.readline()

            # line 6 - 6+ncp: element data
            masses = np.zeros(ncp)
            for i in range(ncp):
                masses[i] = float(file.readline().split()[2])

            # skip lines starting with '!'
            line = file.readline()
            while line.strip().startswith('!'):
                line = file.readline()

            # line (6+ncp+offset)+0 / +1: number energies / number angles
            nr_energies = int(line.split()[0])
            nr_angles = int(file.readline().split()[0])
            nr_total = nr_angles * nr_energies

            for _ in range(4):
                file.readline()

            # line (6+ncp+offset)+6: elements list
            elements_projectiles = []
            line_elements = file.readline().split()
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
                line = file.readline().split()

                if not line:
                    break

                while len(line) < expected_line_elements:
                    line.extend(file.readline().split())

                energies[i] = line[0]
                angles[i] = line[1]
                mean_depth[i] = line[2]

                for j in range(ncp_proj):
                    refl_coefficients[i, j] = floatSafe(line[3 + 2 * j], 0)
                    energ_refl_coefficients[i, j] = floatSafe(line[3 + 2 * j + 1], 0)
                for j in range(ncp):
                    sputt_coefficients[i, j] = floatSafe(line[3 + 2 * ncp_proj + 2 * j], 0)
                    energ_sputt_coefficients[i, j] = floatSafe(line[3 + 2 * ncp_proj + 2 * j + 1], 0)

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

        depth_file = f'{self.save_folder}/{filename}'
        if not path.exists(depth_file):
            return

        with open(depth_file, 'r') as file:
            content = [line.strip().lower() for line in file.readlines() if line.strip()]

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

        damage_file = f'{self.save_folder}/{filename}'
        if not path.exists(damage_file):
            return

        with open(damage_file, 'r') as file:
            content = [line.strip().lower() for line in file.readlines()]

        line_content = content[2].split()
        ncp = int(line_content[0])
        nr_of_projectiles = int(float(line_content[1]))

        nr_of_depth_steps = np.zeros(ncp, dtype=int)
        data_start_line = np.zeros(ncp, dtype=int)

        for i in range(ncp):
            depth_step_index = 3 + i * (4 + 1 + 5) + int(np.sum(nr_of_depth_steps[:i])) + 1
            data_start_line[i] = depth_step_index + 3
            nr_of_depth_steps[i] = int(content[depth_step_index].split()[0])

        file_elements = []
        for i in range(ncp):
            element_line_index = 2 + i * (4 + 1 + 5) + int(np.sum(nr_of_depth_steps[:i])) + 1
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

    def getParticleData(self, projectile_or_recoil: str = 'p') -> Optional[List[np.ndarray]]:
        """
        Returns content from particle files

        :param projectile_or_recoil: string to indentify if particle ('p') of recoil ('r') data should be used

        :return: list of file data per element
                 or None
        """

        is_projectile = projectile_or_recoil.startswith('p')
        letter_file_name = 'p' if is_projectile else 'r'
        file_path = f'{self.save_folder}/partic_back_{letter_file_name}.dat'
        if not path.exists(file_path):
            return

        old_data_len = len(self.particle_back_p_data) if is_projectile else len(self.particle_back_r_data)

        with open(file_path, 'r') as file:
            for _ in range(4):
                file.readline()
            line_content = file.readline().split()
            if not all(column in line_content for column in ['cosp', 'cosa', 'end-energy']):
                return
            cosp_idx = line_content.index('cosp')
            cosa_idx = line_content.index('cosa')
            end_energy_idx = line_content.index('end-energy')

        new_particle_file_data = fileToNpArray(file_path,
                                               skip_header=5 + old_data_len,
                                               skip_footer=2,
                                               usecols=(0, cosp_idx, cosa_idx, end_energy_idx))

        if new_particle_file_data.size:
            # Fix the data shape if just a single line was read
            if new_particle_file_data.ndim == 1:
                new_particle_file_data = new_particle_file_data[np.newaxis, ...]

            if is_projectile:
                if self.particle_back_p_data.size:
                    self.particle_back_p_data = np.append(self.particle_back_p_data, new_particle_file_data, axis=0)
                else:
                    self.particle_back_p_data = new_particle_file_data

            else:
                if self.particle_back_r_data.size:
                    self.particle_back_r_data = np.append(self.particle_back_r_data, new_particle_file_data, axis=0)
                else:
                    self.particle_back_r_data = new_particle_file_data

        particle_file_data = self.particle_back_p_data if is_projectile else self.particle_back_r_data
        if not particle_file_data.size:
            return

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

        file_path = f'{self.save_folder}/E0_31_target.dat'
        if not path.exists(file_path):
            return

        if not self.masses.size:
            self.getOutputFileData()

        with open(file_path, 'r') as file:
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

    def listParameters(self, save_folder: str, list_widget: ListWidget):
        """
        Builds ListWidget from files in save folder

        :param save_folder: folder for output files
        :param list_widget: empty ListWidget (extension of QListWidget) that should be written to
        """

        files = listdir(save_folder)
        info_file = 'E0_31_target.dat'
        if info_file not in files:
            info_file = 'E0_31_target001.dat'
            if info_file not in files:
                list_widget.addItem(ListWidgetItem('Corrupted input files', bold=True))
                return

        self.updateData(save_folder, info_file)

        # dynamic
        if self.is_dynamic:
            list_widget.addItem(ListWidgetItem('Results overview (only for finished static Simulations)', bold=True, grey=True))
            list_widget.addItemEmpty()

        # static
        elif 'output.dat' in files:
            list_widget.addItem(ListWidgetItem('Results overview:', bold=True))

            output_data = self.getOutputFileData()
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

            for i, element in enumerate(self.elements):
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

                for i, element in enumerate(self.elements):
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

            for i, element in enumerate(self.elements):
                if reflection_coefficients[i]:
                    list_widget.addItem(ListWidgetItem(f'{element}\t{roundToStr(reflection_coefficients[i])}', indent=2))

            if not np.sum(reflection_coefficients):
                list_widget.addItem(ListWidgetItem('No projectile reflection occurred.', indent=2))

            # transmission coefficients
            if transmission_happening:
                list_widget.addItemEmpty()
                list_widget.addItem(ListWidgetItem('Transmission coefficients:', indent=1))

                for i, element in enumerate(self.elements):
                    if transmission_coefficients[i]:
                        list_widget.addItem(ListWidgetItem(f'{element}\t{roundToStr(transmission_coefficients[i])}', indent=2))

                if not np.sum(transmission_coefficients):
                    list_widget.addItem(ListWidgetItem('No transmission effects occurred.', indent=2))

            # implantation depth
            list_widget.addItemEmpty()
            list_widget.addItem(ListWidgetItem('Mean implantation depth:', indent=1))

            for i, element in enumerate(self.elements):
                if implantation_depth[i]:
                    list_widget.addItem(ListWidgetItem(f'{element}\t{implantation_depth[i]:.3f} Å', indent=2))

            if not np.sum(implantation_depth):
                list_widget.addItem(ListWidgetItem('No projectile implantation occurred.', indent=2))

            # energy loss
            list_widget.addItemEmpty()
            list_widget.addItem(ListWidgetItem('Mean projectile energy loss:', indent=1))
            list_widget.addItem(ListWidgetItem('\tNuclear\tElectronic\tTotal', indent=2))

            for i, element in enumerate(self.elements):
                if energy_loss_total[i]:
                    list_widget.addItem(ListWidgetItem(f'{element}\t{energy_loss_nuclear[i]:.3f} eV\t{energy_loss_electron[i]:.3f} eV\t{energy_loss_total[i]:.3f} eV', indent=2))

            list_widget.addItemEmpty()

        # depth statistic
        depth_proj_exists = 'depth_proj.dat' in files
        depth_recoil_exists = 'depth_recoil.dat' in files
        depth_damage_exists = 'depth_damage.dat' in files

        if depth_proj_exists or depth_recoil_exists or depth_damage_exists:
            list_widget.addItem(ListWidgetItem('Plot depth statistic:', bold=True))

            if depth_proj_exists:
                list_widget.addItem(ListWidgetItem('Implantation depth',
                                                   indent=1,
                                                   function=self.plotFct,
                                                   function_args={'plot': self.plotImplantationDepth}))
                list_widget.addItem(ListWidgetItem('Projectile energy loss',
                                                   indent=1,
                                                   function=self.plotFct,
                                                   function_args={'plot': self.plotEnergyLossDepth}))

            if depth_recoil_exists or depth_damage_exists:
                list_widget.addItem(ListWidgetItem('Ion-induced damages',
                                                   indent=1,
                                                   function=self.plotFct,
                                                   function_args={'plot': self.plotVacanciesDepth}))

        else:
            list_widget.addItem(ListWidgetItem('Plot depth statistics (only for finished static Simulations)', bold=True, grey=True))

        list_widget.addItemEmpty()

        # fluence dependent quantities
        if self.is_dynamic:
            list_widget.addItem(ListWidgetItem('Plot over fluence:', bold=True))

            list_widget.addItem(ListWidgetItem('Sputtering yields',
                                               indent=1,
                                               function=self.plotFct,
                                               function_args={'plot': self.plotSputterYields}))
            list_widget.addItem(ListWidgetItem('Total sputtering yield (atoms/ion)',
                                               indent=1,
                                               function=self.plotFct,
                                               function_args={'plot': self.plotSputterYieldsTotal}))
            list_widget.addItem(ListWidgetItem('Net mass removal (amu/ion)',
                                               indent=1,
                                               function=self.plotFct,
                                               function_args={'plot': self.plotSputterYieldsTotalAmu}))
            list_widget.addItem(ListWidgetItem('Reflection coefficients',
                                               indent=1,
                                               function=self.plotFct,
                                               function_args={'plot': self.plotReflectionCoefficients}))
            list_widget.addItem(ListWidgetItem('Reemission coefficients',
                                               indent=1,
                                               function=self.plotFct,
                                               function_args={'plot': self.plotReemissionCoefficients}))
            list_widget.addItem(ListWidgetItem('Surface concentrations',
                                               indent=1,
                                               function=self.plotFct,
                                               function_args={'plot': self.plotSurfaceConcentrations}))
            list_widget.addItem(ListWidgetItem('Surface level',
                                               indent=1,
                                               function=self.plotFct,
                                               function_args={'plot': self.plotSurfaceLevel}))
            list_widget.addItem(ListWidgetItem('Concentrations over depth',
                                               indent=1,
                                               function=self.plotFct,
                                               function_args={'plot': self.updateDepthConcentration,
                                                              'plot_args': {'set_to_max': True}}))

        else:
            list_widget.addItem(ListWidgetItem('Plot over fluence (only for dynamic Simulations)', bold=True, grey=True))

        list_widget.addItemEmpty()

        # angular dependence
        nr_energies = 0
        nr_angles = 0
        series_data = self.getSerieFileData()

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
                                               function=self.plotFct,
                                               function_args={'plot': self.plotAngularSputterYields}))
            list_widget.addItem(ListWidgetItem('Angular dependence of sputtered mass (amu/ion)',
                                               indent=1,
                                               function=self.plotFct,
                                               function_args={'plot': self.plotAngularMassYields}))
            list_widget.addItem(ListWidgetItem('Angular dependence of reflection coefficients',
                                               indent=1,
                                               function=self.plotFct,
                                               function_args={'plot': self.plotAngularReflection}))
            list_widget.addItem(ListWidgetItem('Angular dependence of implantation depth',
                                               indent=1,
                                               function=self.plotFct,
                                               function_args={'plot': self.plotAngularMeanDepth}))
        else:
            list_widget.addItem(ListWidgetItem('Plot angular dependence (only for "angle sweep")', bold=True, grey=True))
        list_widget.addItemEmpty()

        if nr_energies > 1:
            list_widget.addItem(ListWidgetItem('Plot energy dependence:', bold=True))
            list_widget.addItem(ListWidgetItem('Energy dependence of sputtering yields (atoms/ion)',
                                               indent=1,
                                               function=self.plotFct,
                                               function_args={'plot': self.plotEnergySputterYields}))
            list_widget.addItem(ListWidgetItem('Energy dependence of sputtered mass (amu/ion)',
                                               indent=1,
                                               function=self.plotFct,
                                               function_args={'plot': self.plotEnergyMassYields}))
            list_widget.addItem(ListWidgetItem('Energy dependence of reflection coefficients',
                                               indent=1,
                                               function=self.plotFct,
                                               function_args={'plot': self.plotEnergyReflection}))
            list_widget.addItem(ListWidgetItem('Energy dependence of implantation depth',
                                               indent=1,
                                               function=self.plotFct,
                                               function_args={'plot': self.plotEnergyMeanDepth}))
        else:
            list_widget.addItem(ListWidgetItem('Plot energy dependence (only for "energy sweep")', bold=True, grey=True))
        list_widget.addItemEmpty()

        # reflected projectiles and sputtered recoils
        back_p_exists = 'partic_back_p.dat' in files
        back_r_exists = 'partic_back_r.dat' in files

        if back_p_exists or back_r_exists:
            list_widget.addItem(ListWidgetItem('Plot secondary particle distributions:', bold=True))

            for i, element in enumerate(self.elements):
                if back_p_exists:
                    list_widget.addItem(ListWidgetItem(f'Backscattered {element} ions',
                                                       indent=1,
                                                       function=self.plotFct,
                                                       function_args={'plot': self.plotPolar,
                                                                      'plot_args': {'element': i, 'projectile_or_recoil': 'p'}}))
                if back_r_exists:
                    list_widget.addItem(ListWidgetItem(f'Backsputtered {element} recoil atoms',
                                                       indent=1,
                                                       function=self.plotFct,
                                                       function_args={'plot': self.plotPolar,
                                                                      'plot_args': {'element': i, 'projectile_or_recoil': 'r'}}))
            list_widget.addItemEmpty()

            if back_p_exists:
                list_widget.addItem(ListWidgetItem('Polar angles of backscattered ions',
                                                   indent=1,
                                                   function=self.plotFct,
                                                   function_args={'plot': self.plotParticlesPolarP}))
            if back_r_exists:
                list_widget.addItem(ListWidgetItem('Polar angles of backsputtered recoils',
                                                   indent=1,
                                                   function=self.plotFct,
                                                   function_args={'plot': self.plotParticlesPolarR}))
            list_widget.addItemEmpty()

            if back_p_exists:
                list_widget.addItem(ListWidgetItem('Energy of backscattered ions',
                                                   indent=1,
                                                   function=self.plotFct,
                                                   function_args={'plot': self.plotParticlesEnergyP}))
            if back_r_exists:
                list_widget.addItem(ListWidgetItem('Energy of backsputtered recoils',
                                                   indent=1,
                                                   function=self.plotFct,
                                                   function_args={'plot': self.plotParticlesEnergyR}))
            list_widget.addItemEmpty()

        else:
            list_widget.addItem(ListWidgetItem('Plot secondary particle distributions (only with additional output options)', bold=True, grey=True))

    def plotFct(self, plot: Callable = None, plot_args: dict = None, hide: bool = True):
        """
        Call the plot function in a new thread with function parameters

        :param plot: plot function
        :param plot_args: plot function parameters as dictionary
        :param hide: hide toolbar
        """

        if hide:
            self.emit({
                'hide': True
            })
        super().plotFct(plot, plot_args)

    def plotImplantationDepth(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return projectile stops over depth"""

        depth_data = self.getDepthFileData('depth_proj.dat')

        if depth_data is None:
            return

        (ncp,
         file_elements,
         nr_of_depth_steps,
         max_nr_depth_steps,
         nr_of_projectiles,
         depth_data) = depth_data

        mpl_settings = MplCanvasSettings()

        depth_x_values = depth_data[:, :, 0]
        depth_delta = depth_x_values[:, 1] - depth_x_values[:, 0]
        stops = depth_data[:, :, 1]

        data = []
        plot_labels = []
        flag_plots = False

        for k in range(ncp):
            if np.max(stops[k]) > 0 and nr_of_projectiles[k]:
                mpl_settings.plot(depth_x_values[k, :nr_of_depth_steps[k]],
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
            return

        mpl_settings.set_xlim(xmin=0.0)
        mpl_settings.set_ylim(ymin=0.0)
        mpl_settings.legend()
        mpl_settings.set_ylabel('Stopping Probability [1/Å]')
        mpl_settings.set_xlabel('Depth [Å]')

        return (data, plot_labels), mpl_settings

    def plotEnergyLossDepth(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return projectile energy loss over depth"""

        depth_data = self.getDepthFileData('depth_proj.dat')

        if depth_data is None:
            return

        (ncp,
         file_elements,
         nr_of_depth_steps,
         max_nr_depth_steps,
         nr_of_projectiles,
         depth_data) = depth_data

        mpl_settings = MplCanvasSettings()

        depth_x_values = depth_data[:, :, 0]
        depth_delta = depth_x_values[:, 1] - depth_x_values[:, 0]
        nuclear_loss = depth_data[:, :, 3] * 1e6  # convert from MeV to eV
        electron_loss = depth_data[:, :, 4] * 1e6  # convert from MeV to eV
        total_loss = nuclear_loss + electron_loss

        data = []
        plot_labels = []
        flag_plots = False

        for k in range(ncp):
            if (np.max(nuclear_loss[k]) + np.max(electron_loss[k])) > 0 and nr_of_projectiles[k]:
                color = self.colors[self.getElementIndex(file_elements[k])]
                mpl_settings.plot(depth_x_values[k, :nr_of_depth_steps[k]],
                                  nuclear_loss[k, :nr_of_depth_steps[k]] / nr_of_projectiles[k] / depth_delta[k],
                                  label=f'{file_elements[k]} (nuclear)',
                                  linestyle='--',
                                  linewidth=self.line_width,
                                  color=color)
                mpl_settings.plot(depth_x_values[k, :nr_of_depth_steps[k]],
                                  electron_loss[k, :nr_of_depth_steps[k]] / nr_of_projectiles[k] / depth_delta[k],
                                  label=f'{file_elements[k]} (electronic)',
                                  linestyle=':',
                                  linewidth=self.line_width,
                                  color=color)
                mpl_settings.plot(depth_x_values[k, :nr_of_depth_steps[k]],
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
            return

        mpl_settings.set_ylim(ymin=0.0)
        mpl_settings.set_xlim(xmin=0.0)
        mpl_settings.legend()
        mpl_settings.set_ylabel('Energy Loss (normalized) [eV/Å]')
        mpl_settings.set_xlabel('Depth [Å]')

        return (data, plot_labels), mpl_settings

    def plotVacanciesDepth(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return vacancies over depth"""

        use_depth_damage = path.exists(f'{self.save_folder}/depth_damage.dat')

        if use_depth_damage:
            depth_data = self.getDamageDepthFileData('depth_damage.dat')
        else:
            depth_data = self.getDepthFileData('depth_recoil.dat')

        if depth_data is None:
            return

        (ncp,
         file_elements,
         nr_of_depth_steps,
         max_nr_depth_steps,
         nr_of_projectiles,
         depth_data) = depth_data

        mpl_settings = MplCanvasSettings()

        depth_x_values = depth_data[:, :, 0]
        depth_delta = depth_x_values[:, 1] - depth_x_values[:, 0]
        if use_depth_damage:
            vacancies = depth_data[:, :, -1]
        else:
            vacancies = depth_data[:, :, 7]
            nr_of_projectiles = nr_of_projectiles[0]

        data = []
        plot_labels = []
        nr_of_plots = 0

        for k in range(ncp):
            if np.max(vacancies[k]) > 0:
                mpl_settings.plot(depth_x_values[k, :nr_of_depth_steps[k]],
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
            return

        if nr_of_plots > 1 and all(x == depth_delta[0] for x in depth_delta):
            mpl_settings.plot(depth_x_values[np.argmax(nr_of_depth_steps), :max_nr_depth_steps],
                              np.sum(vacancies[:, :max_nr_depth_steps], axis=0) / nr_of_projectiles / depth_delta[0],
                              label='Total',
                              linewidth=self.line_width,
                              color=self.first_color)

            data.append(depth_x_values[np.argmax(nr_of_depth_steps), :])
            data.append(np.sum(vacancies[:, :max_nr_depth_steps], axis=0) / nr_of_projectiles / depth_delta[0])
            plot_labels.append('Depth (Total) [Angs]')
            plot_labels.append('Vacancies (Total) [1/Angs/ion]')

        mpl_settings.set_ylim(ymin=0.0)
        mpl_settings.set_xlim(xmin=0.0)
        mpl_settings.legend()
        mpl_settings.set_ylabel('Vacancies [1/Å/ion]')
        mpl_settings.set_xlabel('Depth [Å]')
        mpl_settings.set_title(f'Total Vacancies: {np.round(np.sum(vacancies) / nr_of_projectiles, 2)} / Ion')

        return (data, plot_labels), mpl_settings

    def plotAngularSputterYields(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return angular dependent sputter yields"""

        serie_data = self.getSerieFileData()

        if serie_data is None:
            return

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

            popt, pcov = curve_fit(self.ecksteinAngleFit,
                                   angles[:last_index],
                                   total_yield[:last_index],
                                   p0=[total_yield[0], 90., 1., 1., 1.6],
                                   sigma=angle_distance_weights[:last_index],
                                   bounds=(0., [np.max(total_yield), 90., 10., 1., 10.]))

            angles_fit = np.arange(0., 90., 0.1)
            mpl_settings.plot(angles_fit,
                              self.ecksteinAngleFit(angles_fit, *popt),
                              label='Eckstein Fit',
                              linestyle='--',
                              linewidth=1,
                              color='black')

            mpl_settings.set_title(f'Fit: Y$_0$ = {np.round(popt[0], 3)} atoms/ion, $\\alpha_0$ = {np.round(popt[1], 3)}°, b = {np.round(popt[2], 3)}, c = {np.round(popt[3], 3)}, f = {np.round(popt[4], 3)}')
            fit_params_string = f'Fit: Y0 = {np.round(popt[0], 3)} atoms/ion, alpha0 = {np.round(popt[1], 3)}°, b = {np.round(popt[2], 3)}, c = {np.round(popt[3], 3)}, f = {np.round(popt[4], 3)}'

        data = []
        plot_labels = []

        plot_counter = 0
        for i, element in enumerate(elements):
            if np.max(sputt_coefficients[:, i]) > 0.:
                mpl_settings.plot(angles[:last_index],
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
            return

        elif plot_counter > 1:
            mpl_settings.plot(angles[:last_index],
                              total_yield[:last_index],
                              label='Total',
                              marker='o',
                              linestyle='',
                              color=self.first_color)

            data.append(total_yield[:last_index])
            plot_labels.append('Total')
            plot_labels.append(fit_params_string)

        mpl_settings.set_xlabel('Angle of Incidence $\\alpha$ [°]')
        mpl_settings.set_ylabel('Sputtering Yield Y [atoms/ion]')
        mpl_settings.set_ylim(ymin=0.)
        mpl_settings.set_xlim(xmin=-5., xmax=90.)
        mpl_settings.legend()

        return (data, plot_labels), mpl_settings

    def plotAngularMassYields(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return angular dependant mass yields"""

        serie_data = self.getSerieFileData()

        if serie_data is None:
            return

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

            popt, pcov = curve_fit(self.ecksteinAngleFit,
                                   angles[:last_index],
                                   amu_yield[:last_index],
                                   sigma=angle_distance_weights[:last_index],
                                   p0=[amu_yield[0], 90., 1., 1., 1.6],
                                   bounds=(0., [np.max(amu_yield), 90., 10., 1., 10.]))

            angles_fit = np.arange(0., 90., 0.1)
            mpl_settings.plot(angles_fit,
                              self.ecksteinAngleFit(angles_fit, *popt),
                              label='Eckstein Fit',
                              linestyle='--',
                              linewidth=1,
                              color='black')
            mpl_settings.set_title(f'Fit: Y$_0$ = {np.round(popt[0], 3)} amu/ion, $\\alpha_0$ = {np.round(popt[1], 3)}°, b = {np.round(popt[2], 3)}, c = {np.round(popt[3], 3)}, f = {np.round(popt[4], 3)}')
            fit_params_string = f'Fit: Y0 = {np.round(popt[0], 3)} amu/ion, alpha0 = {np.round(popt[1], 3)}°, b = {np.round(popt[2], 3)}, c = {np.round(popt[3], 3)}, f = {np.round(popt[4], 3)}'

        mpl_settings.plot(angles[:last_index],
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

        mpl_settings.set_xlabel('Angle of Incidence $\\alpha$ [°]')
        mpl_settings.set_ylabel('Sputtering Yield y [amu/ion]')
        mpl_settings.set_ylim(ymin=0.)
        mpl_settings.set_xlim(xmin=-5., xmax=90.)
        mpl_settings.legend()

        return (data, plot_labels), mpl_settings

    def plotAngularReflection(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return angular dependent reflection coefficients"""

        serie_data = self.getSerieFileData()

        if serie_data is None:
            return

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
                mpl_settings.plot(angles[:last_index],
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
            return

        elif plot_counter > 1:
            mpl_settings.plot(angles[:last_index],
                              total_yield[:last_index],
                              label='Total',
                              marker='o',
                              linestyle='',
                              color=self.first_color)

        mpl_settings.set_xlabel('Angle of Incidence $\\alpha$ [°]')
        mpl_settings.set_ylabel('Reflection Coefficient R')
        mpl_settings.set_ylim(ymin=0.)
        mpl_settings.set_xlim(xmin=-5., xmax=90.)
        mpl_settings.legend()

        return (data, plot_labels), mpl_settings

    def plotAngularMeanDepth(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return angular dependent mean depth"""

        serie_data = self.getSerieFileData()

        if serie_data is None:
            return

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

        mpl_settings.plot(angles[:last_index],
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

        mpl_settings.set_xlabel('Angle of Incidence $\\alpha$ [°]')
        mpl_settings.set_ylabel('Implantation Depth [Å]')
        mpl_settings.set_ylim(ymin=0.)
        mpl_settings.set_xlim(xmin=-5., xmax=90.)

        return (data, plot_labels), mpl_settings

    def plotEnergySputterYields(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return energy dependent sputter yields"""

        serie_data = self.getSerieFileData()

        if serie_data is None:
            return

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
                mpl_settings.plot(energies[:last_index],
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
            return

        elif plot_counter > 1:
            mpl_settings.plot(energies[:last_index],
                              total_yield[:last_index],
                              label='Total',
                              marker='o',
                              linestyle='',
                              color=self.first_color)
            data.append(total_yield[:last_index])
            plot_labels.append('Total')

        mpl_settings.set_xlabel('Kinetic Energy E [eV]')
        mpl_settings.set_ylabel('Sputtering Yield Y [atoms/ion]')
        mpl_settings.set_yscale('log')
        mpl_settings.set_xscale('log')
        mpl_settings.legend()

        return (data, plot_labels), mpl_settings

    def plotEnergyMassYields(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return energy dependent mass yields"""

        serie_data = self.getSerieFileData()

        if serie_data is None:
            return

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

        mpl_settings.plot(energies[:last_index],
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

        mpl_settings.set_xlabel('Kinetic Energy E [eV]')
        mpl_settings.set_ylabel('Sputtering Yield y [amu/ion]')
        mpl_settings.set_yscale('log')
        mpl_settings.set_xscale('log')
        mpl_settings.legend()

        return (data, plot_labels), mpl_settings

    def plotEnergyReflection(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return energy dependent reflection coefficients"""

        serie_data = self.getSerieFileData()

        if serie_data is None:
            return

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
                mpl_settings.plot(energies[:last_index],
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
            return

        elif plot_counter > 1:
            mpl_settings.plot(energies[:last_index],
                              total_yield[:last_index],
                              label='Total',
                              marker='o',
                              linestyle='',
                              color=self.first_color)

        mpl_settings.set_xlabel('Kinetic Energy E [eV]')
        mpl_settings.set_ylabel('Reflection Coefficient R')
        mpl_settings.set_yscale('log')
        mpl_settings.set_xscale('log')
        mpl_settings.legend()

        return (data, plot_labels), mpl_settings

    def plotEnergyMeanDepth(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return energy dependent mean depth"""

        serie_data = self.getSerieFileData()

        if serie_data is None:
            return

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

        mpl_settings.plot(energies[:last_index],
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

        mpl_settings.set_xlabel('Kinetic Energy E [eV]')
        mpl_settings.set_ylabel('Implantation Depth [Å]')
        mpl_settings.set_yscale('log')
        mpl_settings.set_xscale('log')

        return (data, plot_labels), mpl_settings

    def plotParticlesPolar(self, projectile_or_recoil: str = 'p') -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return data of backscattered particles"""

        is_projectile = projectile_or_recoil.startswith('p')
        particle_data = self.getParticleData(projectile_or_recoil)

        mpl_settings = MplCanvasSettings()
        mpl_settings.set_projection('polar')

        if particle_data is None or not particle_data:
            mpl_settings.set_title('No data found')
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

            hist, bin_edges = np.histogram(polar_angles, density=True, bins=72, range=(-np.pi / 2, np.pi / 2))
            bin_edges_new = 0.5 * (bin_edges[:-1] + bin_edges[1:])
            polar_plot_norm = np.absolute(np.cos(bin_edges[:-1]) - np.cos(bin_edges[1:])) / np.sum(np.absolute(np.cos(bin_edges[:-1]) - np.cos(bin_edges[1:])))
            # 0.5 ... normalization because both + and - polar angle are shown, np.pi/180. for conversion from 1/rad to 1/deg
            plot_data = 0.5 * np.pi / 180. * np.divide(hist, np.absolute(polar_plot_norm))
            mpl_settings.plot(bin_edges_new,
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
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        if is_projectile:
            mpl_settings.set_title('Backscattered projectiles over polar angle')
        else:
            mpl_settings.set_title('Sputtered recoils over polar angle')

        mpl_settings.set_xlabel('Probability [1/°]')
        mpl_settings.grid(True)
        mpl_settings.set_theta(
            thetagrids=tuple([i * 10 for i in range(-9, 10)]),
            thetamin=-90,
            thetamax=90,
            theta_offset=np.pi / 2,
            theta_direction=-1)
        mpl_settings.tick_params(
            axis='y',
            labelrotation=45,
            pad=4,
            labelsize=8)
        mpl_settings.legend()

        return (data, plot_labels), mpl_settings

    def plotParticlesPolarP(self) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return data of backscattered projectiles"""

        return self.plotParticlesPolar('p')

    def plotParticlesPolarR(self) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return data of backscattered recoils"""

        return self.plotParticlesPolar('r')

    def plotParticlesEnergy(self, projectile_or_recoil: str = 'p') -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return energy of backscattered particles"""

        is_projectile = projectile_or_recoil.startswith('p')
        particle_data = self.getParticleData(projectile_or_recoil)

        mpl_settings = MplCanvasSettings()

        if particle_data is None or not particle_data:
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        data = []
        plot_labels = []

        plot_counter = 0
        for i, element in enumerate(self.elements):
            plot_data = particle_data[i]
            energies = plot_data[:, 2]

            if not energies.size:
                continue

            if is_projectile:
                hist, bin_edges = np.histogram(energies, density=True, bins=100)

            # use very fine resolution in binning for sputtered atoms because lower energies are of more interest
            else:
                hist, bin_edges = np.histogram(energies, density=True, bins=int(np.max(energies) / 0.2))

            bin_edges_new = 0.5 * (bin_edges[:-1] + bin_edges[1:])
            mpl_settings.plot(bin_edges_new,
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

        mpl_settings.set_xlabel('Energy [eV]')
        if is_projectile:
            mpl_settings.set_ylabel('Reflected ions [1/eV]')
        else:
            mpl_settings.set_ylabel('Sputtered atoms [1/eV]')
        mpl_settings.set_ylim(ymin=0.)
        mpl_settings.set_xlim(xmin=0.)
        mpl_settings.legend()

        return (data, plot_labels), mpl_settings

    def plotParticlesEnergyP(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return energy of backscattered projectiles"""

        return self.plotParticlesEnergy('p')

    def plotParticlesEnergyR(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return energy of backscattered recoils"""

        return self.plotParticlesEnergy('r')

    def plotPolar(self, element: int, projectile_or_recoil: str = 'p', n_bins: int = 30) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return backscattered particles of element"""

        if element not in range(len(self.elements)):
            return
        is_projectile = projectile_or_recoil.startswith('p')
        particle_data = self.getParticleData(projectile_or_recoil)

        mpl_settings = MplCanvasSettings()
        mpl_settings.set_projection('polar')

        if particle_data is None or not particle_data:
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        data = []
        plot_labels = []

        plot_data = particle_data[element]
        if len(plot_data) == 0:
            mpl_settings.set_title('No data found')
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

        mpl_settings.set_theta(
            thetamin=0,
            thetamax=360,
            theta_direction=-1,
            theta_zero_location='E'
        )
        mpl_settings.set_yticklabels([])
        mpl_settings.pcolormesh(a, r, hist.T, cmap='viridis', zorder=-1, vmin=0.)
        mpl_settings.pcolormesh_label('Distribution of Particles [1/sr]', rotation=90)

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

        if is_projectile:
            title = f'Angular distribution of backscattered {self.elements[element]} projectiles'
        else:
            title = f'Angular distribution of backsputtered {self.elements[element]} recoil atoms'
        mpl_settings.set_title(title)

        return (data, plot_labels), mpl_settings

    def plotSputterYields(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return sputter yields"""

        e031_data = self.getE031TargetData()

        if e031_data is None:
            return

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
            mpl_settings.plot(fluence_array[1:],
                              sputtered_yield[1:, i],
                              label=element,
                              color=self.colors[i])

            data.append(sputtered_yield[1:, i])
            plot_labels.append(element)

        mpl_settings.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.set_ylabel('Sputtering Yield Y [atoms/ion]')
        mpl_settings.set_ylim(ymin=0.)
        mpl_settings.legend()

        return (data, plot_labels), mpl_settings

    def plotSputterYieldsTotal(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return total sputter yields"""

        e031_data = self.getE031TargetData()

        if e031_data is None:
            return

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

        mpl_settings.plot(fluence_array[1:],
                          np.sum(sputtered_yield[1:, :], axis=1),
                          color=self.first_color)

        mpl_settings.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.set_ylabel('Sputtering Yield Y [atoms/ion]')
        mpl_settings.set_ylim(ymin=0.)

        return ([fluence_array[1:], np.sum(sputtered_yield[1:, :], axis=1)], ['Fluence[10^20 ions/m^2]', 'Y [atoms/ion]']), mpl_settings

    def plotSputterYieldsTotalAmu(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return total sputter yields amu"""

        e031_data = self.getE031TargetData()

        if e031_data is None:
            return

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

        mpl_settings.plot(fluence_array[1:],
                          amu_yield[1:],
                          color=self.first_color)

        mpl_settings.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.set_ylabel('Net Mass Removal y [amu/ion]')

        return ([fluence_array[1:], amu_yield[1:]], ['Fluence[10^20 ions/m^2]', 'y [amu/ion]']), mpl_settings

    def plotReflectionCoefficients(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return reflection coefficients"""

        e031_data = self.getE031TargetData()

        if e031_data is None:
            return

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
            mpl_settings.plot(fluence_array[1:],
                              reflected_yield[1:, i],
                              label=element,
                              color=self.colors[i])

            data.append(reflected_yield[1:, i])
            plot_labels.append(element)

        mpl_settings.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.set_ylabel('Reflection Coefficient R [atoms/ion]')
        mpl_settings.set_ylim(ymin=0., ymax=1.)
        mpl_settings.legend()

        return (data, plot_labels), mpl_settings

    def plotReemissionCoefficients(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return reemission coefficients"""

        e031_data = self.getE031TargetData()

        if e031_data is None:
            return

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
            mpl_settings.plot(fluence_array[1:],
                              reemitted_yield[1:, i],
                              label=element,
                              color=self.colors[i])

            data.append(reemitted_yield[1:, i])
            plot_labels.append(element)

        mpl_settings.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.set_ylabel('Reemission Coefficient [atoms/ion]')
        mpl_settings.set_ylim(ymin=0., ymax=1.)
        mpl_settings.legend()

        return (data, plot_labels), mpl_settings

    def plotSurfaceConcentrations(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return surface concentrations"""

        e031_data = self.getE031TargetData()

        if e031_data is None:
            return

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
            mpl_settings.plot(fluence_array[1:],
                              surface_conc[1:, i],
                              label=element,
                              color=self.colors[i])

            data.append(surface_conc[1:, i])
            plot_labels.append(element)

        mpl_settings.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.set_ylabel('Surface Concentration')
        mpl_settings.set_ylim(ymin=0., ymax=1.)
        mpl_settings.legend()

        return (data, plot_labels), mpl_settings

    def plotSurfaceLevel(self) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return surface levels"""

        e031_data = self.getE031TargetData()

        if e031_data is None:
            return

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

        mpl_settings.plot(fluence_array[1:],
                          surface[1:],
                          color=self.first_color)

        mpl_settings.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.set_ylabel('Surface Erosion [Å]')

        return ([fluence_array[1:], surface[1:]], ['Fluence[10^20 ions/m^2]', 'Surface Erosion [Angs]']), mpl_settings

    def updateDepthConcentration(self, set_to_max: bool = False) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Updates the plot and data of the depth concentration"""

        e031_data = self.getE031TargetData()

        if e031_data is None:
            return

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
            return

        self.fluence_array = fluence_array
        self.depth_array = depth_array
        self.conc_array = conc_array

        history_step = 0
        if set_to_max:
            history_step = max_hist
        result = self.plotDepthConcentration(history_step=history_step)

        # emit signal for HlPlot Layout
        self.emit({
            'hide': False,
            'max_history': max_hist,
            'history': max_hist
        })

        return result

    def plotDepthConcentration(self, history_step: int = 0) -> Optional[Tuple[Tuple[list, list], MplCanvasSettings]]:
        """Plot and return the depth concentration"""

        if self.depth_array is None or self.conc_array is None or self.fluence_array is None:
            return

        mpl_settings = MplCanvasSettings()

        data = [self.depth_array]
        plot_labels = ['Depth [Angs]']

        for i, element in enumerate(self.elements):
            mpl_settings.plot(self.depth_array,
                              self.conc_array[history_step, i, :],
                              label=element,
                              linewidth=2,
                              color=self.colors[i])

            data.append(self.conc_array[history_step, i, :])
            plot_labels.append(element)

        mpl_settings.set_ylim(ymin=0.0, ymax=1.0)
        mpl_settings.legend()
        mpl_settings.set_xlabel('Depth [Å]')
        mpl_settings.set_ylabel('Concentrations')

        mpl_settings.set_title(f'Fluence: {self.fluence_array[history_step]:.2f}$\\times 10^{{20}}$/m$^2$')

        return (data, plot_labels), mpl_settings
