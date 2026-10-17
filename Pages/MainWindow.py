from typing import List, Optional

from PyQt6.QtCore import Qt, QCoreApplication, QUrl, QPoint, QTimer, QElapsedTimer, QProcess
from PyQt6.QtGui import QIcon, QKeySequence, QCloseEvent, QDesktopServices, QGuiApplication
from PyQt6.QtWidgets import QMainWindow, QTabWidget, QMessageBox, QApplication

from Utility.GlobalConf import GlobalConf

from Utility.Dialogs import AboutDialog, ManualDialog, PreferencesDialog, DownloadDialog, selectFileDialog, showMessageBox
from Utility.Layouts import ProgressTabBar, TimeProgressBar
from Utility.Icons import getIcon
from Utility.Typing import notNone

from Pages.ConfigurationPage import ConfigurationPage
from Pages.ProgramPage import SimulationPage

from Containers.SimulationConfiguration import SimulationConfiguration


class MainWindow(QMainWindow):
    """
    Class used for main layout
    """

    def __init__(self, app: QApplication):
        super().__init__()
        GlobalConf()
        self.app = app

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

        self.window_title = GlobalConf.title

        #
        # MENU BAR
        #

        # File
        self.menu = notNone(self.menuBar())
        self.menu_file = notNone(self.menu.addMenu('&File'))
        self.menu_file.setToolTipsVisible(True)

        # Save all
        self.action_save_all = notNone(self.menu_file.addAction(getIcon('save'), 'Save all'))
        self.action_save_all.setToolTip('Save configuration for all tabs')
        self.action_save_all.setShortcut(QKeySequence('Ctrl+Alt+S'))
        self.action_save_all.triggered.connect(lambda: self.menuSave())

        # Open all - not needed
        # self.action_open_all = self.menu_file.addAction(getIcon('open'), 'Open all')
        # self.action_open_all.setToolTip('Open one configuration for all tabs')
        # self.action_open_all.setShortcut(QKeySequence(Qt.CTRL + Qt.ALT + Qt.Key_O))
        # self.action_open_all.triggered.connect(lambda: self.menuOpen())

        # Reset all
        self.action_reset_all = notNone(self.menu_file.addAction(getIcon('refresh'), 'Reset all'))
        self.action_reset_all.setToolTip('Resets configuration for all tabs')
        self.action_reset_all.setShortcut(QKeySequence('Ctrl+Alt+N'))
        self.action_reset_all.triggered.connect(lambda: self.menuReset())

        self.menu_file.addSeparator()

        # Close all
        self.action_close_all = notNone(self.menu_file.addAction(getIcon('close'), 'Close all tabs'))
        self.action_close_all.setToolTip('Closes all tabs')
        self.action_close_all.setShortcut(QKeySequence('Ctrl+Alt+W'))
        self.action_close_all.triggered.connect(lambda: self.menuCloseAll())

        self.menu_file.addSeparator()

        # Preferences
        self.action_preferences = notNone(self.menu_file.addAction(getIcon('preferences'), 'Preferences'))
        self.action_preferences.setToolTip('Open preferences dialog')
        self.action_preferences.setShortcut(QKeySequence('Ctrl+H'))
        self.action_preferences.triggered.connect(self.openPreferences)

        self.menu_file.addSeparator()

        # Quit
        self.action_quit = notNone(self.menu_file.addAction('Quit'))
        self.action_quit.setToolTip('Quit the program')
        self.action_quit.setShortcut(QKeySequence.StandardKey.Quit)
        self.action_quit.triggered.connect(lambda: self.close())

        # Simulation
        self.menu_simulation = notNone(self.menu.addMenu('&Simulation'))
        self.menu_simulation.setToolTipsVisible(True)

        # Close current tab
        self.closeAction = notNone(self.menu_simulation.addAction(getIcon('close'), 'Close current tab'))
        self.closeAction.setToolTip('Closes currently active tab')
        self.closeAction.setShortcut(QKeySequence('Ctrl+W'))
        self.closeAction.setDisabled(True)
        self.closeAction.triggered.connect(lambda: self.menuClose())

        self.menu_simulation.addSeparator()

        # queue of "Run all": pages that wait, pages that run and all pages of the current batch
        self.run_queue: List[SimulationPage] = []
        self.run_active: List[SimulationPage] = []
        self.run_batch: List[SimulationPage] = []
        self.run_durations: List[float] = []
        self.run_batch_timer = QElapsedTimer()
        self.run_status_timer = QTimer(self)
        self.run_status_timer.setInterval(1000)
        self.run_status_timer.timeout.connect(self.updateRunAllStatus)

        # Run all tabs
        self.action_run_all = notNone(self.menu_simulation.addAction(getIcon('play'), 'Run all tabs'))
        self.action_run_all.setToolTip('Runs all opened tabs, at most the given number of simulations at the same time (the others wait in a queue)')
        self.action_run_all.setShortcut(QKeySequence('Ctrl+Alt+R'))
        self.action_run_all.triggered.connect(lambda: self.menuRun())

        # Run all tabs detached
        self.action_run_all_detached = notNone(self.menu_simulation.addAction(getIcon('play_detached'), 'Run all tabs detached'))
        self.action_run_all_detached.setToolTip('Runs all opened tab in detached mode')
        self.action_run_all_detached.setShortcut(QKeySequence('Ctrl+Alt+Shift+R'))
        self.action_run_all_detached.triggered.connect(lambda: self.menuRun(detached=True))

        self.menu_simulation.addSeparator()

        # comparison of simulations
        self.action_compare = notNone(self.menu_simulation.addAction(getIcon('compare'), 'Compare simulations...'))
        self.action_compare.setToolTip('Compares the results of several simulations of the program of the current tab in one table and plot')
        self.action_compare.triggered.connect(lambda: self.openComparison())

        self.menu_simulation.addSeparator()

        # Abort all tabs
        self.action_abort_all = notNone(self.menu_simulation.addAction(getIcon('abort'), 'Abort all tabs'))
        self.action_abort_all.setToolTip('Aborts all running tabs')
        self.action_abort_all.setShortcut(QKeySequence('Ctrl+Alt+P'))
        self.action_abort_all.triggered.connect(lambda: self.menuAbort())

        # Help
        self.menu_help = notNone(self.menu.addMenu('&Help'))
        self.menu_help.setToolTipsVisible(True)

        # Manual
        self.manual_path = GlobalConf.program_path
        self.action_manual = notNone(self.menu_help.addAction(getIcon('book'), 'Manual'))
        self.action_manual.triggered.connect(lambda: self.openUserManual())

        # Manual
        self.action_manual = notNone(self.menu_help.addAction(getIcon('help'), 'Quick Manual'))
        self.action_manual.triggered.connect(lambda: ManualDialog(self).show())


        self.menu_help.addSeparator()

        # About
        self.action_about = notNone(self.menu_help.addAction('About'))
        self.action_about.triggered.connect(lambda: AboutDialog(self).open())

        self.setMenuBar(self.menu)

        #
        # TABS FOR DIFFERENT SIMULATION PROGRAMS
        #

        self.tab_simulations = QTabWidget(self)
        self.tab_bar_simulations = ProgressTabBar(self)
        self.tab_simulations.setTabBar(self.tab_bar_simulations)
        self.tab_simulations.currentChanged.connect(lambda index: self.tabChanged(index))
        self.setCentralWidget(self.tab_simulations)

        # Add simulation configuration tab
        self.simulation_configuration_page = ConfigurationPage(self)
        self.addSimulationTab(self.simulation_configuration_page, 'Configurations')
        self.simulation_configuration_page.open(default=True)

        # apply the theme from the preferences, also react to theme changes of the operating system
        self.applyTheme()
        notNone(self.app.styleHints()).colorSchemeChanged.connect(lambda _: QTimer.singleShot(0, self.refreshStyleSheets))

        #
        # STATUS BAR
        #

        self.statusBar()

        #
        # Setup window location and signals
        #

        self.tab_simulations.currentChanged.connect(lambda index: self.writeWindowTitleTab(index))

        # the saved geometry contains the display and the maximized state, the window opens on the same display again
        width, height = GlobalConf.getWindowSize()
        x, y = GlobalConf.getWindowCenter()
        geometry = GlobalConf.getWindowGeometry()
        if geometry is not None and self.restoreGeometry(geometry):
            pass
        elif width == height == -1:
            self.showMaximized()
        else:
            self.resize(width, height)
            frame_geometry = self.frameGeometry()
            center_point = QPoint(x, y)

            # the stored center also defines the display; if this display is not available anymore, use the primary display
            if (x == y == 0) or QGuiApplication.screenAt(center_point) is None:
                center_point = notNone(QGuiApplication.primaryScreen()).availableGeometry().center()
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
            self.tab_bar_simulations.setProgress(index, sc.progress)
        else:
            self.tab_bar_simulations.setProgress(index, 0)

        if sc.unsaved_changes:
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
        update_widget = getattr(self.tab_simulations.widget(index), 'updateWidget', None)
        if update_widget is not None:
            update_widget()

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

        notNone(self.statusBar()).showMessage(msg, visible_time)

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

        # keep order of tabs in sync with order of configurations (first tab is the configuration page)
        for i, sc in enumerate(self.simulation_configs):
            index = self.tab_simulations.indexOf(sc.tab_widget)
            if index != i + 1:
                self.tab_bar_simulations.moveTab(index, i + 1)
        for sc in self.simulation_configs:
            self.simChanged(sc)

        self.old_simulation_configs = self.simulation_configs.copy()

    def menuSave(self):
        """Save all tabs"""

        # save config for configuration page
        self.simulation_configuration_page.save(autosave=True)

        # save config for all simulation tabs
        for sc in self.simulation_configs:
            if sc.tab_widget is not None:
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
        if file is None:
            self.writeStatusBar('Loading aborted')
            return
        folder = file.resolve().parent

        # load file in all simulation tabs
        for sc in self.simulation_configs:
            if sc.tab_widget is not None:
                sc.tab_widget.loadSettings(folder)

    def menuReset(self):
        """Resets all configurations"""

        # reset (new) in all simulation tabs
        for sc in self.simulation_configs:
            if sc.tab_widget is not None:
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

        self.runSimulations([sc for sc in self.simulation_configs if sc.tab_widget is not None], detached=detached)

    def currentSimulationPage(self) -> Optional[SimulationPage]:
        """Returns the page of the current simulation tab or None"""

        page = self.tab_simulations.currentWidget()
        return page if isinstance(page, SimulationPage) else None

    def openComparison(self, page: Optional[SimulationPage] = None):
        """Opens the comparison of simulations (of the program of the current tab, starting with its folder)"""

        from Pages.CompareDialog import CompareDialog

        page = page or self.currentSimulationPage()
        if page is None:
            self.writeStatusBar('Select the tab of a simulation to compare it with other simulations')
            return
        folders = [page.simulation_configuration.save_folder] if page.simulation_configuration.save_folder else []
        dialog = CompareDialog(self, type(page.evaluation_class.analysis), page.simulation_class.element_data, folders)
        dialog.show()

    def setMaxParallelRuns(self, value: int):
        """Sets the maximum number of simultaneous simulations and starts waiting simulations"""

        GlobalConf.max_parallel_runs = int(value)
        GlobalConf.setValue(GlobalConf.max_parallel_runs_name, GlobalConf.max_parallel_runs)
        self.startQueuedSimulations()

    def runSimulations(self, configurations: List[SimulationConfiguration], detached: bool = False):
        """
        Runs several simulations. The warnings about the parameters are shown once for all simulations and at most
        GlobalConf.max_parallel_runs simulations run at the same time, the others wait in a queue

        :param configurations: configurations of the simulations
        :param detached: (optional) run in detached mode (all at once, they can not be tracked)
        """

        pages = [
            sc.tab_widget for sc in configurations
            if sc.tab_widget is not None and not sc.running and sc.tab_widget not in self.run_queue
        ]
        if not pages:
            return

        # warnings of all simulations, the user decides
        warnings = []
        for page in pages:
            warnings += [f'{page.simulation_configuration.title}: {warning}' for warning in page.runWarnings()]
        if warnings:
            _, result = showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                'Some simulations might fail, give wrong results or create very large files',
                info_message='Press "OK" to run all simulations anyway.',
                detailed_message='\n\n'.join(warnings),
                standard_buttons=QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                expand_details=True
            )
            if result == QMessageBox.StandardButton.Cancel:
                return

        # the files of previous runs are deleted (asked once)
        if not GlobalConf.skip_delete_info:
            msg_box, result = showMessageBox(
                self,
                QMessageBox.Icon.Information,
                'Attention!',
                'Files in the working directories will be deleted',
                info_message='In order to run the simulations, all non-input files in their working directories will be deleted automatically.',
                detailed_message='\n'.join(str(page.simulation_configuration.save_folder) for page in pages if page.simulation_configuration.save_folder),
                standard_buttons=QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                check_box_text='Do not show again'
            )
            if result == QMessageBox.StandardButton.Cancel:
                return
            if msg_box.checkBox().isChecked():
                GlobalConf.skip_delete_info = True

        if detached:
            for page in pages:
                page.runSimulation(detached=True, check_warnings=False, ask_delete=False)
            return

        if not self.run_queue and not self.run_active:
            self.run_batch = []
            self.run_durations = []
            self.run_batch_timer.restart()
        for page in pages:
            page.setRunStatus(SimulationPage.RunStatus.QUEUED)
        self.run_queue += pages
        self.run_batch += pages
        self.startQueuedSimulations()
        self.run_status_timer.start()
        self.updateRunAllStatus()

    def runningSimulations(self) -> int:
        """Number of running simulations of all tabs (simulations of "Run all", single runs and of parameter scans)"""

        pages = list(self.run_active)
        for sc in self.simulation_configs:
            if sc.tab_widget is not None and sc.tab_widget not in pages:
                pages.append(sc.tab_widget)
        count = 0
        for page in pages:
            scan = getattr(page, 'scan', None)
            if scan is not None and scan.isRunning():
                count += len(scan.running)
            elif page in self.run_active or page.process.state() != QProcess.ProcessState.NotRunning:
                count += 1
        return count

    def freeRunSlots(self) -> int:
        """Number of simulations that can be started (at most GlobalConf.max_parallel_runs simulations of all tabs run)"""

        return max(1, GlobalConf.max_parallel_runs) - self.runningSimulations()

    def startQueuedSimulations(self):
        """
        Starts waiting simulations until GlobalConf.max_parallel_runs simulations of all tabs run: first the tabs of "Run
        all", then the simulations of the parameter scans
        """

        while self.run_queue and self.freeRunSlots() > 0:
            page = self.run_queue.pop(0)
            try:
                started = page.runSimulation(check_warnings=False, ask_delete=False)
            except RuntimeError:
                # tab was closed
                continue
            if started:
                self.run_active.append(page)
            else:
                if page.run_status == SimulationPage.RunStatus.QUEUED:
                    page.setRunStatus(SimulationPage.RunStatus.READY)
                self.run_batch.remove(page)

        # simulations of the parameter scans
        for sc in self.simulation_configs:
            if self.freeRunSlots() <= 0:
                break
            if sc.tab_widget is not None:
                sc.tab_widget.scan.startJobs()

    def simulationFinished(self, page: SimulationPage):
        """A simulation has finished: the next simulations of the queue are started"""

        if page in self.run_active:
            self.run_active.remove(page)
            self.run_durations.append(page.run_progress.elapsed_timer_final / 1000)
        self.startQueuedSimulations()
        self.updateRunAllStatus()

    def runAllRemainingTime(self) -> Optional[float]:
        """
        Returns an estimate of the remaining time (in s) of all simulations of "Run all" or None if unknown.
        The remaining time of running simulations follows from their progress, waiting simulations take the mean
        duration of the finished and running ones and start when a simulation finishes
        """

        # remaining time of the running simulations (None if unknown)
        running: List[Optional[float]] = []
        durations = list(self.run_durations)
        for page in self.run_active:
            progress = page.run_progress.value()
            elapsed = page.run_progress.elapsed_timer.elapsed() / 1000
            if progress < 1 or elapsed <= 0:
                running.append(None)
                continue
            total = elapsed * 100 / progress
            durations.append(total)
            running.append(max(total - elapsed, 0.))
        if not durations:
            return None
        mean_duration = sum(durations) / len(durations)
        slots = [mean_duration if slot is None else slot for slot in running]
        slots += [0.] * max(0, max(1, GlobalConf.max_parallel_runs) - len(slots))
        for _ in self.run_queue:
            index = slots.index(min(slots))
            slots[index] += mean_duration
        return max(slots) if slots else 0.

    def updateRunAllStatus(self):
        """Shows the progress of all simulations of "Run all" in the status bar"""

        if not self.run_batch:
            self.run_status_timer.stop()
            return
        total = len(self.run_batch)
        running = len(self.run_active)
        waiting = len(self.run_queue)
        finished = total - running - waiting
        elapsed = self.run_batch_timer.elapsed() / 1000 if self.run_batch_timer.isValid() else 0
        if not running and not waiting:
            self.writeStatusBar(f'Run all: {total} simulation{"s" if total > 1 else ""} finished in {TimeProgressBar.formatTime(elapsed)}', visible_time=0)
            self.run_batch = []
            self.run_status_timer.stop()
            return
        remaining = self.runAllRemainingTime()
        text = f'Run all: {finished} of {total} finished, {running} running, {waiting} waiting, elapsed {TimeProgressBar.formatTime(elapsed)}'
        if remaining is not None:
            text += f', about {TimeProgressBar.formatTime(remaining)} remaining'
        self.writeStatusBar(text, visible_time=0)

    def menuAbort(self):
        """Aborts all tabs (also the waiting simulations of "Run all")"""

        for page in self.run_queue:
            try:
                page.setRunStatus(SimulationPage.RunStatus.READY)
            except RuntimeError:
                pass
        self.run_queue = []
        for sc in self.simulation_configs:
            if sc.tab_widget is None:
                continue
            if sc.tab_widget.scan.isRunning():
                sc.tab_widget.scan.abort()
            elif sc.running:
                sc.tab_widget.process.kill()

    def openPreferences(self):
        """Opens the preferences dialog"""

        dialog = PreferencesDialog(self)
        dialog.finished.connect(lambda _: self.simulation_configuration_page.updateSaveFolderPlaceholder())
        # a higher number of simultaneous simulations starts waiting simulations
        dialog.finished.connect(lambda _: self.startQueuedSimulations())
        dialog.open()

    def openUserManual(self):
        """Opens the user-manual of the GUI"""

        url = QUrl.fromLocalFile(str(self.manual_path / 'BCA-GUIDE_manual.pdf'))
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

    def applyTheme(self):
        """Applies the theme selected in GlobalConf.theme (system, light, dark or srim)"""

        color_schemes = {
            'system': Qt.ColorScheme.Unknown,
            'light': Qt.ColorScheme.Light,
            'dark': Qt.ColorScheme.Dark,
            'srim': Qt.ColorScheme.Light,
        }
        notNone(self.app.styleHints()).setColorScheme(color_schemes.get(GlobalConf.theme, Qt.ColorScheme.Unknown))

        if GlobalConf.theme == 'srim':
            self.app.setWindowIcon(QIcon(':/assets/tu_logo_loco.png'))
            self.setStyleSheet('background: url(:/assets/clouds.png) repeat center center fixed; background-color: #2db9ff;')
            self.window_title = 'BCA-SRIM'
        else:
            self.app.setWindowIcon(QIcon(':/assets/tu_logo.png'))
            self.setStyleSheet('')
            self.window_title = GlobalConf.title

        self.writeWindowTitleTab(self.tab_simulations.currentIndex())
        QTimer.singleShot(0, self.refreshStyleSheets)

    def refreshStyleSheets(self):
        """
        Widgets with a style sheet (and their children) keep the palette of the time the style sheet was set.
        Setting the style sheets again updates them to the current palette after a theme change.
        """

        for widget in self.app.allWidgets():
            style_sheet = widget.styleSheet()
            if style_sheet:
                widget.setStyleSheet(style_sheet)

    def closeEvent(self, event: Optional[QCloseEvent]):
        """
        Executed when close button is pressed

        :param event: close event
        """

        if event is None:
            return

        # check for unsaved changes/running simulations
        closable = self.simulation_configuration_page.checkClosableAll()

        if closable:
            self.simulation_configuration_page.save(autosave=True, no_config=not GlobalConf.keep_configurations_info)

            # terminate all running processes
            for sc in self.simulation_configs:
                if sc.tab_widget is not None:
                    sc.tab_widget.process.kill()
                    sc.tab_widget.scan.stop(ask=False)

            GlobalConf.updateSettings()

            # the center is also saved for maximized windows, it defines the display (also of the splash screen)
            if self.isMaximized():
                dimensions = (-1, -1)
            else:
                dimensions = (self.width(), self.height())
            center = self.frameGeometry().center()
            GlobalConf.updateWindowSize(*dimensions)
            GlobalConf.updateWindowCenter(center.x(), center.y())
            GlobalConf.updateWindowGeometry(self.saveGeometry())

            event.accept()

        else:
            event.ignore()
