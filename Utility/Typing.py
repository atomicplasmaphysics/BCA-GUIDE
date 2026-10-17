"""Helpers for type checking (mypy)"""

from typing import Optional, TypeVar


T = TypeVar('T')


def notNone(value: Optional[T]) -> T:
    """
    Returns the value and raises a RuntimeError if it is None.
    Many functions of PyQt6 are typed to return None in error cases (e.g. QMenuBar.addMenu), which does not happen here

    :param value: value that is not None
    """

    if value is None:
        raise RuntimeError('unexpected None')
    return value
