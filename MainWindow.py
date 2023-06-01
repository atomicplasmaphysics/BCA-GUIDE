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


from typing import List

from PyQt6.QtCore import Qt, QCoreApplication, QFileInfo, QUrl, QDir, QPoint
from PyQt6.QtGui import QIcon, QKeySequence, QCloseEvent, QDesktopServices, QGuiApplication
from PyQt6.QtWidgets import QMainWindow, QTabWidget, QMessageBox

import resources

from GlobalConf import GlobalConf
from Dialogs import AboutDialog, ManualDialog, PreferencesDialog

from Utility.Dialogs import selectFileDialog, showMessageBox, DownloadDialog

from Pages.ConfigurationPage import ConfigurationPage
from Pages.ProgramPage import SimulationPage

from Containers.SimulationConfiguration import SimulationConfiguration


class MainWindow(QMainWindow):
    """
    Class used for main layout
    """

    def __init__(self):
        super().__init__()
        GlobalConf()

        #
        # Global variables
        #

        self.simulation_configs: List[SimulationConfiguration] = []  # configuration data for each simulation
        self.old_simulation_configs: List[SimulationConfiguration] = []

        #
        # QCoreApplication Parameters
        #

        QCoreApplication.setOrganizationName('TUWien')
        QCoreApplication.setOrganizationDomain('www.tuwien.at')
        QCoreApplication.setApplicationName(GlobalConf.title)

        super().__init__()
        self.setWindowIcon(QIcon(':/icons/tu_logo.png'))
        self.window_title = GlobalConf.title

        #
        # MENU BAR
        #

        # File
        self.menu = self.menuBar()
        self.menu_file = self.menu.addMenu('&File')
        self.menu_file.setToolTipsVisible(True)

        # Save all
        self.action_save_all = self.menu_file.addAction(QIcon(':/icons/save.png'), 'Save all')
        self.action_save_all.setToolTip('Save configuration for all tabs')
        self.action_save_all.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.ALT | Qt.Key.Key_S))
        self.action_save_all.triggered.connect(lambda: self.menuSave())

        # Open all - not needed
        # self.action_open_all = self.menu_file.addAction(QIcon(':/icons/open.png'), 'Open all')
        # self.action_open_all.setToolTip('Open one configuration for all tabs')
        # self.action_open_all.setShortcut(QKeySequence(Qt.CTRL + Qt.ALT + Qt.Key_O))
        # self.action_open_all.triggered.connect(lambda: self.menuOpen())

        # Reset all
        self.action_reset_all = self.menu_file.addAction(QIcon(':/icons/refresh.png'), 'Reset all')
        self.action_reset_all.setToolTip('Resets configuration for all tabs')
        self.action_reset_all.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.ALT | Qt.Key.Key_N))
        self.action_reset_all.triggered.connect(lambda: self.menuReset())

        self.menu_file.addSeparator()

        # Close all
        self.action_close_all = self.menu_file.addAction(QIcon(':/icons/close.png'), 'Close all tabs')
        self.action_close_all.setToolTip('Closes all tabs')
        self.action_close_all.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.ALT | Qt.Key.Key_W))
        self.action_close_all.triggered.connect(lambda: self.menuCloseAll())

        self.menu_file.addSeparator()

        # Preferences
        self.action_preferences = self.menu_file.addAction(QIcon(':/icons/preferences.png'), 'Preferences')
        self.action_preferences.setToolTip('Open preferences dialog')
        self.action_preferences.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_H))
        self.action_preferences.triggered.connect(lambda: PreferencesDialog(self).open())

        self.menu_file.addSeparator()

        # Quit
        self.action_quit = self.menu_file.addAction('Quit')
        self.action_quit.setToolTip('Quit the program')
        self.action_quit.setShortcut(QKeySequence.StandardKey.Quit)
        self.action_quit.triggered.connect(lambda: self.close())

        # Simulation
        self.menu_simulation = self.menu.addMenu('&Simulation')
        self.menu_simulation.setToolTipsVisible(True)

        # Close current tab
        self.closeAction = self.menu_simulation.addAction(QIcon(':/icons/close.png'), 'Close current tab')
        self.closeAction.setToolTip('Closes currently active tab')
        self.closeAction.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_W))
        self.closeAction.setDisabled(True)
        self.closeAction.triggered.connect(lambda: self.menuClose())

        self.menu_simulation.addSeparator()

        # Run all tabs
        self.action_run_all = self.menu_simulation.addAction(QIcon(':/icons/play.png'), 'Run all tabs')
        self.action_run_all.setToolTip('Runs all opened tab')
        self.action_run_all.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.ALT | Qt.Key.Key_R))
        self.action_run_all.triggered.connect(lambda: self.menuRun())

        # Run all tabs detached
        self.action_run_all_detached = self.menu_simulation.addAction(QIcon(':/icons/play_detached.png'), 'Run all tabs detached')
        self.action_run_all_detached.setToolTip('Runs all opened tab in detached mode')
        self.action_run_all_detached.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.ALT | Qt.Modifier.SHIFT | Qt.Key.Key_R))
        self.action_run_all_detached.triggered.connect(lambda: self.menuRun(detached=True))

        # Abort all tabs
        self.action_abort_all = self.menu_simulation.addAction(QIcon(':/icons/abort.png'), 'Abort all tabs')
        self.action_abort_all.setToolTip('Aborts all running tabs')
        self.action_abort_all.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.ALT | Qt.Key.Key_P))
        self.action_abort_all.triggered.connect(lambda: self.menuAbort())

        # Help
        self.menu_help = self.menu.addMenu('&Help')
        self.menu_help.setToolTipsVisible(True)

        # Manual
        self.manual_path = QDir.currentPath()
        self.action_manual = self.menu_help.addAction(QIcon(':/icons/book.png'), 'Manual')
        self.action_manual.triggered.connect(self.openUserManual)

        # Manual
        self.action_manual = self.menu_help.addAction(QIcon(':/icons/help.png'), 'Quick Manual')
        self.action_manual.triggered.connect(lambda: ManualDialog(self).show())

        # About
        self.action_about = self.menu_help.addAction('About')
        self.action_about.triggered.connect(lambda: AboutDialog(self).open())

        self.setMenuBar(self.menu)

        #
        # TABS FOR DIFFERENT SIMULATION PROGRAMS
        #

        self.tab_simulations = QTabWidget(self)
        self.tab_simulations.currentChanged.connect(lambda index: self.tabChanged(index))
        self.setCentralWidget(self.tab_simulations)

        # Add simulation configuration tab
        self.simulation_configuration_page = ConfigurationPage(self)
        self.addSimulationTab(self.simulation_configuration_page, 'Configurations')
        self.simulation_configuration_page.open(default=True)

        #
        # STATUS BAR
        #

        self.statusBar()

        #
        # Setup window location and signals
        #

        # TODO: also store display where GUI was displayed

        self.tab_simulations.currentChanged.connect(lambda index: self.writeWindowTitleTab(index))

        width, height = GlobalConf.getWindowSize()
        x, y = GlobalConf.getWindowCenter()
        if width == height == -1:
            self.showMaximized()
        else:
            self.resize(width, height)
            frame_geometry = self.frameGeometry()
            center_point = QPoint(x, y)
            if x == y == 0:
                center_point = QGuiApplication.screens()[0].availableVirtualGeometry().center()
            frame_geometry.moveCenter(center_point)
            self.move(frame_geometry.topLeft())

    def addSimulationTab(self, widget, title: str):
        """
        Add simulation tab

        :param widget: widget to add in new tab
        :param title: title of tab
        """

        self.tab_simulations.addTab(widget, title)
        self.tab_simulations.setCurrentIndex(0)
        return widget

    def removeSimulationTab(self, widget):
        """
        Remove an existing simulation tab

        :param widget: widget to remove
        """

        index = self.tab_simulations.indexOf(widget)
        self.tab_simulations.removeTab(index)

    def changeSimulationTab(self, widget, title: str):
        """
        Change simulation tab title

        :param widget: widget to be changed
        :param title: new title
        """

        index = self.tab_simulations.indexOf(widget)
        self.tab_simulations.setTabText(index, title)

    def switchSettingsTab(self, sc: SimulationConfiguration):
        """
        Switches to settings tab and selects current simulation

        :param sc: selected SimulationConfiguration
        """

        self.simulation_configuration_page.selectConfigView(sc.title)
        self.tab_simulations.setCurrentIndex(0)

    def simChanged(self, sc: SimulationConfiguration):
        """
        Simulation settings have changed

        :param sc: changed SimulationConfiguration
        """

        index = self.tab_simulations.indexOf(sc.tab_widget)
        title = sc.title
        if sc.running:
            title = f'{title} ⧖'
        elif sc.unsaved_changes:
            title = f'{title} *'
        self.tab_simulations.setTabText(index, title)

        index = self.tab_simulations.indexOf(sc.tab_widget)
        if self.tab_simulations.currentIndex() == index:
            self.writeWindowTitleTab(index)

    def tabChanged(self, index: int):
        """
        Called when tab is changed

        :param index: index of active tab
        """

        tab_widget = self.tab_simulations.widget(index)
        if hasattr(tab_widget, 'updateWidget'):
            tab_widget.updateWidget()

        # disable/enable close current tab - menu
        self.closeAction.setDisabled(index == 0)

        # set active flags for each simulation configuration
        for i in range(self.tab_simulations.count()):
            widget = self.tab_simulations.widget(i)
            # check if simulation page or configuration page is selected
            if isinstance(widget, SimulationPage):
                sc = widget.simulation_configuration
                sc.is_active = i == index

    def writeStatusBar(self, msg: str, visible_time: int = 3000):
        """
        Write to status bar

        :param msg: new text of status bar
        :param visible_time: (optional) time in ms until status bar is cleared again. If 0, then message will stay persistent
        """

        self.statusBar().showMessage(msg, visible_time)

    def writeWindowTitleTab(self, index: int):
        """
        Writes title to main window based on index of tab

        :param: index: index of tab
        """

        widget = self.tab_simulations.widget(index)

        # check if simulation page or configuration page is selected
        if isinstance(widget, SimulationPage):
            sc = widget.simulation_configuration
            window_title = f'{self.window_title}: {sc.title} (Prog: {sc.program_name} v{sc.version})'
            if sc.running:
                window_title = f'{window_title} ⧖'
            elif sc.unsaved_changes:
                window_title = f'{window_title} *'
            self.setWindowTitle(window_title)
        else:
            self.setWindowTitle(self.window_title)

    def updateTabs(self):
        """Updates tabs if simulation configuration changed"""

        for sc in self.simulation_configs:
            if sc not in self.old_simulation_configs:
                self.old_simulation_configs.append(sc)
                sc.tab_widget = self.addSimulationTab(SimulationPage(self, sc), sc.title)
            if sc.changed:
                self.changeSimulationTab(sc.tab_widget, sc.title)
                sc.changed = False

        for sc in self.old_simulation_configs:
            if sc not in self.simulation_configs:
                self.removeSimulationTab(sc.tab_widget)

        self.old_simulation_configs = self.simulation_configs.copy()

    def menuSave(self):
        """Save all tabs"""

        # save config for configuration page
        self.simulation_configuration_page.save(autosave=True)

        # save config for all simulation tabs
        for sc in self.simulation_configs:
            sc.tab_widget.saveSettings()

    def menuOpen(self):
        """Open one configuration for all tabs"""

        # select file
        file = selectFileDialog(
            self,
            False,
            'Load input file',
            GlobalConf.save_path
        )
        folder = QFileInfo(file).canonicalPath()
        if len(folder) == 0:
            self.writeStatusBar('Loading aborted')
            return

        # load file in all simulation tabs
        for sc in self.simulation_configs:
            sc.tab_widget.loadSettings(folder)

    def menuReset(self):
        """Resets all configurations"""

        # reset (new) in all simulation tabs
        for sc in self.simulation_configs:
            sc.tab_widget.resetSettings()

    def menuCloseAll(self):
        """Closes all tabs"""

        # delete current tab
        non_closable = []
        for selected_conf in reversed(self.simulation_configs):
            if selected_conf is not None:
                # check if it is closeable
                if selected_conf.tab_widget is not None:
                    if not selected_conf.tab_widget.isClosable():
                        non_closable.append(selected_conf.title)
                    else:
                        self.simulation_configs.remove(selected_conf)

        if non_closable:
            showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                f'Some tabs are either running (⧖) or have unsaved changes (*). "{", ".join(non_closable)}"'
            )

        # replot and relist
        self.simulation_configuration_page.clearConfigView()
        self.simulation_configuration_page.listConfigView()

    def menuClose(self):
        """Closes active tab"""

        index = self.tab_simulations.currentIndex()
        if not index:
            return

        # delete current tab
        selected_conf = self.simulation_configs[index - 1]
        if selected_conf is not None:
            # check if it is closeable
            if selected_conf.tab_widget is not None:
                if not selected_conf.tab_widget.isClosable():
                    showMessageBox(
                        self,
                        QMessageBox.Icon.Warning,
                        'Warning!',
                        f'"{selected_conf.title}" is currently not closeable. It is either running (⧖) or has unsaved changes (*)'
                    )
                    return
            self.simulation_configs.remove(selected_conf)

        # replot and relist
        self.simulation_configuration_page.clearConfigView()
        self.simulation_configuration_page.listConfigView()

    def menuRun(self, detached: bool = False):
        """
        Runs all tabs

        :param detached: (optional) runs in detached mode
        """

        non_closeable = []
        for sc in self.simulation_configs:
            if sc.tab_widget is not None:
                if sc.running:
                    non_closeable.append(f'» "{sc.title}" is running')

        if non_closeable:
            _, result = showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                'At least one simulation is currently running (⧖). Please wait until the simulation has finished',
                detailed_message='\n'.join(non_closeable),
                standard_buttons=QMessageBox.StandardButton.Ok
            )
            return

        for sc in self.simulation_configs:
            sc.tab_widget.runSimulation(detached=detached)

    def menuAbort(self):
        """Aborts all tabs"""

        for sc in self.simulation_configs:
            if sc.running:
                sc.tab_widget.process.kill()

    def openUserManual(self):
        """Opens the user-manual of the GUI"""
        url = QUrl(f'{self.manual_path}/BCA-GUIDE_manual.pdf')
        opened = QDesktopServices.openUrl(url)

        # if failed to open, try to download it
        if not opened:
            dialog = DownloadDialog(
                parent=self,
                url='https://repositum.tuwien.at/bitstream/20.500.12708/152394/1/2022-BCA-GUIDE%20Manual-ao.pdf',
                path=self.manual_path,
                name='BCA-GUIDE_manual.pdf',
                expected_file_size=818324
            )
            dialog.open()

    def closeEvent(self, event: QCloseEvent):
        """
        Executed when close button is pressed

        :param event: close event
        """

        # check for unsaved changes/running simulations
        closable = self.simulation_configuration_page.checkClosableAll()

        if closable:
            self.simulation_configuration_page.save(autosave=True, no_config=not GlobalConf.keep_configurations_info)

            # terminate all running processes
            for sc in self.simulation_configs:
                sc.tab_widget.process.kill()

            GlobalConf.updateSettings()

            if self.isMaximized():
                dimensions = (-1, -1)
                center = (0, 0)
            else:
                dimensions = (self.width(), self.height())
                center = (int(self.pos().x() + self.width() / 2), int(self.pos().y() + self.height() / 2))
            GlobalConf.updateWindowSize(*dimensions)
            GlobalConf.updateWindowCenter(*center)

            event.accept()

        else:
            event.ignore()
