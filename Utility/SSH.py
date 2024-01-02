from __future__ import annotations

from typing import Union, Tuple, Optional, List
from stat import S_ISDIR
from socket import gaierror

from paramiko import SSHClient, AutoAddPolicy, AuthenticationException, SFTPAttributes
from paramiko.ssh_exception import NoValidConnectionsError
from paramiko.channel import ChannelStdinFile, ChannelFile, ChannelStderrFile


from PyQt6.QtCore import QProcess, QTimer, pyqtSignal, QObject


class SSHConnection:
    """
    Class that stores the configuration for an SSH connection

    :param hostname: hostname or IP of server
    :param username: username to login
    :param password: (optional) password to login
    :param port: (optional) ssh port
    """

    def __init__(self, hostname: str, username: str, password: str = '', port: int = 22):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port

    def __str__(self) -> str:
        """Stringify configuration"""
        return f'{self.username}@{self.hostname}:{self.port}'


class SSH:
    """
    Provides an SSH connection and SFTP connection to a server.
    Instances can be created with the class methods SSH.connectPassword() or SSH.connectSSHConnection()

    :param ssh_client: SSHClient
    """

    def __init__(self, ssh_client: SSHClient):
        self.ssh = ssh_client
        self.sftp = self.ssh.open_sftp()
        self.sftp.chdir('.')
        self.start_dir = self.sftp.getcwd()

        self.stdin: Optional[ChannelStdinFile] = None
        self.stdout: Optional[ChannelFile] = None
        self.stderr: Optional[ChannelStderrFile] = None

        self.username = ''
        self.hostname = ''
        self.port = 0

    @classmethod
    def connectPassword(cls, hostname: str, username: str, password: str = None, port: int = 22) -> Union[SSH, str]:
        """Creates <SSH> from hostname, username, password and port"""
        ssh_client = SSHClient()
        ssh_client.set_missing_host_key_policy(AutoAddPolicy())
        try:
            ssh_client.connect(hostname=hostname, port=port, username=username, password=password)
            ssh = cls(ssh_client)
            ssh.username = username
            ssh.hostname = hostname
            ssh.port = port
            return ssh
        except AuthenticationException:
            return f'Authentication failed for username "{username}".'
        except TimeoutError:
            return f'Timeout: No server was found on hostname "{hostname}".'
        except gaierror:
            return f'Address of hostname "{hostname}" could not be resolved.'
        except NoValidConnectionsError:
            return 'This is not a valid connection.'
        except UnicodeError:
            return f'Hostname "{hostname}" is not valid or too long.'
        except BaseException as exception:
            return f'General exception: {exception}'

    @classmethod
    def connectSSHConnection(cls, connection: SSHConnection) -> Union[SSH, str]:
        """Creates <SSH> from <SSHConnection>"""
        return SSH.connectPassword(
            hostname=connection.hostname,
            username=connection.username,
            password=connection.password,
            port=connection.port
        )

    def execCommand(self, cmd: str) -> Tuple[ChannelStdinFile, ChannelFile, ChannelStderrFile]:
        """Executes command"""
        self.stdin, self.stdout, self.stderr = self.ssh.exec_command(command=cmd)
        return self.stdin, self.stdout, self.stderr

    def readStdout(self) -> bytes:
        """Returns stdout without blocking"""
        if not self.stdout.channel.exit_status_ready():
            b_list = []
            while self.stdout.channel.recv_ready():
                b_list.append(self.stdout.channel.recv(1024))
            return b''.join(b_list)

        else:
            return self.stdout.read()

    def listDir(self, directory: str = '') -> Union[Tuple[List[SFTPAttributes], List[SFTPAttributes]], str]:
        """Lists directory"""
        old_directory = self.sftp.getcwd()
        if not directory:
            directory = old_directory

        try:
            self.sftp.chdir(directory)
            folder_contents = self.sftp.listdir_attr()
        except FileNotFoundError:
            self.sftp.chdir(old_directory)
            return 'File Not Found'
        except (PermissionError, IOError):
            self.sftp.chdir(old_directory)
            return 'No Permission'

        folder_contents.sort(key=lambda i: i.filename.lower())
        dirs = []
        files = []

        # Iterate over the folder contents
        for item in folder_contents:
            if S_ISDIR(item.st_mode):
                dirs.append(item)
            else:
                files.append(item)

        return dirs, files

    def close(self):
        """Closes SSH connection"""
        self.sftp.close()
        self.ssh.close()

    def __enter__(self):
        """Entering point in contextmanager"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit point of contextmanager"""
        self.close()

    def __str__(self):
        """String version of SSH connection"""
        if not self.hostname or not self.username or not self.port:
            return 'Not initialized'
        return f'{self.username}@{self.hostname}:{self.port}'


class InteractiveShell(QObject):
    """
    Provides a basic interactive SSH shell.

    :param ssh: SSH
    """

    recv_ready = pyqtSignal(bool)

    def __init__(self, ssh: SSH):
        super().__init__()

        self.ssh_client = ssh.ssh
        self.channel = self.ssh_client.get_transport().open_session()
        self.channel.get_pty()
        self.channel.invoke_shell()

        # timer for checking if we have output
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.updateLoop)
        self.update_timer.start(100)

    def execCommand(self, cmd: str):
        """Executes a given command"""
        self.channel.send(f'{cmd}\n'.encode())

    def readStdout(self) -> str:
        """Returns current stdout"""
        b_list = []
        while self.channel.recv_ready():
            b_list.append(self.channel.recv(1024))
        b_array = b''.join(b_list)
        std_out = b_array.decode()
        return std_out

    def updateLoop(self):
        """Continuously called to check if we have output"""
        if self.channel.recv_ready():
            self.recv_ready.emit(True)


class SSHProcess(QProcess):
    """
    Extends the QProcess for an SSH process

    :param ssh: initialized <SSH> class
    :param parent: (optional) parent widget
    """

    def __init__(self, ssh: SSH, parent=None):
        super().__init__(parent)
        self.ssh = ssh

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.updateLoop)

    def start(self, command: str, arguments=None, mode=None):
        """Starts executing given command"""
        self.ssh.execCommand(command)
        self.update_timer.start(100)

    def updateLoop(self):
        """Continuously called during execution of command"""
        if not self.ssh.stdout.channel.exit_status_ready():
            if self.ssh.stdout.channel.recv_ready():
                self.readyRead.emit()
        else:
            self.update_timer.stop()
            self.readyRead.emit()

            exit_code = self.ssh.stdout.channel.recv_exit_status()
            exit_status = QProcess.ExitStatus.CrashExit
            if not self.ssh.stderr.read().decode():
                exit_status = QProcess.ExitStatus.NormalExit

            self.finished.emit(exit_code, exit_status)

    def readAll(self) -> bytes:
        """Reads output of command"""
        return self.ssh.readStdout()


# TODO: remove this
def main():
    ssh_connection = SSHConnection('128.131.53.79', 'ag-aumayr', '112sos911')
    with SSH.connectSSHConnection(ssh_connection) as ssh:
        dirs, files = ssh.listDir()
        for d in dirs:
            print(d.filename)
        for f in files:
            print(f.filename)


# TODO: remove this
if __name__ == '__main__':
    main()
