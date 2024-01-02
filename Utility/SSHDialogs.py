from sys import argv

from typing import List, Optional, Tuple

from PyQt6.QtWidgets import (QDialog, QApplication, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
                             QListWidget, QListWidgetItem, QSplitter, QWidget, QGroupBox, QMessageBox)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QPainter, QColor

import resources

from Styles import Styles

from Utility.Layouts import VBoxTitleLayout, LineEdit, SpinBox, InputHBoxLayout, SpinBoxRange, PasswordLineEdit, \
    TerminalEditor
from Utility.Dialogs import showMessageBox
from Utility.SSH import SSH, SSHConnection, InteractiveShell


class SSHConnectionsDialog(QDialog):
    """
    Popup window that manages all SSH connections.

    :param parent: parent widget
    :param connections: (optional) list of <SSHConnection>
    """

    def __init__(self, parent, connections: List[SSHConnection] = None):
        super().__init__(parent)

        self.setWindowTitle('SSH Connection Manager')
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint)

        self.current_connection: Optional[SSHConnection] = None
        if connections is None:
            connections = []
        self.connections: List[SSHConnection] = connections

        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.layout)

        # SPLITTER
        self.splitter = QSplitter()
        self.splitter.setChildrenCollapsible(False)
        self.layout.addWidget(self.splitter)

        # EDIT CONFIGURATION
        self.configuration_vbox = VBoxTitleLayout(self, 'SSH Connection Configuration', add_stretch=False)
        self.configuration_group_vbox = QVBoxLayout()

        split = 30

        # Host
        self.hostname = LineEdit(
            placeholder='Hostname or IP',
            parent=self
        )
        self.layout_hostname = InputHBoxLayout(
            'Host:',
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
        self.try_output = QLabel()
        self.try_output.setWordWrap(True)
        self.configuration_group_vbox.addWidget(self.try_output)

        # Save button
        self.save_hbox = QHBoxLayout()
        self.save_hbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.configuration_group_vbox.addLayout(self.save_hbox)

        self.save_hbox.addStretch(1)
        self.save_configuration_button_text = 'Save configuration'
        self.save_configuration_button = QPushButton(self.save_configuration_button_text)
        self.save_configuration_button.setToolTip(
            'Saves the configuration.\nOnly available if "Try connection" succeeds')
        self.save_configuration_button.setDisabled(True)
        self.save_hbox.addWidget(self.save_configuration_button, 4)
        self.save_configuration_button.clicked.connect(self.saveConfigView)
        self.save_hbox.addStretch(1)

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

        # Close button
        self.close_button = QPushButton('Close SSH Connection Manager')
        self.close_button.setToolTip('Closes the SSH Connection Manager')
        self.close_button.clicked.connect(self.accept)
        self.layout.addWidget(self.close_button)

        self.listConfigView()

    def unsavedConfigView(self):
        """Called when the current settings ara changed"""
        self.save_configuration_button.setText(f'{self.save_configuration_button_text} (unsaved)')
        self.try_output.setText('')
        self.save_configuration_button.setDisabled(True)

    def tryConnection(self):
        """Tries connecting. On success save button is enabled"""
        disable_elements = [
            self.hostname,
            self.port,
            self.username,
            self.password,
            self.try_configuration_button,
            self.save_configuration_button
        ]

        hostname = self.hostname.text()
        if not hostname:
            self.try_output.setText('Hostname missing.')
            self.try_output.setStyleSheet(f'color: {Styles.red_hex};')
            return

        username = self.username.text()
        if not username:
            self.try_output.setText('Username missing')
            self.try_output.setStyleSheet(f'color: {Styles.red_hex};')
            return

        password = self.password.text()

        port = self.port.value()
        if not port:
            self.try_output.setText('Invalid port')
            self.try_output.setStyleSheet(f'color: {Styles.red_hex};')
            return

        for element in disable_elements:
            element.setDisabled(True)

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        ssh = SSH.connectPassword(hostname=hostname, username=username, password=password, port=port)
        if isinstance(ssh, str):
            self.try_output.setText(ssh)
            self.try_output.setStyleSheet(f'color: {Styles.red_hex};')
        else:
            self.try_output.setText('Successfully connected')
            self.try_output.setStyleSheet(f'color: {Styles.green_hex};')
            ssh.ssh.close()
            self.save_configuration_button.setEnabled(True)

        QApplication.restoreOverrideCursor()

        for element in disable_elements[:-1]:
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
        self.try_output.setText('Saved')
        self.try_output.setStyleSheet(f'color: {Styles.green_hex};')
        self.save_configuration_button.setDisabled(True)

        current_connection = str(self.current_connection)
        self.listConfigView()

        # highlight saved item in configuration list
        j = 0
        for i in range(self.connection_list.count()):
            if self.connection_list.item(i).text() == current_connection:
                j = i
                break
        self.connection_list.setCurrentRow(j)

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

    def paintEvent(self, event):
        """White background"""
        painter = QPainter(self)
        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(QColor(255, 255, 255))
        painter.drawRect(self.rect())


class FileFolderItem(QListWidgetItem):
    """
    Extends the QListWidgetItem to also display an icon whether it is a file or folder

    :param folder: whether it is a folder
    :param text: text of item
    :param selectable: (optional) whether it is selectable
    """

    def __init__(self, *args, folder: bool = False, text: str = '.', selectable: bool = True, **kwargs):
        self.folder = folder
        super().__init__(*args, **kwargs)
        self.setText(text)

        if self.folder:
            self.setIcon(QIcon(':/icons/open.png'))
        else:
            self.setIcon(QIcon(':/icons/file.png'))

        if not selectable:
            self.setFlags(Qt.ItemFlag.NoItemFlags)


class SSHFilesDialog(QDialog):
    """
    Popup window that displays files on an SSH server

    :param parent: parent widget
    :param ssh: <SSH> connection
    :param title: title of this popup
    :param folders: (optional) whether a folder is returnable
    :param files: (optional) whether a file is returnable
    """

    # TODO: multi-selection

    def __init__(self, parent, ssh: SSH, title: str, folders: bool = True, files: bool = True):
        self.ssh = ssh
        self.folders = folders
        self.files = files
        self.final_path = ''

        super().__init__(parent)

        self.setWindowTitle(title)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint)

        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.server_label = QLabel(f'<b>Server:</b> {str(self.ssh)}')
        self.layout.addWidget(self.server_label)

        self.path_hbox = QHBoxLayout()
        self.path_hbox.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.back_button = QPushButton()
        self.back_button.setIcon(QIcon(':/icons/up.png'))
        self.back_button.setToolTip('Move up a folder')
        self.back_button.clicked.connect(self.chdirBack)
        self.path_hbox.addWidget(self.back_button)

        self.path_label = QLineEdit()
        self.path_label.setToolTip('Current path')
        self.path_label.setReadOnly(True)
        self.path_hbox.addWidget(self.path_label)

        self.layout.addLayout(self.path_hbox)

        self.list_view = QListWidget()
        self.list_view.itemDoubleClicked.connect(lambda i: self.changeDir(i))
        self.layout.addWidget(self.list_view)

        self.info_label = QLabel()
        self.info_label.setStyleSheet(f'color: {Styles.red_hex};')
        self.layout.addWidget(self.info_label)

        self.action_hbox = QHBoxLayout()

        self.cancel_button = QPushButton('Cancel')
        self.cancel_button.setToolTip('Cancel this popup')
        self.cancel_button.clicked.connect(self.accept)
        self.action_hbox.addWidget(self.cancel_button)

        self.open_button = QPushButton('Open')
        self.open_button.setToolTip('Open the selected item')
        self.open_button.clicked.connect(self.openPressed)
        self.action_hbox.addWidget(self.open_button)

        self.layout.addLayout(self.action_hbox)

        self.layout.addStretch()
        self.setLayout(self.layout)

        self.label_timer = QTimer()
        self.label_timer.timeout.connect(self.labelTimeout)

        self.filListView()

    def filListView(self):
        """Populates the ListWidget with items from the current folder"""
        self.path_label.setText(self.ssh.sftp.getcwd())
        self.list_view.clear()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        list_dir = self.ssh.listDir()
        QApplication.restoreOverrideCursor()

        if isinstance(list_dir, str):
            info_item = QListWidgetItem(list_dir)
            info_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_view.addItem(info_item)

        else:
            dirs, files = list_dir
            for d in dirs:
                self.list_view.addItem(FileFolderItem(text=d.filename, folder=True, selectable=True))
            for f in files:
                self.list_view.addItem(FileFolderItem(text=f.filename, folder=False, selectable=self.files))

    def chdir(self, directory: str):
        """Changes working directory in the specified directory"""
        self.ssh.sftp.chdir(directory)
        self.filListView()

    def changeDir(self, item: FileFolderItem):
        """Change directory based on selected item"""
        if item.folder:
            self.chdir(f'{self.ssh.sftp.getcwd()}/{item.text()}')

    def chdirBack(self):
        """Moves a directory up"""
        self.chdir('/' + '/'.join(self.ssh.sftp.getcwd().split('/')[:-1]))

    def setInfoLabel(self, info: str, timeout: int = 5000):
        """Sets info-text for some timeout-time to the info label"""
        self.info_label.setText(info)
        self.label_timer.start(timeout)

    def labelTimeout(self):
        """Called when label has text for timeout-time"""
        self.info_label.setText('')
        self.label_timer.stop()

    def openPressed(self):
        """Sets the selected folder"""
        path = self.ssh.sftp.getcwd()
        selected_items: List[FileFolderItem] = self.list_view.selectedItems()
        if not self.folders and (not selected_items or selected_items[0].folder):
            self.setInfoLabel('No file selected')
            return

        if not self.files and selected_items and not selected_items[0].folder:
            self.setInfoLabel('No folder selected')
            return

        if selected_items:
            path += '/' + selected_items[0].text()

        self.final_path = path
        self.accept()


class SSHSelectionDialog(QDialog):
    """
    Popup window that selects SSH connection.

    :param parent: parent widget
    :param connections: (optional) list of <SSHConnection>
    """

    def __init__(self, parent, connections: List[SSHConnection] = None):
        super().__init__(parent)

        self.setWindowTitle('SSH Connection Manager')
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint)

        self.current_connection: Optional[SSHConnection] = None
        if connections is None:
            connections = []
            # TODO: no connection set up, please set up connection in SSH->connections
        self.connections: List[SSHConnection] = connections


class SSHTerminalWindow(QDialog):
    """
    Popup window that provides terminal for the SSH connection.

    :param parent: parent widget
    :param connection: <SSHConnection>
    """

    def __init__(self, parent, connection: SSHConnection):
        super().__init__(parent)

        self.setWindowTitle(f'SSH Terminal for "{str(connection)}"')
        self.setWindowFlags(Qt.WindowType.Window)

        self.ssh_client = SSH.connectSSHConnection(connection)
        self.interactive_shell = InteractiveShell(self.ssh_client)
        self.interactive_shell.recv_ready.connect(self.updateOutput)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.layout.setContentsMargins(0, 0, 0, 0)

        self.terminal = TerminalEditor(self, border=False)
        self.terminal.enterSignal.connect(self.execCommand)
        self.layout.addWidget(self.terminal)

        self.showMaximized()

    def updateOutput(self):
        """Updates terminal"""
        self.terminal.insertPlainText(self.interactive_shell.readStdout().replace('\r', ''))

    def execCommand(self, cmd: str):
        """Executes a command"""
        try:
            self.interactive_shell.execCommand(cmd)
            if cmd == 'exit':
                self.close()

        except OSError as error:
            _, button = showMessageBox(
                self,
                QMessageBox.Icon.Warning,
                'Terminal Error',
                f'Warning: {error}',
                info_message='Close terminal?',
                standard_buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if button == QMessageBox.StandardButton.Yes:
                self.close()

    def closeEvent(self, event):
        self.ssh_client.close()
        event.accept()


def filesDialogSSH(ssh_connection: SSHConnection, parent=None, title: str = 'Choose file',
                   path: str = '', folders: bool = True, files: bool = True) -> Tuple[str, str]:
    """
    Opens an SSH file dialog and returns the selected item

    :param ssh_connection: SSHConnection
    :param parent: (optional) parent widget
    :param title: (optional) title of file dialog popup
    :param path: (optional) starting path
    :param folders: whether folders are selectable
    :param files: whether files are selectable

    :return: (path of selected file or folder, error)
    """

    # TODO: multi-selection

    # try connecting
    with SSH.connectSSHConnection(ssh_connection) as ssh:
        # connection failed
        if isinstance(ssh, str):
            return '', ssh

        # open filedialog
        files_dialog = SSHFilesDialog(parent=parent, ssh=ssh, title=title, folders=folders, files=files)

        if path:
            files_dialog.chdir(path)

        if files_dialog.exec():
            return files_dialog.final_path, ''


# TODO: remove this
def test_ssh_files():
    ssh_connections = SSHConnection('128.131.53.79', 'ag-aumayr', '112sos911')
    path = '/home/ag-aumayr/Alexander_Redl/SDTrimSP/saves'

    path, error = filesDialogSSH(
        ssh_connection=ssh_connections,
        title='Choose folder',
        files=True,
        folders=False,
        path=path
    )
    print(f'path: {path}')
    print(f'error: {error}')


# TODO: remove this
def test_ssh_connection_manager():
    ssh_connections = [SSHConnection('128.131.53.79', 'ag-aumayr', '112sos911')]
    SSHConnectionsDialog(None, ssh_connections).exec()


# TODO: remove this
def test_ssh_connection_selection():
    ssh_connections = [SSHConnection('128.131.53.79', 'ag-aumayr', '112sos911')]


# TODO: remove this
def test_ssh_terminal():
    ssh_connection = SSHConnection('128.131.53.79', 'ag-aumayr', '112sos911')
    SSHTerminalWindow(None, ssh_connection).exec()


# TODO: remove this
if __name__ == '__main__':
    app = QApplication(argv)
    app.processEvents()

    # test_ssh_connection_manager()
    # test_ssh_files()
    # test_ssh_connection_selection()
    test_ssh_terminal()

    app.exec()
