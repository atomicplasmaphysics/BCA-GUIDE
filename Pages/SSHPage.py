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


from __future__ import annotations
from typing import Optional, List, TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QSplitter, QWidget, QPushButton, QListWidget, QLabel, QListWidgetItem,
    QVBoxLayout, QGroupBox, QHBoxLayout, QApplication, QMessageBox
)

from Styles import Styles

from Utility.Layouts import (
    TabWithToolbar, VBoxTitleLayout, InputHBoxLayout, LineEdit, SpinBox,
    SpinBoxRange, PasswordLineEdit, HBoxSeperatorLayout
)
from Utility.SSH import SSH, SSHConnection
from Utility.SSHDialogs import SSHTerminalWindow
from Utility.Dialogs import showMessageBox

# avoiding circular import, but still get type hinting functionality
if TYPE_CHECKING:
    from MainWindow import MainWindow


class SSHPage(TabWithToolbar):
    """
    Page for configuring SSH parameters
    """

    def __init__(self, main_window: MainWindow):
        """
        :param main_window: main Window object
        """

        super().__init__()
        self.main_window = main_window

        self.current_connection: Optional[SSHConnection] = None
        # TODO: change connections
        self.connections: List[SSHConnection] = [SSHConnection('128.131.53.79', 'ag-aumayr', '112sos911')]

        # SPLITTER
        self.splitter = QSplitter()
        self.splitter.setChildrenCollapsible(False)
        self.page.addWidget(self.splitter)

        # EDIT CONFIGURATION
        self.configuration_vbox = VBoxTitleLayout(self, 'SSH Connection Configuration', add_stretch=False)
        self.configuration_group_vbox = QVBoxLayout()

        split = 10

        # Host
        self.hostname = LineEdit(
            placeholder='Hostname or IP',
            parent=self
        )
        self.layout_hostname = InputHBoxLayout(
            'Hostname:',
            self.hostname,
            tooltip='Enter hostname or IP',
            split=split
        )
        self.hostname.textChanged.connect(self.unsavedConfigView)
        self.configuration_group_vbox.addLayout(self.layout_hostname)

        # Port
        self.port = SpinBox(
            default=22,
            input_range=SpinBoxRange.ONE_INF,
            parent=self
        )
        self.layout_port = InputHBoxLayout(
            'Port:',
            self.port,
            tooltip='Enter port',
            split=split
        )
        self.port.textChanged.connect(self.unsavedConfigView)
        self.configuration_group_vbox.addLayout(self.layout_port)

        # Username
        self.username = LineEdit(
            placeholder='Username',
            parent=self
        )
        self.layout_username = InputHBoxLayout(
            'Username:',
            self.username,
            tooltip='Enter username',
            split=split
        )
        self.username.textChanged.connect(self.unsavedConfigView)
        self.configuration_group_vbox.addLayout(self.layout_username)

        # Password
        self.password = PasswordLineEdit(
            placeholder='Password',
            parent=self
        )
        self.layout_password = InputHBoxLayout(
            'Password:',
            self.password,
            tooltip='Enter password',
            split=split
        )
        self.password.textChanged.connect(self.unsavedConfigView)
        self.configuration_group_vbox.addLayout(self.layout_password)

        # Description of try connection
        self.try_description = QLabel('<i>Before a SSH connection can be saved, it has to successfully be tested first. Verify the SSH connection by clicking the "Try connection" button. On success the "Save configuration" button will be enabled.</i>')
        self.try_description.setWordWrap(True)
        self.configuration_group_vbox.addWidget(self.try_description)

        # Try connection button
        self.try_hbox = QHBoxLayout()
        self.try_hbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.configuration_group_vbox.addLayout(self.try_hbox)

        self.try_hbox.addStretch(1)
        self.try_configuration_button = QPushButton('Try connection')
        self.try_configuration_button.setToolTip('Tries to connect to server')
        self.try_hbox.addWidget(self.try_configuration_button, 4)
        self.try_configuration_button.clicked.connect(self.tryConnection)
        self.try_hbox.addStretch(1)

        # Try output
        self.try_output = QLabel('-')
        self.try_output.setStyleSheet(f'color: {Styles.red_hex};')
        self.try_output.setWordWrap(True)
        self.layout_try_output = InputHBoxLayout(
            'Connection status:',
            self.try_output,
            tooltip='Status of connection. Updated once the "Try connection" button is pressed.',
            split=split
        )
        self.configuration_group_vbox.addLayout(self.layout_try_output)

        # Horizontal separator
        self.hbox_separate = HBoxSeperatorLayout('On successful connection')
        self.configuration_group_vbox.addLayout(self.hbox_separate)

        # Save button
        self.save_hbox = QHBoxLayout()
        self.save_hbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.configuration_group_vbox.addLayout(self.save_hbox)

        self.save_hbox.addStretch(1)
        self.save_configuration_button_text = 'Save configuration'
        self.save_configuration_button = QPushButton(self.save_configuration_button_text)
        self.save_configuration_button.setToolTip('Saves the configuration.\nOnly available if "Try connection" succeeds')
        self.save_configuration_button.setDisabled(True)
        self.save_hbox.addWidget(self.save_configuration_button, 4)
        self.save_configuration_button.clicked.connect(self.saveConfigView)
        self.save_hbox.addStretch(1)

        # Terminal button
        self.terminal_hbox = QHBoxLayout()
        self.terminal_hbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.configuration_group_vbox.addLayout(self.terminal_hbox)

        self.terminal_hbox.addStretch(1)
        self.terminal_button = QPushButton('Open terminal')
        self.terminal_button.setToolTip('Opens terminal for the configuration.\nOnly available if "Try connection" succeeds')
        self.terminal_button.setDisabled(True)
        self.terminal_hbox.addWidget(self.terminal_button, 4)
        self.terminal_button.clicked.connect(self.openTerminal)
        self.terminal_hbox.addStretch(1)

        # Stretch to bottom
        self.configuration_group_vbox.addStretch(1)
        self.configuration_group_vbox.setAlignment(Qt.AlignmentFlag.AlignRight)

        # Add a parent to the configuration_vbox and add that to the splitter
        self.configuration_vbox_parent = QWidget(self)
        self.configuration_group = QGroupBox(self)
        self.configuration_group.setLayout(self.configuration_group_vbox)
        self.configuration_vbox.addWidget(self.configuration_group)
        self.configuration_vbox_parent.setLayout(self.configuration_vbox)
        self.splitter.addWidget(self.configuration_vbox_parent)

        # SELECT CONFIGURATION
        self.connections_vbox = VBoxTitleLayout(self, 'List of SSH Connections', add_stretch=False)
        self.connections_list_vbox = QVBoxLayout()

        # Information
        self.list_label = QLabel('Click to edit connection')
        self.list_label.setMaximumHeight(20)
        self.connections_list_vbox.addWidget(self.list_label, Qt.AlignmentFlag.AlignLeft)

        # List of SSH configurations
        self.connection_list = QListWidget()
        self.connection_list.setStyleSheet(Styles.list_style)
        self.connections_list_vbox.addWidget(self.connection_list)
        self.connection_list.currentItemChanged.connect(self.loadConfigView)

        self.new_connection_text = 'Add new connection'

        # Stretch to bottom
        self.connections_list_vbox.setAlignment(Qt.AlignmentFlag.AlignRight)

        # Delete button
        self.delete_hbox = QHBoxLayout()
        self.connections_list_vbox.addLayout(self.delete_hbox)

        self.delete = QPushButton('Delete connection')
        self.delete.setToolTip('Deletes the selected connection')
        self.delete_hbox.addWidget(self.delete)
        self.delete.clicked.connect(self.deleteConfigView)
        self.delete.setDisabled(True)

        # Add a parent to the simulationConfigurationListLayout and add that to the splitter (=self)
        self.connections_list_parent = QWidget(self)
        self.connections_list_group = QGroupBox(self)
        self.connections_list_group.setLayout(self.connections_list_vbox)
        self.connections_vbox.addWidget(self.connections_list_group)
        self.connections_list_parent.setLayout(self.connections_vbox)
        self.splitter.addWidget(self.connections_list_parent)

        # Division between columns
        self.splitter.setStretchFactor(0, 70)
        self.splitter.setStretchFactor(1, 30)

        # clear everything on startup
        self.listConfigView()

    def unsavedConfigView(self):
        """Called when the current settings ara changed"""

        self.save_configuration_button.setText(f'{self.save_configuration_button_text} (unsaved)')
        self.try_output.setText('-')
        self.save_configuration_button.setDisabled(True)
        self.terminal_button.setDisabled(True)

    def tryConnection(self):
        """Tries connecting. On success save button is enabled"""

        disable_elements = [
            self.hostname,
            self.port,
            self.username,
            self.password,
            self.try_configuration_button,
            self.save_configuration_button,
            self.terminal_button
        ]

        hostname = self.hostname.text()
        if not hostname:
            showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                '"Hostname" can not be empty'
            )
            return

        username = self.username.text()
        if not username:
            showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                '"Username" can not be empty'
            )
            return

        password = self.password.text()

        port = self.port.value()
        if not port:
            showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Warning!',
                'Invalid port'
            )
            return

        for element in disable_elements:
            element.setDisabled(True)

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        ssh_connection = SSHConnection(
            hostname=hostname,
            username=username,
            password=password,
            port=port
        )
        ssh = SSH.connectSSHConnection(ssh_connection)

        if isinstance(ssh, str):
            self.try_output.setText(ssh)
            self.try_output.setStyleSheet(f'color: {Styles.red_hex};')

        else:
            self.try_output.setText('Successfully connected')
            self.try_output.setStyleSheet(f'color: {Styles.green_hex};')
            self.current_connection = ssh_connection
            ssh.ssh.close()
            self.save_configuration_button.setEnabled(True)
            self.terminal_button.setEnabled(True)

        QApplication.restoreOverrideCursor()

        for element in disable_elements[:-2]:
            element.setEnabled(True)

    def saveConfigView(self):
        """Save configuration"""

        hostname = self.hostname.text()
        username = self.username.text()
        password = self.password.text()
        port = self.port.value()

        if self.current_connection is None:
            self.current_connection = SSHConnection(
                hostname=hostname,
                username=username,
                password=password,
                port=port
            )
            self.connections.append(self.current_connection)

        else:
            self.current_connection.hostname = hostname
            self.current_connection.username = username
            self.current_connection.password = password
            self.current_connection.port = port

        self.save_configuration_button.setText(self.save_configuration_button_text)

        current_connection = str(self.current_connection)
        self.listConfigView()

        self.main_window.writeStatusBar('SSH configuration saved!')

        # highlight saved item in configuration list
        j = 0
        for i in range(self.connection_list.count()):
            if self.connection_list.item(i).text() == current_connection:
                j = i
                break
        self.connection_list.setCurrentRow(j)

        self.try_output.setText('Saved')
        self.try_output.setStyleSheet(f'color: {Styles.green_hex};')

        self.save_configuration_button.setEnabled(True)
        self.terminal_button.setEnabled(True)

    def listConfigView(self):
        """List configuration from self.current_connection"""

        self.connection_list.clear()
        self.connection_list.addItem(self.new_connection_text)
        for connection in self.connections:
            self.connection_list.addItem(QListWidgetItem(str(connection)))
        self.connection_list.setCurrentRow(0)

    def loadConfigView(self, list_item):
        """
        Load configuration from self.connections into configuration editor

        :param list_item: selected item in list
        """

        if list_item is None:
            return

        connection_name = list_item.text()
        self.hostname.setFocus()

        # If 'Add new connection' is pressed
        if connection_name == self.new_connection_text:
            self.clearConfigView()
            self.current_connection = None
            self.delete.setDisabled(True)
            self.save_configuration_button.setText(self.save_configuration_button_text)
            return

        else:
            self.delete.setEnabled(True)

        # Try to get SSHConnection
        for connection in self.connections:
            if str(connection) == connection_name:
                self.current_connection = connection
                break

        # Extract variables
        if self.current_connection is not None:
            self.hostname.setText(self.current_connection.hostname)
            self.username.setText(self.current_connection.username)
            self.password.setText(self.current_connection.password)
            self.port.setValue(self.current_connection.port)
            self.save_configuration_button.setText(self.save_configuration_button_text)

    def clearConfigView(self):
        """Reset configuration editor"""

        self.hostname.setText('')
        self.username.setText('')
        self.password.setText('')
        self.port.setValue(self.port.default)

    def deleteConfigView(self):
        """Delete configuration from self.connections and reset configuration editor"""

        if self.current_connection is not None:
            self.connections.remove(self.current_connection)
        self.current_connection = None
        self.clearConfigView()
        self.listConfigView()

    def openTerminal(self):
        """Opens connection in terminal"""

        if self.current_connection is None:
            return

        SSHTerminalWindow(self, self.current_connection).show()
