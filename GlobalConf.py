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


from PyQt5.QtCore import QDir, QSettings, QLocale


class GlobalConf:
    """
    Class storing global configurations
    """

    # title
    title = 'BCA-GUIDE'

    # settings object
    settings = QSettings('TU Wien', title)

    # path of save folder
    save_path_name = 'save_path'
    save_path = settings.value(save_path_name, defaultValue=f'{QDir.currentPath()}/saves', type=str)

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

    # window parameters
    window_width_name = 'window_width'
    window_height_name = 'window_height'

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
            GlobalConf.save_path_name: GlobalConf.save_path,
            GlobalConf.use_default_language_name: GlobalConf.use_default_language,
            GlobalConf.skip_element_info_name: GlobalConf.skip_element_info,
            GlobalConf.skip_delete_info_name: GlobalConf.skip_delete_info,
            GlobalConf.skip_open_multiple_info_name: GlobalConf.skip_open_multiple_info,
            GlobalConf.keep_configurations_info_name: GlobalConf.keep_configurations_info,
            GlobalConf.no_autodetect_version_name: GlobalConf.no_autodetect_version
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
    def getWindowSize():
        """Returns (width, height) of window"""
        return (GlobalConf.settings.value(GlobalConf.window_width_name, defaultValue=1100, type=int),
                GlobalConf.settings.value(GlobalConf.window_height_name, defaultValue=800, type=int))
