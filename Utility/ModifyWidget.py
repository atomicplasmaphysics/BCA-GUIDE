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


from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QSpinBox, QDoubleSpinBox, QWidget, QComboBox, QGraphicsDropShadowEffect, QGraphicsColorizeEffect


def setWidgetBackground(widget: QWidget, enabled: bool, color: QColor = QColor(144, 12, 63, 255)):
    """
    Sets widget background to some color

    :param widget: widget to highlight
    :param enabled: enable/disable background
    :param color: (optional) color of background - default(rbg(144, 12, 63): darkish red)
    """

    if not enabled:
        widget.setGraphicsEffect(None)
        return
    colorize_effect = QGraphicsColorizeEffect()
    colorize_effect.setColor(color)
    widget.setGraphicsEffect(colorize_effect)


def setWidgetHighlight(widget: QWidget, enabled: bool, color: QColor = QColor(255, 0, 0, 255)):
    """
    Sets widget highlight to some color

    :param widget: widget to highlight
    :param enabled: enable/disable highlight
    :param color: (optional) color of highlight - default(rbg(255, 0, 0): red)
    """

    if not enabled:
        widget.setGraphicsEffect(None)
        return
    drop_shadow_effect = QGraphicsDropShadowEffect()
    drop_shadow_effect.setColor(color)
    drop_shadow_effect.setOffset(0)
    drop_shadow_effect.setBlurRadius(10)
    widget.setGraphicsEffect(drop_shadow_effect)


def widgetGetValue(widget):
    """
    Gets value of QWidget
    Currently QSpinBox, QDoubleSpinBox and QComboBox are supported

    :param widget: widget where the value should be taken from
    """

    if isinstance(widget, QSpinBox) or isinstance(widget, QDoubleSpinBox):
        return widget.value()
    elif isinstance(widget, QComboBox):
        return widget.currentIndex()


def widgetGetValue(widget):
    """
    Gets the value of a widget
    Currently QSpinBox, QDoubleSpinBox and QComboBox are supported

    :param widget: widget where value should be read from
    """

    if isinstance(widget, QSpinBox) or isinstance(widget, QDoubleSpinBox):
        return widget.value()

    elif isinstance(widget, QComboBox):
        return widget.currentIndex()


def widgetSetValue(widget, value):
    """
    Sets value of QWidget
    Currently QSpinBox, QDoubleSpinBox and QComboBox are supported

    :param widget: widget where value should be set
    :param value: value to be set
    """

    if isinstance(widget, QSpinBox) or isinstance(widget, QDoubleSpinBox):
        if widget.value() != value:
            widget.setValue(value)

    elif isinstance(widget, QComboBox):
        value = int(value)
        if widget.currentIndex() != value:
            widget.setCurrentIndex(value)


def widgetSetValueOfWidget(target, source):
    """
    Sets value of QWidget target to value of QWidget source
    Currently QSpinBox, QDoubleSpinBox and QComboBox are supported

    :param target: widget where value should be set
    :param source: widget where to get value from
    """

    value = 0
    if isinstance(source, QSpinBox) or isinstance(source, QDoubleSpinBox):
        value = source.value()

    elif isinstance(source, QComboBox):
        value = source.currentIndex()

    widgetSetValue(target, value)
