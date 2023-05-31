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


from typing import List, Union, Tuple, Dict, Optional, Callable
from os import path, listdir
from re import findall

import numpy as np


from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QCheckBox, QLabel, QGridLayout, QSlider

from Utility.Layouts import (
    MplCanvas, MplCanvasSettings, InputHBoxLayout, DoubleSpinBox, SpinBox,
    SpinBoxRange, LineEdit, ComboBox, ListWidget, ListWidgetItem, setWidgetBackground
)
from Utility.Functions import (
    dateStr, alphanumeric, getFileNameFromFileList, getFilesNameFromFileList,
    fileToNpArray, roundToStr, normalizeList
)
from Utility.Indexing import DefaultAssumed, RunningIndex, ElementList

from TableWidgets.CompTable import CompRow
from TableWidgets.CustomTable import CustomRowField

from Containers.Arguments import (
    ArgumentValues, SimulationArguments, GeneralBeamArguments, GeneralTargetArguments,
    RowArguments, StructureArguments, GeneralArguments
)
from Containers.Element import Element, Elements
from Containers.Compound import Compound

from Simulations.Simulations import (
    SimulationsInput, SimulationsOutput, HlGeneralTargetSettings,
    VlGeneralSimulationSettings, HlGeneralPlot
)


class DefaultValues:
    """
    Default values for this simulation
    """

    # general settings
    iq0 = 0
    idrel = 1
    nh = 1e6
    prcs = 1e-4
    flct = 1.0
    nrthr = 1
    iwc = 1
    inel = 3
    iproj = False
    dmg0 = 0.0
    ires = 3
    idfout = 100
    iddout = 100
    idqout = 100

    # beam/target row
    e0 = 500.0
    alpha = 0.0
    qubeam = 0
    qumax = 1.0

    # general target settings
    xmax = 2000.0
    nqx = 200
    dthf = 0
    globaldensity = False

    # output settings
    outp = False
    ardn = False
    spyl = False
    reem = False
    srfc = False
    pdfc = False
    srfe = False
    fthi = False
    edep = False
    incd = False
    rang = False
    scat = False
    sput = False
    vcin = False
    rrlv = False


class DictLookup:
    """
    Class to store lookup dictionaries that link simulation values to meaningful values
    """

    ie0 = {
        ArgumentValues.KineticEnergy.FILE: -1,
        ArgumentValues.KineticEnergy.FIXED: 0,
        ArgumentValues.KineticEnergy.LINEAR_RAMP: 1
    }

    iadis = {
        ArgumentValues.Angle.FIXED: 0,
        ArgumentValues.Angle.GAUSSIAN_2D: 1,
        ArgumentValues.Angle.COS_2D: 2,
        ArgumentValues.Angle.PARABOLIC_1D: 3
    }

    idrel = {
        ArgumentValues.Mode.STATIC: 0,
        ArgumentValues.Mode.DYNAMIC: 1,
        ArgumentValues.Mode.STATIC_NO_RECOIL: 0
    }

    inel = {
        ArgumentValues.InelasticLossModel.LINDHARD_SCHARFF: 1,
        ArgumentValues.InelasticLossModel.OEN_ROBINSON: 2,
        ArgumentValues.InelasticLossModel.LINDHARD_SCHARFF_AND_OEN_ROBINSON: 3
    }

    ires = {
        -1: 0,
        2: 1,
        3: 2
    }


class HlTargetSettings(HlGeneralTargetSettings):
    """
    QHBoxLayout for general target settings

    :param version: version of simulation
    """

    def __init__(self, version: str):
        super().__init__(version)

        # thickness
        self.thickness = DoubleSpinBox(
            default=DefaultValues.xmax,
            input_range=SpinBoxRange.ZERO_INF
        )
        self.layout_thickness = InputHBoxLayout(
            'Thickness [Å]:',
            self.thickness,
            tooltip='<i>geom xmax</i><br>Thickness of the whole target'
        )
        self.thickness.valueChanged.connect(lambda _: self.updateSegmentThickness())
        self.thickness.valueChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_thickness)
        self.addSpacing(10)

        # segments
        self.segments = SpinBox(
            default=DefaultValues.nqx,
            input_range=(1, 5e4)
        )
        self.layout_segments = InputHBoxLayout(
            'Target segments:',
            self.segments,
            tooltip='<i>geom nqx</i><br>The amount of discrete segments the target is divided into'
        )
        self.segments.valueChanged.connect(lambda _: self.updateSegmentThickness())
        self.segments.valueChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_segments)
        self.addSpacing(10)

        # segment thickness (automatically calculated)
        self.segment_thickness = DoubleSpinBox(
            default=DefaultValues.xmax / DefaultValues.nqx,
            input_range=SpinBoxRange.ZERO_INF,
            decimals=4
        )
        self.layout_segment_thickness = InputHBoxLayout(
            'Segment thickness [Å]:',
            self.segment_thickness,
            tooltip='The resulting thickness of each segment. A value ≥2Å is recommended',
            disabled=True
        )
        self.addLayout(self.layout_segment_thickness)
        self.addSpacing(10)

        # thin film thickness
        self.thin_film = DoubleSpinBox(
            default=DefaultValues.dthf,
            input_range=SpinBoxRange.INF_INF,
            decimals=4
        )
        self.layout_thin_film = InputHBoxLayout(
            'Thin film thickness [Å]:',
            self.thin_film,
            tooltip='<i>geom dthf</i><br>0: semi-infinite body<br>>0: free-supported thin film with thickness from depth node closest to dthf<br><0: free-supported thin film with thickness from empty bottom layers in layer input'
        )
        self.thin_film.valueChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_thin_film)
        self.addSpacing(10)

        # global density
        self.global_density = DoubleSpinBox(
            input_range=SpinBoxRange.INF_INF,
            decimals=5
        )
        self.layout_global_density = InputHBoxLayout(
            'Global density [g/cm³]:',
            self.global_density,
            tooltip='<i>#globaldensity</i><br>Toggle a global density, which the individual target element densities will be calculated from.\nCan only be used if there is just one layer in the target composition',
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
        self.layout_thin_film.reset()
        self.layout_global_density.reset()

        self.updateSegmentThickness()
        self.changedGlobDens()

    def getArguments(self) -> GeneralTargetArguments:
        """Returns <GeneralTargetArguments> container of parameters for target settings"""

        global_density = False
        if self.layout_global_density.checkbox.isChecked():
            global_density = self.global_density.value()

        return GeneralTargetArguments(
            thickness=self.thickness.value(),  # geom xmax
            segments=self.segments.value(),  # geom nqx
            film_thickness=self.thin_film.value(),  # geom dthf
            global_density=global_density  # #globaldensity
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
        xmax = target_args.thickness
        if 'thickness' in assumed:
            xmax = DefaultValues.xmax
            self.layout_thickness.mark()
            not_loadable.append('Thickness of target')
        self.thickness.setValue(xmax)

        # segments
        nqx = target_args.segments
        if 'segments' in assumed:
            nqx = DefaultValues.nqx
            self.layout_segments.mark()
            not_loadable.append('Number of segments of target')
        self.segments.setValue(nqx)

        # thin film thickness
        dthf = target_args.get('film_thickness')
        if isinstance(dthf, float):
            self.thin_film.setValue(dthf)
        else:
            self.thin_film.setValue(DefaultValues.dthf)
            self.layout_thin_film.mark()
            not_loadable.append('Thin film thickness')

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

        # title
        self.simulation_title = LineEdit(
            default=f'TRIDYN{dateStr("%d%m")}',
            placeholder='Choose a title...',
            max_length=10
        )
        self.layout_simulation_title = InputHBoxLayout(
            'Simulation Title (exactly 10 characters):',
            self.simulation_title,
            tooltip='10 character run ID. Will be automatically filled with underlines to a length of 10 if less characters are provided'
        )
        self.simulation_title.editingFinished.connect(self.checkTitle)
        self.simulation_title.textChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_simulation_title)

        # comment
        self.comment = LineEdit(
            placeholder='Further comment'
        )
        self.layout_comment = InputHBoxLayout(
            'Comment:',
            self.comment,
            split=20,
            tooltip='Additional arbitrary comment'
        )
        self.comment.textChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_comment)

        # simulation method
        self.calculation_method = ComboBox(
            default=DefaultValues.idrel,
            entries=[
                'static',
                'dynamic'
            ],
            entries_save=[
                ArgumentValues.Mode.STATIC,
                ArgumentValues.Mode.DYNAMIC
            ],
            numbering=0,
            label_default=True,
            tooltips=[
                'Suppression of dynamic relaxation (TRIM); full static calculation'
                'Full dynamic calculation'
            ]
        )
        self.layout_calculation_method = InputHBoxLayout(
            'Calculation method:',
            self.calculation_method,
            tooltip='<i>cdat idrel</i>'
        )
        self.calculation_method.currentIndexChanged.connect(lambda _: self.edited())
        self.calculation_method.currentIndexChanged.connect(lambda _: self.checkVacancyLevel())
        self.calculation_method.currentIndexChanged.connect(lambda _: self.checkOutputOptions())
        self.addLayout(self.layout_calculation_method)

        # recoil suppression
        self.layout_recoils = InputHBoxLayout(
            'Treatment of incident projectiles only',
            None,
            checkbox=DefaultValues.iproj,
            tooltip='<i>coll iproj</i><br>If checked, only the treatment of incident projectiles (no recoil) is calculated. Otherwise all atoms are treated.'
        )
        self.layout_recoils.checkbox.toggled.connect(lambda _: self.edited())
        self.addLayout(self.layout_recoils)

        # inelastic loss model
        self.inelastic_loss_model = ComboBox(
            default=DefaultValues.inel,
            entries=[
                'nonlocal',
                'local',
                'eq.part. local/nonlocal'
            ],
            numbering=1,
            label_default=True,
            entries_save=[
                ArgumentValues.InelasticLossModel.LINDHARD_SCHARFF,
                ArgumentValues.InelasticLossModel.OEN_ROBINSON,
                ArgumentValues.InelasticLossModel.LINDHARD_SCHARFF_AND_OEN_ROBINSON
            ],
            tooltips=[
                'Lindhard-Scharff',
                'Oen-Robinson',
                'Equipartition of Lindhard-Scharff and Oen-Robinson'
            ]
        )
        self.layout_inelastic_loss_model = InputHBoxLayout(
            'Electronic stopping mode:',
            self.inelastic_loss_model,
            tooltip='<i>elst inel</i>'
        )
        self.inelastic_loss_model.currentIndexChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_inelastic_loss_model)

        # collisions
        self.collisions = SpinBox(
            default=DefaultValues.iwc,
            input_range=SpinBoxRange.ONE_INF
        )
        self.layout_collisions = InputHBoxLayout(
            'Weak collisions:',
            self.collisions,
            tooltip='<i>coll iwc</i><br>Max. order of weak collision shells'
        )
        self.collisions.valueChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_collisions)

        # number of pseudo-particles
        self.projectiles = SpinBox(
            default=DefaultValues.nh,
            input_range=SpinBoxRange.ZERO_INF
        )
        self.layout_projectiles = InputHBoxLayout(
            'Number of pseudo-particles:',
            self.projectiles,
            checkbox=False,
            disabled=True,
            tooltip='<i>pspr nh</i><br>How many pseudo-particles will be simulated in the run. Either <i>pspr nh</i> or <i>prec prcs</i> can be defined'
        )
        self.projectiles.valueChanged.connect(lambda _: self.edited())
        self.layout_projectiles.checkbox.toggled.connect(lambda _: self.edited())
        self.layout_projectiles.checkbox.toggled.connect(lambda _: self.updatePrecisionOrProjectiles(precision=False))
        self.addLayout(self.layout_projectiles)

        # precision
        self.precision = DoubleSpinBox(
            default=DefaultValues.prcs,
            input_range=(1e-10, 100),
            decimals=8,
            step_size=1e-4
        )
        self.layout_precision = InputHBoxLayout(
            'Precision factor:',
            self.precision,
            checkbox=True,
            tooltip='<i>prec prcs</i><br>Represents the relative change of the average areal density in a depth interval per added or removed pseudoatom. Either <i>pspr nh</i> or <i>prec prcs</i> can be defined'
        )
        self.precision.valueChanged.connect(lambda _: self.edited())
        self.layout_precision.checkbox.toggled.connect(lambda _: self.edited())
        self.layout_precision.checkbox.toggled.connect(lambda _: self.updatePrecisionOrProjectiles(precision=True))
        self.addLayout(self.layout_precision)

        # fluence
        self.fluence = DoubleSpinBox(
            default=DefaultValues.flct,
            input_range=SpinBoxRange.ZERO_INF,
        )
        self.layout_fluence = InputHBoxLayout(
            'Fluence [atoms/Å<sup>2</sup>]:',
            self.fluence,
            tooltip='<i>cdat flct</i><br>Fluence of incident atoms'
        )
        self.fluence.valueChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_fluence)

        # threads
        self.threads = SpinBox(
            default=DefaultValues.nrthr,
            input_range=SpinBoxRange.ZERO_INF
        )
        self.layout_threads = InputHBoxLayout(
            'Number of threads:',
            self.threads,
            tooltip='<i>thrd nrthr</i><br>Number of used threads. 0 will use the max. number of threads available'
        )

        self.threads.valueChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_threads)

        # vacancy level
        self.vacancy_level = DoubleSpinBox(
            default=DefaultValues.dmg0,
            input_range=SpinBoxRange.ZERO_INF
        )
        self.layout_vacancy_level = InputHBoxLayout(
            'Max. vacancy level (dpa):',
            self.vacancy_level,
            checkbox=False,
            tooltip='<i>damg dmg0</i><br>Activation of point defect recording: Saturable damage - maximum vacancy level. If 0, vacancy generation is unlimited. Requires dynamic mode'
        )
        self.vacancy_level.valueChanged.connect(lambda _: self.edited())
        self.addLayout(self.layout_vacancy_level)

        # additional output options
        self.addSpacing(10)
        self.addWidget(QLabel('<b>Additional output options</b>'))

        self.additionalGrid = QGridLayout()
        self.addLayout(self.additionalGrid)

        # frequency log output
        self.log_frequency = SpinBox(
            default=DefaultValues.idfout,
            input_range=SpinBoxRange.ZERO_INF
        )
        self.layout_log_frequency = InputHBoxLayout(
            'Log messages:',
            self.log_frequency,
            tooltip='<i>fout idfout</i><br>Number of performance log messages during the entire run. 0 suppresses any log messages (Progress bar will not work).'
        )
        self.log_frequency.valueChanged.connect(lambda _: self.edited())
        self.additionalGrid.addLayout(self.layout_log_frequency, 0, 0)

        # frequency integral output
        self.integral_frequency = SpinBox(
            default=DefaultValues.iddout,
            input_range=SpinBoxRange.ZERO_INF,
            step_size=DefaultValues.idqout
        )
        self.layout_integral_frequency = InputHBoxLayout(
            'Integral outputs:',
            self.integral_frequency,
            tooltip='<i>fout iddout</i><br>Number of integral data outputs during the entire run. 0 suppresses any output. Must be a multiple of <i>fout idqout</i>. Requires dynamic mode'
        )
        self.integral_frequency.valueChanged.connect(lambda _: self.edited())
        self.additionalGrid.addLayout(self.layout_integral_frequency, 1, 0)

        # frequency integral output
        self.output_frequency = SpinBox(
            default=DefaultValues.idqout,
            input_range=SpinBoxRange.ZERO_INF
        )
        self.layout_output_frequency = InputHBoxLayout(
            'Profile outputs:',
            self.output_frequency,
            tooltip='<i>fout idqout</i><br>Number of 3D and 2D profile outputs during the entire run. 0 suppresses any output. Requires dynamic mode'
        )
        self.output_frequency.valueChanged.connect(lambda _: self.edited())
        self.additionalGrid.addLayout(self.layout_output_frequency, 1, 1)

        self.integral_frequency.editingFinished.connect(lambda: self.updateIntegralFrequency())
        self.output_frequency.valueChanged.connect(lambda _: self.updateIntegralFrequency())

        # reflected projectiles
        self.layout_reflected_projectiles = InputHBoxLayout(
            'Reflected projectiles',
            None,
            checkbox=False,
            tooltip='<i>outl incd scat</i><br>Compute the angle and energy distributions of reflected projectiles and write them to output files'
        )
        self.layout_reflected_projectiles.checkbox.clicked.connect(lambda _: self.edited())
        self.additionalGrid.addLayout(self.layout_reflected_projectiles, 2, 0)

        # sputtered recoils
        self.layout_sputtered_recoils = InputHBoxLayout(
            'Sputtered recoil atoms',
            None,
            checkbox=False,
            tooltip='<i>outl incd sput</i><br>Compute the angle and energy distributions of sputtered recoil atoms and write them to output files'
        )
        self.layout_sputtered_recoils.checkbox.clicked.connect(lambda _: self.edited())
        self.additionalGrid.addLayout(self.layout_sputtered_recoils, 3, 0)

        """
        # profile outputs
        self.outProfile = InputHBoxLayout(
            'Profile outputs',
            None,
            checkbox=DefaultValues.outp,
            tooltip='<i>outp</i><br>Activation of profile outputs<br>dynamic: damage profile<br>static: average damage generation profile per unit of fluence'
        )
        self.outProfile.checkbox.clicked.connect(lambda _: self.edited())
        self.additionalGrid.addLayout(self.outProfile, 2, 0)

        # deposited energy profiles
        self.energyProfile = InputHBoxLayout(
            'Deposited energy profiles',
            None,
            checkbox=DefaultValues.edep,
            tooltip='<i>edep</i><br>Generates 1D deposition profiles of energy deposited into nuclear and electronic collisions, averaged over the entire run.'
        )
        self.energyProfile.checkbox.clicked.connect(lambda _: self.edited())
        self.additionalGrid.addLayout(self.energyProfile, 2, 1)

        # areal density (components)
        self.arealDensityCompOutp = InputHBoxLayout(
            'Areal density (components)',
            None,
            checkbox=DefaultValues.ardn,
            tooltip='<i>outi ardn</i><br>Areal density of components'
        )
        self.arealDensityCompOutp.checkbox.clicked.connect(lambda _: self.edited())
        self.additionalGrid.addLayout(self.arealDensityCompOutp, 3, 0)

        # sputter yield
        self.sputterYieldOutp = InputHBoxLayout(
            'Sputter yield',
            None,
            checkbox=DefaultValues.spyl,
            tooltip='<i>outi spyl</i><br>Sputter yield of components'
        )
        self.sputterYieldOutp.checkbox.clicked.connect(lambda _: self.edited())
        self.additionalGrid.addLayout(self.sputterYieldOutp, 3, 1)

        # reemitted ammounts
        self.reemittedOutp = InputHBoxLayout(
            'Reemitted amounts',
            None,
            checkbox=DefaultValues.reem,
            tooltip='<i>outi reem</i><br>Reemitted amounts of components'
        )
        self.reemittedOutp.checkbox.clicked.connect(lambda _: self.edited())
        self.additionalGrid.addLayout(self.reemittedOutp, 4, 0)

        # surface atomic fraction
        self.surfAtomicOutp = InputHBoxLayout(
            'Surface atomic fraction',
            None,
            checkbox=DefaultValues.srfc,
            tooltip='<i>outi srfc</i><br>Surface atomic fraction of components'
        )
        self.surfAtomicOutp.checkbox.clicked.connect(lambda _: self.edited())
        self.additionalGrid.addLayout(self.surfAtomicOutp, 4, 1)

        # areal density (vacancies)
        self.arealDensityVacOutp = InputHBoxLayout(
            'Areal density (vacancies)',
            None,
            checkbox=DefaultValues.pdfc,
            tooltip='<i>outi pdfc</i><br>Areal density of vacancies and interstititals'
        )
        self.arealDensityVacOutp.checkbox.clicked.connect(lambda _: self.edited())
        self.additionalGrid.addLayout(self.arealDensityVacOutp, 5, 0)

        # swelling
        self.swellingOutp = InputHBoxLayout(
            'Swelling',
            None,
            checkbox=DefaultValues.srfe,
            tooltip='<i>outi srfe</i><br>Swelling / shrinking'
        )
        self.swellingOutp.checkbox.clicked.connect(lambda _: self.edited())
        self.additionalGrid.addLayout(self.swellingOutp, 5, 1)

        # thin film thickness
        self.thinFilmOutp = InputHBoxLayout(
            'Thin film thickness',
            None,
            checkbox=DefaultValues.fthi,
            tooltip='<i>outi fthi</i><br>Thin film thickness'
        )
        self.thinFilmOutp.checkbox.clicked.connect(lambda _: self.edited())
        self.additionalGrid.addLayout(self.thinFilmOutp, 6, 0)

        # incident projectiles
        self.incidentProjOutp = InputHBoxLayout(
            'Incident projectiles',
            None,
            checkbox=DefaultValues.incd,
            tooltip='<i>outl incd</i><br>Incident pseudoprojectiles'
        )
        self.incidentProjOutp.checkbox.clicked.connect(lambda _: self.edited())
        self.additionalGrid.addLayout(self.incidentProjOutp, 7, 0)

        # deposited projectiles
        self.depositProjOutp = InputHBoxLayout(
            'Deposited projectiles',
            None,
            checkbox=DefaultValues.rang,
            tooltip='<i>outl rang</i><br>Deposited pseudoprojectiles'
        )
        self.depositProjOutp.checkbox.clicked.connect(lambda _: self.edited())
        self.additionalGrid.addLayout(self.depositProjOutp, 7, 1)

        # scattered projectiles
        self.scatterProjOutp = InputHBoxLayout(
            'Scattered projectiles',
            None,
            checkbox=DefaultValues.scat,
            tooltip='<i>outl scat</i><br>Scattered / transmitted pseudoprojectiles'
        )
        self.scatterProjOutp.checkbox.clicked.connect(lambda _: self.edited())
        self.additionalGrid.addLayout(self.scatterProjOutp, 8, 0)

        # sputtered recoil atoms
        self.sputterRecoilAtomsOutp = InputHBoxLayout(
            'Sputtered recoil atoms',
            None,
            checkbox=DefaultValues.sput,
            tooltip='<i>outl sput</i><br>Sputtered pseudo recoil atoms'
        )
        self.sputterRecoilAtomsOutp.checkbox.clicked.connect(lambda _: self.edited())
        self.additionalGrid.addLayout(self.sputterRecoilAtomsOutp, 8, 1)

        # vacancy formation
        self.vacancyFormOutp = InputHBoxLayout(
            'Vacancy formation',
            None,
            checkbox=DefaultValues.vcin,
            tooltip='<i>outl vcin</i><br>Overthreshold pseudo recoil atom start and termination (vacancy and interstitial formation)'
        )
        self.vacancyFormOutp.checkbox.clicked.connect(lambda _: self.edited())
        self.additionalGrid.addLayout(self.vacancyFormOutp, 9, 0)

        # relocation vectors
        self.relocVectorOutp = InputHBoxLayout(
            'Relocation vectors',
            None,
            checkbox=DefaultValues.rrlv,
            tooltip='<i>outl rrlv</i><br>Overthreshold pseudo recoil atom relocation vectors'
        )
        self.relocVectorOutp.checkbox.clicked.connect(lambda _: self.edited())
        self.additionalGrid.addLayout(self.relocVectorOutp, 9, 1)
        """

        self.checkTitle()
        self.checkVacancyLevel()
        self.updatePrecisionOrProjectiles()
        self.updateIntegralFrequency()
        self.checkOutputOptions()

    def checkTitle(self):
        """Check the title of the simulation and change it to exactly 10 characters without whitespace"""

        title = self.simulation_title.text()
        title = title.replace(' ', '_')
        title = alphanumeric(title)
        title = title.ljust(10, '_')
        self.simulation_title.setText(title)

    def checkVacancyLevel(self):
        """Checks if saturable damage can be selected"""

        if self.calculation_method.getValue(save=True) == ArgumentValues.Mode.DYNAMIC:
            self.layout_vacancy_level.setEnabled(True)
            if not self.layout_vacancy_level.checkbox.isChecked():
                self.vacancy_level.setEnabled(False)
        else:
            self.layout_vacancy_level.setEnabled(False)

    def checkOutputOptions(self):
        """Checks if output settings can be selected"""

        if self.calculation_method.getValue(save=True) == ArgumentValues.Mode.DYNAMIC:
            self.layout_reflected_projectiles.checkbox.setChecked(True)
            self.layout_reflected_projectiles.checkbox.setEnabled(False)

        else:
            self.layout_reflected_projectiles.checkbox.setEnabled(True)

    def updatePrecisionOrProjectiles(self, precision: bool = True):
        """Either precision or projectiles can be set"""

        if precision is True:
            precision = self.layout_precision.checkbox.isChecked()
        else:
            precision = not self.layout_projectiles.checkbox.isChecked()

        self.projectiles.setEnabled(not precision)
        self.layout_projectiles.checkbox.setChecked(not precision)

        self.precision.setEnabled(precision)
        self.layout_precision.checkbox.setChecked(precision)

    def updateIntegralFrequency(self):
        """Updates the value of the integralFrequency input field"""

        idqout = self.output_frequency.value()
        iddout = self.integral_frequency.value()

        if idqout == 0:
            self.integral_frequency.setSingleStep(0)
            self.integral_frequency.setValue(0)
            return

        self.integral_frequency.setSingleStep(idqout)
        self.integral_frequency.setValue(idqout * round(iddout / idqout))

    def reset(self):
        """Resets all input fields"""

        self.simulation_title.default = f'TRIDYN{dateStr("%d%m")}'
        self.layout_simulation_title.reset()
        self.layout_comment.reset()
        self.layout_calculation_method.reset()
        self.layout_recoils.reset()
        self.layout_inelastic_loss_model.reset()
        self.layout_collisions.reset()
        self.layout_projectiles.reset()
        self.layout_precision.reset()
        self.layout_fluence.reset()
        self.layout_threads.reset()
        self.layout_vacancy_level.reset()
        self.layout_log_frequency.reset()
        self.layout_integral_frequency.reset()
        self.layout_output_frequency.reset()

        self.layout_reflected_projectiles.reset()
        self.layout_sputtered_recoils.reset()

        """
        self.outProfile.reset()
        self.energyProfile.reset()
        self.arealDensityCompOutp.reset()
        self.sputterYieldOutp.reset()
        self.reemittedOutp.reset()
        self.surfAtomicOutp.reset()
        self.arealDensityVacOutp.reset()
        self.swellingOutp.reset()
        self.thinFilmOutp.reset()
        self.incidentProjOutp.reset()
        self.depositProjOutp.reset()
        self.scatterProjOutp.reset()
        self.sputterRecoilAtomsOutp.reset()
        self.vacancyFormOutp.reset()
        self.relocVectorOutp.reset()
        """

        self.checkTitle()
        self.checkVacancyLevel()
        self.updatePrecisionOrProjectiles()
        self.updateIntegralFrequency()
        self.checkOutputOptions()

    def getArguments(self) -> GeneralArguments:
        """Returns <GeneralArguments> container of parameters for general simulation settings"""

        outi = []
        outl = []
        edep = False
        outp = True

        mode = self.calculation_method.getValue(save=True)
        no_recoils = self.layout_recoils.checkbox.isChecked()
        if mode == ArgumentValues.Mode.STATIC:

            outl.append('rang')
            edep = True

            if no_recoils:
                mode = ArgumentValues.Mode.STATIC_NO_RECOIL

        else:
            outi.extend(['spyl', 'srfc', 'srfe', 'reem'])
            outl.extend(['incd', 'rang', 'scat', 'rrlv'])

        vacancy_level = DefaultValues.dmg0
        if self.layout_vacancy_level.checkbox.isChecked():
            vacancy_level = self.vacancy_level.value()

        precision = self.layout_precision.checkbox.isChecked()
        if precision:
            precision = self.precision.value()

        if self.layout_reflected_projectiles.checkbox.isChecked():
            outl.extend(['incd', 'scat'])

        if self.layout_sputtered_recoils.checkbox.isChecked():
            outl.extend(['incd', 'sput'])

        """
        if self.outProfile.checkbox.isChecked():
            outp = True
        if self.energyProfile.checkbox.isChecked():
            edep = True
        
        if self.arealDensityCompOutp.checkbox.isChecked():
            outi.append('ardn')
        if self.sputterYieldOutp.checkbox.isChecked():
            outi.append('spyl')
        if self.reemittedOutp.checkbox.isChecked():
            outi.append('reem')
        if self.surfAtomicOutp.checkbox.isChecked():
            outi.append('srfc')
        if self.arealDensityVacOutp.checkbox.isChecked():
            outi.append('pdfc')
        if self.swellingOutp.checkbox.isChecked():
            outi.append('srfe')
        if self.thinFilmOutp.checkbox.isChecked():
            outi.append('fthi')

        if self.incidentProjOutp.checkbox.isChecked():
            outl.append('incd')
        if self.depositProjOutp.checkbox.isChecked():
            outl.append('rang')
        if self.scatterProjOutp.checkbox.isChecked():
            outl.append('scat')
        if self.sputterRecoilAtomsOutp.checkbox.isChecked():
            outl.append('sput')
        if self.vacancyFormOutp.checkbox.isChecked():
            outl.append('vcin')
        if self.relocVectorOutp.checkbox.isChecked():
            outl.append('rrlv')
        """

        return GeneralArguments(
            title=self.simulation_title.text(),
            comment=self.comment.text(),
            mode=mode,  # cdat idrel
            no_recoils=no_recoils,  # coll iproj
            inelastic_loss_model=self.inelastic_loss_model.getValue(save=True),  # elst inel
            collisions=self.collisions.value(),  # cdat iwc
            projectiles=self.projectiles.value(),  # pspr nh
            precision=precision,  # prec prcs
            fluence=self.fluence.value(),  # cdat flct
            threads=self.threads.value(),  # thrd nrthr
            vacancy_level=vacancy_level,  # damg dmg0
            log_frequency=self.log_frequency.value(),  # fout idfout
            integral_frequency=self.integral_frequency.value(),  # fout iddout
            output_frequency=self.output_frequency.value(),  # fout idqout
            profile_output=outp,  # outp
            profile_energy=edep,  # edep
            integral_outputs=outi,  # outi
            projectile_outputs=outl,  # outl
            log_reflected='scat' in outl,  # outl scat
            log_sputtered='sput' in outl  # outl sput
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
            title = f'TRIDYN{dateStr("%d%m")}'
            self.layout_simulation_title.mark()
            not_loadable.append('Simulation title')
        self.simulation_title.setText(title)
        self.checkTitle()

        # comment
        comment = settings.comment
        if isinstance(comment, str) and comment.strip() != '':
            self.comment.setText(comment)
        elif len(title) > 10:
            self.comment.setText(title[10:].strip())

        # recoil suppression
        iproj = settings.get('no_recoils')

        # simulation method
        idrel = settings.mode
        if idrel not in DictLookup.idrel or 'mode' in assumed:
            idrel = self.calculation_method.getDefaultSave()
            self.layout_calculation_method.mark()
            not_loadable.append('Calculation mode')
        elif idrel == ArgumentValues.Mode.STATIC_NO_RECOIL:
            idrel = ArgumentValues.Mode.STATIC
            iproj = True
        self.calculation_method.setValue(idrel, from_entries_save=True)

        # recoil suppression
        if not isinstance(iproj, bool):
            iproj = DefaultValues.iproj
            self.layout_recoils.mark()
            not_loadable.append('Recoil suppression')
        self.layout_recoils.checkbox.setChecked(iproj)

        # inelastic loss model
        inel = settings.get('inelastic_loss_model')
        if inel is None:
            inel = arguments.get('inelastic_loss_model')
        if inel not in DictLookup.inel or 'inelastic_loss_model' in assumed:
            inel = self.inelastic_loss_model.getDefaultSave()
            self.layout_inelastic_loss_model.mark()
            not_loadable.append('Inelastic loss model')
        self.inelastic_loss_model.setValue(inel, from_entries_save=True)

        # collisions
        iwc = settings.get('collisions')
        if not isinstance(iwc, int):
            iwc = DefaultValues.iwc
            self.layout_collisions.mark()
            not_loadable.append('Number of collisions')
        self.collisions.setValue(iwc)

        # number of pseudo-particles
        nh = settings.get('projectiles')
        hist = settings.get('histories')
        try:
            nh = int(float(nh))
        except (ValueError, TypeError):
            nh = DefaultValues.nh
            self.layout_projectiles.mark()
            not_loadable.append('Pseudo-particles')
        if isinstance(hist, int):
            nh = nh * hist
        self.layout_projectiles.checkbox.setChecked(True)
        self.projectiles.setValue(nh)

        # precision
        prcs = settings.get('precision')
        if not isinstance(prcs, float):
            if prcs is not False:
                prcs = DefaultValues.prcs
                self.layout_precision.mark()
                self.precision.setValue(prcs)
                self.precision.setValue(False)
                not_loadable.append('Precision')
        else:
            self.precision.setValue(prcs)
            self.layout_precision.checkbox.setChecked(True)

        # fluence
        flct = settings.fluence
        if not isinstance(flct, float) or 'fluence' in assumed:
            flct = DefaultValues.flct
            self.layout_fluence.mark()
            not_loadable.append('Fluence')
        self.fluence.setValue(flct)

        # threads
        nrthr = settings.threads
        if not isinstance(nrthr, int) or 'threads' in assumed:
            nrthr = DefaultValues.nrthr
            self.layout_threads.mark()
            not_loadable.append('Threads')
        self.threads.setValue(nrthr)

        # vacancy level
        dmg0 = settings.get('vacancy_level')
        if not isinstance(dmg0, float):
            dmg0 = DefaultValues.dmg0
            self.layout_vacancy_level.mark()
            not_loadable.append('Vacancy level')
        self.vacancy_level.setValue(dmg0)
        self.layout_vacancy_level.checkbox.setChecked(dmg0 != 0)

        # frequency log output
        idfout = settings.get('log_frequency')
        if not isinstance(idfout, int):
            idfout = DefaultValues.idfout
        self.log_frequency.setValue(idfout)

        # frequency integral output
        iddout = settings.get('integral_frequency')
        if not isinstance(iddout, int):
            iddout = DefaultValues.iddout
        self.integral_frequency.setValue(iddout)

        # frequency integral output
        idqout = settings.get('output_frequency')
        if not isinstance(idqout, int):
            idqout = DefaultValues.idqout
        self.output_frequency.setValue(idqout)

        outi = settings.get('integral_outputs')
        if not isinstance(outi, list):
            outi = []

        outl = settings.get('projectile_outputs')
        if not isinstance(outl, list):
            outl = []

        # reflected projectiles and sputtered recoils
        self.layout_reflected_projectiles.checkbox.setChecked(all(item in outl for item in ['incd', 'scat']))
        self.layout_sputtered_recoils.checkbox.setChecked(all(item in outl for item in ['incd', 'sput']))

        if settings.get('log_reflected'):
            self.layout_reflected_projectiles.checkbox.setChecked(True)

        if settings.get('log_sputtered'):
            self.layout_sputtered_recoils.checkbox.setChecked(True)

        if idrel == ArgumentValues.Mode.DYNAMIC:
            self.layout_reflected_projectiles.checkbox.setChecked(True)

        """
        # profile outputs
        outp = settings.get('profile_output')
        if not isinstance(outp, bool):
            outp = DefaultValues.outp
        self.outProfile.checkbox.setChecked(outp)

        # deposited energy profiles
        edep = settings.get('profile_energy')
        if not isinstance(edep, bool):
            edep = DefaultValues.edep
        self.energyProfile.checkbox.setChecked(edep)

        # areal density (components)
        self.arealDensityCompOutp.checkbox.setChecked(DefaultValues.ardn or 'ardn' in outi)

        # sputter yield
        self.sputterYieldOutp.checkbox.setChecked(DefaultValues.spyl or 'spyl' in outi)

        # reemitted ammounts
        self.reemittedOutp.checkbox.setChecked(DefaultValues.reem or 'reem' in outi)

        # surface atomic fraction
        self.surfAtomicOutp.checkbox.setChecked(DefaultValues.srfc or 'srfc' in outi)

        # areal density (vacancies)
        self.arealDensityVacOutp.checkbox.setChecked(DefaultValues.pdfc or 'pdfc' in outi)

        # swelling
        self.swellingOutp.checkbox.setChecked(DefaultValues.srfe or 'srfe' in outi)

        # thin film thickness
        self.thinFilmOutp.checkbox.setChecked(DefaultValues.fthi or 'fthi' in outi)

        # incident projectiles
        self.incidentProjOutp.checkbox.setChecked(DefaultValues.incd or 'incd' in outl)

        # deposited projectiles
        self.depositProjOutp.checkbox.setChecked(DefaultValues.rang or 'rang' in outl)

        # scattered projectiles
        scat = DefaultValues.scat or 'scat' in outl or bool(settings.get('log_reflected'))
        self.scatterProjOutp.checkbox.setChecked(scat)

        # sputtered recoil atoms
        sput = DefaultValues.sput or 'sput' in outl or bool(settings.get('log_sputtered'))
        self.sputterRecoilAtomsOutp.checkbox.setChecked(sput)

        # vacancy formation
        self.vacancyFormOutp.checkbox.setChecked(DefaultValues.vcin or 'vcin' in outl)

        # relocation vectors
        self.relocVectorOutp.checkbox.setChecked(DefaultValues.rrlv or 'rrlv' in outl)
        """

        self.checkTitle()
        self.checkVacancyLevel()
        self.updatePrecisionOrProjectiles()
        self.updateIntegralFrequency()

        return not_loadable


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
            tooltip='<i>irra qubeam</i><br>How much each element contributes to the beam composition.<br>The abundances of all elements sum up to 1.',
            synced=False,
            limit=1
        ),
        CustomRowField(
            unique='e0',
            label='Energy [eV]',
            tooltip='<i>irra e0</i><br>The kinetic energy (in [eV]) of the incoming ions.',
            synced=False
        ),
        CustomRowField(
            unique='alpha',
            label='Angle [°]',
            tooltip='<i>irra alpha</i><br>The angle of incidence (α) of the incoming ions, measured in degrees from the surface normal.',
            synced=False
        ),
        CustomRowField(
            unique='qumax',
            label='Max conc.',
            tooltip='<i>exst qumax</i><br>The maximum allowed concentration of each element in the target (only dynamic calculations).',
            synced=False,
        ),
        CustomRowField(
            unique='am',
            label='Mass [amu]',
            tooltip='<i>mass am</i><br>The atomic mass (in [amu]) of the element, default taken from internal list.' + modifyHint + syncHint,
            reset_neg=True
        ),
        CustomRowField(
            unique='dns0',
            label='Dens. [1/Å³]',
            tooltip='<i>dens dns0</i><br>The atomic density (in [1/Å³]) of the element, fetched from internal list.' + modifyHint + '<br>Modifying is disabled if a global density is defined.' + syncHint,
            reset_neg=True
        ),
        CustomRowField(
            unique='sbei',
            label='Surf. bind. energy [eV]',
            tooltip='<i>sbem</i><br>The surface binding energy (in [eV]) of this element, fetched from internal list.' + modifyHint + syncHint,
            reset_neg=True
        ),
        CustomRowField(
            unique='ed',
            label='Displ. energy [eV]',
            tooltip='<i>edsp ed</i><br>The displacement energy (in [eV]) of this element, fetched from internal list.' + modifyHint + syncHint,
            reset_neg=True
        ),
        CustomRowField(
            unique='ef',
            label='Cutoff energy [eV]',
            tooltip='<i>efin ef</i><br>The cutoff energy (in [eV]) of this element, by default calculated from min. surface binding energy.',
            synced=False,
        ),
        CustomRowField(
            unique='ires',
            label='Max. conc. action',
            tooltip='<i>exst ires</i><br>Action if max. atomic fraction is reached. Only selectable if max. atomic fraction is different from 1.',
            synced=False
        ),
        # CustomRowField(
        #     unique='ie0',
        #     label='Energy scheme',
        #     tooltip='<i>irrd ie0</i><br>Incident energy scheme.',
        #     synced=False
        # ),
        # CustomRowField(
        #     unique='e0f',
        #     label='Final energy [eV]',
        #     tooltip='<i>irrd e0f</i><br>Final ramp energy in [eV] (only if energy scheme is set to energy ramp).',
        #     synced=False
        # ),
        # CustomRowField(
        #     unique='iadis',
        #     label='Angular distribution',
        #     tooltip='<i>angd iadis</i><br>Type of angular distribution.',
        #     synced=False
        # ),
        # CustomRowField(
        #     unique='adpar1',
        #     label='Ang. dist. parameter 1',
        #     tooltip='<i>angd adpar1</i><br>iadis = 1: fwhm (°)<br>iadis = 2: fwhm (°)<br>iadis = 3: full width (°)',
        #     synced=False
        # ),
        # CustomRowField(
        #     unique='adpar2',
        #     label='Ang. dist. parameter 2',
        #     tooltip='<i>angd adpar2</i><br>iadis = 1: cuttoff angle in units of std. deviation<br>iadis = 2: exponent x<br>iadis = 3: relative central sag',
        #     synced=False
        # ),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # abundances
        self.abundance = DoubleSpinBox(
            input_range=(0, 1),
            step_size=0.01
        )
        self.abundance.valueChanged.connect(lambda: self.updateHighlightWidgetValue(self.abundance, 0))
        self.abundance.valueChanged.connect(self.contentChanged.emit)

        # kinetic energy
        self.kinetic_energy = DoubleSpinBox(
            default=DefaultValues.e0,
            input_range=(0, 1e8)
        )
        self.kinetic_energy.valueChanged.connect(self.contentChanged.emit)

        # incident angle
        self.angle = DoubleSpinBox(
            default=DefaultValues.alpha,
            input_range=(-90, 90),
            step_size=0.01
        )
        self.angle.valueChanged.connect(self.contentChanged.emit)

        # maximum concentration
        self.max_concentration = DoubleSpinBox(
            default=1,
            input_range=(0, 1),
            decimals=4
        )
        self.max_concentration.valueChanged.connect(self.contentChanged.emit)
        self.max_concentration.valueChanged.connect(self.updateMaxConcentration)

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

        # cutoff energy
        self.cutoff_energy = QWidget()
        self.cutoff_energy.setContentsMargins(0, 0, 0, 0)
        self.cutoff_energy.setStyleSheet('border: 1px solid black;')
        self.cutoff_energy_hbox = QHBoxLayout()
        self.cutoff_energy_hbox.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.cutoff_energy_hbox.setContentsMargins(5, 0, 0, 0)
        self.cutoff_energy.setLayout(self.cutoff_energy_hbox)
        self.cutoff_energy_checkbox = QCheckBox()
        self.cutoff_energy_checkbox.setStyleSheet('border: none;')
        self.cutoff_energy_hbox.addWidget(self.cutoff_energy_checkbox)
        self.cutoff_energy_input = DoubleSpinBox(
            input_range=(-1e3, 1e3),
            decimals=self.element_precision
        )
        self.cutoff_energy_input.setEnabled(False)
        self.cutoff_energy_input.setStyleSheet('border: none; border-right: 1px solid black;')
        self.cutoff_energy_hbox.addWidget(self.cutoff_energy_input, stretch=10)

        self.cutoff_energy_checkbox.toggled.connect(self.checkCutoffEnergy)
        self.cutoff_energy_checkbox.toggled.connect(self.contentChanged.emit)
        self.cutoff_energy_input.valueChanged.connect(self.contentChanged.emit)

        # action switch qumax
        self.action_switch = ComboBox(
            default=DefaultValues.ires - 1,
            entries=[
                '-1: transfer',
                '2: reemission 1',
                '3: reemission 2'
            ],
            entries_save=[
                -1,
                2,
                3
            ],
            label_default=True,
            tooltips=[
                '"Diffusive" transfer to nearest unsaturated layer if atomic fraction exceeds <i>exst qumax</i>',
                'Incorporation of fraction (1-[<i>qu</i>]/[<i>qumax</i>]), direct reemission of fraction [<i>qu</i>]/[<i>qumax</i>]',
                'Direct reemission if local atomic fraction exceeds <i>exst qumax</i>'
            ]
        )

        self.action_switch.setDisabled(True)
        self.action_switch.currentIndexChanged.connect(self.contentChanged.emit)
        self.action_switch.mouseReleaseEvent = lambda _: setWidgetBackground(self.action_switch, False)

        # kinetic energy mode
        """
        self.modeKineticEnergy = QComboBox()
        self.modeKineticEnergyItemsText = [
            'run_id_abc.edn',
            'constant',
            'linear ramp'
        ]
        self.modeKineticEnergyItemsSave = [
            ArgumentValues.KineticEnergy.FILE,
            ArgumentValues.KineticEnergy.FIXED,
            ArgumentValues.KineticEnergy.LINEAR_RAMP
        ]

        self.modeKineticEnergyItemsText[DefaultValues.ie0 + 1] = f'{self.modeKineticEnergyItemsText[DefaultValues.ie0 + 1]} (default)'
        self.modeKineticEnergyItems = [f'{i - 1}: {item_text}' for i, item_text in enumerate(self.modeKineticEnergyItemsText)]

        self.modeKineticEnergyTooltips = [
            'The energy distribution of the beam is randomly read from the <i>run_id_abc.edn</i> file',
            'The energy (in eV) for each element in the beam is constant (<i>irra e0</i>)',
            'The energy distribution is a linear ramp starting with <i>irra e0</i> and a final ramp energy of <i>irrd e0f</i>'
        ]
        self.modeKineticEnergy.addItems(self.modeKineticEnergyItems)
        self.modeKineticEnergy.currentIndexChanged.connect(self.contentChanged.emit)
        for i in range(self.modeKineticEnergy.count()):
            self.modeKineticEnergy.setItemData(i, self.modeKineticEnergyTooltips[i], Qt.ToolTipRole)
        self.modeKineticEnergy.setCurrentIndex(DefaultValues.ie0 + 1)
        self.modeKineticEnergy.mouseReleaseEvent = lambda _: setWidgetBackground(self.modeKineticEnergy, False)
        """

        # kinetic energy ramp end
        """
        self.kinEnergyEnd = QDoubleSpinBox()
        self.kinEnergyEnd.setRange(0, 1e8)
        self.kinEnergyEnd.setValue(DefaultValues.e0f)
        self.kinEnergyEnd.valueChanged.connect(self.contentChanged.emit)
        """

        # incident angle mode
        """
        self.modeAngle = QComboBox()
        self.modeAngleItemsText = [
            'constant',
            'gaussian distr.',
            'cosine distr.',
            'parabolic distr.'
        ]
        self.modeAngleItemsSave = [
            ArgumentValues.Angle.FIXED,
            ArgumentValues.Angle.GAUSSIAN_2D,
            ArgumentValues.Angle.COS_2D,
            ArgumentValues.Angle.PARABOLIC_1D
        ]

        self.modeAngleItemsText[DefaultValues.iadis] = f'{self.modeAngleItemsText[DefaultValues.iadis]} (default)'
        self.modeAngleItems = [f'{i}: {item_text}' for i, item_text in enumerate(self.modeAngleItemsText)]

        self.modeAngleTooltips = [
            'The angle α (in °) for each element in the beam is constant (<i>irra alpha</i>)',
            'The angle α follow a 2D axially symmetric gaussian distribution',
            'The angle α follow a 2D axially symmetric cosine distribution',
            'The angle α follow a 1D hollow parabolic distribution'
        ]
        self.modeAngle.addItems(self.modeAngleItems)
        self.modeAngle.currentIndexChanged.connect(self.contentChanged.emit)
        for i in range(self.modeAngle.count()):
            self.modeAngle.setItemData(i, self.modeAngleTooltips[i], Qt.ToolTipRole)
        self.modeAngle.setCurrentIndex(DefaultValues.alpha)
        self.modeAngle.mouseReleaseEvent = lambda _: setWidgetBackground(self.modeAngle, False)
        """

        # incident angle parameter 1
        """
        self.angleParam1 = QDoubleSpinBox()
        self.angleParam1.setRange(-1e8, 1e8)
        self.angleParam1.setValue(DefaultValues.adpar1)
        self.angleParam1.valueChanged.connect(self.contentChanged.emit)
        """

        # incident angle parameter 2
        """
        self.angleParam2 = QDoubleSpinBox()
        self.angleParam2.setRange(-1e8, 1e8)
        self.angleParam2.setValue(DefaultValues.adpar2)
        self.angleParam2.valueChanged.connect(self.contentChanged.emit)
        """

        self.row_widgets += [
            self.abundance,
            self.kinetic_energy,
            self.angle,
            self.max_concentration,
            self.atomic_mass,
            self.atomic_density,
            self.surface_binding_energy,
            self.displacement_energy,
            self.cutoff_energy,
            self.action_switch,
            # self.modeKineticEnergy,
            # self.kinEnergyEnd,
            # self.modeAngle,
            # self.angleParam1,
            # # self.angleParam2
        ]

        self.updateHighlightWidgetValue(self.abundance, 0)

        self.clearSpinboxButtons()

    def checkCutoffEnergy(self):
        """Checks if cutoff energy can be entered by user"""

        self.cutoff_energy_input.setEnabled(self.cutoff_energy_checkbox.isChecked())

    def updateMaxConcentration(self, max_concentration):
        """Enable/Disable max.concentration action depending if max_concentration = 1"""

        self.action_switch.setDisabled(max_concentration == 1)

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

        cutoff_energy = element.cutoff_energy
        if not isinstance(cutoff_energy, float):
            self.cutoff_energy_checkbox.setChecked(False)
            cutoff_energy = 0
        else:
            self.cutoff_energy_checkbox.setChecked(True)
        self.cutoff_energy_input.setValue(round(cutoff_energy, self.element_precision))

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

        cutoff_energy = element.cutoff_energy
        if not isinstance(cutoff_energy, float):
            self.cutoff_energy_checkbox.setChecked(False)
            cutoff_energy = 0
        else:
            self.cutoff_energy_checkbox.setChecked(True)
        self.cutoff_energy_input.setValue(round(cutoff_energy, self.element_precision))

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

        if self.cutoff_energy_checkbox.isChecked():
            cutoff_energy = self.cutoff_energy_input.value()
            if cutoff_energy != self.element.cutoff_energy:
                modified = True
                new_element.cutoff_energy = self.cutoff_energy_input.value()
        elif self.element.cutoff_energy is not None:
            modified = True
            new_element.cutoff_energy = None

        new_element.modified = modified

        return new_element

    def getArguments(self) -> RowArguments:
        """Returns <RowArguments> container of parameters for row"""

        return RowArguments(
            index=self.element_index.value(),
            symbol=self.element.symbol,  # atda
            element=self.getElement(),
            abundance=self.abundance.value(),  # irra qubeam (beam) / comp (target)
            energy=self.kinetic_energy.value(),  # irra e0
            angle=self.angle.value(),  # irra alpha
            max_atomic_fraction=self.max_concentration.value(),  # exst qumax
            max_atomic_fraction_action=self.action_switch.getValue(save=True),  # exst ires
            # kinetic_energy_mode=self.modeKineticEnergyItemsSave[self.modeKineticEnergy.currentIndex()],  # irrd ie0
            # energy_ramp_end=self.kinEnergyEnd.value(),  # irrd e0f
            # angle_mode=self.modeAngleItemsSave[self.modeAngle.currentIndex()],  # angd iadis
            # angle_param1=self.angleParam1.value(),  # angd adpar1
            # angle_param2=self.angleParam2.value()  # angd adpar2
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
            qubeam = DefaultValues.qubeam
        self.abundance.setValue(qubeam)

        # maximum concentration
        qumax = arguments.max_atomic_fraction
        if 'max_atomic_fraction' in assumed:
            qumax = DefaultValues.qumax
        self.max_concentration.setValue(qumax)

        # incidence energy
        e0 = arguments.energy
        if 'energy' in assumed:
            e0 = DefaultValues.e0
        self.kinetic_energy.setValue(e0)

        # incidence angle
        alpha = arguments.angle
        if 'angle' in assumed:
            alpha = DefaultValues.alpha
        self.angle.setValue(alpha)

        ires = arguments.get('max_atomic_fraction_action')
        ires = DictLookup.ires.get(ires)
        if ires is None:
            ires = DefaultValues.ires - 1
        self.action_switch.setCurrentIndex(ires)

        # kinetic energy mode
        """
        ie0 = arguments.get('kinetic_energy_mode')
        if ie0 not in DictLookup.ie0:
            ie0 = general_arguments.get('kinetic_energy_mode')
        if ie0 not in DictLookup.ie0:
            setWidgetBackground(self.modeKineticEnergy, True)
            self.modeKineticEnergy.setCurrentIndex(DefaultValues.ie0 + 1)
        else:
            item_index = self.modeKineticEnergyItemsSave.index(ie0)
            self.modeKineticEnergy.setCurrentIndex(item_index)
        """

        # final ramp energy
        """
        e0f = arguments.get('energy_ramp_end')
        if not isinstance(e0f, float):
            e0f = DefaultValues.e0f
        self.kinEnergyEnd.setValue(e0f)
        """

        # angle mode
        """
        iadis = arguments.get('angle_mode')
        if iadis not in DictLookup.iadis:
            iadis = general_arguments.get('angle_mode')
        if iadis not in DictLookup.iadis:
            setWidgetBackground(self.modeAngle, True)
            self.modeAngle.setCurrentIndex(DefaultValues.iadis)
        else:
            item_index = self.modeAngleItemsSave.index(iadis)
            self.modeAngle.setCurrentIndex(item_index)
        """

        # angle mode parameter 1
        """
        adpar1 = arguments.get('angle_param1')
        if not isinstance(adpar1, float):
            adpar1 = DefaultValues.adpar1
        self.angleParam1.setValue(adpar1)
        """

        # angle mode parameter 1
        """
        adpar2 = arguments.get('angle_param2')
        if not isinstance(adpar2, float):
            adpar2 = DefaultValues.adpar2
        self.angleParam2.setValue(adpar2)
        """


class CompRowTargetSettings(CompRowBeamSettings):
    """
    CompRow for target

    :param version: version of simulation
    """

    rowFields = CompRowBeamSettings.rowFields[3:8] + CompRowBeamSettings.rowFields[9:10]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.row_widgets = self.row_widgets[0:3] + self.row_widgets[6:11] + self.row_widgets[12:13]

    def getArguments(self) -> RowArguments:
        """Returns <RowArguments> container of parameters for row"""

        self.max_concentration.setRange(0, 1)

        return super().getArguments()

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


class ElementData(Elements):
    """
    Simulation supported elements and element specific data
    """

    elementList = [
        Element(
            symbol='H',
            name={
                'en': 'hydrogen',
                'de': 'Wasserstoff'
            },
            atomic_nr=1,
            period=1,
            group=1,
            atomic_mass=1.008,
            atomic_density=0.04271,
            surface_binding_energy=0.0,
            displacement_energy=8.0
        ),
        Element(
            symbol='He',
            name={
                'en': 'helium',
                'de': 'Helium'
            },
            atomic_nr=2,
            period=1,
            group=18,
            atomic_mass=4.0026,
            atomic_density=0.01894,
            surface_binding_energy=0.0,
            displacement_energy=8.0
        ),
        Element(
            symbol='Li',
            name={
                'en': 'lithium',
                'de': 'Lithium'
            },
            atomic_nr=3,
            period=2,
            group=1,
            atomic_mass=6.939,
            atomic_density=0.04597,
            surface_binding_energy=1.67,
            displacement_energy=8.0
        ),
        Element(
            symbol='Be',
            name={
                'en': 'beryllium',
                'de': 'Beryllium'
            },
            atomic_nr=4,
            period=2,
            group=2,
            atomic_mass=9.0122,
            atomic_density=0.12046,
            surface_binding_energy=3.38,
            displacement_energy=8.0
        ),
        Element(
            symbol='B',
            name={
                'en': 'boron',
                'de': 'Bor'
            },
            atomic_nr=5,
            period=2,
            group=13,
            atomic_mass=10.811,
            atomic_density=0.13093,
            surface_binding_energy=5.73,
            displacement_energy=8.0
        ),
        Element(
            symbol='C',
            name={
                'en': 'carbon',
                'de': 'Kohlenstoff'
            },
            atomic_nr=6,
            period=2,
            group=14,
            atomic_mass=12.011,
            atomic_density=0.11364,
            surface_binding_energy=7.41,
            displacement_energy=8.0
        ),
        Element(
            symbol='N',
            name={
                'en': 'nitrogen',
                'de': 'Stickstoff'
            },
            atomic_nr=7,
            period=2,
            group=15,
            atomic_mass=14.007,
            atomic_density=0.03481,
            surface_binding_energy=0.0,
            displacement_energy=8.0
        ),
        Element(
            symbol='O',
            name={
                'en': 'oxygen',
                'de': 'Sauerstoff'
            },
            atomic_nr=8,
            period=2,
            group=16,
            atomic_mass=15.999,
            atomic_density=0.04302,
            surface_binding_energy=0.0,
            displacement_energy=8.0
        ),
        Element(
            symbol='F',
            name={
                'en': 'fluorine',
                'de': 'Fluor'
            },
            atomic_nr=9,
            period=2,
            group=17,
            atomic_mass=18.998,
            atomic_density=0.03522,
            surface_binding_energy=0.0,
            displacement_energy=8.0
        ),
        Element(
            symbol='Ne',
            name={
                'en': 'neon',
                'de': 'Neon'
            },
            atomic_nr=10,
            period=2,
            group=18,
            atomic_mass=20.183,
            atomic_density=0.03585,
            surface_binding_energy=0.0,
            displacement_energy=8.0
        ),
        Element(
            symbol='Na',
            name={
                'en': 'sodium',
                'de': 'Natrium'
            },
            atomic_nr=11,
            period=3,
            group=1,
            atomic_mass=22.989,
            atomic_density=0.02541,
            surface_binding_energy=1.12,
            displacement_energy=8.0
        ),
        Element(
            symbol='Mg',
            name={
                'en': 'magnesium',
                'de': 'Magnesium'
            },
            atomic_nr=12,
            period=3,
            group=2,
            atomic_mass=24.312,
            atomic_density=0.04302,
            surface_binding_energy=1.54,
            displacement_energy=8.0
        ),
        Element(
            symbol='Al',
            name={
                'en': 'aluminum',
                'de': 'Aluminium'
            },
            atomic_nr=13,
            period=3,
            group=13,
            atomic_mass=26.981,
            atomic_density=0.06023,
            surface_binding_energy=3.36,
            displacement_energy=8.0
        ),
        Element(
            symbol='Si',
            name={
                'en': 'silicon',
                'de': 'Silicium'
            },
            atomic_nr=14,
            period=3,
            group=14,
            atomic_mass=28.086,
            atomic_density=0.04977,
            surface_binding_energy=4.7,
            displacement_energy=8.0
        ),
        Element(
            symbol='P',
            name={
                'en': 'phosphoros',
                'de': 'Phosphor(weiss)'
            },
            atomic_nr=15,
            period=3,
            group=15,
            atomic_mass=30.973,
            atomic_density=0.03542,
            surface_binding_energy=3.27,
            displacement_energy=8.0
        ),
        Element(
            symbol='S',
            name={
                'en': 'sulfur',
                'de': 'Schwefel'
            },
            atomic_nr=16,
            period=3,
            group=16,
            atomic_mass=32.064,
            atomic_density=0.03885,
            surface_binding_energy=2.88,
            displacement_energy=8.0
        ),
        Element(
            symbol='Cl',
            name={
                'en': 'chlorine',
                'de': 'Chlor'
            },
            atomic_nr=17,
            period=3,
            group=17,
            atomic_mass=35.453,
            atomic_density=0.0322,
            surface_binding_energy=0.0,
            displacement_energy=8.0
        ),
        Element(
            symbol='Ar',
            name={
                'en': 'argon',
                'de': 'Argon'
            },
            atomic_nr=18,
            period=3,
            group=18,
            atomic_mass=39.948,
            atomic_density=0.02488,
            surface_binding_energy=0.0,
            displacement_energy=8.0
        ),
        Element(
            symbol='K',
            name={
                'en': 'potassium',
                'de': 'Kalium'
            },
            atomic_nr=19,
            period=4,
            group=1,
            atomic_mass=39.102,
            atomic_density=0.01329,
            surface_binding_energy=0.93,
            displacement_energy=8.0
        ),
        Element(
            symbol='Ca',
            name={
                'en': 'calcium',
                'de': 'Calcium'
            },
            atomic_nr=20,
            period=4,
            group=2,
            atomic_mass=40.08,
            atomic_density=0.02014,
            surface_binding_energy=1.83,
            displacement_energy=8.0
        ),
        Element(
            symbol='Sc',
            name={
                'en': 'scandium',
                'de': 'Scandium'
            },
            atomic_nr=21,
            period=4,
            group=3,
            atomic_mass=44.956,
            atomic_density=0.04015,
            surface_binding_energy=3.49,
            displacement_energy=8.0
        ),
        Element(
            symbol='Ti',
            name={
                'en': 'titanium',
                'de': 'Titan'
            },
            atomic_nr=22,
            period=4,
            group=4,
            atomic_mass=47.9,
            atomic_density=0.05682,
            surface_binding_energy=4.89,
            displacement_energy=8.0
        ),
        Element(
            symbol='V',
            name={
                'en': 'vanadium',
                'de': 'Vanadium'
            },
            atomic_nr=23,
            period=4,
            group=5,
            atomic_mass=50.942,
            atomic_density=0.07213,
            surface_binding_energy=5.33,
            displacement_energy=8.0
        ),
        Element(
            symbol='Cr',
            name={
                'en': 'chromium',
                'de': 'Chrom'
            },
            atomic_nr=24,
            period=4,
            group=6,
            atomic_mass=51.996,
            atomic_density=0.0833,
            surface_binding_energy=4.12,
            displacement_energy=8.0
        ),
        Element(
            symbol='Mn',
            name={
                'en': 'maganese',
                'de': 'Mangan'
            },
            atomic_nr=25,
            period=4,
            group=7,
            atomic_mass=54.938,
            atomic_density=0.0815,
            surface_binding_energy=2.98,
            displacement_energy=8.0
        ),
        Element(
            symbol='Fe',
            name={
                'en': 'iron',
                'de': 'Eisen'
            },
            atomic_nr=26,
            period=4,
            group=8,
            atomic_mass=55.847,
            atomic_density=0.08483,
            surface_binding_energy=4.34,
            displacement_energy=8.0
        ),
        Element(
            symbol='Co',
            name={
                'en': 'cobalt',
                'de': 'Cobalt'
            },
            atomic_nr=27,
            period=4,
            group=9,
            atomic_mass=58.933,
            atomic_density=0.09095,
            surface_binding_energy=4.43,
            displacement_energy=8.0
        ),
        Element(
            symbol='Ni',
            name={
                'en': 'nickel',
                'de': 'Nickel'
            },
            atomic_nr=28,
            period=4,
            group=10,
            atomic_mass=58.71,
            atomic_density=0.09128,
            surface_binding_energy=4.46,
            displacement_energy=8.0
        ),
        Element(
            symbol='Cu',
            name={
                'en': 'copper',
                'de': 'Kupfer'
            },
            atomic_nr=29,
            period=4,
            group=11,
            atomic_mass=63.54,
            atomic_density=0.08483,
            surface_binding_energy=3.52,
            displacement_energy=8.0
        ),
        Element(
            symbol='Zn',
            name={
                'en': 'zinc',
                'de': 'Zink'
            },
            atomic_nr=30,
            period=4,
            group=12,
            atomic_mass=65.37,
            atomic_density=0.06546,
            surface_binding_energy=1.35,
            displacement_energy=8.0
        ),
        Element(
            symbol='Ga',
            name={
                'en': 'gallium',
                'de': 'Gallium'
            },
            atomic_nr=31,
            period=4,
            group=13,
            atomic_mass=69.72,
            atomic_density=0.05104,
            surface_binding_energy=2.82,
            displacement_energy=8.0
        ),
        Element(
            symbol='Ge',
            name={
                'en': 'germanium',
                'de': 'Germanium'
            },
            atomic_nr=32,
            period=4,
            group=14,
            atomic_mass=72.59,
            atomic_density=0.04428,
            surface_binding_energy=3.88,
            displacement_energy=8.0
        ),
        Element(
            symbol='As',
            name={
                'en': 'arsenic',
                'de': 'Arsen'
            },
            atomic_nr=33,
            period=4,
            group=15,
            atomic_mass=74.922,
            atomic_density=0.04597,
            surface_binding_energy=1.26,
            displacement_energy=8.0
        ),
        Element(
            symbol='Se',
            name={
                'en': 'selenium',
                'de': 'Selen'
            },
            atomic_nr=34,
            period=4,
            group=16,
            atomic_mass=78.96,
            atomic_density=0.0365,
            surface_binding_energy=2.14,
            displacement_energy=8.0
        ),
        Element(
            symbol='Br',
            name={
                'en': 'bromine (liquid)',
                'de': 'Brom'
            },
            atomic_nr=35,
            period=4,
            group=17,
            atomic_mass=79.909,
            atomic_density=0.02562,
            surface_binding_energy=0.0,
            displacement_energy=8.0
        ),
        Element(
            symbol='Kr',
            name={
                'en': 'krypton',
                'de': 'Krypton'
            },
            atomic_nr=36,
            period=4,
            group=18,
            atomic_mass=83.8,
            atomic_density=0.0187,
            surface_binding_energy=0.0,
            displacement_energy=8.0
        ),
        Element(
            symbol='Rb',
            name={
                'en': 'rubidium',
                'de': 'Rubidium'
            },
            atomic_nr=37,
            period=5,
            group=1,
            atomic_mass=85.47,
            atomic_density=0.01077,
            surface_binding_energy=0.86,
            displacement_energy=8.0
        ),
        Element(
            symbol='Sr',
            name={
                'en': 'strontium',
                'de': 'Strontium'
            },
            atomic_nr=38,
            period=5,
            group=2,
            atomic_mass=87.62,
            atomic_density=0.01787,
            surface_binding_energy=1.7,
            displacement_energy=8.0
        ),
        Element(
            symbol='Y',
            name={
                'en': 'yttrium',
                'de': 'Yttrium'
            },
            atomic_nr=39,
            period=5,
            group=3,
            atomic_mass=88.905,
            atomic_density=0.03041,
            surface_binding_energy=4.24,
            displacement_energy=8.0
        ),
        Element(
            symbol='Zr',
            name={
                'en': 'zirkonium',
                'de': 'Zirkonium'
            },
            atomic_nr=40,
            period=5,
            group=4,
            atomic_mass=91.22,
            atomic_density=0.04271,
            surface_binding_energy=6.33,
            displacement_energy=8.0
        ),
        Element(
            symbol='Nb',
            name={
                'en': 'niobium',
                'de': 'Niob'
            },
            atomic_nr=41,
            period=5,
            group=5,
            atomic_mass=92.906,
            atomic_density=0.05576,
            surface_binding_energy=7.59,
            displacement_energy=8.0
        ),
        Element(
            symbol='Mo',
            name={
                'en': 'molybdenum',
                'de': 'Molybdaen'
            },
            atomic_nr=42,
            period=5,
            group=6,
            atomic_mass=95.94,
            atomic_density=0.06407,
            surface_binding_energy=6.83,
            displacement_energy=8.0
        ),
        Element(
            symbol='Tc',
            name={
                'en': 'technetium',
                'de': 'Technetium'
            },
            atomic_nr=43,
            period=5,
            group=7,
            atomic_mass=99.0,
            atomic_density=0.0714,
            surface_binding_energy=0.0,
            displacement_energy=8.0
        ),
        Element(
            symbol='Ru',
            name={
                'en': 'ruthenium',
                'de': 'Ruthenium'
            },
            atomic_nr=44,
            period=5,
            group=8,
            atomic_mass=101.07,
            atomic_density=0.07256,
            surface_binding_energy=6.69,
            displacement_energy=8.0
        ),
        Element(
            symbol='Rh',
            name={
                'en': 'rhodium',
                'de': 'Rhodium'
            },
            atomic_nr=45,
            period=5,
            group=9,
            atomic_mass=102.91,
            atomic_density=0.07256,
            surface_binding_energy=5.78,
            displacement_energy=8.0
        ),
        Element(
            symbol='Pd',
            name={
                'en': 'palladium',
                'de': 'Palladium'
            },
            atomic_nr=46,
            period=5,
            group=10,
            atomic_mass=106.4,
            atomic_density=0.06767,
            surface_binding_energy=3.91,
            displacement_energy=8.0
        ),
        Element(
            symbol='Ag',
            name={
                'en': 'silver',
                'de': 'Silber'
            },
            atomic_nr=47,
            period=5,
            group=11,
            atomic_mass=107.87,
            atomic_density=0.05847,
            surface_binding_energy=2.97,
            displacement_energy=8.0
        ),
        Element(
            symbol='Cd',
            name={
                'en': 'cadmium',
                'de': 'Cadmium'
            },
            atomic_nr=48,
            period=5,
            group=12,
            atomic_mass=112.4,
            atomic_density=0.04597,
            surface_binding_energy=1.16,
            displacement_energy=8.0
        ),
        Element(
            symbol='In',
            name={
                'en': 'indium',
                'de': 'Indium'
            },
            atomic_nr=49,
            period=5,
            group=13,
            atomic_mass=114.82,
            atomic_density=0.03836,
            surface_binding_energy=2.49,
            displacement_energy=8.0
        ),
        Element(
            symbol='Sn',
            name={
                'en': 'tin',
                'de': 'Zinn'
            },
            atomic_nr=50,
            period=5,
            group=14,
            atomic_mass=118.69,
            atomic_density=0.03695,
            surface_binding_energy=3.12,
            displacement_energy=8.0
        ),
        Element(
            symbol='Sb',
            name={
                'en': 'antimony',
                'de': 'Antimon'
            },
            atomic_nr=51,
            period=5,
            group=15,
            atomic_mass=121.75,
            atomic_density=0.03273,
            surface_binding_energy=2.72,
            displacement_energy=8.0
        ),
        Element(
            symbol='Te',
            name={
                'en': 'tellurium',
                'de': 'Tellur'
            },
            atomic_nr=52,
            period=5,
            group=16,
            atomic_mass=127.6,
            atomic_density=0.02938,
            surface_binding_energy=2.02,
            displacement_energy=8.0
        ),
        Element(
            symbol='I',
            name={
                'en': 'iodine',
                'de': 'Iod'
            },
            atomic_nr=53,
            period=5,
            group=17,
            atomic_mass=126.9,
            atomic_density=0.02343,
            surface_binding_energy=0.0,
            displacement_energy=8.0
        ),
        Element(
            symbol='Xe',
            name={
                'en': 'xenon',
                'de': 'Xenon'
            },
            atomic_nr=54,
            period=5,
            group=18,
            atomic_mass=131.3,
            atomic_density=0.01403,
            surface_binding_energy=0.0,
            displacement_energy=8.0
        ),
        Element(
            symbol='Cs',
            name={
                'en': 'cesium',
                'de': 'Caesium'
            },
            atomic_nr=55,
            period=6,
            group=1,
            atomic_mass=132.91,
            atomic_density=0.0086,
            surface_binding_energy=0.81,
            displacement_energy=8.0
        ),
        Element(
            symbol='Ba',
            name={
                'en': 'barium',
                'de': 'Barium'
            },
            atomic_nr=56,
            period=6,
            group=2,
            atomic_mass=137.34,
            atomic_density=0.01544,
            surface_binding_energy=1.84,
            displacement_energy=8.0
        ),
        Element(
            symbol='La',
            name={
                'en': 'lanthanum',
                'de': 'Lanthan'
            },
            atomic_nr=57,
            period=8,
            group=3,
            atomic_mass=138.91,
            atomic_density=0.02676,
            surface_binding_energy=4.42,
            displacement_energy=8.0
        ),
        Element(
            symbol='Ce',
            name={
                'en': 'cerium',
                'de': 'Cer'
            },
            atomic_nr=58,
            period=8,
            group=4,
            atomic_mass=140.12,
            atomic_density=0.02868,
            surface_binding_energy=4.23,
            displacement_energy=8.0
        ),
        Element(
            symbol='Pr',
            name={
                'en': 'praseodymium',
                'de': 'Praseodym'
            },
            atomic_nr=59,
            period=8,
            group=5,
            atomic_mass=140.91,
            atomic_density=0.02895,
            surface_binding_energy=3.71,
            displacement_energy=8.0
        ),
        Element(
            symbol='Nd',
            name={
                'en': 'neodymium',
                'de': 'Neodym'
            },
            atomic_nr=60,
            period=8,
            group=6,
            atomic_mass=144.24,
            atomic_density=0.02923,
            surface_binding_energy=3.28,
            displacement_energy=8.0
        ),
        Element(
            symbol='Pm',
            name={
                'en': 'promethium',
                'de': 'Promethium'
            },
            atomic_nr=61,
            period=8,
            group=7,
            atomic_mass=147.0,
            atomic_density=0.02635,
            surface_binding_energy=0.0,
            displacement_energy=8.0
        ),
        Element(
            symbol='Sm',
            name={
                'en': 'samarium',
                'de': 'Samarium'
            },
            atomic_nr=62,
            period=8,
            group=8,
            atomic_mass=150.35,
            atomic_density=0.03026,
            surface_binding_energy=2.16,
            displacement_energy=8.0
        ),
        Element(
            symbol='Eu',
            name={
                'en': 'europium',
                'de': 'Europium'
            },
            atomic_nr=63,
            period=8,
            group=9,
            atomic_mass=151.96,
            atomic_density=0.02084,
            surface_binding_energy=1.85,
            displacement_energy=8.0
        ),
        Element(
            symbol='Gd',
            name={
                'en': 'gadolinium',
                'de': 'Gadolinium'
            },
            atomic_nr=64,
            period=8,
            group=10,
            atomic_mass=157.25,
            atomic_density=0.03026,
            surface_binding_energy=3.57,
            displacement_energy=8.0
        ),
        Element(
            symbol='Tb',
            name={
                'en': 'terbium',
                'de': 'Terbium'
            },
            atomic_nr=65,
            period=8,
            group=11,
            atomic_mass=158.92,
            atomic_density=0.03136,
            surface_binding_energy=3.81,
            displacement_energy=8.0
        ),
        Element(
            symbol='Dy',
            name={
                'en': 'dysprosium',
                'de': 'Dysprosium'
            },
            atomic_nr=66,
            period=8,
            group=12,
            atomic_mass=162.5,
            atomic_density=0.0317,
            surface_binding_energy=2.89,
            displacement_energy=8.0
        ),
        Element(
            symbol='Ho',
            name={
                'en': 'holmium',
                'de': 'Holmium'
            },
            atomic_nr=67,
            period=8,
            group=13,
            atomic_mass=164.93,
            atomic_density=0.0322,
            surface_binding_energy=3.05,
            displacement_energy=8.0
        ),
        Element(
            symbol='Er',
            name={
                'en': 'erbium',
                'de': 'Erbium'
            },
            atomic_nr=68,
            period=8,
            group=14,
            atomic_mass=167.26,
            atomic_density=0.03273,
            surface_binding_energy=3.05,
            displacement_energy=8.0
        ),
        Element(
            symbol='Tm',
            name={
                'en': 'thulium',
                'de': 'Thulium'
            },
            atomic_nr=69,
            period=8,
            group=15,
            atomic_mass=168.93,
            atomic_density=0.03327,
            surface_binding_energy=2.52,
            displacement_energy=8.0
        ),
        Element(
            symbol='Yb',
            name={
                'en': 'ytterbium',
                'de': 'Ytterbium'
            },
            atomic_nr=70,
            period=8,
            group=16,
            atomic_mass=173.04,
            atomic_density=0.02428,
            surface_binding_energy=1.74,
            displacement_energy=8.0
        ),
        Element(
            symbol='Lu',
            name={
                'en': 'litetium',
                'de': 'Litetium'
            },
            atomic_nr=71,
            period=6,
            group=3,
            atomic_mass=174.97,
            atomic_density=0.03383,
            surface_binding_energy=4.29,
            displacement_energy=8.0
        ),
        Element(
            symbol='Hf',
            name={
                'en': 'hafnium',
                'de': 'Hafnium'
            },
            atomic_nr=72,
            period=6,
            group=4,
            atomic_mass=178.49,
            atomic_density=0.04428,
            surface_binding_energy=6.31,
            displacement_energy=8.0
        ),
        Element(
            symbol='Ta',
            name={
                'en': 'tantal',
                'de': 'Tantal'
            },
            atomic_nr=73,
            period=6,
            group=5,
            atomic_mass=180.95,
            atomic_density=0.05525,
            surface_binding_energy=8.1,
            displacement_energy=8.0
        ),
        Element(
            symbol='W',
            name={
                'en': 'tungsten',
                'de': 'Wolfram'
            },
            atomic_nr=74,
            period=6,
            group=6,
            atomic_mass=183.85,
            atomic_density=0.0632,
            surface_binding_energy=8.68,
            displacement_energy=8.0
        ),
        Element(
            symbol='Re',
            name={
                'en': 'rhenium',
                'de': 'Rhenium'
            },
            atomic_nr=75,
            period=6,
            group=7,
            atomic_mass=186.2,
            atomic_density=0.06805,
            surface_binding_energy=8.09,
            displacement_energy=8.0
        ),
        Element(
            symbol='Os',
            name={
                'en': 'osmium',
                'de': 'Osmium'
            },
            atomic_nr=76,
            period=6,
            group=8,
            atomic_mass=190.2,
            atomic_density=0.07144,
            surface_binding_energy=8.13,
            displacement_energy=8.0
        ),
        Element(
            symbol='Ir',
            name={
                'en': 'iridium',
                'de': 'Iridium'
            },
            atomic_nr=77,
            period=6,
            group=9,
            atomic_mass=192.2,
            atomic_density=0.07052,
            surface_binding_energy=6.9,
            displacement_energy=8.0
        ),
        Element(
            symbol='Pt',
            name={
                'en': 'platinum',
                'de': 'Platin'
            },
            atomic_nr=78,
            period=6,
            group=10,
            atomic_mass=195.09,
            atomic_density=0.06618,
            surface_binding_energy=5.86,
            displacement_energy=8.0
        ),
        Element(
            symbol='Au',
            name={
                'en': 'gold',
                'de': 'Gold'
            },
            atomic_nr=79,
            period=6,
            group=11,
            atomic_mass=196.97,
            atomic_density=0.05904,
            surface_binding_energy=3.8,
            displacement_energy=8.0
        ),
        Element(
            symbol='Hg',
            name={
                'en': 'mercury',
                'de': 'Quecksilber'
            },
            atomic_nr=80,
            period=6,
            group=12,
            atomic_mass=200.59,
            atomic_density=0.04069,
            surface_binding_energy=0.64,
            displacement_energy=8.0
        ),
        Element(
            symbol='Tl',
            name={
                'en': 'thallium',
                'de': 'Thallium'
            },
            atomic_nr=81,
            period=6,
            group=13,
            atomic_mass=204.37,
            atomic_density=0.03501,
            surface_binding_energy=1.88,
            displacement_energy=8.0
        ),
        Element(
            symbol='Pb',
            name={
                'en': 'lead',
                'de': 'Blei'
            },
            atomic_nr=82,
            period=6,
            group=14,
            atomic_mass=207.19,
            atomic_density=0.03291,
            surface_binding_energy=2.03,
            displacement_energy=8.0
        ),
        Element(
            symbol='Bi',
            name={
                'en': 'bismuth',
                'de': 'Bismuth'
            },
            atomic_nr=83,
            period=6,
            group=15,
            atomic_mass=208.98,
            atomic_density=0.02827,
            surface_binding_energy=2.17,
            displacement_energy=8.0
        ),
        Element(
            symbol='Po',
            name={
                'en': 'polonium',
                'de': 'Polonium'
            },
            atomic_nr=84,
            period=6,
            group=16,
            atomic_mass=210.0,
            atomic_density=0.02653,
            surface_binding_energy=1.5,
            displacement_energy=8.0
        ),
        Element(
            symbol='At',
            name={
                'en': 'astatine',
                'de': 'Astatium'
            },
            atomic_nr=85,
            period=6,
            group=17,
            atomic_mass=210.0,
            atomic_density=0.02868,
            surface_binding_energy=0.0,
            displacement_energy=8.0
        ),
        Element(
            symbol='Rn',
            name={
                'en': 'radon',
                'de': 'Radon'
            },
            atomic_nr=86,
            period=6,
            group=18,
            atomic_mass=222.0,
            atomic_density=0.02688,
            surface_binding_energy=0.0,
            displacement_energy=8.0
        ),
        Element(
            symbol='Fr',
            name={
                'en': 'francium',
                'de': 'Francium'
            },
            atomic_nr=87,
            period=7,
            group=1,
            atomic_mass=223.0,
            atomic_density=0.027,
            surface_binding_energy=0.0,
            displacement_energy=8.0
        ),
        Element(
            symbol='Ra',
            name={
                'en': 'radium',
                'de': 'Radium'
            },
            atomic_nr=88,
            period=7,
            group=2,
            atomic_mass=226.0,
            atomic_density=0.01338,
            surface_binding_energy=0.0,
            displacement_energy=8.0
        ),
        Element(
            symbol='Ac',
            name={
                'en': 'actinium',
                'de': 'Actinium'
            },
            atomic_nr=89,
            period=9,
            group=3,
            atomic_mass=227.0,
            atomic_density=0.02653,
            surface_binding_energy=0.0,
            displacement_energy=8.0
        ),
        Element(
            symbol='Th',
            name={
                'en': 'thorium',
                'de': 'Thorium'
            },
            atomic_nr=90,
            period=9,
            group=4,
            atomic_mass=232.0,
            atomic_density=0.03026,
            surface_binding_energy=5.93,
            displacement_energy=8.0
        ),
        Element(
            symbol='Pa',
            name={
                'en': 'protactinium',
                'de': 'Protactinium'
            },
            atomic_nr=91,
            period=9,
            group=5,
            atomic_mass=231.0,
            atomic_density=0.04015,
            surface_binding_energy=0.0,
            displacement_energy=8.0
        ),
        Element(
            symbol='U',
            name={
                'en': 'u238',
                'de': 'U238'
            },
            atomic_nr=92,
            period=9,
            group=6,
            atomic_mass=238.04,
            atomic_density=0.04818,
            surface_binding_energy=5.42,
            displacement_energy=8.0
        ),
    ]

    def __init__(self):
        super().__init__(self.elementList)


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
        self.history_step_slider = QSlider(Qt.Orientation.Horizontal)
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
    Class for TRIDYN2022 specific parameters
    """

    # parameters should be different for each simulation class
    Name = 'TRIDYN'
    Versions = [
        '2022'
    ]
    Description = '''
The TRIDYN computer simulation describes ion irradiation effects in amorphous
multicomponent material systems with a planar surface, and keeps track of the
dynamic modification of the system due to ion implantation, atomic relocation,
sputtering and thin film deposition. TRIDYN is based on the binary collision
approximation.

A practically unlimited number of different atomic species and up to
20 irradiation/deposition conditions with different incident species, energies
and angles of incidence may be simultaneously treated.

The code allows to predict 1D compositional and damage profiles, surface
erosion (when sputtering prevails) or surface extension (when deposition prevails),
and provides detailed statistics on ion slowing down, recoil transport and
ion mixing, sputtering and vacuum/solid transitions. It may also be run
in static mode.'''
    Logo = ':icons/aboutlogo_hzdr.png'
    About = '''
Wolfhard Möller

<a href="https://www.hzdr.de/">https://www.hzdr.de/</a>
    '''
    SaveFolder = 'TRIDYN'
    InputFilename = '*.in'
    LayerFilename = '*.lay'
    ExampleAdditionalSetting = 'e.g. dsrf 10'
    SkipList = [InputFilename, LayerFilename, '*.prv', '*.ed*']
    OutputTooltips = {
        InputFilename: 'Input file',
        LayerFilename: 'Layer input file',
        '*.prv': 'Previous composition and damage profile output',
        '*.ed*': 'energy distribution function for component id <b>X</b> (*.ed<b>X</b>)',
        '*_indat.dat': 'Initial parameter protocol',
        '*_ardn.dat': 'Areal densities of components',
        '*_spyl.dat': 'Sputtering yields of components',
        '*_pdfc.dat': 'Total areal density of vacancies and interstitials',
        '*_srfc.dat': 'Surface composition data',
        '*_srfe.dat': 'Irradiation induced swelling / shrinking',
        '*_reem.dat': 'Reemitted amounts of components',
        '*_thtf.dat': 'Film thickness',
        '*_prnnn.dat': 'Composition and damage profile',
        '*_prstc.dat': 'Single relocation profile',
        '*_mixng.dat': 'Ion mixing parameter profile',
        '*_edepn.dat': 'Nuclear energy deposition profiles',
        '*_edepe.dat': 'Electronic energy deposition profiles',
        '*_prlst.dat': 'Incident pseudoprojectiles',
        '*_rglst.dat': 'Deposited pseudoprojectiles',
        '*_bslst.dat': 'Scattered pseudoprojectiles',
        '*_splst.dat': 'Sputtered pseudo recoil atoms: emission and generation',
        '*_rvlst.dat': 'Deposited pseudo recoil atoms: displacement vectors',
        '*_rclst.dat': 'Deposited pseudo recoil atoms: generation and termination',
        '*_out.dat': 'Protocol output'
    }
    InputParameters = {
        'cdat': [int, float, int],
        'geom': [float, int, float],
        'atda': str,
        'comp': str,
        'irra': [int, float, float, float],
        'thrd': int,
        'pspr': int,
        'irrd': [int, float, float],
        'angd': [int, int, float, float, float],
        'coll': [int, float],
        'rcsp': int,
        'damg': float,
        'cmpd': str,
        'mass': [int, float],
        'edsp': [int, float],
        'edsc': str,
        'elst': int,
        'elsc': [int, float],
        'efin': [int, float],
        'elbk': [int, float],
        'dens': [int, float],
        'sbem': str,
        'sbei': [int, int, float],
        'sbes': float,
        'sbec': float,
        'relx': float,
        'exst': [int, float, int, int],
        'qmxv': str,
        'prec': float,
        'fout': [int, int, int],
        'outp': None,
        'lout': str,
        'outi': str,
        'dsrf': float,
        'mixg': None,
        'edep': None,
        'outl': str,
        'sclm': str,
        'rand': int
    }
    CompoundList = [
        Compound(
            'CHps',
            elements={'C': 8, 'H': 8}
        ),
        Compound(
            elements={'Fe': 1, 'B': 1}
        ),
        Compound(
            elements={'Mg': 1, 'B': 2}
        ),
        Compound(
            elements={'Ti': 1, 'B': 2}
        ),
        Compound(
            elements={'Al': 4, 'C': 3}
        ),
        Compound(
            elements={'Si': 1, 'C': 1}
        ),
        Compound(
            elements={'Ta': 1, 'C': 1}
        ),
        Compound(
            elements={'Ti': 1, 'C': 1}
        ),
        Compound(
            elements={'W': 1, 'C': 1}
        ),
        Compound(
            elements={'Al': 2, 'O': 3}
        ),
        Compound(
            elements={'As': 2, 'O': 3}
        ),
        Compound(
            elements={'B': 2, 'O': 3}
        ),
        Compound(
            elements={'Co': 1, 'O': 1}
        ),
        Compound(
            elements={'Cr': 2, 'O': 3}
        ),
        Compound(
            elements={'Cs': 2, 'O': 1}
        ),
        Compound(
            elements={'Cu': 2, 'O': 1}
        ),
        Compound(
            elements={'Fe': 2, 'O': 3}
        ),
        Compound(
            elements={'Ga': 2, 'O': 3}
        ),
        Compound(
            elements={'Ge': 1, 'O': 2}
        ),
        Compound(
            elements={'Mg': 1, 'O': 1}
        ),
        Compound(
            elements={'Mn': 3, 'O': 4}
        ),
        Compound(
            elements={'P': 2, 'O': 5}
        ),
        Compound(
            elements={'Ru': 1, 'O': 2}
        ),
        Compound(
            elements={'Se': 1, 'O': 2}
        ),
        Compound(
            elements={'Si': 1, 'O': 2}
        ),
        Compound(
            elements={'Sn': 1, 'O': 2}
        ),
        Compound(
            elements={'Ta': 2, 'O': 5}
        ),
        Compound(
            elements={'Ti': 1, 'O': 2}
        ),
        Compound(
            elements={'U': 1, 'O': 2}
        ),
        Compound(
            elements={'W': 1, 'O': 3}
        ),
        Compound(
            elements={'Zn': 1, 'O': 1}
        ),
        Compound(
            elements={'Zr': 1, 'O': 2}
        ),
        Compound(
            elements={'Al': 1, 'N': 1}
        ),
        Compound(
            'cBN',
            elements={'B': 1, 'N': 1}
        ),
        Compound(
            'hBN',
            elements={'B': 1, 'N': 1}
        ),
        Compound(
            elements={'Cr': 1, 'N': 1}
        ),
        Compound(
            elements={'Cu': 3, 'N': 1}
        ),
        Compound(
            elements={'Ga': 1, 'N': 1}
        ),
        Compound(
            elements={'Hf': 1, 'N': 1}
        ),
        Compound(
            elements={'Mo': 1, 'N': 1}
        ),
        Compound(
            elements={'Si': 3, 'N': 4}
        ),
        Compound(
            elements={'Ti': 1, 'N': 1}
        ),
        Compound(
            elements={'W': 2, 'N': 1}
        ),
        Compound(
            elements={'Zr': 1, 'N': 1}
        ),
        Compound(
            elements={'Mo': 1, 'S': 2}
        ),
        Compound(
            elements={'Co': 1, 'Si': 2}
        ),
        Compound(
            elements={'Fe': 1, 'Si': 2}
        ),
        Compound(
            elements={'Fe': 1, 'Si': 1}
        ),
        Compound(
            elements={'Mg': 1, 'Si': 2}
        ),
        Compound(
            elements={'Pt': 1, 'Si': 1}
        ),
        Compound(
            elements={'Ti': 1, 'Si': 2}
        ),
        Compound(
            elements={'W': 1, 'Si': 2}
        ),
        Compound(
            elements={'Al': 1, 'As': 1}
        ),
        Compound(
            elements={'Ga': 1, 'As': 1}
        ),
        Compound(
            elements={'In': 1, 'As': 1}
        ),
        Compound(
            elements={'Ga': 1, 'Sb': 1}
        )
    ]

    # Reference to classes
    HlTargetSettings = HlTargetSettings
    VlSimulationSettings = VlSimulationSettings
    CompRowBeamSettings = CompRowBeamSettings
    CompRowTargetSettings = CompRowTargetSettings

    # Maximum number of components
    MaxComponents = 20

    def __init__(self):
        super().__init__()

        # elements are updated here
        self.element_data = ElementData()
        self.element_data_default = False

    @staticmethod
    def getVersionName(folder: str, binary: str) -> Union[str, bool]:
        """
        Returns version of simulation depending on selected folder and binary or False if no version can be determined

        :param folder: main folder of simulation
        :param binary: binary of simulation
        """

        # check on path or binary path
        version = findall(r'(?<=tridyn).\d+', (binary + folder).lower())
        if version:
            return f'TRIDYN {version[0]}'

        return False

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

        # pdf should have 'userguide' in title and not be in any subdirectory
        files = [file for file in listdir(folder) if path.isfile(f'{folder}/{file}') and path.splitext(f'{folder}/{file}')[1].lower() == '.pdf' and 'userguide' in file.lower()]
        if files:
            return f'{folder}/{files[0]}'

        return False

    @staticmethod
    def updateElements(folder: str, version: str) -> bool:
        """
        Updates list of <Element> for this simulation

        :param folder: main folder of simulation
        :param version: version of simulation
        """

        # already loaded in __init__()
        return True

    def nameInputFile(self, arguments: SimulationArguments, version: str) -> str:
        """
        Returns file-name of input file

        :param arguments: <SimulationArguments> container
        :param version: version of simulation

        :return: file-name of input file
        """

        filename = self.InputFilename
        title = arguments.title
        title = alphanumeric(title)
        title = title.ljust(10, '_')
        filename = filename.replace('*', title)

        return filename

    def makeInputFile(self, arguments: SimulationArguments, folder: str, version: str) -> str:
        """
        Returns input file as string

        :param arguments: <SimulationArguments> container
        :param folder: folder of simulation
        :param version: version of simulation

        :return: input file for simulation as string
        """

        rows = arguments.beam_rows + arguments.target_rows
        rows = [row for row in rows if row.symbol]
        rows = sorted(rows)
        mask_beam = [1 if row in arguments.beam_rows else 0 for row in rows]

        abundances = [round(row.abundance, 2) for row in rows]
        elements = [row.element for row in rows]
        original_elements = [row.element if not row.element.modified else row.element.getOriginal() for row in rows]
        changed_elements = any(element.modified for element in elements)

        # obligatory control parameters
        title = arguments.settings.title

        comment = arguments.settings.comment

        iq0 = int(len(arguments.structure) > 1)

        flct = arguments.settings.fluence

        idrel = arguments.settings.mode
        idrel = DictLookup.idrel.get(idrel)
        if idrel is None:
            idrel = DefaultValues.idrel

        xmax = float(arguments.target_args.thickness)

        nqx = arguments.target_args.segments

        dthf = arguments.target_args.get('film_thickness')
        if isinstance(dthf, int) or isinstance(dthf, float):
            dthf = float(dthf)
        else:
            dthf = DefaultValues.dthf

        atda = ' '.join([element.symbol for element in elements])

        qu = [1.0 - m for m in mask_beam]
        if arguments.structure and len(arguments.structure[0].abundances) == sum(qu):
            j = 0
            abundance_list = arguments.structure[0].abundances
            for i, q in enumerate(qu):
                if q == 1:
                    qu[i] = abundance_list[j]
                    j += 1

        qu = normalizeList(qu)
        qu = [f'{q}' for q in qu]
        qu = ' '.join(qu)

        comp = ''
        if not iq0:
            comp = f'\ncomp {qu}'

        irra = ''
        qubeam = [round(a, 2) if m == 1 else 0.0 for a, m in zip(abundances, mask_beam)]
        qubeam = normalizeList(qubeam)
        for i, mask in enumerate(mask_beam):
            if mask != 1:
                continue
            row = rows[i]
            irra += f'\nirra {i + 1} {row.energy} {row.angle} {qubeam[i]}'

        # optional control parameters
        cmpd = []

        for compound in arguments.settings.compounds:
            cmpd.append(compound.name_save)

        nrthr = arguments.settings.threads

        prcs = arguments.settings.get('precision')
        if not isinstance(prcs, float):
            prcs = False

        nh = DefaultValues.nh
        hist = arguments.settings.get('histories')
        if not isinstance(hist, int):
            hist = 1
        proj = arguments.settings.get('projectiles')
        if not isinstance(proj, int):
            proj = nh
        nh = hist * proj

        pspr = ''
        prec = f'\nprec {prcs}'
        if prcs is False:
            pspr = f'\npspr {nh}'
            prec = ''

        iwc = arguments.settings.get('collisions')
        if not isinstance(iwc, int):
            iwc = DefaultValues.iwc

        iproj = DefaultValues.iproj
        if arguments.settings.get('no_recoils') or arguments.settings.mode == ArgumentValues.Mode.STATIC_NO_RECOIL:
            iproj = True
        iproj = 0 - int(iproj)

        dmg0 = arguments.settings.get('vacancy_level')
        if not isinstance(dmg0, float):
            dmg0 = DefaultValues.dmg0

        am = ''
        ed = ''
        ef = ''
        dns0 = ''
        sbem = ''
        sbem_flag = False

        if changed_elements:
            for i, (element, original_element) in enumerate(zip(elements, original_elements)):
                if element.atomic_mass != original_element.atomic_mass:
                    am += f'mass {i + 1} {element.atomic_mass}\n'

                if element.displacement_energy != original_element.displacement_energy:
                    ed += f'edsp {i + 1} {element.displacement_energy}\n'

                if element.cutoff_energy != original_element.cutoff_energy:
                    ef += f'efin {i + 1} {element.cutoff_energy}\n'

                if element.atomic_density != original_element.atomic_density:
                    dns0 += f'dens {i + 1} {element.atomic_density}\n'

                if element.surface_binding_energy != original_element.surface_binding_energy:
                    sbem_flag = True

        if sbem_flag:
            sbem = 'sbem\n'
            sbes = [element.surface_binding_energy for element in elements]
            for sbe_1 in sbes:
                sbe_row = [f'{(sbe_2 + sbe_1) / 2}' if (sbe_1 and sbe_2) else '0.00' for sbe_2 in sbes]
                sbem += ' '.join(sbe_row) + '\n'

        global_density = arguments.target_args.get('global_density')
        if isinstance(global_density, float):
            dns0 += f'#gdns {global_density}\n'

        # sbem needs to be before am, ef and dns0
        modifications = sbem + am + ed + ef + dns0
        if modifications:
            modifications = f'\n{modifications.strip()}'

        inel = arguments.settings.get('inelastic_loss_model')
        inel = DictLookup.inel.get(inel)
        if inel is None:
            inel = DefaultValues.inel

        exst = '\n'
        for i, row in enumerate(rows):
            ires = row.get('max_atomic_fraction_action')
            if ires is None:
                ires = DefaultValues.ires
            if row.max_atomic_fraction != 1:
                exst += f'exst {i + 1} {row.max_atomic_fraction} {ires} 0\n'

        idfout = arguments.get('log_frequency')
        if not isinstance(idfout, int):
            idfout = DefaultValues.idfout

        iddout = arguments.get('integral_frequency')
        if not isinstance(iddout, int):
            iddout = DefaultValues.iddout

        idqout = arguments.get('output_frequency')
        if not isinstance(idqout, int):
            idqout = DefaultValues.idqout

        output = ''

        outp = arguments.get('profile_output')
        if isinstance(outp, bool) and outp is True:
            output += '\noutp'

        edep = arguments.get('profile_energy')
        if isinstance(edep, bool) and edep is True:
            output += '\nedep'

        outi_l = arguments.get('integral_outputs')
        if not isinstance(outi_l, list):
            outi_l = []

        outl_l = arguments.get('projectile_outputs')
        if not isinstance(outl_l, list):
            outl_l = []

        scat = arguments.get('log_reflected')
        if isinstance(scat, bool) and scat is True:
            outl_l.append('scat')

        sput = arguments.get('log_sputtered')
        if isinstance(sput, bool) and sput is True:
            outl_l.append('sput')

        outi = ''
        for outi_i in outi_l:
            if outi_i not in outi:
                outi += f' {outi_i}'

        outl = ''
        for outl_i in outl_l:
            if outl_i not in outl:
                outl += f' {outl_i}'

        # additional control parameters
        additions = ''

        for addition in arguments.additional:
            addition = str(addition).strip()

            if addition.startswith('cmpd'):
                cmpd.append(addition[4:].strip())
                continue

            if addition.startswith('outi'):
                outi_l = [a.strip() for a in addition.split(' ') if a.strip()]
                if len(outi_l) > 1:
                    for outi_i in outi_l[1:]:
                        if outi_i not in outi:
                            outi += f' {outi_i}'
                continue

            if addition.startswith('outl'):
                outl_l = [a.strip() for a in addition.split(' ') if a.strip()]
                if len(outl_l) > 1:
                    for outl_i in outl_l[1:]:
                        if outl_i not in outl:
                            outl += f' {outl_i}'
                continue

            additions += f'\n{addition}'

        if cmpd:
            cmpd_line = '\ncmpd '
            cmpd = cmpd_line + cmpd_line.join(cmpd)
        else:
            cmpd = ''

        if outi:
            output += f'\nouti{outi}'

        if outl:
            output += f'\noutl{outl}'

        out = f'''
{title} {comment}
# obligatory control parameters
cdat {iq0} {flct} {idrel}
geom {xmax} {nqx} {dthf}
atda {atda}{comp}
{irra.strip()}
# optional control parameters{cmpd}
thrd {nrthr}{pspr}{prec}
coll {iwc} {iproj}
damg {dmg0}{modifications}
elst {inel}{exst.rstrip()}
fout {idfout} {iddout} {idqout}{output}
{additions.lstrip()}
'''

        return f'{out.strip()}\n'

    def nameLayerFile(self, arguments: SimulationArguments, version: str) -> str:
        """
        Returns file-name of layer file

        :param arguments: <SimulationArguments> container
        :param version: version of simulation

        :return: file-name of layer file
        """

        filename = self.LayerFilename
        title = arguments.title
        title = alphanumeric(title)
        title = title.ljust(10, '_')
        filename = filename.replace('*', title)

        return filename

    @staticmethod
    def makeLayerFile(arguments: SimulationArguments, folder: str, version: str) -> str:
        """
        Returns layer input file as string

        :param arguments: <SimulationArguments> container
        :param folder: folder of simulation
        :param version: version of simulation

        :return: layer input file for simulation as string
        """

        structures = arguments.structure
        if len(structures) < 2:
            return ''

        rows = arguments.beam_rows + arguments.target_rows
        rows = [row for row in rows if row.symbol]
        rows = sorted(rows)
        mask_target = [0 if row in arguments.beam_rows else 1 for row in rows]

        layer_info_total = []
        for structure in structures:
            if not structure.segments:
                continue
            abundance_list = [0.0] * len(rows)
            if arguments.structure and len(arguments.structure[0].abundances) == sum(mask_target):
                j = 0
                for i, m in enumerate(mask_target):
                    if m == 1:
                        abundance_list[i] = structure.abundances[j]
                        j += 1
            layer_line = ('  '.join([f'{abundance:>13.5E}' for abundance in abundance_list])).strip()
            layer_line_rest = (layer_line + '\n') * (structure.segments - 1)
            layer_info_total.append(f'{layer_line}    {structure.name}\n{layer_line_rest}'.strip())

        layer_info_total = '\n'.join(layer_info_total)

        return f'{layer_info_total.strip()}\n'

    def loadFiles(self, folder: str, version: str) -> Union[Tuple[SimulationArguments, list], str, bool]:
        """
        Returns Tuple of <SimulationArguments> container if it can load input files from folder and list of errors while loading
        Returns string of error if input file can not be opened
        Returns False if not implemented

        :param folder: folder of input files
        :param version: version of simulation

        :return: Tuple(<SimulationArguments>, list), str or False
        """

        files = listdir(folder)

        input_file = getFileNameFromFileList(self.InputFilename, files)
        layer_file = getFileNameFromFileList(self.LayerFilename, files)

        if not input_file:
            return False

        # get all contents from input file
        with open(f'{folder}/{input_file}', 'r') as file:
            contents = [line.strip() for line in file.readlines() if line.strip()]

        # obligatory input needs to be provided
        if len(contents) < 5:
            return False

        assumed = DefaultAssumed()
        error_list = []

        def getListIndex(values: list, idx: int):
            """Returns idx-th element of list values, or None if index is out of range"""

            try:
                return values[idx]
            except IndexError:
                return None

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

        def getValueList(values: list, value_type, default_value, item=None, lookup_dict=None, assumed_cls: DefaultAssumed = None) -> list:
            """Returns list of values converted to value_type. If conversion of list element is not successful, it is replaced by default_value"""

            if assumed_cls is None:
                assumed_cls = []
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

        identifiers = []
        # extract variables from contents
        title = getValue(contents[0], str, f'TRIDYN{dateStr("%d%m")}', 'title', assumed_cls=assumed)
        iq0 = DefaultValues.iq0
        flct = DefaultValues.flct
        idrel = DefaultValues.idrel
        xmax = DefaultValues.xmax
        nqx = DefaultValues.nqx
        dthf = DefaultValues.dthf
        atda = []
        comp = []
        e0 = {}
        alpha = {}
        qubeam = {}
        nrthr = DefaultValues.nrthr
        nh = -1
        iwc = DefaultValues.iwc
        iproj = 0 - int(DefaultValues.iproj)
        dmg0 = DefaultValues.dmg0
        cmpd: List[Compound] = []
        am = {}
        ed = {}
        ef = {}
        dns0 = {}
        gdns = False
        sbem = {}
        inel = DefaultValues.inel
        qumax = {}
        ires = {}
        prcs = -1
        idfout = DefaultValues.idfout
        iddout = DefaultValues.iddout
        idqout = DefaultValues.idqout
        outp = False
        outi = []
        outl = []
        edep = False

        additional = []
        for i, content in enumerate(contents[1:]):
            split = [sp.strip() for sp in content.split(' ') if sp.strip()]
            if not split:
                continue

            if split[0] == 'cdat':
                if 'cdat' in identifiers:
                    continue
                iq0 = getValue(getListIndex(split, 1), int, iq0, 'composition_profile', assumed_cls=assumed)
                flct = getValue(getListIndex(split, 2), float, flct, 'fluence', assumed_cls=assumed)
                idrel = getValueDict(getListIndex(split, 3), DictLookup.idrel, idrel, 'mode', assumed_cls=assumed)
                identifiers.append('cdat')
                continue

            if split[0] == 'geom':
                if 'geom' in identifiers:
                    continue
                xmax = getValue(getListIndex(split, 1), float, xmax, 'thickness', assumed_cls=assumed)
                nqx = getValue(getListIndex(split, 2), int, nqx, 'segments', assumed_cls=assumed)
                dthf = getValue(getListIndex(split, 3), float, dthf, 'thin_film_thickness', assumed_cls=assumed)
                identifiers.append('geom')
                continue

            if split[0] == 'atda':
                if 'atda' in identifiers:
                    continue
                atda = getValueList(split[1:], str, 'H', 'symbol', assumed_cls=assumed)
                identifiers.append('atda')
                continue

            if split[0] == 'comp':
                if 'comp' in identifiers:
                    continue
                comp = getValueList(split[1:], float, DefaultValues.qubeam, 'abundance', assumed_cls=assumed)
                identifiers.append('comp')
                continue

            if split[0] == 'irra':
                icp = getValue(getListIndex(split, 1), int, 0, 'beam', assumed_cls=assumed)
                if not icp:
                    continue
                e0[icp] = getValue(getListIndex(split, 2), float, DefaultValues.e0, 'energy', assumed_cls=assumed)
                alpha[icp] = getValue(getListIndex(split, 3), float, DefaultValues.alpha, 'angle', assumed_cls=assumed)
                qubeam[icp] = getValue(getListIndex(split, 4), float, DefaultValues.qubeam, 'abundance', assumed_cls=assumed)
                continue

            if split[0] == 'thrd':
                if 'thrd' in identifiers:
                    continue
                nrthr = getValue(getListIndex(split, 1), int, nrthr, 'threads', assumed_cls=assumed)
                identifiers.append('thrd')
                continue

            if split[0] == 'pspr':
                if 'pspr' in identifiers:
                    continue
                nh = getValue(getListIndex(split, 1), int, DefaultValues.nh, 'projectiles', assumed_cls=assumed)
                identifiers.append('pspr')
                continue

            if split[0] == 'coll':
                if 'coll' in identifiers:
                    continue
                iwc = getValue(getListIndex(split, 1), int, iwc, 'collisions', assumed_cls=assumed)
                iproj = getValue(getListIndex(split, 2), int, iproj, 'recoil', assumed_cls=assumed)
                identifiers.append('coll')
                continue

            if split[0] == 'damg':
                if 'damg' in identifiers:
                    continue
                dmg0 = getValue(getListIndex(split, 1), float, dmg0, 'vacancy_level', assumed_cls=assumed)
                identifiers.append('damg')
                continue

            if split[0] == 'cmpd':
                cmpid = getValue(getListIndex(split, 1), str, '', 'compound', assumed_cls=assumed)
                if not cmpid or cmpid in [c.name_save for c in cmpd]:
                    continue
                cmpd.append(Compound(name=cmpid))
                continue

            if split[0] == 'mass':
                nocp = getValue(getListIndex(split, 1), int, 0, 'atomic_mass', assumed_cls=assumed)
                if not nocp:
                    continue
                am[nocp] = getValue(getListIndex(split, 2), float, -1.0)
                continue

            if split[0] == 'edsp':
                nocp = getValue(getListIndex(split, 1), int, 0, 'displacement_energy', assumed_cls=assumed)
                if not nocp:
                    continue
                ed[nocp] = getValue(getListIndex(split, 2), float, -1.0)
                continue

            if split[0] == 'efin':
                nocp = getValue(getListIndex(split, 1), int, 0, 'cutoff_energy', assumed_cls=assumed)
                if not nocp:
                    continue
                ef[nocp] = getValue(getListIndex(split, 2), float, -1.0)
                continue

            if split[0] == 'dens':
                nocp = getValue(getListIndex(split, 1), int, 0, 'atomic_density', assumed_cls=assumed)
                if not nocp:
                    continue
                dns0[nocp] = getValue(getListIndex(split, 2), float, -1.0)
                continue

            if split[0] == '#gdns':
                if '#gdns' in identifiers:
                    continue
                gdns = getValue(getListIndex(split, 1), float, gdns)
                identifiers.append('#gdns')
                continue

            if split[0] == 'sbem':
                if 'sbem' in identifiers:
                    continue
                j = 1
                while True:
                    j += 1
                    next_content = getListIndex(contents, i + j)
                    if not isinstance(next_content, str):
                        break
                    elif not next_content.strip():
                        break
                    elif not next_content.strip()[0].isdigit() and next_content.strip()[0] != '.':
                        break
                    next_list = getValueList([item.strip() for item in next_content.split(' ') if item.strip()], float, -1.0, assumed_cls=assumed)
                    sbem[j - 1] = getValue(getListIndex(next_list, j - 2), float, -1.0, assumed_cls=assumed)
                identifiers.append('sbem')
                continue

            if split[0] == 'elst':
                if 'elst' in identifiers:
                    continue
                inel = getValueDict(getListIndex(split, 1), DictLookup.inel, inel, 'inelastic_loss_model', assumed_cls=assumed)
                identifiers.append('elst')
                continue

            if split[0] == 'exst':
                nocp = getValue(getListIndex(split, 1), int, 0, 'qumax', assumed_cls=assumed)
                if not nocp:
                    continue
                qumax[nocp] = getValue(getListIndex(split, 2), float, DefaultValues.qumax, 'qumax', assumed_cls=assumed)
                ires[nocp] = getValue(getListIndex(split, 3), int, DefaultValues.ires, 'ires', assumed_cls=assumed)
                continue

            if split[0] == 'prec':
                if 'prec' in identifiers:
                    continue
                prcs = getValue(getListIndex(split, 1), float, DefaultValues.prcs, 'precision', assumed_cls=assumed)
                identifiers.append('prec')
                continue

            if split[0] == 'fout':
                if 'fout' in identifiers:
                    continue
                idfout = getValue(getListIndex(split, 1), int, idfout)
                iddout = getValue(getListIndex(split, 2), int, iddout)
                idqout = getValue(getListIndex(split, 3), int, idqout)
                identifiers.append('fout')
                continue

            if split[0] == 'outp':
                if 'outp' in identifiers:
                    continue
                outp = True
                identifiers.append('outp')
                continue

            if split[0] == 'edep':
                if 'edep' in identifiers:
                    continue
                edep = True
                identifiers.append('edep')
                continue

            if split[0] == 'outi':
                if 'outi' in identifiers:
                    continue
                outi = split[1:]
                identifiers.append('outi')
                continue

            if split[0] == 'outl':
                if 'outl' in identifiers:
                    continue
                outl = split[1:]
                identifiers.append('outl')
                continue

            if split[0].isalpha():
                additional.append(content)

        ncp = len(atda)
        layer_counter = RunningIndex()

        structure = []
        if iq0 > 0:
            error_layer = 'Layer file has incorrect format.'
            if not input_file:
                error_list.append('No known layer files in this directory, assuming no layer file.')
            else:
                # get all contents from layer file
                with open(f'{folder}/{layer_file}', 'r') as file:
                    last_content = []
                    last_abundances = False
                    segment_count = 0
                    extended_lines = file.readlines()
                    extended_lines.append('end')
                    for line in extended_lines:
                        line = line.strip()
                        if not line:
                            continue

                        if line != 'end':
                            content = [sp.strip() for sp in line.split(' ') if sp.strip()]
                            if len(content) < ncp:
                                if error_layer not in error_list:
                                    error_list.append(error_layer)
                                continue

                            abundances = content[:ncp]

                            try:
                                abundances = [float(a) for a in abundances]
                            except ValueError:
                                if error_layer not in error_list:
                                    error_list.append(error_layer)
                                continue

                            if last_abundances is False:
                                last_abundances = abundances
                                last_content = content

                            if abundances == last_abundances:
                                segment_count += 1
                                continue

                        name = f'Layer{layer_counter.get()}'
                        if len(last_content) > ncp:
                            name = last_content[ncp]

                        if not segment_count:
                            segment_count = 1

                        structure.append(StructureArguments(
                            name=name,
                            segments=segment_count,
                            thickness=xmax / segment_count,
                            abundances=last_abundances
                        ))

                        last_abundances = abundances
                        last_content = content
                        segment_count = 1

        index = RunningIndex()

        def rowList(qu_list: list, typ: str) -> List[RowArguments]:
            """Converts the qu_list into a list of <RowArguments>"""
            rows: List[RowArguments] = []
            for ii, (qu_i, symbol_i) in enumerate(zip(qu_list, atda)):
                if not qu_i:
                    continue

                assumed_row = DefaultAssumed()

                element_i = self.element_data.elementFromSymbol(symbol_i)
                if element_i is None:
                    element_i = Element()
                    error_list.append(f'Element {symbol_i} unknown, left empty')
                    symbol_i = ''

                # check if element is modified
                else:
                    am_i = am.get(ii + 1)
                    if am_i is not None and am_i != -1.0:
                        element_i.atomic_mass = am_i
                        element_i.modified = True
                    ed_i = ed.get(ii + 1)
                    if ed_i is not None and ed_i != -1.0:
                        element_i.displacement_energy = ed_i
                        element_i.modified = True
                    ef_i = ef.get(ii + 1)
                    if ef_i is not None and ef_i != -1.0:
                        element_i.cutoff_energy = ef_i
                        element_i.modified = True
                    dns0_i = dns0.get(ii + 1)
                    if dns0_i is not None and dns0_i != -1.0:
                        element_i.atomic_density = dns0_i
                        element_i.modified = True
                    sbem_i = sbem.get(ii + 1)
                    if sbem_i is not None and sbem_i != -1.0:
                        element_i.surface_binding_energy = sbem_i
                        element_i.modified = True

                qumax_i = qumax.get(ii + 1)
                if qumax_i is None:
                    qumax_i = DefaultValues.qumax
                    assumed_row.assumed('max_atomic_fraction')

                ires_i = ires.get(ii + 1)
                if ires_i is None:
                    ires_i = DefaultValues.ires
                    assumed_row.assumed('max_atomic_fraction_action')

                row_parameters = {
                    'index': index.get(),
                    'symbol': symbol_i,
                    'element': element_i,
                    'abundance': qu_i,
                    'max_atomic_fraction': qumax_i,
                    'max_atomic_fraction_action': ires_i
                }

                if typ == 'beam':
                    e0_i = e0.get(ii + 1)
                    if e0_i is None:
                        e0_i = DefaultValues.e0
                        assumed_row.assumed('energy')
                    alpha_i = alpha.get(ii + 1)
                    if alpha_i is None:
                        alpha_i = DefaultValues.alpha
                        assumed_row.assumed('angle')

                    row_parameters.update({
                        'energy': e0_i,
                        'angle': alpha_i
                    })

                row_parameters.update({
                    'assumed': assumed_row
                })
                rows.append(RowArguments(**row_parameters))
            return rows

        # beam_rows data (List[<RowArguments>])
        qubeam_list = []
        for i in range(ncp):
            qubeam_i = qubeam.get(i + 1)
            if qubeam_i is None:
                qubeam_i = DefaultValues.qubeam
            qubeam_list.append(qubeam_i)
        beam_rows = rowList(qubeam_list, 'beam')

        # target_rows data (List[<RowArguments>])
        if not comp:
            if not structure:
                return 'Abundances of target composition can not be read.'
            comp = [0.0] * ncp
            for struct in structure:
                for i in range(ncp):
                    comp[i] += struct.abundances[i]
        target_rows = rowList(comp, 'target')

        # beam_args data (<GeneralBeamArguments>)
        beam_args = GeneralBeamArguments()

        # target_args data (<GeneralTargetArguments>)
        target_args = GeneralTargetArguments(
            thickness=xmax,
            segments=nqx,
            global_density=gdns,
            film_thickness=dthf
        )

        # settings data (<GeneralArguments>)
        if prcs == -1:
            prcs = False
            if nh == -1:
                nh = DefaultValues.nh

        settings = GeneralArguments(
            title=title,
            mode=idrel,
            no_recoil=iproj,
            inelastic_loss_model=inel,
            collisions=iwc,
            projectiles=nh,
            precision=prcs,
            fluence=flct,
            threads=nrthr,
            compounds=cmpd,
            vacancy_level=dmg0,
            log_frequency=idfout,
            integral_frequency=iddout,
            output_frequency=idqout,
            profile_output=outp,
            profile_energy=edep,
            integral_outputs=outi,
            projectile_outputs=outl,
            log_reflected='scat' in outl,
            log_sputtered='sput' in outl
        )

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

        else:
            target_indices = [i for i, c in enumerate(comp) if c]
            for struct in structure:
                abundances = [sa for i, sa in enumerate(struct.abundances) if i in target_indices]
                struct.abundances = abundances

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
        sbem_flag = False
        for i, setting in enumerate(settings.split('\n')):
            setting = setting.strip()
            if setting.startswith('#'):
                continue

            if '=' in settings:
                errors.append(f'Line {i + 1}: No "=" allowed')
                continue

            content = [sp.strip() for sp in setting.split()]
            if not content:
                continue

            if sbem_flag:
                isnumeric = True
                try:
                    float(content[0])
                except ValueError:
                    isnumeric = False

                if isnumeric:
                    continue
                sbem_flag = False

            if content[0] == 'sbem':
                sbem_flag = True
                continue

            parameter_type = self.InputParameters.get(content[0], False)
            if parameter_type is False:
                errors.append(f'Line {i + 1}: Unknown variable "{content[0]}"')

            if parameter_type is None:
                if len(content) > 1:
                    errors.append(f'Line {i + 1}: "{content[0]}" does not take arguments')
                continue

            elif isinstance(parameter_type, list):
                error = False
                try:
                    if len(parameter_type) == len(content[1:]):
                        for t, c in zip(parameter_type, content[1:]):
                            t(c)
                    else:
                        error = True
                except (ValueError, IndexError):
                    error = True
                finally:
                    if error:
                        arguments = ' '.join([str(t) for t in parameter_type])
                        errors.append(f'Line {i + 1}: variable "{content[0]}" has wrong arguments (should be "{content[0]} {arguments}")')
                continue

            data_type = str
            try:
                float(content[1])
                data_type = float
                int(content[1])
                data_type = int
            except (ValueError, IndexError):
                pass

            if parameter_type != data_type and not (parameter_type is None or parameter_type is str):
                errors.append(f'Line {i + 1}: variable "{content[0]}" has wrong type (should be {parameter_type})')

        return errors

    def cmd(self, binary: str, save_folder: str, input_file: str, version: str) -> (str, bool, str):
        """
        Returns command to be executed

        :param binary: path to binary executable
        :param save_folder: path to save folder
        :param input_file: file name of input file
        :param version: version of simulation

        :return: Tuple of
                    str: command to be executed in QProcess
                    bool: True if input file should be piped
                    str: command to be executed in cmd/shell
        """

        return (
            f'"{binary}"',
            True,
            f'"{binary}" < "{save_folder}/{input_file}"'
        )

    def getProgress(self, save_folder: str, process_log: str, version: str) -> int:
        """
        Returns progress in % of running simulation.
        Negative return value indicates some error.

        :param save_folder: folder for output files
        :param process_log: most recent output of process
        :param version: version of simulation
        """

        split = process_log.lstrip().split(' ', 1)
        try:
            simulated = int(split[0])
        except ValueError:
            return -1

        files = listdir(save_folder)
        indat_file_template = '*_indat.dat'
        indat_file = getFileNameFromFileList(indat_file_template, files)
        if not indat_file:
            return -1

        with open(f'{save_folder}/{indat_file}', 'r') as file:
            file.readline()
            line_contents = [sp.strip() for sp in file.readline().split(' ') if sp.strip()]
            try:
                particles = int(line_contents[3])
            except (ValueError, IndexError):
                return -1

        return round(100 * simulated / particles)


class SimulationOutput(SimulationsOutput):
    """
    Class for displaying TRIDYN2022 specific parameters and plots
    """

    # References to classes
    HlPlot = HlPlot

    def __init__(self, plot: MplCanvas, element_data: Elements):
        super().__init__(plot, element_data)

        self.is_dynamic = False
        self.initial_protocol = {}

        self.scattered_data: List[Tuple[np.ndarray]] = []
        self.sputtered_data: List[Tuple[np.ndarray]] = []

        self.depth_profile_data = ()

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
        self.initial_protocol = {}

        self.scattered_data = []
        self.sputtered_data = []

        self.depth_profile_data = ()

        self.fluence_array = None
        self.depth_array = None
        self.conc_array = None

    def updateData(self, save_folder: str) -> bool:
        """
        Update evaluation data from file

        :param save_folder: path to save folder
        """

        self.save_folder = save_folder
        initial_data = self.getInitialData()
        if initial_data is None:
            self.save_folder = ''
            return False

        elements = ElementList()
        masses = []

        self.initial_protocol = initial_data

        # data from protocol file
        ncp = initial_data['ncp']
        cp = initial_data['cp']

        # check if both are equal
        if ncp != len(cp):
            return False

        for c in cp:
            element = self.element_data.elementFromNr(c['zz'])
            elements.append(element.symbol)
            masses.append(element.atomic_mass)

        self.elements = elements
        self.masses = np.array(masses)
        self.is_dynamic = initial_data['idrel'] == 1

        return True

    def genfromtxt(self, filename: str, skip_header: int = 0, **kwargs) -> Optional[np.ndarray]:
        """
        Extension of numpy genfromtxt.
        Searches filename in save_folder and returns data inside

        :param filename: name of file
        :param skip_header: skips first lines

        :return: None if file does not exist
                 numpy.array of data in file
        """

        file = getFileNameFromFileList(filename, listdir(self.save_folder))
        if not file:
            return

        # numpy genfromtxt is very slow, use own implementation instead
        # data = np.genfromtxt(f'{self.save_folder}/{file}', skip_header=skip_header, **kwargs)
        data = fileToNpArray(f'{self.save_folder}/{file}', skip_header=skip_header, **kwargs)

        if not data.size:
            return

        return data

    def getInitialData(self) -> Optional[Dict]:
        """
        Returns the initial parameters (*_indat.dat file data)

        :return: Dict(
                    'id',
                    'flct', 'pseu', 'prcs', 'nh', 'ncp', 'nirr', 'idrel', 'iproj', 'irand', 'ioutd',
                    'xmax', 'nqx', 'dthf', 'dsf', 'srex',
                    'inel', 'iwc', 'dmg0', 'csbe',
                    'ifout', 'idout', 'iqout', 'nqxn', 'nqxx',
                    'irgl', 'iscl', 'ispl', 'ircl',
                    'cp': List({
                        'zz', 'm', 'be', 'ef', 'ed', 'qu0', 'dns0', 'ck', 'ircsp',
                        'ires', 'irep', 'qumax', 'pmxv', 'sbv'
                    }),
                    'ir': List({
                        'ircp', 'ie0', 'e0', 'ef0', 'alpha0', 'qubeam', 'iadis', 'adpar'
                    }
                 )

                 or None
        """

        protocol = getFileNameFromFileList('*_indat.dat', listdir(self.save_folder))
        if not protocol:
            return

        result = {}

        with open(f'{self.save_folder}/{protocol}', 'r') as file:
            # 'id'
            result['id'] = file.readline()

            # 'flct', 'pseu', 'prcs', 'nh', 'ncp', 'nirr', 'idrel', 'iproj', 'irand', 'ioutd'
            contents = file.readline().strip().split()
            result['flct'] = float(contents[0])
            result['pseu'] = float(contents[1])
            result['prcs'] = float(contents[2])
            result['nh'] = int(contents[3])
            result['ncp'] = int(contents[4])
            result['nirr'] = int(contents[5])
            result['idrel'] = int(contents[6][0])  # only first character, since '*****' is added in static mode
            result['iproj'] = int(contents[7])
            result['irand'] = int(contents[8])
            result['ioutd'] = contents[9] == 'T'

            # 'xmax', 'nqx', 'dthf', 'dsf', 'srex'
            contents = file.readline().strip().split()
            result['xmax'] = float(contents[0])
            result['nqx'] = int(contents[1])
            result['dthf'] = float(contents[2])
            result['dsf'] = float(contents[3])
            result['srex'] = float(contents[4])

            # 'inel', 'iwc', 'dmg0', 'csbe'
            contents = file.readline().strip().split()
            result['inel'] = int(contents[0])
            result['iwc'] = int(contents[1])
            result['dmg0'] = float(contents[2])
            result['csbe'] = float(contents[3])

            # 'ifout', 'idout', 'iqout', 'nqxn', 'nqxx'
            contents = file.readline().strip().split()
            result['ifout'] = int(contents[0])
            result['idout'] = int(contents[1])
            result['iqout'] = int(contents[2])
            result['nqxn'] = int(contents[3])
            result['nqxx'] = int(contents[4])

            # 'irgl', 'iscl', 'ispl', 'ircl'
            contents = file.readline().strip().split()
            result['irgl'] = contents[0] == 'T'
            result['iscl'] = contents[1] == 'T'
            result['ispl'] = contents[2] == 'T'
            result['ircl'] = contents[3] == 'T'

            cp = []
            for _ in range(result['ncp']):
                cp_result = {}

                # 'zz', 'm', 'be', 'ef', 'ed', 'qu0', 'dns0', 'ck', 'ircsp'
                contents = file.readline().strip().split()
                cp_result['zz'] = int(float(contents[0]))
                cp_result['m'] = float(contents[1])
                cp_result['be'] = float(contents[2])
                cp_result['ef'] = float(contents[3])
                cp_result['ed'] = float(contents[4])
                cp_result['qu0'] = float(contents[5])
                cp_result['dns0'] = float(contents[6])
                cp_result['ck'] = float(contents[7])
                cp_result['ircsp'] = contents[8] == 'T'

                # 'ires', 'irep', 'qumax', 'pmxv', 'sbv'
                contents = file.readline().strip().split()
                cp_result['ires'] = int(contents[0])
                cp_result['irep'] = int(contents[1])
                cp_result['qumax'] = float(contents[2])
                cp_result['pmxv'] = float(contents[3])
                cp_result['sbv'] = [float(val) for val in contents[4:]]

                cp.append(cp_result)
            result['cp'] = cp

            ir = []
            for _ in range(result['nirr']):
                ir_result = {}

                # 'ircp', 'ie0', 'e0', 'ef0', 'alpha0', 'qubeam', 'iadis', 'adpar'
                contents = file.readline().strip().split()
                ir_result['ircp'] = int(contents[0])
                ir_result['ie0'] = int(contents[1])
                ir_result['e0'] = float(contents[2])
                ir_result['ef0'] = float(contents[3])
                ir_result['alpha0'] = float(contents[4])
                ir_result['qubeam'] = float(contents[5])
                ir_result['iadis'] = int(contents[6])
                ir_result['adpar'] = [float(val) for val in contents[7:]]

                ir.append(ir_result)
            result['ir'] = ir

        return result

    def getProtocolData(self) -> Optional[Tuple[np.ndarray, ...]]:
        """
        Returns the output protocol (*_out.dat file data)

        :return: Tuple(
                    sputter_yield,
                    transmission_yield,
                    reflection,
                    transmission,
                    implantation,
                    energy_loss
                 )

                 or None
        """

        protocol = getFileNameFromFileList('*_out.dat', listdir(self.save_folder))
        if not protocol:
            return

        sputter_yield = np.zeros(len(self.elements))
        transmission_yield = np.zeros(len(self.elements))
        reflection = np.zeros(len(self.elements))
        transmission = np.zeros(len(self.elements))
        implantation = np.zeros(len(self.elements))
        energy_loss = np.zeros((len(self.elements), 3))
        particles = np.zeros(len(self.elements))
        launched_total = 0

        with open(f'{self.save_folder}/{protocol}', 'r') as file:
            lines = [line.strip() for line in file.readlines()]

        for i, line in enumerate(lines):
            if line.startswith('pseudoprojectile statistics:'):
                for j, line_data in enumerate(lines[i:]):
                    if not line_data:
                        break

                    if line_data.startswith('irradiation condition'):
                        element = int(lines[i + j].split('=')[1].strip()) - 1
                        launched = float(lines[i + j + 1].split('=')[1].strip().split()[0])
                        depth = float(lines[i + j + 2].split('=')[2].strip().split()[0])
                        scattered = float(lines[i + j + 3].split('=')[1].strip().split()[0])
                        transmitted = float(lines[i + j + 4].split('=')[1].strip().split()[0])
                        launched_total += launched

                        if element in range(len(self.elements)):
                            reflection[element] = scattered / launched
                            transmission[element] = transmitted / launched
                            implantation[element] = depth
                            particles[element] = launched

            elif line.startswith('pseudo recoil atom statistics:'):
                for j, line_data in enumerate(lines[i:]):
                    if not line_data:
                        break

                    if line_data.startswith('component'):
                        element = int(lines[i + j].split(':')[0][-3:]) - 1
                        generated = float(lines[i + j + 1].split('=')[1].strip().split()[0])
                        sputtered = float(lines[i + j + 2].split('=')[1].strip().split()[0])
                        transmitted = float(lines[i + j + 3].split('=')[1].strip().split()[0])

                        if element in range(len(self.elements)):
                            sputter_yield[element] = sputtered / launched_total
                            transmission_yield[element] = transmitted / launched_total
                            particles[element] += generated

            elif line.startswith('deposited energy'):
                for j, line_data in enumerate(lines[i:]):
                    if not line_data:
                        break

                    if line_data.startswith('component'):
                        element = int(lines[i + j].split(':')[0][-3:]) - 1
                        electronic = float(lines[i + j + 1].split('=')[1].strip().split()[0])
                        nuclear = float(lines[i + j + 2].split('=')[1].strip().split()[0])

                        if element in range(len(self.elements)):
                            energy_loss[element] = np.array([electronic, nuclear, 0])

        particles_reshaped = particles.reshape(-1, 1)
        energy_loss = np.divide(energy_loss, particles_reshaped, out=np.zeros_like(energy_loss), where=particles_reshaped != 0)
        energy_loss[:, 2] = np.sum(energy_loss[:, 0:2], axis=1)

        return (
            sputter_yield,
            transmission_yield,
            reflection,
            transmission,
            implantation,
            energy_loss
        )

    def getSputterYieldData(self) -> Optional[Tuple[np.ndarray, ...]]:
        """
        Returns the sputtering yields of components (*_spyl.dat file data)

        :return: Tuple(
                    fluence,
                    sputtered_yield
                 )

                 or None
        """

        data = self.genfromtxt('*_spyl.dat', skip_header=2, colum_required=len(self.elements))
        if data is None:
            return

        return data[:, 0], data[:, 1:]

    def getDepthProfile(self) -> Optional[Tuple[np.ndarray, ...]]:
        """
        Returns all depth profile outputs (*_prXXX.dat files data)

        :return: Tuple(
                    swelling_shrinking,
                    partial_fluences,
                    reemitted,
                    layer_depth,
                    atomic_density,
                    interstitial,
                    vacancies,
                    atomic_fractions
                 )

                 or None
        """

        profiles = getFilesNameFromFileList('*_pr*.dat', listdir(self.save_folder))
        profiles = [profile for profile in profiles if profile[-7:-4].isnumeric()]
        if not profiles:
            return
        profiles = sorted(profiles, key=lambda x: int(x[-7:-4]))

        if self.depth_profile_data:
            read_elements = self.depth_profile_data[0].size
            profiles = profiles[read_elements:]

            if not profiles:
                return self.depth_profile_data

        new_profiles = len(profiles)

        with open(f'{self.save_folder}/{profiles[0]}', 'r') as file:
            lines = [line.strip() for line in file.readlines() if line.strip()]
            columns = len(lines[5].split())
            layers = len(lines) - 5

        nirr = self.initial_protocol['nirr'] if isinstance(self.initial_protocol['nirr'], int) else 1

        swelling_shrinking = np.zeros(new_profiles)
        partial_fluences = np.zeros((new_profiles, nirr))
        reemitted = np.zeros((new_profiles, len(self.elements)))
        layer_depth = np.zeros((new_profiles, layers))
        atomic_density = np.zeros((new_profiles, layers))

        interstitial = None
        vacancies = None
        damg = columns - 2 - len(self.elements)
        if damg:
            interstitial = np.zeros((new_profiles, layers))
            vacancies = np.zeros((new_profiles, layers))

        atomic_fractions = np.zeros((len(self.elements), new_profiles, layers))

        for i, profile in enumerate(profiles):
            profile = f'{self.save_folder}/{profile}'
            with open(profile, 'r') as file:
                swelling_shrinking[i] = float(file.readline().strip().split()[0].replace('D', 'E'))

                partial_fluence = [float(flcp.replace('D', 'E')) for flcp in file.readline().strip().split()]
                if len(partial_fluence) != nirr:
                    partial_fluence = partial_fluence[:nirr]
                    partial_fluence.extend([0] * (nirr - len(partial_fluence)))
                partial_fluences[i] = np.array(partial_fluence)

                reemitted[i] = np.array([float(reem.replace('D', 'E')) for reem in file.readline().strip().split()])

            # numpy genfromtxt is very slow
            # data = np.genfromtxt(profile, skip_header=5)
            data = fileToNpArray(profile, skip_header=5)

            layer_depth[i] = data[:, 0]
            atomic_density[i] = data[:, 1]

            if damg:
                interstitial[i] = data[:, 2]
                vacancies[i] = data[:, 3]

            for j in range(len(self.elements)):
                atomic_fractions[j, i] = data[:, -len(self.elements) + j]

        if self.depth_profile_data:
            swelling_shrinking = np.append(self.depth_profile_data[0], swelling_shrinking, axis=0)
            partial_fluences = np.append(self.depth_profile_data[1], partial_fluences, axis=0)
            reemitted = np.append(self.depth_profile_data[2], reemitted, axis=0)
            layer_depth = np.append(self.depth_profile_data[3], layer_depth, axis=0)
            atomic_density = np.append(self.depth_profile_data[4], atomic_density, axis=0)
            interstitial = np.append(self.depth_profile_data[5], interstitial, axis=0)
            vacancies = np.append(self.depth_profile_data[6], vacancies, axis=0)
            atomic_fractions = np.append(self.depth_profile_data[7], atomic_fractions, axis=1)

        self.depth_profile_data = (
            swelling_shrinking,
            partial_fluences,
            reemitted,
            layer_depth,
            atomic_density,
            interstitial,
            vacancies,
            atomic_fractions
        )

        return self.depth_profile_data

    def getSurfaceCompositionData(self) -> Optional[Tuple[np.ndarray, ...]]:
        """
        Returns the surface atomic fractions of components (*_srfc.dat file data)

        :return: Tuple(
                    fluence,
                    surface_fractions
                 )

                 or None
        """

        data = self.genfromtxt('*_srfc.dat', skip_header=2)
        if data is None:
            return

        return data[:, 0], data[:, 1:]

    def getSwellingShrinkingData(self) -> Optional[Tuple[np.ndarray, ...]]:
        """
        Returns the swelling/shrinking (*_srfe.dat file data)

        :return: Tuple(
                    fluence,
                    surface
                 )

                 or None
        """

        data = self.genfromtxt('*_srfe.dat', skip_header=2)
        if data is None:
            return

        return data[:, 0], -data[:, 1]

    def getReemittedData(self) -> Optional[Tuple[np.ndarray, ...]]:
        """
        Returns the reemitted amounts of components (*_reem.dat file data)

        :return: Tuple(
                    fluence,
                    reemitted
                 )

                 or None
        """

        data = self.genfromtxt('*_reem.dat', skip_header=2)
        if data is None:
            return

        return data[:, 0], data[:, 1:]

    def getArealDensityData(self) -> Optional[Tuple[np.ndarray, ...]]:
        """
        Returns the areal density of components (*_ardn.dat file data)

        :return: Tuple(
                    fluence,
                    areal_densities
                 )

                 or None
        """

        data = self.genfromtxt('*_ardn.dat', skip_header=2)
        if data is None:
            return

        return data[:, 0], data[:, 1:]

    def getIncidentData(self) -> Optional[List[Optional[Tuple[np.ndarray, ...]]]]:
        """
        Returns the incident pseudo projectiles (*_prlst.dat file data)

        :return: List(
                    Tuple(
                        proj_number,
                        energy,
                        coordinates
                    )

                    or None
                 )

                 or None
        """

        data = self.genfromtxt('*_prlst.dat', skip_header=2)
        if data is None:
            return

        element, count = np.unique(data[:, 0], return_counts=True)

        result = [None] * len(self.elements)

        for e in element:
            i = int(e) - 1
            if i not in range(len(self.elements)):
                continue
            mask = np.where(data[:, 0] == e)
            result[i] = (
                data[mask][:, 1],
                data[mask][:, 2],
                data[mask][:, 3:6]
            )

        return result

    def getDepositedData(self) -> Optional[List[Optional[Tuple[np.ndarray, ...]]]]:
        """
        Returns the deposited pseudo projectiles (*_rglst.dat file data)

        :return: List(
                    Tuple(
                        proj_number,
                        collisions,
                        coordinates
                    )

                    or None
                 )

                 or None
        """

        data = self.genfromtxt('*_rglst.dat', skip_header=2)
        if data is None:
            return

        element, count = np.unique(data[:, 0], return_counts=True)

        result = [None] * len(self.elements)

        for e in element:
            i = int(e) - 1
            if i not in range(len(self.elements)):
                continue
            mask = np.where(data[:, 0] == e)
            result[i] = (
                data[mask][:, 1],
                data[mask][:, 2],
                data[mask][:, 3:6]
            )

        return result

    def getScatteredData(self) -> Optional[List[Optional[Tuple[np.ndarray, ...]]]]:
        """
        Returns the scattered pseudo projectiles (*_bslst.dat file data)

        :return: List(
                    Tuple(
                        proj_number,
                        collisions,
                        energy,
                        cosines,
                        coordinates
                    )

                    or None
                 )

                 or None
        """

        if len(self.scattered_data) != len(self.elements):
            self.scattered_data = [None] * len(self.elements)

        old_length = 0
        for sd in self.scattered_data:
            if sd is not None:
                old_length += len(sd[0])

        data = self.genfromtxt('*_bslst.dat', skip_header=2 + old_length)
        if data is None:
            if all([sd is None for sd in self.scattered_data]):
                return
            return self.scattered_data

        element, count = np.unique(data[:, 0], return_counts=True)

        for e in element:
            i = int(e) - 1
            if i not in range(len(self.elements)):
                continue
            mask = np.where(data[:, 0] == e)
            if self.scattered_data[i] is None:
                self.scattered_data[i] = (
                    data[mask][:, 1],
                    data[mask][:, 2],
                    data[mask][:, 3],
                    data[mask][:, 4:7],
                    data[mask][:, 7:10]
                )
            else:
                self.scattered_data[i] = (
                    np.append(self.scattered_data[i][0], data[mask][:, 1], axis=0),
                    np.append(self.scattered_data[i][1], data[mask][:, 2], axis=0),
                    np.append(self.scattered_data[i][2], data[mask][:, 3], axis=0),
                    np.append(self.scattered_data[i][3], data[mask][:, 4:7], axis=0),
                    np.append(self.scattered_data[i][4], data[mask][:, 7:10], axis=0)
                )

        return self.scattered_data

    def getSputteredData(self) -> Optional[List[Optional[Tuple[np.ndarray, ...]]]]:
        """
        Returns the sputtered recoils (*_splst.dat file data)

        :return: List(
                    Tuple(
                        proj_number,
                        collisions,
                        energy,
                        cosines,
                        coordinates,
                        start_energy,
                        start_cosines,
                        start_coordinates
                    )

                    or None
                 )

                 or None
        """

        if len(self.sputtered_data) != len(self.elements):
            self.sputtered_data = [None] * len(self.elements)

        old_length = 0
        for sd in self.sputtered_data:
            if sd is not None:
                old_length += len(sd[0])

        data = self.genfromtxt('*_splst.dat', skip_header=2 + old_length)
        if data is None:
            if all([sd is None for sd in self.sputtered_data]):
                return
            return self.sputtered_data

        element, count = np.unique(data[:, 0], return_counts=True)

        for e in element:
            i = int(e) - 1
            if i not in range(len(self.elements)):
                continue
            mask = np.where(data[:, 0] == e)
            if self.sputtered_data[i] is None:
                self.sputtered_data[i] = (
                    data[mask][:, 1],
                    data[mask][:, 2],
                    data[mask][:, 3],
                    data[mask][:, 4:7],
                    data[mask][:, 7:10],
                    data[mask][:, 10],
                    data[mask][:, 11:14],
                    data[mask][:, 14:17]
                )
            else:
                self.sputtered_data[i] = (
                    np.append(self.sputtered_data[i][0], data[mask][:, 1], axis=0),
                    np.append(self.sputtered_data[i][1], data[mask][:, 2], axis=0),
                    np.append(self.sputtered_data[i][2], data[mask][:, 3], axis=0),
                    np.append(self.sputtered_data[i][3], data[mask][:, 4:7], axis=0),
                    np.append(self.sputtered_data[i][4], data[mask][:, 7:10], axis=0),
                    np.append(self.sputtered_data[i][5], data[mask][:, 10], axis=0),
                    np.append(self.sputtered_data[i][6], data[mask][:, 11:14], axis=0),
                    np.append(self.sputtered_data[i][7], data[mask][:, 14:17], axis=0)
                )

        return self.sputtered_data

    def getEnergyDepositionData(self) -> Optional[Tuple[np.ndarray, ...]]:
        """
        Returns the nuclear and electronic energy deposition (*_edepn.dat and *_edepe.dat file data)

        :return: Tuple(
                    depth,
                    nuclear_deposition,
                    electronic_deposition
                 )

                 or None
        """

        electronic_data = self.genfromtxt('*_edepn.dat', skip_header=2)
        nuclear_data = self.genfromtxt('*_edepe.dat', skip_header=2)
        if electronic_data is None or nuclear_data is None:
            return

        return electronic_data[:, 0], electronic_data[:, 1:], nuclear_data[:, 1:]

    def listParameters(self, save_folder: str, list_widget: ListWidget):
        """
        Builds ListWidget from files in save folder

        :param save_folder: folder for output files
        :param list_widget: empty ListWidget (extension of QListWidget) that should be written to
        """

        files = listdir(save_folder)
        tooltip_slow = '<b>Waring:</b> While the simulations is running, the refreshing of this plot will cause lag.'

        if not self.updateData(save_folder):
            list_widget.addItem(ListWidgetItem('Corrupted input files', bold=True))
            return

        # dynamic
        if self.is_dynamic:
            list_widget.addItem(
                ListWidgetItem('Results overview (only for finished static Simulations)', bold=True, grey=True))
            list_widget.addItemEmpty()

        # static
        elif getFileNameFromFileList('*_out.dat', files):
            list_widget.addItem(ListWidgetItem('Results overview:', bold=True))

            protocol_data = self.getProtocolData()
            if protocol_data is None:
                list_widget.addItem(ListWidgetItem('Corrupted input file', indent=1))
                return

            (sputter_yield,
             transmission_yield,
             reflection,
             transmission,
             implantation,
             energy_loss) = protocol_data

            transmission_happening = transmission_yield.any() or transmission.any()

            # sputtering yields
            list_widget.addItem(ListWidgetItem('Sputtering yields:', indent=1))

            for i, element in enumerate(self.elements):
                if sputter_yield[i]:
                    list_widget.addItem(ListWidgetItem(f'{element}\t{roundToStr(sputter_yield[i])} atoms/ion', indent=2))

            if not sputter_yield.any():
                list_widget.addItem(ListWidgetItem('No sputtering occurred.', indent=2))

            else:
                list_widget.addItemEmpty()
                list_widget.addItem(ListWidgetItem(f'Total\t{roundToStr(float(np.sum(sputter_yield)))} atoms/ion', indent=2))
                list_widget.addItem(ListWidgetItem(f'\t{roundToStr(float(np.sum(np.dot(sputter_yield, self.masses))))} amu/ion', indent=2))

            # transmission sputtering yields
            if transmission_happening:
                list_widget.addItemEmpty()
                list_widget.addItem(ListWidgetItem('Transmission sputtering yields:', indent=1))

                for i, element in enumerate(self.elements):
                    if transmission_yield[i]:
                        list_widget.addItem(ListWidgetItem(f'{element}\t{roundToStr(transmission_yield[i])} atoms/ion', indent=2))

                if not transmission_yield.any():
                    list_widget.addItem(ListWidgetItem('No transmission sputtering occurred.', indent=2))

                else:
                    list_widget.addItemEmpty()
                    list_widget.addItem(
                        ListWidgetItem(f'Total\t{roundToStr(float(np.sum(transmission_yield)))} atoms/ion', indent=2))
                    list_widget.addItem(
                        ListWidgetItem(f'\t{roundToStr(float(np.sum(np.dot(transmission_yield, self.masses))))} amu/ion', indent=2))

            # reflection coefficients
            list_widget.addItemEmpty()
            list_widget.addItem(ListWidgetItem('Reflection coefficients:', indent=1))

            for i, element in enumerate(self.elements):
                if reflection[i]:
                    list_widget.addItem(
                        ListWidgetItem(f'{element}\t{roundToStr(reflection[i])}', indent=2))

            if not np.sum(reflection):
                list_widget.addItem(ListWidgetItem('No projectile reflection occurred.', indent=2))

            # transmission coefficients
            if transmission_happening:
                list_widget.addItemEmpty()
                list_widget.addItem(ListWidgetItem('Transmission coefficients:', indent=1))

                for i, element in enumerate(self.elements):
                    if transmission[i]:
                        list_widget.addItem(
                            ListWidgetItem(f'{element}\t{roundToStr(transmission[i])}', indent=2))

                if not np.sum(transmission):
                    list_widget.addItem(ListWidgetItem('No transmission effects occurred.', indent=2))

            # implantation depth
            list_widget.addItemEmpty()
            list_widget.addItem(ListWidgetItem('Mean implantation depth:', indent=1))

            for i, element in enumerate(self.elements):
                if implantation[i]:
                    list_widget.addItem(ListWidgetItem(f'{element}\t{implantation[i]:.3f} Å', indent=2))

            if not np.sum(implantation):
                list_widget.addItem(ListWidgetItem('No projectile implantation occurred.', indent=2))

            # energy loss
            list_widget.addItemEmpty()
            list_widget.addItem(ListWidgetItem('Mean deposited energy by projectiles and recoils:',
                                               tooltip='Varies from the mean energy loss of SDTrimSP',
                                               indent=1))
            list_widget.addItem(ListWidgetItem('\tNuclear\tElectronic\tTotal', indent=2))

            for i, element in enumerate(self.elements):
                if energy_loss[i].any():
                    list_widget.addItem(ListWidgetItem(f'{element}\t{energy_loss[i, 1]:.3f} eV\t{energy_loss[i, 0]:.3f} eV\t{energy_loss[i, 2]:.3f} eV', indent=2))

            list_widget.addItemEmpty()

        # depth statistic
        energy_loss_exists = getFileNameFromFileList('*_edepn.dat', files)
        depth_deposited_exists = getFileNameFromFileList('*_rglst.dat', files)

        if not self.is_dynamic and (energy_loss_exists or depth_deposited_exists):
            list_widget.addItem(ListWidgetItem('Plot depth statistic:', bold=True))

            if depth_deposited_exists:
                list_widget.addItem(ListWidgetItem('Implantation depth',
                                                   indent=1,
                                                   function=self.plotFct,
                                                   function_args={'plot': self.plotImplantationDepth}))
            if energy_loss_exists:
                list_widget.addItem(ListWidgetItem('Projectile energy loss',
                                                   indent=1,
                                                   function=self.plotFct,
                                                   function_args={'plot': self.plotEnergyLossDepth}))
            if True:
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
                                               tooltip=tooltip_slow,
                                               function=self.plotFct,
                                               function_args={'plot': self.plotSputterYieldsTotalAmu}))
            list_widget.addItem(ListWidgetItem('Reflection coefficients',
                                               indent=1,
                                               tooltip=tooltip_slow,
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

        # reflected projectiles and sputtered recoils
        scatter_exist = getFileNameFromFileList('*_bslst.dat', files)
        sputter_exist = getFileNameFromFileList('*_splst.dat', files)

        if scatter_exist or sputter_exist:
            list_widget.addItem(ListWidgetItem('Plot secondary particle distributions:', bold=True))

            for i, element in enumerate(self.elements):
                if scatter_exist:
                    list_widget.addItem(ListWidgetItem(f'Backscattered {element} ions',
                                                       indent=1,
                                                       function=self.plotFct,
                                                       function_args={'plot': self.plotPolarScatter,
                                                                      'plot_args': {'element': i}}))
                if sputter_exist:
                    list_widget.addItem(ListWidgetItem(f'Backsputtered {element} recoil atoms',
                                                       indent=1,
                                                       function=self.plotFct,
                                                       function_args={'plot': self.plotPolarSputter,
                                                                      'plot_args': {'element': i}}))
            list_widget.addItemEmpty()

            if scatter_exist:
                list_widget.addItem(ListWidgetItem('Polar angles of backscattered ions',
                                                   indent=1,
                                                   function=self.plotFct,
                                                   function_args={'plot': self.plotParticlesPolarScatter}))
            if sputter_exist:
                list_widget.addItem(ListWidgetItem('Polar angles of backsputtered recoils',
                                                   indent=1,
                                                   function=self.plotFct,
                                                   function_args={'plot': self.plotParticlesPolarSputter}))
            list_widget.addItemEmpty()

            if scatter_exist:
                list_widget.addItem(ListWidgetItem('Energy of backscattered ions',
                                                   indent=1,
                                                   function=self.plotFct,
                                                   function_args={'plot': self.plotEnergyScatter}))
            if sputter_exist:
                list_widget.addItem(ListWidgetItem('Energy of backsputtered recoils',
                                                   indent=1,
                                                   function=self.plotFct,
                                                   function_args={'plot': self.plotEnergySputter}))
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

    def plotImplantationDepth(self, n_bins: int = 40) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return projectile stops over depth"""

        deposited_data = self.getDepositedData()

        mpl_settings = MplCanvasSettings()
        if deposited_data is None:
            mpl_settings = MplCanvasSettings()
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        data = []
        plot_labels = []
        flag_plots = False

        for i, element in enumerate(self.elements):
            plot_data = deposited_data[i]

            if plot_data is None:
                continue

            (proj_number,
             collisions,
             coordinates) = plot_data

            hist, bin_edges = np.histogram(coordinates[:, 0], bins=n_bins, density=True)
            bin_edges = (bin_edges[1:] + bin_edges[:-1]) / 2

            mpl_settings.plot(bin_edges,
                              hist,
                              label=element,
                              linewidth=self.line_width,
                              color=self.colors[i])
            data.append(bin_edges)
            data.append(hist)
            plot_labels.append(f'Depth ({element}) [Angs]')
            plot_labels.append(f'Stopping probability ({element}) [1/Angs]')
            flag_plots = True

        if not flag_plots:
            mpl_settings = MplCanvasSettings()
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        mpl_settings.set_xlim(xmin=0.0)
        mpl_settings.set_ylim(ymin=0.0)
        mpl_settings.legend()
        mpl_settings.set_ylabel('Stopping Probability [1/Å]')
        mpl_settings.set_xlabel('Depth [Å]')

        return (data, plot_labels), mpl_settings

    def plotEnergyLossDepth(self) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return projectile energy loss over depth"""

        depth_data = self.getEnergyDepositionData()

        if depth_data is None:
            mpl_settings = MplCanvasSettings()
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        (depth,
         nuclear_deposition,
         electronic_deposition) = depth_data

        mpl_settings = MplCanvasSettings()

        data = []
        plot_labels = []
        flag_plots = False

        beam = [item['ircp'] for item in self.initial_protocol['ir']]

        for i, element in enumerate(self.elements):
            if i + 1 not in beam:
                continue

            mpl_settings.plot(depth,
                              nuclear_deposition[:, i],
                              label=f'{element} (nuclear)',
                              linestyle='--',
                              linewidth=self.line_width,
                              color=self.colors[i])
            mpl_settings.plot(depth,
                              electronic_deposition[:, i],
                              label=f'{element} (electronic)',
                              linestyle=':',
                              linewidth=self.line_width,
                              color=self.colors[i])
            total_deposition = nuclear_deposition[:, i] + electronic_deposition[:, i]
            mpl_settings.plot(depth,
                              total_deposition,
                              label=f'{element} (total)',
                              linestyle='-',
                              linewidth=self.line_width,
                              color=self.colors[i])
            data.append(depth)
            data.append(nuclear_deposition[:, i])
            data.append(electronic_deposition[:, i])
            data.append(total_deposition)
            plot_labels.append(f'Depth ({element}) [Angs]')
            plot_labels.append(f'Energy Loss (normalized) ({element}, nuclear) [eV/Angs]')
            plot_labels.append(f'Energy Loss (normalized) ({element}, electronic) [eV/Angs]')
            plot_labels.append(f'Energy Loss (normalized) ({element}, total) [eV/Angs]')
            flag_plots = True

        if not flag_plots:
            mpl_settings = MplCanvasSettings()
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        mpl_settings.set_ylim(ymin=0.0)
        mpl_settings.set_xlim(xmin=0.0)
        mpl_settings.legend()
        mpl_settings.set_ylabel('Energy Loss (normalized) [eV/Å]')
        mpl_settings.set_xlabel('Depth [Å]')

        return (data, plot_labels), mpl_settings

    def plotVacanciesDepth(self) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return vacancies over depth"""

        depth_data = self.getDepthProfile()

        if depth_data is None:
            mpl_settings = MplCanvasSettings()
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        mpl_settings = MplCanvasSettings()

        (swelling_shrinking,
         partial_fluences,
         reemitted,
         layer_depth,
         atomic_density,
         interstitial,
         vacancies,
         atomic_fractions) = depth_data

        depth_delta = layer_depth[0, 0]
        if layer_depth.size > 1:
            depth_delta = layer_depth[0, 1] - layer_depth[0, 0]

        mpl_settings.plot(layer_depth[0, :],
                          vacancies[0, :] / depth_delta,
                          label='Total',
                          linewidth=self.line_width,
                          color=self.first_color)

        mpl_settings.set_ylim(ymin=0.0)
        mpl_settings.set_xlim(xmin=0.0)
        mpl_settings.legend()
        mpl_settings.set_ylabel('Vacancies [1/Å/ion]')
        mpl_settings.set_xlabel('Depth [Å]')
        mpl_settings.set_title(f'Total Vacancies: {np.round(np.sum(vacancies[0, :]) / len(self.initial_protocol["ir"]), 2)} / Ion')

        return ([layer_depth[0, :], vacancies[0, :]], ['Depth (Total) [Angs]', 'Vacancies (Total) [1/Angs/ion]']), mpl_settings

    def plotSputterYields(self) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return sputter yields"""

        yield_data = self.getSputterYieldData()

        if yield_data is None:
            mpl_settings = MplCanvasSettings()
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        (fluence,
         sputtered_yield) = yield_data

        mpl_settings = MplCanvasSettings()

        data = [fluence]
        plot_labels = ['Fluence[10^20 ions/m^2]']

        for i, element in enumerate(self.elements):
            mpl_settings.plot(fluence,
                              sputtered_yield[:, i],
                              label=element,
                              color=self.colors[i])

            data.append(sputtered_yield[:, i])
            plot_labels.append(element)

        mpl_settings.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.set_ylabel('Sputtering Yield Y [atoms/ion]')
        mpl_settings.set_ylim(ymin=0.)
        mpl_settings.legend()

        return (data, plot_labels), mpl_settings

    def plotSputterYieldsTotal(self) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return total sputter yields"""

        yield_data = self.getSputterYieldData()

        if yield_data is None:
            mpl_settings = MplCanvasSettings()
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        (fluence,
         sputtered_yield) = yield_data

        mpl_settings = MplCanvasSettings()

        mpl_settings.plot(fluence,
                          np.sum(sputtered_yield[:, :], axis=1),
                          color=self.first_color)

        mpl_settings.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.set_ylabel('Sputtering Yield Y [atoms/ion]')
        mpl_settings.set_ylim(ymin=0.)

        return ([fluence, np.sum(sputtered_yield[:, :], axis=1)], ['Fluence[10^20 ions/m^2]', 'Y [atoms/ion]']), mpl_settings

    def plotSputterYieldsTotalAmu(self) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return total sputter yields amu"""
        # net_mass_removal = sum_{elements} (element.mass * [element.sputtered + element.reemitted - element.deposited / element.incoming])

        yield_data = self.getSputterYieldData()
        reemitted_data = self.getReemittedData()
        deposited_data = self.getDepositedData()
        initial_data = self.initial_protocol

        if None in [yield_data, deposited_data, initial_data]:
            mpl_settings = MplCanvasSettings()
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        mpl_settings = MplCanvasSettings()

        (fluence_yield,
         sputtered_yield) = yield_data

        if reemitted_data is not None:
            (fluence_reemitted,
             reemitted_yield) = reemitted_data

            if fluence_yield.size + 1 != fluence_reemitted.size:
                mpl_settings = MplCanvasSettings()
                mpl_settings.set_title('No data found')
                return None, mpl_settings

            reemitted_yield = reemitted_yield[1:, :] - reemitted_yield[:-1, :]

        else:
            reemitted_yield = np.zeros(sputtered_yield.shape)

        particles_per_step = initial_data['idout']

        fluence_hist_bins = np.arange(0, particles_per_step * fluence_yield.size + 1, particles_per_step)
        yield_amu = np.zeros(fluence_yield.size)

        for i, (element, deposited) in enumerate(zip(self.elements, deposited_data)):
            sputter = sputtered_yield[:, i]
            reemitted = reemitted_yield[:, i]

            summe = sputter + reemitted

            if deposited is not None:
                (proj_number_deposited,
                 collisions_deposited,
                 coordinates_deposited) = deposited

                hist_deposited, _ = np.histogram(proj_number_deposited - 1, fluence_hist_bins)

                summe -= hist_deposited * initial_data['flct'] / initial_data['nh']

            yield_amu += self.masses[i] * summe

        mpl_settings.plot(fluence_yield,
                          yield_amu,
                          color=self.first_color)

        mpl_settings.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.set_ylabel('Net Mass Removal y [amu/ion]')

        return ([fluence_yield, yield_amu], ['Fluence[10^20 ions/m^2]', 'y [amu/ion]']), mpl_settings

    def plotReflectionCoefficients(self) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return reflection coefficients"""

        scattered_data = self.getScatteredData()
        incident_data = self.getIncidentData()
        initial_data = self.initial_protocol

        if None in [incident_data, initial_data]:
            mpl_settings = MplCanvasSettings()
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        mpl_settings = MplCanvasSettings()

        particles = initial_data['nh']
        particles_per_step = initial_data['idout']
        fluence_total = initial_data['flct']
        max_incident_proj_nbr = 0

        # get maximum incident projectile number to calculate maximum fluence
        for incident in incident_data:
            if incident is None:
                continue

            (proj_number_incident,
             energy_incident,
             coordinates_incident) = incident

            max_incident_proj_nbr = max(np.max(proj_number_incident), max_incident_proj_nbr)

        fluence_hist_bins = np.arange(0, max_incident_proj_nbr + 1, particles_per_step)
        fluence = fluence_total * 0.5 / particles * (fluence_hist_bins[1:] + fluence_hist_bins[:-1])
        reflected = np.zeros((fluence_hist_bins.size - 1, len(self.elements)))

        if scattered_data is not None:
            for i, (element, scatter, incident) in enumerate(zip(self.elements, scattered_data, incident_data)):
                if None in [scatter, incident]:
                    continue

                (proj_number_scatter,
                 collisions_scatter,
                 energy_scatter,
                 cosines_scatter,
                 coordinates_scatter) = scatter

                (proj_number_incident,
                 energy_incident,
                 coordinates_incident) = incident

                hist_scatter, _ = np.histogram(proj_number_scatter, fluence_hist_bins)
                hist_incident, _ = np.histogram(proj_number_incident, fluence_hist_bins)

                reflected[:, i] = hist_scatter / hist_incident

        data = [fluence]
        plot_labels = ['Fluence[10^20 ions/m^2]']

        for i, element in enumerate(self.elements):
            mpl_settings.plot(fluence,
                              reflected[:, i],
                              label=element,
                              color=self.colors[i])

            data.append(reflected[:, i])
            plot_labels.append(element)

        mpl_settings.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.set_ylabel('Reflection Coefficient R [atoms/ion]')
        mpl_settings.set_ylim(ymin=0., ymax=1.)
        mpl_settings.legend()

        return (data, plot_labels), mpl_settings

    def plotReemissionCoefficients(self) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return reemission coefficients"""

        reemitted_data = self.getReemittedData()
        initial_data = self.initial_protocol

        if None in [reemitted_data, initial_data]:
            mpl_settings = MplCanvasSettings()
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        (fluence,
         reemitted) = reemitted_data

        fluence = 0.5 * (fluence[:-1] + fluence[1:])
        reemitted = reemitted[1:, :] - reemitted[:-1, :]
        reemitted *= initial_data['nh'] / initial_data['idout'] / initial_data['flct']

        mpl_settings = MplCanvasSettings()

        data = [fluence]
        plot_labels = ['Fluence[10^20 ions/m^2]']

        for i, element in enumerate(self.elements):
            mpl_settings.plot(fluence,
                              reemitted[:, i],
                              label=element,
                              color=self.colors[i])

            data.append(reemitted[:, i])
            plot_labels.append(element)

        mpl_settings.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.set_ylabel('Reemission Coefficient [atoms/ion]')
        mpl_settings.set_ylim(ymin=0., ymax=1.)
        mpl_settings.legend()

        return (data, plot_labels), mpl_settings

    def plotSurfaceConcentrations(self) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return surface concentrations"""

        surface_data = self.getSurfaceCompositionData()

        if surface_data is None:
            mpl_settings = MplCanvasSettings()
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        (fluence,
         surface_fractions) = surface_data

        mpl_settings = MplCanvasSettings()

        data = [fluence]
        plot_labels = ['Fluence[10^20 ions/m^2]']

        for i, element in enumerate(self.elements):
            mpl_settings.plot(fluence,
                              surface_fractions[:, i],
                              label=element,
                              color=self.colors[i])

            data.append(surface_fractions[:, i])
            plot_labels.append(element)

        mpl_settings.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.set_ylabel('Surface Concentration')
        mpl_settings.set_ylim(ymin=0., ymax=1.)
        mpl_settings.legend()

        return (data, plot_labels), mpl_settings

    def plotSurfaceLevel(self) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return surface levels"""

        surface_data = self.getSwellingShrinkingData()

        if surface_data is None:
            mpl_settings = MplCanvasSettings()
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        (fluence,
         surface) = surface_data

        mpl_settings = MplCanvasSettings()

        mpl_settings.plot(fluence,
                          surface,
                          color=self.first_color)

        mpl_settings.set_xlabel('Fluence [$10^{20}$ ions/m$^2$]')
        mpl_settings.set_ylabel('Surface Erosion [Å]')

        return ([fluence, surface], ['Fluence[10^20 ions/m^2]', 'Surface Erosion [Angs]']), mpl_settings

    def updateDepthConcentration(self, set_to_max: bool = False) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Updates the plot and data of the depth concentration"""

        depth_data = self.getDepthProfile()

        if depth_data is None:
            mpl_settings = MplCanvasSettings()
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        (swelling_shrinking,
         partial_fluences,
         reemitted,
         layer_depth,
         atomic_density,
         interstitial,
         vacancies,
         atomic_fractions) = depth_data

        max_hist = swelling_shrinking.shape[0] - 1
        if max_hist < 0:
            mpl_settings = MplCanvasSettings()
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        self.fluence_array = np.sum(partial_fluences, axis=1)
        self.depth_array = layer_depth
        self.conc_array = atomic_fractions

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

    def plotDepthConcentration(self, history_step: int = 0) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return the depth concentration"""

        if self.depth_array is None or self.conc_array is None or self.fluence_array is None:
            mpl_settings = MplCanvasSettings()
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        mpl_settings = MplCanvasSettings()

        data = [self.depth_array[history_step, :]]
        plot_labels = ['Depth [Angs]']

        for i, element in enumerate(self.elements):
            mpl_settings.plot(self.depth_array[history_step, :],
                              self.conc_array[i, history_step, :],
                              label=element,
                              linewidth=2,
                              color=self.colors[i])

            data.append(self.conc_array[i, history_step, :])
            plot_labels.append(element)

        mpl_settings.set_ylim(ymin=0.0, ymax=1.0)
        mpl_settings.legend()
        mpl_settings.set_xlabel('Depth [Å]')
        mpl_settings.set_ylabel('Concentrations')

        mpl_settings.set_title(f'Fluence: {self.fluence_array[history_step]:.2f}$\\times 10^{{20}}$/m$^2$')

        return (data, plot_labels), mpl_settings

    @staticmethod
    def plotPolar(cosines: np.array, mpl_settings: MplCanvasSettings, n_bins: int = 30) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return backscattered/backsputtered particles of element"""

        data = []
        plot_labels = []

        phi = np.arctan2(cosines[:, 2], -cosines[:, 1])
        theta = np.arccos(-cosines[:, 0])

        lowerlimit = 0

        spacing = np.arange(lowerlimit, n_bins + 1)
        rbins = np.arccos(1 - spacing / n_bins)
        abins = np.linspace(-np.pi, np.pi, 4 * n_bins)

        hist, _, _ = np.histogram2d(phi, theta, bins=(abins, rbins))
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

        return (data, plot_labels), mpl_settings

    def plotPolarScatter(self, element: int, n_bins: int = 30) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return backscattered particles of element"""

        mpl_settings = MplCanvasSettings()
        mpl_settings.set_projection('polar')

        if element not in range(len(self.elements)):
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        scattered_data = self.getScatteredData()

        if scattered_data is None:
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        plot_data = scattered_data[element]
        if plot_data is None:
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        (proj_number,
         collisions,
         energy,
         cosines,
         coordinates) = plot_data

        result = self.plotPolar(cosines, mpl_settings, n_bins)

        if result is None:
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        data, mpl_settings = result

        mpl_settings.set_title(f'Angular distribution of backscattered {self.elements[element]} projectiles')

        return data, mpl_settings

    def plotPolarSputter(self, element: int, n_bins: int = 30) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return backsputtered recoils of element"""

        mpl_settings = MplCanvasSettings()
        mpl_settings.set_projection('polar')

        if element not in range(len(self.elements)):
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        scattered_data = self.getSputteredData()

        if scattered_data is None:
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        plot_data = scattered_data[element]
        if plot_data is None:
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        (proj_number,
         collisions,
         energy,
         cosines,
         coordinates,
         start_energy,
         start_cosines,
         start_coordinates) = plot_data

        result = self.plotPolar(cosines, mpl_settings, n_bins)

        if result is None:
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        data, mpl_settings = result

        mpl_settings.set_title(f'Angular distribution of backsputtered {self.elements[element]} recoil atoms')

        return data, mpl_settings

    def plotEnergyScatter(self) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return energy of backscattered projectiles"""

        scattered_data = self.getScatteredData()

        if scattered_data is None:
            mpl_settings = MplCanvasSettings()
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        data = []
        plot_labels = []

        mpl_settings = MplCanvasSettings()

        plot_counter = 0
        for i, element in enumerate(self.elements):
            plot_data = scattered_data[i]
            if plot_data is None:
                continue

            (proj_number,
             collisions,
             energy,
             cosines,
             coordinates) = plot_data

            hist, bin_edges = np.histogram(energy, density=True, bins=100)
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
            mpl_settings = MplCanvasSettings()
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        mpl_settings.set_xlabel('Energy [eV]')
        mpl_settings.set_ylabel('Reflected ions [1/eV]')
        mpl_settings.set_ylim(ymin=0.)
        mpl_settings.set_xlim(xmin=0.)
        mpl_settings.legend()

        return (data, plot_labels), mpl_settings

    def plotEnergySputter(self) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return energy of backscattered projectiles"""

        sputtered_data = self.getSputteredData()

        if sputtered_data is None:
            mpl_settings = MplCanvasSettings()
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        data = []
        plot_labels = []

        mpl_settings = MplCanvasSettings()

        plot_counter = 0
        for i, element in enumerate(self.elements):
            plot_data = sputtered_data[i]
            if plot_data is None:
                continue

            (proj_number,
             collisions,
             energy,
             cosines,
             coordinates,
             start_energy,
             start_cosines,
             start_coordinates) = plot_data

            hist, bin_edges = np.histogram(energy, density=True, bins=int(np.max(energy) / 0.2))
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
            mpl_settings = MplCanvasSettings()
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        mpl_settings.set_xlabel('Energy [eV]')
        mpl_settings.set_ylabel('Sputtered atoms [1/eV]')
        mpl_settings.set_ylim(ymin=0.)
        mpl_settings.set_xlim(xmin=0.)
        mpl_settings.legend()

        return (data, plot_labels), mpl_settings

    def plotParticlesPolar(self, cosines_array: List[np.array], mpl_settings: MplCanvasSettings) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return data of backscattered/backsputtered particles"""

        data = []
        plot_labels = []

        plot_counter = 0
        for i, element in enumerate(self.elements):
            plot_data = cosines_array[i]
            if plot_data is None:
                continue
            cos_polar = -plot_data[:, 0]
            polar_angles = np.arccos(np.asarray(cos_polar)) * np.sign(-plot_data[:, 1])

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
            mpl_settings = MplCanvasSettings()
            mpl_settings.set_title('No data found')
            return None, mpl_settings

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

    def plotParticlesPolarScatter(self) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return data of backscattered projectiles"""

        scattered_data = self.getScatteredData()

        mpl_settings = MplCanvasSettings()
        mpl_settings.set_projection('polar')

        if scattered_data is None:
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        cosines_array = []
        for data in scattered_data:
            if data is None:
                cosines_array.append(None)
                continue
            (proj_number,
             collisions,
             energy,
             cosines,
             coordinates) = data
            cosines_array.append(cosines)

        result = self.plotParticlesPolar(cosines_array, mpl_settings)

        if result is None:
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        data, mpl_settings = result

        mpl_settings.set_title('Backscattered projectiles over polar angle')

        return data, mpl_settings

    def plotParticlesPolarSputter(self) -> Optional[Tuple[Optional[Tuple[list, list]], MplCanvasSettings]]:
        """Plot and return data of backsputtered projectiles"""

        sputtered_data = self.getSputteredData()

        mpl_settings = MplCanvasSettings()
        mpl_settings.set_projection('polar')

        if sputtered_data is None:
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        cosines_array = []
        for data in sputtered_data:
            if data is None:
                cosines_array.append(None)
                continue
            (proj_number,
             collisions,
             energy,
             cosines,
             coordinates,
             start_energy,
             start_cosines,
             start_coordinates) = data
            cosines_array.append(cosines)

        result = self.plotParticlesPolar(cosines_array, mpl_settings)

        if result is None:
            mpl_settings.set_title('No data found')
            return None, mpl_settings

        data, mpl_settings = result

        mpl_settings.set_title('Sputtered recoils over polar angle')

        return data, mpl_settings
