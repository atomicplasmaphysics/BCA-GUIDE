# BCA-GUIDE - a graphical user interface for bca simulations to simulate sputtering, ion implantation and the
# dynamic effects of ion irradiation
#
# Copyright(C) 2025, Alexander Redl, Simon Osanger, Paul S.Szabo, David Weichselbaum, Herbert Biber, Christian Cupak,
# Andreas Mutzke, Wolfhard Möller, Richard A.Wilhelm, Friedrich Aumayr
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


from PyQt6.QtCore import Qt, QSize, QRect, QPoint, QTimer
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QIcon, QColor, QGuiApplication

import assets.resources  # noqa: F401 (registers the resources of Qt)

from Utility.GlobalConf import GlobalConf
from Pages.MainWindow import MainWindow

from Utility.Layouts import SplashPixmap
from Utility.Logger import setupLogging
from Utility.Typing import notNone

# TODO: make tabs detachable -> open them in their own window, such that multiple simulations can be seen at the same time


def selfTest() -> int:
    """
    Checks the started GUI (e.g. the executable of PyInstaller, see setup/pyinstaller.py): the simulation modules are loaded,
    the images of the resources and the manual of the GUI are found. Returns the exit code (0: everything found)
    """

    from PyQt6.QtGui import QPixmap
    from Simulations.SimulationsList import SimulationsList

    problems = []
    if not {'SDTrimSP', 'TRIDYN'} <= set(SimulationsList().simulation_program_names):
        problems.append(f'simulation modules: {SimulationsList().simulation_program_names}')
    if QPixmap(':/assets/tu_logo.png').isNull():
        problems.append('resources')
    if not (GlobalConf.program_path / 'BCA-GUIDE_manual.pdf').is_file():
        problems.append(f'manual in {GlobalConf.program_path}')
    for problem in problems:
        logging.error(f'Self test failed: {problem}')
    return 1 if problems else 0


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
        app_id = f'TUWIEN.IAP.{GlobalConf.title.upper().replace(" ", ".")}'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)

    # start application
    app = QApplication(argv)
    app.setWindowIcon(QIcon(':/assets/tu_logo.png'))

    # the splash screen is shown on the display of the main window (saved center of the window), otherwise on the primary one
    x, y = GlobalConf.getWindowCenter()
    display = QGuiApplication.screenAt(QPoint(x, y)) if (x, y) != (0, 0) else None
    if display is None:
        display = app.primaryScreen()
    screen = notNone(display).availableGeometry()
    splash_size = QSize(min(620, int(screen.width() * 0.5)), min(300, int(screen.height() * 0.5)))

    # show splashscreen on startup
    pixmap = SplashPixmap(
        image=':/assets/splash.png',
        text=f'v. {GlobalConf.version}',
        box=QRect(530, 65, 90, 25),
        align=Qt.AlignmentFlag.AlignLeft,
        color=QColor('#154167'),
        font_size=22
    )
    pixmap = pixmap.scaled(splash_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    splash = QSplashScreen(display, pixmap)
    splash_geometry = splash.frameGeometry()
    splash_geometry.moveCenter(screen.center())
    splash.move(splash_geometry.topLeft())
    splash.show()
    app.processEvents()
    main_window = MainWindow(app)
    main_window.show()
    splash.finish(main_window)

    # --self-test: checks the GUI after it has started and quits with the result as exit code
    if '--self-test' in argv:
        QTimer.singleShot(1000, lambda: app.exit(selfTest()))
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
