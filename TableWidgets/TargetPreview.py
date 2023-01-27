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


from PyQt5.QtCore import QSize, QRect, Qt
from PyQt5.QtGui import QPen, QPalette, QPainter, QColor, QFont, QFontMetrics
from PyQt5.QtWidgets import QWidget


class TargetPreview(QWidget):
    """
    QWidget for preview of target

    :param parent: parent widget
    """

    def __init__(self, parent):
        super().__init__(parent)

        self.antialiased = True
        self.setBackgroundRole(QPalette.Base)
        self.setAutoFillBackground(True)
        self.pen = QPen(QColor(0, 0, 0))

        self.font = QFont()
        self.font_metrics = QFontMetrics(self.font)

        self.layers = []
        self.elements = []
        self.total_segments = 0
        self.element_widths = []

        self.legend_size = 15
        self.legend_margin = 2
        self.legend_spacing_x = 7
        self.legend_spacing_y = 5

        self.target_width = 120
        self.x_margin = 15
        self.y_margin = 15

    def minimumSizeHint(self):
        """Returns minimum size"""

        return QSize(150, 100)

    def setTargetInfo(self, elements: list, layers: list):
        """
        Sets elements in layers

        :param elements: list of elements
        :param layers: list of layers
        """

        self.elements = elements
        self.element_widths = []
        for element in self.elements:
            self.element_widths.append(self.font_metrics.horizontalAdvance(element))

        self.layers = []
        self.total_segments = 0
        for row in layers:
            self.layers.append([row.segment_count, row.layer_name, row.abundances])
            self.total_segments += row.segment_count
        self.update()

    def resizeEvent(self, event):
        """
        When widget is resized

        :param event: resize event
        """

        self.target_width = self.width() * 0.9
        self.x_margin = (self.width() - self.target_width) / 2
        self.y_margin = (self.height() * 0.05) / 2

    def paintEvent(self, event):
        """
        When widget is painted

        :param event: paint event
        """

        painter = QPainter(self)
        painter.setPen(self.pen)
        painter.setRenderHint(QPainter.Antialiasing, self.antialiased)

        x_coord = self.x_margin
        y_coord = self.y_margin

        # Draw elements legend
        if len(self.elements) > 0:
            for i in range(len(self.elements)):
                x_coord_new = x_coord + self.element_widths[i] + 2 * self.legend_margin + self.legend_spacing_x
                if x_coord + self.x_margin > self.target_width:
                    x_coord = self.x_margin
                    x_coord_new = x_coord + self.element_widths[i] + 2 * self.legend_margin + self.legend_spacing_x
                    y_coord = y_coord + self.legend_size + self.legend_spacing_y

                rect = QRect(
                    int(x_coord),
                    int(y_coord),
                    int(self.element_widths[i] + 2 * self.legend_margin),
                    int(self.legend_size)
                )
                painter.fillRect(rect, QColor.fromHsv(int(i * 359 / len(self.elements)), 255, 255, 127))
                rect.translate(self.legend_margin, 0)
                rect.setSize(QSize(self.element_widths[i], self.legend_size))
                painter.drawText(rect, Qt.AlignCenter, f'{self.elements[i]}')

                x_coord = x_coord_new

        painter.drawRect(QRect(0, 0, int(self.width() - 1), int(self.height() - 1)))

        if not self.total_segments:
            return

        # Draw the target layers
        last_layer_y = int(y_coord + self.legend_size + self.legend_spacing_y)
        target_height = self.height() - last_layer_y - self.y_margin
        for i, layer in enumerate(self.layers):
            layer_height = round(target_height * layer[0] / self.total_segments)
            rect = QRect(
                int(self.x_margin),
                last_layer_y,
                int(self.target_width),
                layer_height
            )
            painter.drawRect(rect)

            # Color the layer depending on composition
            last_x = self.x_margin
            for j in range(len(self.elements)):
                w = self.target_width * layer[2][j]
                rect2 = QRect(
                    round(last_x),
                    last_layer_y,
                    round(last_x + w) - round(last_x),
                    layer_height
                )
                painter.fillRect(rect2, QColor.fromHsv(int(j * 359 / len(self.elements)), 255, 255, 127))
                last_x += w

            painter.drawText(rect, Qt.AlignCenter, f'{layer[1]}')
            last_layer_y += layer_height
