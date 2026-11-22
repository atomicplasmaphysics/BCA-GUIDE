from typing import Optional, TypeVar


T = TypeVar('T')


def notNone(value: Optional[T]) -> T:
    """
    Returns value and raises a RuntimeError if it is None (for PyQt6 functions typed as optional, e.g. QMenuBar.addMenu)

    :param value: value that is not None
    """

    if value is None:
        raise RuntimeError('unexpected None')
    return value
