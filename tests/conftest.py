"""
Shared fixtures for the BCA-GUIDE tests.

The GUI is created with the offscreen platform (no windows are shown), set BCA_TEST_SHOW=1 to use the normal platform.
The settings are redirected to a temporary ini file and the default save folder to a temporary folder,
so the tests never change the settings or saves of the user.

With --test-dir=DIR (or the environment variable BCA_TEST_DIR) all temporary files of the tests are created in DIR/tmp
(instead of the temporary folder of the system drive) and the simulation runs are kept in DIR/simulation_data.
"""

import os
import sys
import time
import shutil
from pathlib import Path
from typing import Callable, List, Optional

if not os.environ.get('BCA_TEST_SHOW'):
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QMessageBox

SIMULATION_PROGRAMS = ROOT / 'Simulation Programs'
# examples of the GUI (saves/<program>/example_*) and further simulations of the tests (tests/saves/<program>)
SAVES = ROOT / 'saves'
TEST_SAVES = Path(__file__).resolve().parent / 'saves'
DATA = Path(__file__).resolve().parent / 'data'


def pytest_addoption(parser):
    parser.addoption('--simulations', action='store_true', default=False, help='also run the simulation programs (slow)')
    parser.addoption(
        '--simulation-data', action='store', default='',
        help='folder where the simulation runs are kept (with --simulations) and that is checked by test_simulation_data.py'
    )
    parser.addoption(
        '--test-dir', action='store', default=os.environ.get('BCA_TEST_DIR', ''),
        help='folder for all files of the tests: DIR/tmp for temporary files, DIR/simulation_data for the simulation runs '
             '(default: environment variable BCA_TEST_DIR)'
    )


def pytest_configure(config):
    config.addinivalue_line('markers', 'simulation: runs the simulation programs, only executed with --simulations')

    test_dir = config.getoption('--test-dir')
    if test_dir:
        test_dir = Path(test_dir).resolve()
        # the workers of pytest-xdist get their temporary folder from the main process
        if not config.option.basetemp and not hasattr(config, 'workerinput'):
            (test_dir / 'tmp').parent.mkdir(parents=True, exist_ok=True)
            config.option.basetemp = str(test_dir / 'tmp')
        if not config.getoption('--simulation-data'):
            config.option.simulation_data = str(test_dir / 'simulation_data')
    # absolute: the GUI changes the working directory to the folder of a simulation when it runs
    if config.getoption('--simulation-data'):
        config.option.simulation_data = str(Path(config.getoption('--simulation-data')).resolve())


def pytest_collection_modifyitems(config, items):
    if config.getoption('--simulations'):
        return
    skip = pytest.mark.skip(reason='needs --simulations')
    for item in items:
        if 'simulation' in item.keywords:
            item.add_marker(skip)


class FakeCheckBox:
    def isChecked(self):
        return False


class FakeMessageBox:
    def checkBox(self):
        return FakeCheckBox()


def fakeShowMessageBox(*args, **kwargs):
    """Replacement of showMessageBox that does not block and confirms with Ok"""
    return FakeMessageBox(), QMessageBox.StandardButton.Ok


@pytest.fixture(scope='session')
def qapp(tmp_path_factory):
    """QApplication with redirected settings and save folder"""

    app = QApplication.instance() or QApplication(sys.argv)

    import assets.resources  # noqa: F401 (registers resources)
    from Utility.GlobalConf import GlobalConf

    settings_dir = tmp_path_factory.mktemp('settings')
    GlobalConf.settings = QSettings(str(settings_dir / 'settings.ini'), QSettings.Format.IniFormat)
    GlobalConf.save_path = tmp_path_factory.mktemp('saves')
    GlobalConf.theme = 'system'
    GlobalConf.skip_delete_info = True
    yield app


@pytest.fixture(autouse=True)
def no_message_boxes(monkeypatch):
    """Message boxes do not block the tests"""

    import Utility.Dialogs
    import Pages.MainWindow
    import Pages.ProgramPage
    import Pages.ConfigurationPage
    import Pages.ParameterScan
    for module in (Utility.Dialogs, Pages.MainWindow, Pages.ProgramPage, Pages.ConfigurationPage, Pages.ParameterScan):
        monkeypatch.setattr(module, 'showMessageBox', fakeShowMessageBox)


@pytest.fixture
def errors(monkeypatch) -> List[str]:
    """Collects exceptions that are raised in Qt slots (they would only be printed otherwise)"""

    import logging
    import traceback
    collected = []
    monkeypatch.setattr(sys, 'excepthook', lambda t, v, tb: collected.append(''.join(traceback.format_exception(t, v, tb))))

    # exceptions that are caught by the GUI (e.g. in plots) are logged as errors
    class Collector(logging.Handler):
        def emit(self, record):
            collected.append(self.format(record))

    handler = Collector(level=logging.ERROR)
    handler.setFormatter(logging.Formatter('%(levelname)s %(name)s: %(message)s'))
    logging.getLogger().addHandler(handler)
    yield collected
    logging.getLogger().removeHandler(handler)


def pump(app: QApplication, seconds: float = 0.2, until: Optional[Callable[[], bool]] = None):
    """Processes Qt events for some time or until the condition is True"""

    start = time.time()
    while time.time() - start < seconds:
        app.processEvents()
        if until is not None and until():
            return True
        try:
            time.sleep(0.005)
        except OSError:
            # WinError 1450 (not enough system resources) can occur when many simulations run in parallel
            pass
    return until() if until is not None else True


@pytest.fixture
def main_window(qapp, tmp_path):
    """MainWindow without any simulation configurations"""

    import Pages.MainWindow
    from Utility.GlobalConf import GlobalConf
    GlobalConf.save_path = tmp_path / 'saves'
    GlobalConf.save_path.mkdir()

    window = Pages.MainWindow.MainWindow(qapp)
    window.simulation_configs.clear()
    window.simulation_configuration_page.listConfigView()
    pump(qapp)
    yield window

    for sc in window.simulation_configs:
        if sc.tab_widget is not None:
            sc.tab_widget.scan.stop(ask=False)
            if sc.running:
                sc.tab_widget.process.kill()
    window.deleteLater()
    pump(qapp, 0.05)


def addSimulationPage(window, title: str, program: int, folder: Path, binary: Path, version: str, save_folder: Optional[Path] = None):
    """Adds a simulation configuration and its tab to the main window, returns (configuration, page)"""

    from Containers.SimulationConfiguration import SimulationConfiguration
    from Pages.ProgramPage import SimulationPage

    sc = SimulationConfiguration(title, program, folder, binary, version, save_folder=save_folder)
    window.simulation_configs.append(sc)
    page = sc.tab_widget = window.addSimulationTab(SimulationPage(window, sc), title)
    sc.is_active = True
    return sc, page


def copySave(source: Path, destination: Path) -> Path:
    """Copies an example save folder"""

    shutil.copytree(source, destination)
    return destination
