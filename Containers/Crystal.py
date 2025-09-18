from typing import List, Optional, Union
import logging


class Vec3:
    """
    Container that stores basis vector
    """

    def __init__(self, vec: List[Union[int, float]]):
        self.vec = vec

    def crystal_inp_str(self, delimiter: str = ',') -> str:
        """Returns string of vector to use in crystal input file"""
        return f'{self.vec[0]}{delimiter} {self.vec[1]}{delimiter} {self.vec[2]}'

    def __len__(self) -> int:
        return 3

    def __getitem__(self, idx: int) -> float:
        return self.vec[idx]

    def __setitem__(self, idx: int, val: float):
        self.vec[idx] = val

    def __str__(self) -> str:
        """Returns string of basis vector"""
        return f'[{self.vec[0]}, {self.vec[1]}, {self.vec[2]}]'


class Coordinate(Vec3):
    """
    Container that stores a coordinate

    :param coord: list[x, y, z] of floats
    """

    def __init__(self, coord: Optional[List[float]] = None):
        super().__init__([0, 0, 0])

        if isinstance(coord, list) and len(coord):
            self.vec = [0, 0, 0]

            if len(coord) > 3:
                logging.warning(f'Coordinate "{coord}" must have length 3, will only take first 3 elements. Missing elements will be filled with zeros')

            for i in range(min(len(coord), 3)):
                self.vec[i] = coord[i]

    def crystal_inp_str(self, delimiter: str = '') -> str:
        """Returns string of vector to use in crystal input file"""
        return super().crystal_inp_str(delimiter)


class BasisVector(Vec3):
    """
    Container that stores a basis vector

    :param basis_vec: list[b1, b2, b3] of floats
    :param direction: (optional) direction of vector
    """

    def __init__(self, basis_vec: Optional[List[float]] = None, direction: int = 1):
        super().__init__([0, 0, 0])

        if direction in [1, 2, 3]:
            self.vec[direction - 1] = 1

        if isinstance(basis_vec, list) and len(basis_vec):
            self.vec = [0, 0, 0]

            if len(basis_vec) > 3:
                logging.warning(f'Basis vector "{basis_vec}" must have length 3, will only take first 3 elements. Missing elements will be filled with zeros')

            for i in range(min(len(basis_vec), 3)):
                self.vec[i] = basis_vec[i]


class MillerIndex(Vec3):
    """
    Container that stores a miller index

    :param miller_index: list[h, k, l] of integers
    """

    def __init__(self, miller_index: Optional[List[int]] = None):
        super().__init__([1, 0, 0])

        if isinstance(miller_index, list) and len(miller_index):
            self.vec = [0, 0, 0]

            if len(miller_index) > 3:
                logging.warning(f'Miller index "{miller_index}" must have length 3, will only take first 3 elements. Missing elements will be filled with zeros')

            conversion_error = False
            for i in range(min(len(miller_index), 3)):
                if int(miller_index[i]) != miller_index[i]:
                    conversion_error = True
                self.vec[i] = int(miller_index[i])

            if conversion_error:
                logging.warning(f'Miller index "{miller_index}" is not purely integers, will convert to int()')

    @property
    def h(self) -> int:
        """Returns h (=1) component of miller index vector"""
        return self.vec[0]

    @property
    def k(self) -> int:
        """Returns k (=2) component of miller index vector"""
        return self.vec[1]

    @property
    def l(self) -> int:
        """Returns l (=3) component of miller index vector"""
        return self.vec[2]
