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


from PyQt5.QtCore import QObject, pyqtSignal


class CounterItem(QObject):
    """
    Class for counter item with change signal

    :param value: value of counter item
    """

    rankChanged = pyqtSignal(int)

    def __init__(self, value: int):
        super().__init__()
        self.value = value

    def update(self, value: int):
        """Update own value. Should only be called in Counter class!"""
        if self.value != value:
            self.value = value
            self.rankChanged.emit(self.value)


class Counter(QObject):
    """
    Class for counting how many elements are used and limit number of elements

    :param maximum: maximum number of elements (optional)
    """

    maxReached = pyqtSignal(bool)

    def __init__(self, maximum: int = 1e8):
        super().__init__()
        self.maximum = maximum
        self.entries = []

    def getNext(self):
        """Get next element of counter"""

        next_int = len(self.entries) + 1
        if next_int >= self.maximum:
            self.maxReached.emit(True)
        if next_int > self.maximum:
            return False
        next_item = CounterItem(next_int)
        self.entries.append(next_item)
        return next_item

    def delItem(self, value: int):
        """
        Delete element with value

        :param value: value to be deleted
        """

        if value > len(self.entries):
            return False
        del self.entries[value - 1]
        self.maxReached.emit(False)

        # reorder entries
        for i, entry in enumerate(self.entries):
            entry.update(i + 1)

    def isMaxReached(self):
        """Returns if maximum is reached"""

        return len(self.entries) >= self.maximum


class RunningIndex:
    """
    Class to keep a running index

    :param initial_value: initial index value
    """

    def __init__(self, initial_value: int = 0):
        self.index = initial_value

    def get(self):
        self.index += 1
        return self.index


class DeleteDict(dict):
    """
    Dictionary that deletes its keys if value of key is requested
    """

    def __init__(self):
        super().__init__()

    def get(self, key):
        result = super().get(key)
        if result is not None:
            super().__delitem__(key)
        return result


class DefaultAssumed(list):
    """
    Keeps track if default value is assumed
    -> Some values are not set, not defined in <ArgumentValues> or have wrong type
    """

    def __init__(self):
        super().__init__()

    def assumed(self, item: str):
        self.append(item)


class RepeatingList(list):
    """
    List that acts as repeating list if indices outside the list length are accessed
    """

    def __getitem__(self, item: int):
        item = item % self.__len__()
        return super().__getitem__(item)


class ElementList(list):
    """
    List of elements that creates sub indexes for elements if they occur twice
    """

    def __init__(self):
        self.distinct = {}
        super().__init__()

    @staticmethod
    def rename(item: str, index: int):
        """Rename routine"""

        return f'{item}_[{index}]'

    def append(self, item: str):
        """Append method of list"""

        exists = self.distinct.get(item)

        # append to self and self.distinct if not already in there
        if exists is None:
            self.distinct[item] = 1
            super().append(item)
            return

        # item already in self.distinct, second occurrence
        if exists == 1:
            index = self.index(item)
            self[index] = self.rename(item, exists)

        # rename item and append it
        exists += 1
        super().append(self.rename(item, exists))
        self.distinct[item] = exists
