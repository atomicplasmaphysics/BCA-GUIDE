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


from typing import Union, Tuple, Callable, Optional, List
from time import time
from threading import Thread, Lock

import numpy as np
import matplotlib.pyplot as plt

from PyQt5.QtCore import pyqtSignal, Qt, QObject
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QApplication

from Utility.Layouts import ListWidget, MplCanvas
from Utility.Indexing import RepeatingList, ElementList

from TableWidgets.CompTable import CompRow
from Containers.Element import Element, Elements

from Containers.Arguments import GeneralBeamArguments, GeneralTargetArguments, GeneralArguments, SimulationArguments, RowArguments


class GeneralSettings:
    """
    General settings class, that will be inherited by other GeneralSetting classes
    """

    settingsChanged = pyqtSignal(dict)
    contentChanged = pyqtSignal()

    def __init__(self):
        super().__init__()

    def emit(self, value_dict: dict = None):
        """
        Emits settingsChanged pyqtSignal

        :param value_dict: dictionary to emit
        """

        if value_dict is None:
            return
        self.settingsChanged.emit(value_dict)

    def edited(self):
        """Emits contentChanged pyqtSignal"""

        self.contentChanged.emit()

    def receive(self, value_dict: dict):
        """
        Receives other settingsChanged pyqtSignal -> dict

        :param value_dict: dictionary to be received
        """

        pass

    @staticmethod
    def reset():
        """Resets all input fields"""
        pass

    @staticmethod
    def getArguments():
        """Returns container of parameters for settings"""
        raise NotImplementedError

    @staticmethod
    def loadArguments(arguments: SimulationArguments) -> list:
        """Loads <SimulationArguments> container. Returns list of not loadable parameters (default used)"""
        return []


class HlGeneralBeamSettings(GeneralSettings, QHBoxLayout):
    """
    QHBoxLayout for general beam settings

    :param version: version of simulation
    """

    def __init__(self, version: str):
        super().__init__()
        self.version = version

    @staticmethod
    def getArguments() -> GeneralBeamArguments:
        """Returns <GeneralBeamArguments> container of parameters for general beam settings"""

        return GeneralBeamArguments()


class HlGeneralTargetSettings(GeneralSettings, QHBoxLayout):
    """
    QHBoxLayout for general target settings

    :param version: version of simulation
    """

    def __init__(self, version: str):
        super().__init__()
        self.version = version

    @staticmethod
    def getArguments() -> GeneralTargetArguments:
        """Returns <GeneralTargetArguments> container of parameters for general target settings"""

        return GeneralTargetArguments()


class VlGeneralSimulationSettings(GeneralSettings, QVBoxLayout):
    """
    QVBoxLayout for general simulation settings

    :param version: version of simulation
    """

    def __init__(self, version: str):
        super().__init__()
        self.version = version

    @staticmethod
    def getArguments() -> GeneralArguments:
        """Returns <GeneralArguments> container of parameters for general simulation settings"""

        return GeneralArguments(title='SIMULATION TITLE MISSING')


class CompRowBeamSettings(CompRow):
    """
    CompRow for beam

    :param version: version of simulation
    """

    # list of CustomRowField() elements
    """
    Example:
    rowFields = [
        CustomRowField(                 # First Column
            unique='unique_specifier',  # Unique specifier to link beam and target tables and for reference in input file
            label='label_title',        # Title of column header
            tooltip='tooltip'           # Tooltip for column header (optional)
        ),
        CustomRowField(...),            # Second Column
        ...
    ]
    """
    rowFields = []

    def __init__(self, *args, version: str = '', **kwargs):
        super().__init__(*args, **kwargs)
        self.version = version

        # extend list of widgets
        """
        Example:
        self.rowWidgets += [
            QSpinBox(),
            QDoubleSpinBox(),
            QComboBox(),
            ...
        ]
        """
        self.row_widgets += []

    def getArguments(self) -> RowArguments:
        """Returns <RowArguments> container of parameters for row"""

        return super().getArguments()

    def setArguments(self, arguments: RowArguments, general_arguments: GeneralArguments):
        """
        Sets <RowArguments> container of parameters for row

        :param arguments: container of <RowArguments>
        :param general_arguments: container of <GeneralArguments>
        """

        super().setArguments(arguments, general_arguments)


class CompRowTargetSettings(CompRow):
    """
    CompRow for target

    :param version: version of simulation
    """

    # list of CustomRowField() elements
    """
    Example:
    rowFields = [
        CustomRowField(                 # First Column
            unique='unique_specifier',  # Unique specifier to link beam and target tables and for reference in input file
            label='label_title',        # Title of column header
            tooltip='tooltip'           # Tooltip for column header (optional)
        ),
        CustomRowField(...),            # Second Column
        ...
    ]
    """
    rowFields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # extend list of widgets
        """
        Example:
        self.rowWidgets += [
            QSpinBox(),
            QDoubleSpinBox(),
            QComboBox(),
            ...
        ]
        """
        self.row_widgets += []

    def getArguments(self) -> RowArguments:
        """Returns <RowArguments> container of parameters for row"""

        return super().getArguments()

    def setArguments(self, arguments: RowArguments, general_arguments: SimulationArguments):
        """
        Sets <RowArguments> container of parameters for row

        :param arguments: container of <RowArguments>
        :param general_arguments: container of <GeneralArguments>
        """

        super().setArguments(arguments, general_arguments)


class GeneralElementData(Elements):
    """
    Simulation supported elements and element specific data
    """

    # default element dict from SDTrimSP v6.01
    """
    Example:
    elementList = [
        Element(
            # required
            symbol=<str>
            name=<dict>
            atomic_nr=<int>
            period=<int>
            group=<int>
            atomic_mass=<float>
            atomic_density=<float>
            
            # optional
            mass_density=<float>
            periodic_table_symbol=<str>
            surface_binding_energy=<float>
            displacement_energy=<float>
            cutoff_energy=<float>
            dissociation_heat=<float>
            melt_enthalpy=<float>
            vaporization_energy=<float>
            formation_enthalpy=<float>
        ),
        Element(...),
        ...
    ]
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
            atomic_mass=1.007825,
            atomic_density=0.04231,
            surface_binding_energy=1.1,
            displacement_energy=5.0
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
            atomic_mass=4.002603,
            atomic_density=0.01878,
            surface_binding_energy=0.0,
            displacement_energy=5.0
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
            atomic_mass=6.941,
            atomic_density=0.04633,
            surface_binding_energy=1.64,
            displacement_energy=25.0
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
            atomic_mass=9.012182,
            atomic_density=0.12347,
            surface_binding_energy=3.31,
            displacement_energy=15.0
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
            atomic_density=0.1309,
            surface_binding_energy=5.76,
            displacement_energy=25.0
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
            atomic_density=0.11331,
            surface_binding_energy=7.37,
            displacement_energy=25.0
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
            atomic_mass=14.00674,
            atomic_density=0.03784,
            surface_binding_energy=4.9,
            displacement_energy=25.0
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
            atomic_mass=15.9994,
            atomic_density=0.04291,
            surface_binding_energy=1.0,
            displacement_energy=5.0
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
            atomic_mass=18.998403,
            atomic_density=0.04796,
            surface_binding_energy=0.82,
            displacement_energy=25.0
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
            atomic_mass=20.1797,
            atomic_density=0.03603,
            surface_binding_energy=0.0,
            displacement_energy=5.0
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
            atomic_mass=22.989768,
            atomic_density=0.02544,
            surface_binding_energy=1.11,
            displacement_energy=25.0
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
            atomic_mass=24.305,
            atomic_density=0.04306,
            surface_binding_energy=1.51,
            displacement_energy=10.0
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
            atomic_mass=26.981539,
            atomic_density=0.06022,
            surface_binding_energy=3.42,
            displacement_energy=16.0
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
            atomic_mass=28.08553,
            atomic_density=0.04994,
            surface_binding_energy=4.72,
            displacement_energy=13.0
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
            atomic_mass=30.973761,
            atomic_density=0.03544,
            surface_binding_energy=3.27,
            displacement_energy=25.0
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
            atomic_mass=32.066,
            atomic_density=0.03888,
            surface_binding_energy=2.85,
            displacement_energy=25.0
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
            atomic_mass=35.4527,
            atomic_density=0.0256,
            surface_binding_energy=1.0,
            displacement_energy=25.0
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
            atomic_density=0.0208,
            surface_binding_energy=0.0,
            displacement_energy=5.0
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
            atomic_mass=39.0983,
            atomic_density=0.01328,
            surface_binding_energy=0.93,
            displacement_energy=25.0
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
            atomic_mass=40.078,
            atomic_density=0.02314,
            surface_binding_energy=2.39,
            displacement_energy=25.0
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
            atomic_mass=44.95591,
            atomic_density=0.04004,
            surface_binding_energy=3.9,
            displacement_energy=25.0
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
            atomic_mass=47.867,
            atomic_density=0.05712,
            surface_binding_energy=4.84,
            displacement_energy=19.0
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
            atomic_mass=50.9415,
            atomic_density=0.07223,
            surface_binding_energy=5.33,
            displacement_energy=26.0
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
            atomic_mass=51.9961,
            atomic_density=0.08327,
            surface_binding_energy=5.22,
            displacement_energy=28.0
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
            atomic_mass=54.938049,
            atomic_density=0.08155,
            surface_binding_energy=2.92,
            displacement_energy=25.0
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
            atomic_density=0.08491,
            surface_binding_energy=4.28,
            displacement_energy=17.0
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
            atomic_mass=58.9332,
            atomic_density=0.09084,
            surface_binding_energy=4.39,
            displacement_energy=22.0
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
            atomic_mass=58.6934,
            atomic_density=0.09134,
            surface_binding_energy=4.44,
            displacement_energy=23.0
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
            atomic_mass=63.546,
            atomic_density=0.08486,
            surface_binding_energy=3.2,
            displacement_energy=19.0
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
            atomic_mass=65.39,
            atomic_density=0.06569,
            surface_binding_energy=1.35,
            displacement_energy=14.0
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
            atomic_mass=69.723,
            atomic_density=0.05099,
            surface_binding_energy=2.8,
            displacement_energy=12.0
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
            atomic_mass=72.61,
            atomic_density=0.04415,
            surface_binding_energy=3.85,
            displacement_energy=15.0
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
            atomic_mass=74.9216,
            atomic_density=0.04603,
            surface_binding_energy=3.12,
            displacement_energy=25.0
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
            atomic_density=0.03653,
            surface_binding_energy=2.2,
            displacement_energy=25.0
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
            atomic_mass=79.904,
            atomic_density=0.02353,
            surface_binding_energy=1.16,
            displacement_energy=25.0
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
            atomic_density=0.01734,
            surface_binding_energy=0.0,
            displacement_energy=5.0
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
            atomic_mass=85.4678,
            atomic_density=0.01078,
            surface_binding_energy=0.85,
            displacement_energy=25.0
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
            atomic_density=0.01835,
            surface_binding_energy=1.7,
            displacement_energy=25.0
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
            atomic_mass=88.90585,
            atomic_density=0.03029,
            surface_binding_energy=4.4,
            displacement_energy=25.0
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
            atomic_mass=91.224,
            atomic_density=0.04296,
            surface_binding_energy=6.3,
            displacement_energy=21.0
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
            atomic_mass=92.90638,
            atomic_density=0.05562,
            surface_binding_energy=7.47,
            displacement_energy=28.0
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
            atomic_density=0.06453,
            surface_binding_energy=6.81,
            displacement_energy=33.0
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
            atomic_mass=97.907215,
            atomic_density=0.07073,
            surface_binding_energy=6.81,
            displacement_energy=25.0
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
            atomic_density=0.07966,
            surface_binding_energy=6.73,
            displacement_energy=25.0
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
            atomic_mass=102.9055,
            atomic_density=0.07262,
            surface_binding_energy=5.72,
            displacement_energy=25.0
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
            atomic_mass=106.42,
            atomic_density=0.06802,
            surface_binding_energy=3.91,
            displacement_energy=26.0
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
            atomic_mass=107.8682,
            atomic_density=0.05862,
            surface_binding_energy=2.95,
            displacement_energy=23.0
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
            atomic_mass=112.411,
            atomic_density=0.04634,
            surface_binding_energy=1.16,
            displacement_energy=19.0
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
            atomic_mass=114.818,
            atomic_density=0.03834,
            surface_binding_energy=2.52,
            displacement_energy=15.0
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
            atomic_mass=118.71,
            atomic_density=0.03698,
            surface_binding_energy=3.15,
            displacement_energy=22.0
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
            atomic_mass=121.757,
            atomic_density=0.03306,
            surface_binding_energy=2.74,
            displacement_energy=25.0
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
            atomic_density=0.0295,
            surface_binding_energy=2.04,
            displacement_energy=25.0
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
            atomic_mass=126.90447,
            atomic_density=0.02344,
            surface_binding_energy=1.11,
            displacement_energy=25.0
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
            atomic_mass=131.29,
            atomic_density=0.01348,
            surface_binding_energy=0.0,
            displacement_energy=5.0
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
            atomic_mass=132.90544,
            atomic_density=0.00851,
            surface_binding_energy=0.8,
            displacement_energy=15.0
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
            atomic_mass=137.327,
            atomic_density=0.01587,
            surface_binding_energy=1.89,
            displacement_energy=25.0
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
            atomic_mass=138.9055,
            atomic_density=0.02671,
            surface_binding_energy=4.47,
            displacement_energy=25.0
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
            atomic_mass=140.115,
            atomic_density=0.02911,
            surface_binding_energy=4.39,
            displacement_energy=25.0
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
            atomic_mass=140.90765,
            atomic_density=0.02767,
            surface_binding_energy=3.7,
            displacement_energy=25.0
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
            atomic_density=0.02924,
            surface_binding_energy=3.41,
            displacement_energy=25.0
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
            atomic_mass=145.9127,
            atomic_density=0.0298,
            surface_binding_energy=3.19,
            displacement_energy=25.0
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
            atomic_mass=150.36,
            atomic_density=0.03018,
            surface_binding_energy=2.14,
            displacement_energy=25.0
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
            atomic_mass=151.965,
            atomic_density=0.02078,
            surface_binding_energy=1.83,
            displacement_energy=25.0
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
            atomic_density=0.03024,
            surface_binding_energy=4.14,
            displacement_energy=25.0
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
            atomic_mass=158.92534,
            atomic_density=0.03127,
            surface_binding_energy=4.05,
            displacement_energy=25.0
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
            atomic_density=0.03172,
            surface_binding_energy=3.04,
            displacement_energy=25.0
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
            atomic_mass=164.93032,
            atomic_density=0.03211,
            surface_binding_energy=3.14,
            displacement_energy=25.0
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
            atomic_density=0.03264,
            surface_binding_energy=3.3,
            displacement_energy=25.0
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
            atomic_mass=168.93421,
            atomic_density=0.03323,
            surface_binding_energy=2.42,
            displacement_energy=25.0
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
            atomic_density=0.02424,
            surface_binding_energy=1.58,
            displacement_energy=25.0
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
            atomic_mass=174.967,
            atomic_density=0.03387,
            surface_binding_energy=4.43,
            displacement_energy=17.0
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
            atomic_density=0.04491,
            surface_binding_energy=6.41,
            displacement_energy=25.0
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
            atomic_mass=180.9479,
            atomic_density=0.05543,
            surface_binding_energy=8.1,
            displacement_energy=32.0
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
            atomic_mass=183.84,
            atomic_density=0.06306,
            surface_binding_energy=8.79,
            displacement_energy=38.0
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
            atomic_mass=186.207,
            atomic_density=0.06805,
            surface_binding_energy=8.01,
            displacement_energy=40.0
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
            atomic_mass=190.23,
            atomic_density=0.07151,
            surface_binding_energy=8.18,
            displacement_energy=25.0
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
            atomic_mass=192.217,
            atomic_density=0.07096,
            surface_binding_energy=6.93,
            displacement_energy=25.0
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
            atomic_mass=195.08,
            atomic_density=0.06622,
            surface_binding_energy=5.85,
            displacement_energy=33.0
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
            atomic_mass=196.96655,
            atomic_density=0.05907,
            surface_binding_energy=3.79,
            displacement_energy=36.0
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
            atomic_density=0.04067,
            surface_binding_energy=0.67,
            displacement_energy=25.0
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
            atomic_mass=204.3833,
            atomic_density=0.03492,
            surface_binding_energy=1.88,
            displacement_energy=25.0
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
            atomic_mass=207.2,
            atomic_density=0.03299,
            surface_binding_energy=2.03,
            displacement_energy=11.0
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
            atomic_mass=208.98038,
            atomic_density=0.02821,
            surface_binding_energy=2.17,
            displacement_energy=25.0
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
            atomic_mass=209.9828,
            atomic_density=0.02637,
            surface_binding_energy=1.51,
            displacement_energy=25.0
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
            atomic_mass=209.987126,
            atomic_density=0.02509,
            surface_binding_energy=0.94,
            displacement_energy=25.0
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
            atomic_mass=222.01757,
            atomic_density=0.01193,
            surface_binding_energy=0.0,
            displacement_energy=5.0
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
            atomic_mass=223.019731,
            atomic_density=0.00675,
            surface_binding_energy=0.78,
            displacement_energy=52.0
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
            atomic_mass=226.025402,
            atomic_density=0.01465,
            surface_binding_energy=1.65,
            displacement_energy=25.0
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
            atomic_mass=227.027747,
            atomic_density=0.02669,
            surface_binding_energy=4.21,
            displacement_energy=25.0
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
            atomic_mass=232.03805,
            atomic_density=0.03042,
            surface_binding_energy=6.2,
            displacement_energy=35.0
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
            atomic_mass=231.035878,
            atomic_density=0.04006,
            surface_binding_energy=6.29,
            displacement_energy=25.0
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
            atomic_mass=238.0289,
            atomic_density=0.04832,
            surface_binding_energy=5.55,
            displacement_energy=25.0
        ),
        Element(
            symbol='Np',
            name={
                'en': 'neptunium',
                'de': 'Neptunium'
            },
            atomic_nr=93,
            period=9,
            group=7,
            atomic_mass=237.048166,
            atomic_density=0.05195,
            surface_binding_energy=4.82,
            displacement_energy=25.0
        ),
        Element(
            symbol='Pu',
            name={
                'en': 'plutonium',
                'de': 'Plutonium'
            },
            atomic_nr=94,
            period=9,
            group=8,
            atomic_mass=244.064197,
            atomic_density=0.04895,
            surface_binding_energy=3.65,
            displacement_energy=25.0
        ),
        Element(
            symbol='Am',
            name={
                'en': 'americum',
                'de': 'Americum'
            },
            atomic_nr=95,
            period=9,
            group=9,
            atomic_mass=243.061372,
            atomic_density=0.03387,
            surface_binding_energy=2.94,
            displacement_energy=25.0
        ),
        Element(
            symbol='Cm',
            name={
                'en': 'curium',
                'de': 'Curium'
            },
            atomic_nr=96,
            period=9,
            group=10,
            atomic_mass=247.0703,
            atomic_density=0.03293,
            surface_binding_energy=3.96,
            displacement_energy=25.0
        ),
        Element(
            symbol='Bk',
            name={
                'en': 'berkelium',
                'de': 'Berkelium'
            },
            atomic_nr=97,
            period=9,
            group=11,
            atomic_mass=247.0703,
            atomic_density=0.03605,
            surface_binding_energy=3.02,
            displacement_energy=25.0
        ),
        Element(
            symbol='Cf',
            name={
                'en': 'californium',
                'de': 'Californium'
            },
            atomic_nr=98,
            period=9,
            group=12,
            atomic_mass=251.079579,
            atomic_density=0.0,
            surface_binding_energy=1.81,
            displacement_energy=25.0
        ),
        Element(
            symbol='Es',
            name={
                'en': 'einsteinium',
                'de': 'Einsteinium'
            },
            atomic_nr=99,
            period=9,
            group=13,
            atomic_mass=252.082944,
            atomic_density=0.0,
            surface_binding_energy=1.55,
            displacement_energy=25.0
        ),
        Element(
            symbol='Fm',
            name={
                'en': 'fermium',
                'de': 'Fermium'
            },
            atomic_nr=100,
            period=9,
            group=14,
            atomic_mass=257.075099,
            atomic_density=0.0,
            surface_binding_energy=1.46,
            displacement_energy=25.0
        ),
        Element(
            symbol='Md',
            name={
                'en': 'mendelevium',
                'de': 'Mendelevium'
            },
            atomic_nr=101,
            period=9,
            group=15,
            atomic_mass=258.098427,
            atomic_density=0.0,
            surface_binding_energy=1.2,
            displacement_energy=25.0
        ),
        Element(
            symbol='No',
            name={
                'en': 'nobelium',
                'de': 'Nobelium'
            },
            atomic_nr=102,
            period=9,
            group=16,
            atomic_mass=259.100931,
            atomic_density=0.0,
            surface_binding_energy=1.12,
            displacement_energy=25.0
        ),
        Element(
            symbol='Lr',
            name={
                'en': 'lawrencium',
                'de': 'Lawrencium'
            },
            atomic_nr=103,
            period=7,
            group=3,
            atomic_mass=262.11,
            atomic_density=0.0,
            surface_binding_energy=3.19,
            displacement_energy=25.0
        )
    ]

    def __init__(self):
        super().__init__(self.elementList)


class HlGeneralPlot(QHBoxLayout):
    """
    QHBoxLayout for general plot settings

    :param version: version of simulation
    """

    settingsChanged = pyqtSignal(dict)

    def __init__(self, version: str):
        super().__init__()
        self.version = version

    def emit(self, value_dict: dict = None):
        """
        Emits settingsChanged pyqtSignal

        :param value_dict: dictionary to emit
        """

        if value_dict is None:
            return
        self.settingsChanged.emit(value_dict)

    def receive(self, value_dict: dict):
        """
        Receives pyqtSignal -> dict

        :param value_dict: dictionary to be received
        """

        pass


class SimulationsInput:
    """
    Class for simulation specific parameters
    """

    # parameters should be different for each simulation class

    # name of the simulation
    Name = 'SIMULATION NAME MISSING'
    # supported versions
    Versions = []
    # detailed description of the simulation
    Description = 'SIMULATION DESCRIPTION MISSING'
    # logo for simulation if exists
    Logo = ''
    # information for about section
    About = 'No information available'
    # save folder name of simulation
    SaveFolder = 'default'
    # input file name
    InputFilename = 'input'
    # layer file name
    LayerFilename = 'layer'
    # example for additional settings
    ExampleAdditionalSetting = ''
    # list of skipped files for preview
    SkipList = [InputFilename, LayerFilename]
    # dictionary of tooltips for output files
    OutputTooltips = {'output': 'Output of simulation'}
    # possible input parameters
    InputParameters = {}
    # list of possible compounds
    CompoundList = []
    # group elements in beam and target
    GroupElements = False

    # Reference to classes
    HlBeamSettings = HlGeneralBeamSettings
    HlTargetSettings = HlGeneralTargetSettings
    VlSimulationSettings = VlGeneralSimulationSettings
    CompRowBeamSettings = CompRowBeamSettings
    CompRowTargetSettings = CompRowTargetSettings

    # Maximum number of components
    MaxComponents = 10

    def __init__(self):
        self.element_data = GeneralElementData()
        self.element_data_default = True

    @staticmethod
    def getVersionName(folder: str, binary: str) -> Union[str, bool]:
        """
        Returns version of simulation depending on selected folder and binary

        :param folder: main folder of simulation
        :param binary: binary of simulation

        :return: string of version number or False if no version can be determined
        """

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

        return False

    @staticmethod
    def downloadDoc(parent, folder: str, binary: str, version: str):
        """
        Downloads documentation pdf-file and saves it in the default directory

        :param parent: parent widget
        :param folder: main folder of simulation
        :param binary: binary of simulation
        :param version: version of simulation
        """

        pass

    @staticmethod
    def update(folder: str, binary: str, version: str):
        """
        Updates on startup

        :param folder: folder of simulation
        :param binary: binary path of simulation
        :param version: version of simulation
        """

        pass

    def loadDefaultElements(self, version: str):
        """
        Loads default elements in ElementData

        :param version: version of simulation
        """

        self.element_data = GeneralElementData()
        self.element_data_default = True

    @staticmethod
    def updateElements(folder: str, version: str) -> bool:
        """
        Updates list of <Element> for this simulation

        :param folder: main folder of simulation
        :param version: version of simulation
        """

        return False

    def nameInputFile(self, arguments: SimulationArguments, version: str) -> str:
        """
        Returns file-name of input file

        :param arguments: <SimulationArguments> container
        :param version: version of simulation

        :return: file-name of input file
        """

        return self.InputFilename

    @staticmethod
    def makeInputFile(arguments: SimulationArguments, folder: str, version: str) -> str:
        """
        Returns input file as string

        :param arguments: <SimulationArguments> container
        :param folder: folder of simulation
        :param version: version of simulation

        :return: input file for simulation as string
        """

        return ''

    def nameLayerFile(self, arguments: SimulationArguments, version: str) -> str:
        """
        Returns file-name of layer file

        :param arguments: <SimulationArguments> container
        :param version: version of simulation

        :return: file-name of layer file
        """

        return self.LayerFilename

    @staticmethod
    def makeLayerFile(arguments: SimulationArguments, folder: str, version: str) -> str:
        """
        Returns layer input file as string

        :param arguments: <SimulationArguments> container
        :param folder: folder of simulation
        :param version: version of simulation

        :return: layer input file for simulation as string
        """

        return ''

    @staticmethod
    def loadFiles(folder: str, version: str) -> Union[Tuple[SimulationArguments, list], str, bool]:
        """
        Returns Tuple of <SimulationArguments> container if it can load input files from folder and list of errors while loading
        Returns string of error if input file can not be opened
        Returns False if not implemented

        :param folder: folder of input files
        :param version: version of simulation

        :return: Tuple(<SimulationArguments>, list), str or False
        """

        return False

    @staticmethod
    def checkAdditional(settings: str, version: str) -> List[str]:
        """
        Checks the user defined additional settings and returns list of errors

        :param settings: provided additional settings
        :param version: version of simulation

        :return: list of errors
        """

        return []

    @staticmethod
    def cmd(binary: str, save_folder: str, input_file: str, version: str) -> (str, bool, str):
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
            False,
            f'"{binary}"'
        )

    @staticmethod
    def getProgress(save_folder: str, process_log: str, version: str) -> int:
        """
        Returns progress in % of running simulation.
        Negative return value indicates some error.

        :param save_folder: folder for output files
        :param process_log: most recent output of process
        :param version: version of simulation
        """

        return -1


class SimulationsOutput(QObject):
    """
    Class for displaying simulation specific parameters and plots

    :param plot: MplCanvas class that is used for plotting
    :param element_data: <Elements> container
    """

    # change to True if calculations should be performed in separate thread
    # caution: this will cause flickering of the plots when updating while simulation is running, needs further work
    Threading = False

    # signals
    hlChange = pyqtSignal(dict)

    # References to classes
    HlPlot = HlGeneralPlot

    def __init__(self, plot: MplCanvas, element_data: Elements):
        super().__init__()

        self.plot = plot
        self.element_data = element_data
        self.data = None
        self.save_folder = ''

        self.elements = ElementList()
        self.masses = np.array([])

        self.first_color = 0, 0, 0  # (r, g, b)
        self.line_width = 2

        self.thread_lock = Lock()
        self.thread_last_update = 0

        # colors for plots
        self.colors = RepeatingList()
        order = [4, 0, 6, 8, 14, 12, 16, 18, 10, 3, 5, 1, 7, 9, 15, 13, 17, 11, 19]
        colors = plt.get_cmap('tab20').colors
        for i in order:
            self.colors.append(colors[i])
        self.first_color = colors[2]

    def emit(self, value_dict: dict = None):
        """
        Emits settingsChanged pyqtSignal

        :param value_dict: dictionary to emit
        """

        if value_dict is None:
            return
        self.hlChange.emit(value_dict)

    def receive(self, value_dict: dict):
        """
        Receives pyqtSignal -> dict

        :param value_dict: dictionary to be received
        """

        pass

    def reset(self):
        """Reset class"""

        self.data = None
        self.save_folder = ''

        self.elements = ElementList()
        self.masses = np.array([])

    def clearPlotWindow(self):
        """Clears the plot window"""

        self.plot.fig.clf()
        self.plot.axes = self.plot.fig.add_subplot(projection='rectilinear')
        self.plot.fig.canvas.draw_idle()

    def plotFct(self, plot: Callable = None, plot_args: dict = None):
        """
        Call the plot function in a new thread with function parameters

        :param plot: plot function
        :param plot_args: plot function parameters as dictionary
        """

        if plot is None:
            return

        if plot_args is None:
            plot_args = {}

        if self.Threading:
            thread = Thread(
                target=self.plotFctThread,
                kwargs={
                    'plot': plot,
                    'plot_args': plot_args
                })
            thread.start()

        else:
            # wait cursor
            QApplication.setOverrideCursor(Qt.WaitCursor)

            result = plot(**plot_args)
            if result is None:
                self.data = None
                QApplication.restoreOverrideCursor()
                return

            self.data, plot_settings = result
            plot_settings.apply(self.plot)

            QApplication.restoreOverrideCursor()

    def plotFctThread(self, plot: Callable, plot_args: dict):
        """
        Call the plot function with function parameters

        :param plot: plot function
        :param plot_args: plot function parameters as dictionary
        :return:
        """

        our_time = time()

        # do calculations
        result = plot(**plot_args)
        if not isinstance(result, tuple) or len(result) != 2:
            self.data = None
            return
        self.data, plot_settings = result

        # obtain the lock to update the plot
        with self.thread_lock:

            # check if some other thread has done more recent calculation of same routine
            if our_time <= self.thread_last_update:
                return

            # update plot
            plot_settings.apply(self.plot)
            self.thread_last_update = our_time

    @staticmethod
    def listParameters(save_folder: str, list_widget: ListWidget):
        """
        Builds ListWidget from files in save folder

        :param save_folder: folder for output files
        :param list_widget: empty ListWidget (extension of QListWidget) that should be written to
        """

        raise NotImplementedError

    def getReturnData(self, precision: int = 7) -> Optional[str]:
        """Returns data from plot as string ready to be written in file or None if no data is available"""

        if self.data is None or len(self.data) != 2:
            return

        data, labels = self.data
        output = '\t'.join(labels) + '\n'
        data_len = len(data)
        for i in range(len(data[0])):
            data_i = []
            for j in range(data_len):
                data_i.append(f'{data[j][i]:.{precision}E}')
            output += '\t'.join(data_i) + '\n'
        return output
