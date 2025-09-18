from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QSpinBox, QDoubleSpinBox, QWidget, QComboBox, QGraphicsDropShadowEffect, QGraphicsColorizeEffect


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
