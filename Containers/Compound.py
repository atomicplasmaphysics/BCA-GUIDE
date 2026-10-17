from typing import Dict, List, Optional
from Containers.Element import Element


class Compound:
    """
    Container that stores information about a compound

    :param name: compound name; if not provided will be generated from list of elements
    :param elements: dict of elements in their periodic table format (e.g.: H, Ar, ...) with their corresponding amount
    :param name_save: compound name used in input file
    """

    def __init__(self, name: Optional[str] = None, elements: Optional[Dict[str, int]] = None, name_save: Optional[str] = None):

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

        self.name: str = name
        self.elements: Dict[str, int] = elements if elements is not None else {}
        self.name_save: str = name_save if name_save is not None else name

    def __str__(self) -> str:
        """Returns the string interpretation of the compound"""

        return self.name_save

    def matches(self, elements: Optional[List[Element]] = None) -> bool:
        """
        Check if elements of compound are in list of provided elements

        :param elements: list of provided <Element> containers that should be checked against elements on compound
        """

        if not self.elements or elements is None:
            return False

        return all(element in [element.symbol for element in elements] for element in self.elements.keys())
