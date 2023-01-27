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


from __future__ import annotations
from typing import List, Union


class Element:
    """
    Container that stores all information about one element/isotope

    Required arguments:
    symbol, name, atomic_nr, period, group, atomic_mass, atomic_density

    :param symbol: symbol of element
    :param name: name of element
    :param atomic_nr: atomic number of element
    :param period: period of element
    :param group: group of element
    :param atomic_mass: atomic mass of element
    :param atomic_density: atomic density of element

    :param periodic_table_symbol: (optional) symbol of element in periodic table
    :param mass_density: (optional) mass density of element
    :param surface_binding_energy: (optional) surface binding energy of element
    :param displacement_energy: (optional) displacement energy of element
    :param cutoff_energy: (optional) cut off energy of element
    :param dissociation_heat: (optional) dissociation heat of element
    :param melt_enthalpy: (optional) melt enthalpy of element
    :param vaporization_energy: (optional) vaporization energy of element
    :param formation_enthalpy: (optional) formation enthalpy of element

    :param modified: (optional) if element is modified from original configuration
    :param copy_original: (optional) if element should have a copy of its original form
    """

    def __init__(
        self,
        symbol: str = None,
        name: dict = None,
        atomic_nr: int = None,
        period: int = None,
        group: int = None,
        atomic_mass: float = None,
        atomic_density: float = None,

        periodic_table_symbol: str = '',
        mass_density: float = None,
        surface_binding_energy: float = None,
        displacement_energy: float = None,
        cutoff_energy: float = None,
        dissociation_heat: float = None,
        melt_enthalpy: float = None,
        vaporization_energy: float = None,
        formation_enthalpy: float = None,

        modified: bool = False,
        copy_original: bool = True,
        **kwargs
    ):
        # Check required arguments
        if None in [symbol, name, atomic_nr, period, group, atomic_mass, atomic_density]:
            symbol = ''
            name = {'en': ''}
            atomic_nr = 0
            period = 0
            group = 0
            atomic_mass = 0
            atomic_density = 0

        # Required arguments
        self.symbol = str(symbol)
        self.name = name  # should be dict
        if isinstance(self.name, str):
            self.name = {
                'en': str(self.name)
            }
        self.atomic_nr = int(atomic_nr)
        self.period = int(period)
        self.group = int(group)
        self.atomic_mass = float(atomic_mass)
        self.atomic_density = float(atomic_density)

        # Optional arguments
        self.periodic_table_symbol = str(periodic_table_symbol)
        if not periodic_table_symbol:
            self.periodic_table_symbol = self.symbol
        self.mass_density = mass_density
        self.surface_binding_energy = surface_binding_energy
        self.displacement_energy = displacement_energy
        self.cutoff_energy = cutoff_energy
        self.dissociation_heat = dissociation_heat
        self.melt_enthalpy = melt_enthalpy
        self.vaporization_energy = vaporization_energy
        self.formation_enthalpy = formation_enthalpy

        self.modified = modified

        self.original = None
        if copy_original:
            self.original = self.copy(copy_original=False)

    def copy(self, copy_original: bool = True) -> Element:
        """
        Returns copy of itself

        :param copy_original: if there should be a copy of the original element
        """

        return Element(
            symbol=self.symbol,
            name=self.name,
            atomic_nr=self.atomic_nr,
            period=self.period,
            group=self.group,
            atomic_mass=self.atomic_mass,
            atomic_density=self.atomic_density,

            periodic_table_symbol=self.periodic_table_symbol,
            mass_density=self.mass_density,
            surface_binding_energy=self.surface_binding_energy,
            displacement_energy=self.displacement_energy,
            cutoff_energy=self.cutoff_energy,
            dissociation_heat=self.dissociation_heat,
            melt_enthalpy=self.melt_enthalpy,
            vaporization_energy=self.vaporization_energy,
            formation_enthalpy=self.formation_enthalpy,

            modified=False,
            copy_original=copy_original
        )

    def getOriginal(self) -> Union[Element, None]:
        """Returns its original form"""

        return self.original

    def getInfo(self, spec: str = '') -> str:
        """
        The information string displayed in the periodic table dialog when hovering over the element in possibly different language

        :param spec: can be one language(e.g. 'en', 'de') or multiple languages separated by '|' (e.g. 'en|de')
        """

        return f'{self.__format__(spec)} ({self.symbol}, #{self.atomic_nr}, period {self.period}, group {self.group}), {self.atomic_mass} atomic mass, {self.atomic_density} atomic density'

    def __str__(self) -> str:
        """Returns name of element in english"""

        return self.__format__('en')

    def __format__(self, spec: str) -> str:
        """
        Returns name of element in specified languages

        :param spec: can be one language(e.g. 'en', 'de') or multiple languages separated by '|' (e.g. 'en|de')
        """

        name = self.name.get('en')
        if '|' in spec:
            spec = spec.split('|')

        if isinstance(spec, str):
            name_spec = self.name.get(spec)
            if name_spec:
                name = name_spec

        elif isinstance(spec, list):
            names_spec = []
            for sp in spec:
                name_spec = self.name.get(str(sp))
                if name_spec:
                    names_spec.append(name_spec)
            if len(names_spec):
                name = '/'.join(names_spec)

        return name


class Elements:
    """
    Stores all elements of a simulation

    :param elements: list of <Containers.Element:Element> objects
    """

    def __init__(self, elements: List[Element]):
        self.elements = elements

    def updateElements(self, elements: Union[List[Element], bool]) -> bool:
        """
        Updates internal element list, returns False if no elements are provided

        :param elements: list of <Containers.Element:Element> objects
        """

        if not elements:
            self.elements = []
            return False
        self.elements = elements
        return True

    def elementFromNr(self, atomic_nr: int) -> Union[Element, None]:
        """
        Get element from atomic number

        :param atomic_nr: desired element atomic number
        """

        for element in self.elements:
            if element.atomic_nr == atomic_nr:
                return element.copy()
        return None

    def elementFromSymbol(self, symbol: str) -> Union[Element, None]:
        """
        Get element from symbol

        :param symbol: desired element symbol
        """

        for element in self.elements:
            if element.symbol == symbol:
                return element.copy()
        return None

    def getIsotopes(self, atomic_nr: int) -> List[Element]:
        """
        Get isotopes for atomic number

        :param atomic_nr: desired atomic number
        """

        return [element.copy() for element in self.elements if element.atomic_nr == atomic_nr]

    def elementsMatching(self, text: str) -> List[Element]:
        """
        Return list of elements where name or symbol matches the provided text

        :param text: desired text in element name or element symbol
        """

        text = str.lower(text)
        results = []
        for element in self.elements:
            symbol = str.lower(element.symbol)
            name = '|'.join(element.name.values()).lower()
            if text in symbol or text in name:
                results.append(element.copy())
        return results

    def checkIfDefault(self, element: Element, attribute: str) -> bool:
        """
        Check if attribute of element is default

        :param element: desired element
        :param attribute: desired attribute
        """

        symbol = element.symbol
        orig_element = self.elementFromSymbol(symbol)
        if orig_element is None:
            return False
        if not hasattr(element, attribute) or not hasattr(orig_element, attribute):
            return False
        value = getattr(element, attribute)
        orig_value = getattr(orig_element, attribute)
        if value is not orig_value:
            return False
        return True
