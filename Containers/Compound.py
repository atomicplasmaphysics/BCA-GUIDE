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

from typing import Dict, List
from Containers.Element import Element


class Compound:
    """
    Container that stores information about a compound

    :param name: compound name; if not provided will be generated from list of elements
    :param elements: dict of elements in their periodic table format (e.g.: H, Ar, ...) with their corresponding amount
    :param name_save: compound name used in input file
    """

    def __init__(self, name: str = None, elements: Dict[str, int] = None, name_save: str = None):

        if name_save is None:
            name_save = name

        # generate name if necessary
        if name is None:
            name = ''
            name_save = ''
            if isinstance(elements, dict):
                for element, amount in elements.items():
                    name += element
                    name_save += element
                    if amount > 1:
                        name += f'<sub>{amount}</sub>'
                        name_save += str(amount)
        if not name:
            name = '???'
            name_save = '???'

        self.name = name
        self.elements: Dict = elements
        self.name_save = name_save

    def __str__(self) -> str:
        """Returns the string interpretation of the compound"""

        return self.name_save

    def matches(self, elements: List[Element] = None) -> bool:
        """
        Check if elements of compound are in list of provided elements

        :param elements: list of provided <Element> containers that should be checked against elements on compound
        """

        if self.elements is None or elements is None:
            return False

        return all(element in [element.symbol for element in elements] for element in self.elements.keys())
