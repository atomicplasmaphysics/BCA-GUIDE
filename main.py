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

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QPixmap

import resources

from GlobalConf import GlobalConf
from MainWindow import MainWindow


def main():
    """
    Execute the GUI
    """

    # ctypes.windll only works in Windows
    if system() == 'Windows':
        import ctypes
        # create unique app-id to show taskbar icon (Windows only)
        # in Linux this is not needed, the taskbar icon is set correctly
        app_id = f'TUWIEN.IAP.{GlobalConf.title.upper().replace(" ", ".")}.v1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)

    app = QApplication(argv)

    pixmap = QPixmap(':/icons/splash.png')
    screen = app.screens()[0].availableVirtualGeometry()
    splash_size = QSize(int(min(620, screen.width() * 0.5)), int(min(300, screen.height() * 0.5)))
    pixmap = pixmap.scaled(splash_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    splash = QSplashScreen(pixmap)
    splash.show()
    app.processEvents()

    main_window = MainWindow()
    main_window.show()
    splash.finish(main_window)
    app.exec()


if __name__ == '__main__':
    main()
