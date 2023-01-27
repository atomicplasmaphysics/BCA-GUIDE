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


from typing import List

from Utility.Functions import normalizeList

from Containers.Element import Element


class GlobalDensity:
    """
    Class that calculates the global density for given elements and abundances

    :param elements: (optional) list of elements
    :param abundances: (optional) list of abundances
    :param density: (optional) desired global density (g / cm^3)
    :param density_in_amu: (optional) if density is provided in (amu / A^3)
    """

    # [amu * cm^3 / g * A^3]
    G_TO_AMU = 1 / 1.66

    def __init__(self, elements: List[Element] = None, abundances: List[float] = None, density: float = None, density_in_amu: bool = False):
        if elements is None:
            elements = []
        self.elements = elements

        if abundances is None:
            abundances = []
        self.abundances = abundances

        self.adaptArrays()
        self.density = density
        self.density_in_amu = density_in_amu

    def updateElements(self, elements: List[Element]):
        """
        Updates list of elements

        :param elements: List of elements
        """

        self.elements = elements
        self.adaptArrays()

    def updateAbundances(self, abundances: List[float]):
        """
        Updates list of abundances

        :param abundances: List of abundances
        """

        self.abundances = abundances
        self.adaptArrays()

    def updateDensity(self, density: float, density_in_amu: bool = False):
        """
        Update the desired density.

        :param density: Density in g/cm^3
        :param density_in_amu: If True, density should be provided in amu
        """

        self.density = density
        self.density_in_amu = density_in_amu

    def adaptArrays(self):
        """Adapts length of abundances to length of elements and sums it to 1"""

        difference = len(self.elements) - len(self.abundances)
        if difference:
            if difference < 0:
                self.abundances = self.abundances[:len(self.elements)]
            else:
                self.abundances.extend([0] * difference)
        self.abundances = normalizeList(self.abundances)

    def meanAmu(self) -> float:
        """Returns mean amu per atom of elements"""

        return sum([element.atomic_mass * abundance for (element, abundance) in zip(self.elements, self.abundances)])

    def atomicDensity(self, density: float = None, density_in_amu: bool = None) -> float:
        """
        Calculates the atomic density according to its composition and the density.

        :param density: Density in (g / cm^3)
        :param density_in_amu: If True, density should be provided in (amu / A^3)

        :return: atomic density
        """

        if density is not None:
            self.density = density
        if density_in_amu is not None:
            self.density_in_amu = density_in_amu

        if self.density is None:
            return 0

        global_density = self.density / self.meanAmu()
        if self.density_in_amu:
            return global_density
        return global_density * self.G_TO_AMU

    def atomicDensityElements(self, density: float = None, density_in_amu: bool = None) -> List[Element]:
        """
        Calculates the atomic density according to its composition and the density.

        :param density: Density in (g / cm^3)
        :param density_in_amu: If True, density should be provided in (amu / A^3)

        :return: list of elements with adjusted atomic density
        """

        atomic_density = self.atomicDensity(density, density_in_amu)

        for element in self.elements:
            element.atomic_density = atomic_density
        return self.elements
