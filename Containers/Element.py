from __future__ import annotations
from typing import List, Union, Optional
from math import isfinite


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
        symbol: Optional[str] = None,
        name: Optional[dict] = None,
        atomic_nr: Optional[int] = None,
        period: Optional[int] = None,
        group: Optional[int] = None,
        atomic_mass: Optional[float] = None,
        atomic_density: Optional[float] = None,

        periodic_table_symbol: str = '',
        mass_density: Optional[float] = None,
        surface_binding_energy: Optional[float] = None,
        displacement_energy: Optional[float] = None,
        cutoff_energy: Optional[float] = None,
        dissociation_heat: Optional[float] = None,
        melt_enthalpy: Optional[float] = None,
        vaporization_energy: Optional[float] = None,
        formation_enthalpy: Optional[float] = None,

        modified: bool = False,
        copy_original: bool = True,

        **kwargs
    ):
        # Required arguments (an empty element if one of them is missing)
        if symbol is None or name is None or atomic_nr is None or period is None or group is None or atomic_mass is None or atomic_density is None:
            symbol = ''
            name = {'en': ''}
            atomic_nr = 0
            period = 0
            group = 0
            atomic_mass = 0
            atomic_density = 0

        try:
            atomic_nr, period, group = int(atomic_nr), int(period), int(group)  # type: ignore[arg-type]
            atomic_mass, atomic_density = float(atomic_mass), float(atomic_density)  # type: ignore[arg-type]
            if not (isfinite(atomic_mass) and isfinite(atomic_density)):
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            # damaged data (e.g. of an input.json): an empty element
            symbol, name, atomic_nr, period, group, atomic_mass, atomic_density = '', {'en': ''}, 0, 0, 0, 0., 0.

        def optionalNumber(value):
            """Optional values are finite numbers or None"""
            return value if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) else None

        mass_density = optionalNumber(mass_density)
        surface_binding_energy = optionalNumber(surface_binding_energy)
        displacement_energy = optionalNumber(displacement_energy)
        cutoff_energy = optionalNumber(cutoff_energy)
        dissociation_heat = optionalNumber(dissociation_heat)
        melt_enthalpy = optionalNumber(melt_enthalpy)
        vaporization_energy = optionalNumber(vaporization_energy)
        formation_enthalpy = optionalNumber(formation_enthalpy)

        self.symbol = str(symbol)
        # names in different languages, e.g. {'en': 'Gold', 'de': 'Gold'}
        self.name: dict = {'en': name} if isinstance(name, str) else name if isinstance(name, dict) else {'en': str(name)}
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

        self.modified = bool(modified)

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

        name = str(self.name.get('en', ''))
        if '|' in spec:
            names_spec = []
            for sp in spec.split('|'):
                name_spec = self.name.get(sp)
                if name_spec:
                    names_spec.append(name_spec)
            if len(names_spec):
                name = '/'.join(names_spec)

        else:
            name_spec = self.name.get(spec)
            if name_spec:
                name = name_spec

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

        if not isinstance(elements, list) or not elements:
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
