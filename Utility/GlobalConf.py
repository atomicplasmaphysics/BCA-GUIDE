import os
import sys
from pathlib import Path

from PyQt6.QtCore import QDir, QSettings, QLocale


class GlobalConf:
    """
    Class storing global configurations
    """

    # title
    title = 'BCA-GUIDE'

    # version, update with every release (also used in the commit messages "BCA-GUIDE vX.Y.ZZ")
    version = '1.5.12'

    # folder of the program with the manual of the GUI (for the executable of PyInstaller the folder of its extracted files)
    # and of its assets (images)
    program_path = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    assets_path = program_path / 'assets'

    # settings object
    settings = QSettings('TU Wien', title)

    # path of save folder
    save_path_name = 'save_path'
    save_path: Path = Path(settings.value(save_path_name, defaultValue=str(Path(QDir.currentPath()) / 'saves'), type=str) or Path(QDir.currentPath()) / 'saves')
    save_path_exists = bool(settings.value(save_path_name, defaultValue='', type=str))

    # theme: one of THEMES
    THEMES = {
        'system': 'System (default)',
        'light': 'Light',
        'dark': 'Dark',
        'srim': 'SRIM',
    }
    theme_name = 'theme'
    theme = settings.value(theme_name, defaultValue='system', type=str)
    if theme not in THEMES:
        theme = 'system'

    # language
    language = 'en'
    use_default_language_name = 'use_default_language'
    use_default_language = settings.value(use_default_language_name, defaultValue=True, type=bool)

    # preferences
    skip_element_info_name = 'skip_element_info'
    skip_element_info = settings.value(skip_element_info_name, defaultValue=False, type=bool)

    skip_delete_info_name = 'skip_delete_info'
    skip_delete_info = settings.value(skip_delete_info_name, defaultValue=False, type=bool)

    skip_open_multiple_info_name = 'skip_open_multiple_info'
    skip_open_multiple_info = settings.value(skip_open_multiple_info_name, defaultValue=False, type=bool)

    keep_configurations_info_name = 'keep_configurations_info'
    keep_configurations_info = settings.value(keep_configurations_info_name, defaultValue=True, type=bool)

    no_autodetect_version_name = 'no_autodetect_version'
    no_autodetect_version = settings.value(no_autodetect_version_name, defaultValue=False, type=bool)

    # maximum number of simulations of all tabs that run at the same time ("Run all" and parameter scans), by default two
    # processor cores are left for the GUI and the system (new name of the setting, so that the new default applies)
    max_parallel_runs_name = 'max_simultaneous_runs'
    max_parallel_runs = settings.value(max_parallel_runs_name, defaultValue=max(1, (os.cpu_count() or 1) - 2), type=int)

    # window parameters
    window_width_name = 'window_width'
    window_height_name = 'window_height'
    window_center_x_name = 'window_center_x'
    window_center_y_name = 'window_center_y'
    window_geometry_name = 'window_geometry'

    def __init__(self):
        self.setLanguage()

    @staticmethod
    def setLanguage():
        """Sets default language from computer settings"""
        if not GlobalConf.use_default_language:
            GlobalConf.language = 'en'
            return

        pc_lang = QLocale().system().name()
        pc_lang = pc_lang.split('_')[0]
        if pc_lang != GlobalConf.language:
            GlobalConf.language = f'{pc_lang}|{GlobalConf.language}'

    @staticmethod
    def updateSettings():
        """Updates and saves settings object with general variables"""
        update_dict = {
            GlobalConf.save_path_name: str(GlobalConf.save_path),
            GlobalConf.theme_name: GlobalConf.theme,
            GlobalConf.use_default_language_name: GlobalConf.use_default_language,
            GlobalConf.skip_element_info_name: GlobalConf.skip_element_info,
            GlobalConf.skip_delete_info_name: GlobalConf.skip_delete_info,
            GlobalConf.skip_open_multiple_info_name: GlobalConf.skip_open_multiple_info,
            GlobalConf.keep_configurations_info_name: GlobalConf.keep_configurations_info,
            GlobalConf.no_autodetect_version_name: GlobalConf.no_autodetect_version,
            GlobalConf.max_parallel_runs_name: GlobalConf.max_parallel_runs
        }

        for key, value in update_dict.items():
            GlobalConf.settings.setValue(key, value)

        GlobalConf.settings.sync()

    @staticmethod
    def setValue(key: str, value):
        """Sets value to key"""
        GlobalConf.settings.setValue(key, value)
        GlobalConf.settings.sync()

    @staticmethod
    def getValue(key: str, default_value=None, **kwargs):
        """Returns value of key or default_value if key is not set"""
        return GlobalConf.settings.value(key, defaultValue=default_value, **kwargs)

    @staticmethod
    def updateWindowSize(width, height):
        """Updates and saves settings object with window parameters"""
        GlobalConf.settings.setValue(GlobalConf.window_width_name, width)
        GlobalConf.settings.setValue(GlobalConf.window_height_name, height)

        GlobalConf.settings.sync()

    @staticmethod
    def updateWindowCenter(x, y):
        """Updates and saves settings object with window center parameters"""
        GlobalConf.settings.setValue(GlobalConf.window_center_x_name, x)
        GlobalConf.settings.setValue(GlobalConf.window_center_y_name, y)

        GlobalConf.settings.sync()

    @staticmethod
    def updateWindowGeometry(geometry):
        """Saves the geometry of the window (QByteArray of QWidget.saveGeometry(): position, size, display, maximized)"""
        GlobalConf.settings.setValue(GlobalConf.window_geometry_name, geometry)
        GlobalConf.settings.sync()

    @staticmethod
    def getWindowGeometry():
        """Returns the saved geometry of the window (QByteArray) or None"""
        return GlobalConf.settings.value(GlobalConf.window_geometry_name, defaultValue=None)

    @staticmethod
    def getWindowSize():
        """Returns (width, height) of window"""
        return (GlobalConf.settings.value(GlobalConf.window_width_name, defaultValue=1100, type=int),
                GlobalConf.settings.value(GlobalConf.window_height_name, defaultValue=800, type=int))

    @staticmethod
    def getWindowCenter():
        """Returns (x, y) of window center"""
        return (GlobalConf.settings.value(GlobalConf.window_center_x_name, defaultValue=0, type=int),
                GlobalConf.settings.value(GlobalConf.window_center_y_name, defaultValue=0, type=int))
