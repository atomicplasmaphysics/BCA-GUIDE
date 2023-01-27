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


from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QGridLayout, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget, QComboBox,
    QLineEdit, QWidget, QDialogButtonBox, QCheckBox, QPushButton, QFileDialog
)
from PyQt5.QtGui import QPixmap

from GlobalConf import GlobalConf

from Simulations.SimulationsList import SimulationsList


class ManualDialog(QDialog):
    """
    Dialog for quick manual

    :param parent: parent widget
    """

    class ManualAddSimulation(QLabel):
        """
        Manual widget for adding a simulation

        :param parent: parent widget
        """

        name = 'Add a new configuration'

        def __init__(self, parent):
            super().__init__(parent)
            manual = (
                '1) Open the <b>Configurations</b> tab<br>' +
                '2) Select <b>Add new configuration</b> from the <i>List of Simulation Configurations</i><br>' +
                '3) Provide a title in the <b>Configuration title</b> field<br>' +
                '4) Select a program from the <b>Simulation program</b> list<br>' +
                '5) Select the <b>Simulation folder</b> by clicking on the button with three dots<br>' +
                '6) Select the <b>Simulation binary</b> by clicking on the button with three dots<br>' +
                '7) Check if the <b>Detected simulation</b> matches the desired simulation<br>'
                '8) Confirm the newly added configuration by pressing <b>Save configuration</b>'
            )
            self.setText(manual)

    class ManualEditSimulation(QLabel):
        """
        Manual widget for editing a simulation

        :param parent: parent widget
        """

        name = 'Edit an existing configuration'

        def __init__(self, parent):
            super().__init__(parent)
            manual = (
                '1) Open the <b>Configurations</b> tab<br>' +
                '2) Select the simulation in the <b>List of Simulation Configurations</b><br>' +
                '3) Make the changes in the <b>Simulation Configuration</b><br>'
                '4) Confirm the edited configuration by pressing <b>Save configuration</b>'
            )
            self.setText(manual)

    class ManualImportSimulation(QWidget):
        """
        Manual widget for converting other simulation files

        :param parent: parent widget
        """

        name = 'Convert simulation input files'

        def __init__(self, parent):
            super().__init__(parent)
            icon_size = 30
            self.layout = QVBoxLayout()
            self.layout.addWidget(QLabel(
                'Example: Convert input file for simulation X into input file for simulation Y:<br><br>' +
                '1) Create configurations with the simulation programs X and Y<br>' +
                '2) Open the input file in simulation X'
            ))
            label_open = QLabel('', self)
            label_open.setPixmap(QPixmap(':/icons/open.png').scaled(icon_size, icon_size, transformMode=Qt.SmoothTransformation))
            self.layout.addWidget(label_open)
            self.layout.addWidget(QLabel(
                '3) Save the simulation X'
            ))
            label_save = QLabel('', self)
            label_save.setPixmap(QPixmap(':/icons/save.png').scaled(icon_size, icon_size, transformMode=Qt.SmoothTransformation))
            self.layout.addWidget(label_save)
            self.layout.addWidget(QLabel(
                '4) Change to simulation Y and click the convert button'
            ))
            label_import = QLabel('', self)
            label_import.setPixmap(QPixmap(':/icons/convert.png').scaled(icon_size, icon_size, transformMode=Qt.SmoothTransformation))
            self.layout.addWidget(label_import)
            self.layout.addWidget(QLabel(
                '5) Navigate to the folder, where simulation X was saved and select the <b>input.json</b> file<br>' +
                '6) Select a folder where simulation Y will be saved<br>' +
                '7) Not convertable input parameter are highlighted red in simulation Y<br>' +
                '8) Adjust highlighted parameters and save the simulation Y'
            ))

            self.setLayout(self.layout)

    manualWidgetList = [ManualImportSimulation, ManualAddSimulation, ManualEditSimulation]

    def __init__(self, parent):
        super().__init__(parent)
        self.parent_widget = parent

        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setWindowTitle('Manual')

        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignTop)

        # manual selector
        self.layout_manual_selector = QHBoxLayout()
        self.layout_manual_selector.setAlignment(Qt.AlignLeft)
        self.layout_manual_selector.addWidget(QLabel('Show manual for:'))
        self.manual_selector = QComboBox()
        self.layout_manual_selector.addWidget(self.manual_selector)
        self.manual_selector.currentIndexChanged.connect(lambda i: self.stack.setCurrentIndex(i))
        self.layout.addLayout(self.layout_manual_selector)

        # stack of widgets
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)

        self.layout.addStretch()
        self.setLayout(self.layout)

        for manual in self.manualWidgetList:
            manual_name = 'NAME MISSING'
            if hasattr(manual, 'name'):
                manual_name = manual.name
            self.manual_selector.addItem(manual_name)

            parent = QWidget()
            parent_layout = QVBoxLayout()
            parent_layout.addWidget(manual(self.parent_widget))
            parent_layout.addStretch()
            parent.setLayout(parent_layout)
            self.stack.addWidget(parent)


class PreferencesDialog(QDialog):
    """
    Dialog for preferences

    :param parent: parent widget
    """

    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint)
        self.setWindowTitle('Preferences')

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Path (relative)
        self.save_path_hbox = QHBoxLayout()
        self.save_path_hbox.addWidget(QLabel('Save folder:', self))
        self.label_path = QLineEdit(self)
        self.label_path.setPlaceholderText('Select path to the default save folder')
        self.label_path.setReadOnly(True)
        self.label_path.setMinimumWidth(300)
        self.label_path.setText(GlobalConf.save_path)
        self.label_path.setToolTip('The path to the default save folder, where all output data will be stored')
        self.save_path_hbox.addWidget(self.label_path)
        self.button_path = QPushButton('...', self)
        self.button_path.setMinimumSize(40, 10)
        self.button_path.setMaximumSize(40, 30)
        self.save_path_hbox.addWidget(self.button_path)
        self.button_path.clicked.connect(lambda: self.selectSaveFolder())
        self.layout.addLayout(self.save_path_hbox)

        # Default element table warning
        self.skip_element_info = QCheckBox('Skip the element table warning when the used simulation does not provide used element data', self)
        self.skip_element_info.setChecked(GlobalConf.skip_element_info)
        self.layout.addWidget(self.skip_element_info)

        # File deletion warning
        self.skip_delete_info = QCheckBox('Skip the file deletion warning when running a simulation', self)
        self.skip_delete_info.setChecked(GlobalConf.skip_delete_info)
        self.layout.addWidget(self.skip_delete_info)

        # Load closed configurations
        self.keep_configurations_info = QCheckBox('Keep configurations in all simulation tabs when open GUI again', self)
        self.keep_configurations_info.setChecked(GlobalConf.keep_configurations_info)
        self.layout.addWidget(self.keep_configurations_info)

        # Open in multiple tabs warning (not needed)
        """
        self.skip_open_multiple_info = QCheckBox('Skip the information, that opening a configuration in all tabs will create multiple copies', self)
        self.skip_open_multiple_info.setChecked(GlobalConf.skip_open_multiple_info)
        self.layout.addWidget(self.skip_open_multiple_info)
        """

        # Open in multiple tabs warning
        self.use_default_language = QCheckBox('Use system language for elements (if supported by simulation)', self)
        self.use_default_language.setChecked(GlobalConf.use_default_language)
        self.layout.addWidget(self.use_default_language)

        # Open in multiple tabs warning
        self.no_autodetect_version = QCheckBox('Do not warn if other simulation was detected than selected', self)
        self.no_autodetect_version.setChecked(GlobalConf.no_autodetect_version)
        self.layout.addWidget(self.no_autodetect_version)

        # Ok button
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        self.button_box.accepted.connect(self.updatePreferences)
        self.layout.addWidget(self.button_box)

        self.resize(parent.width() // 2, self.height())

    def selectSaveFolder(self):
        """Select a default save folder"""
        start_dir = GlobalConf.save_path
        folder_dir = QFileDialog.getExistingDirectory(self, 'Select the default save folder', start_dir)

        if folder_dir:
            self.label_path.setText(folder_dir)

    def updatePreferences(self):
        """Updates all preferences"""

        GlobalConf.save_path = self.label_path.text()

        GlobalConf.skip_element_info = self.skip_element_info.isChecked()
        GlobalConf.skip_delete_info = self.skip_delete_info.isChecked()
        # GlobalConf.skip_open_multiple_info = self.skip_open_multiple_info.isChecked()
        GlobalConf.keep_configurations_info = self.keep_configurations_info.isChecked()
        GlobalConf.no_autodetect_version = self.no_autodetect_version.isChecked()

        GlobalConf.use_default_language = self.use_default_language.isChecked()
        GlobalConf.setLanguage()

        self.accept()


class AboutDialog(QDialog):
    """
    Dialog for about-information

    :param parent: parent widget
    """

    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setWindowTitle(f'About {GlobalConf.title}')

        self.layout = QGridLayout()
        self.setLayout(self.layout)

        # GUI about
        self.title_label_gui = QLabel(GlobalConf.title, self)
        self.title_label_gui.setStyleSheet('font-size: 16px; font-weight: bold;')
        self.title_label_gui.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.title_label_gui, 0, 0, 1, 2)

        self.iap_logo = QLabel('', self)
        self.iap_logo.setPixmap(QPixmap(':icons/aboutlogo_iap.png').scaled(280, 113, transformMode=Qt.SmoothTransformation))
        self.layout.addWidget(self.iap_logo, 1, 0)

        self.iap_label = QLabel(
            'Alexander Redl <a href="mailto:redl@iap.tuwien.ac.at">redl@iap.tuwien.ac.at</a><br>' +
            'David Weichselbaum <a href="mailto:weichselbaum@iap.tuwien.ac.at">weichselbaum@iap.tuwien.ac.at</a><br>' +
            'Paul S. Szabo <a href="mailto:szabo@iap.tuwien.ac.at">szabo@iap.tuwien.ac.at</a><br>' +
            '(now at University of California, Berkeley, <a href="mailto:szabo@berkeley.edu">szabo@berkeley.edu</a>)<br>' +
            'Herbert Biber <a href="mailto:biber@iap.tuwien.ac.at">biber@iap.tuwien.ac.at</a><br>' +
            'Christian Cupak<br>' +
            'Rihard A. Wilhelm<br>' +
            'Friedrich Aumayr<br><br>' +
            'Licensed under the <a href="https://www.gnu.org/licenses/gpl-3.0.html">GPLv3</a> license<br><br>' +
            '<a href="https://www.iap.tuwien.ac.at">https://www.iap.tuwien.ac.at</a><br>',
            self
        )
        self.iap_label.setOpenExternalLinks(True)
        self.layout.addWidget(self.iap_label, 1, 1)

        self.empty = QWidget(self)
        self.empty.setFixedHeight(75)
        self.layout.addWidget(self.empty, 2, 0, 2, 2)

        # load simulation abouts
        simulation_list = SimulationsList()
        layout_index = 3

        for title, logo, about in zip(
            simulation_list.simulation_program_names,
            simulation_list.simulation_program_logo,
            simulation_list.simulation_program_about
        ):
            title_label = QLabel(title, self)
            title_label.setStyleSheet('font-size: 16px; font-weight: bold;')
            title_label.setAlignment(Qt.AlignCenter)

            self.layout.addWidget(title_label, layout_index, 0, 1, 2)
            layout_index += 1

            if logo:
                logo_label = QLabel('', self)
                logo_label.setPixmap(QPixmap(logo).scaled(280, 100, transformMode=Qt.SmoothTransformation))
                self.layout.addWidget(logo_label, layout_index, 0)

            information_label = QLabel(about.strip().replace('\n', '<br>'), self)
            information_label.setOpenExternalLinks(True)
            self.layout.addWidget(information_label, layout_index, 1)
            layout_index += 1

        self.resize(parent.width() // 2, self.height())
