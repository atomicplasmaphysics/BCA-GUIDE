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


from sys import argv
from platform import system
import logging


from PyQt6.QtCore import Qt, QSize, QRect
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QIcon, QColor

import resources

from GlobalConf import GlobalConf
from MainWindow import MainWindow

from Utility.Layouts import SplashPixmap
from Utility.Logger import setupLogging


def main():
    """
    Execute the GUI
    """

    # set up logging level
    setupLogging(logging.WARNING)

    # ctypes.windll only works in Windows
    if system() == 'Windows':
        import ctypes
        # create unique app-id to show taskbar icon (Windows only)
        # in Linux this is not needed, the taskbar icon is set correctly
        app_id = f'TUWIEN.IAP.{GlobalConf.title.upper().replace(" ", ".")}.v1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)

    # start application
    app = QApplication(argv)
    app.setWindowIcon(QIcon(':/icons/tu_logo.png'))

    # get splash size
    screen = app.primaryScreen().availableVirtualGeometry()
    splash_size = QSize(int(min(620, screen.width() * 0.5)), int(min(300, screen.height() * 0.5)))

    # show splashscreen on startup
    pixmap = SplashPixmap(
        image=':/icons/splash.png',
        text='v. 1.4.18',
        box=QRect(530, 65, 90, 25),
        align=Qt.AlignmentFlag.AlignLeft,
        color=QColor('#154167'),
        font_size=22
    )
    pixmap = pixmap.scaled(splash_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    splash = QSplashScreen(pixmap)
    splash.show()
    app.processEvents()

    main_window = MainWindow(app)
    main_window.show()
    splash.finish(main_window)
    app.exec()


if __name__ == '__main__':
    main()
