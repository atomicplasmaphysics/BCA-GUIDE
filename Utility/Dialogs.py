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


from urllib.parse import urlparse
from urllib.request import urlretrieve

from PyQt5.QtCore import QFileInfo, Qt, QUrl
from PyQt5.QtGui import QFont, QDesktopServices
from PyQt5.QtWidgets import (
    QCheckBox, QMessageBox, QDialog, QFileDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar
)


def selectFileDialog(parent, for_saving: bool, instruction: str, start_dir: str, file_filter: str = ''):
    """
    Dialog window for selecting a file

    :param parent: parent widget
    :param for_saving: save (True) or open (False)
    :param instruction: instruction text
    :param start_dir: starting directory
    :param file_filter: (optional) filter for allowed files
    """

    if for_saving:
        full_file_path, _ = QFileDialog.getSaveFileName(parent, instruction, start_dir, file_filter)
    else:
        full_file_path, _ = QFileDialog.getOpenFileName(parent, instruction, start_dir, file_filter)

    file_name = QFileInfo(full_file_path).baseName()
    if len(file_name) == 0:
        return None
    return full_file_path


def showMessageBox(parent, icon, window_title: str, text: str, info_message: str = '', detailed_message: str = '',
                   standard_buttons: int = QMessageBox.Ok, check_box_text: str = '', expand_details: bool = False):
    """
    Displays message box

    :param parent: parent widget
    :param icon: icon for message box (e.g. QMessageBox.Warning)
    :param window_title: title of message box
    :param text: text of message box
    :param info_message: (optional) informative text of message box
    :param detailed_message: (optional) detailed text of message box
    :param standard_buttons: (optional) buttons of message box
    :param check_box_text: (optional) if set a checkbox with this text is displayed
    :param expand_details: (optional) automatically expand the details
    """

    msg_box = QMessageBox(icon, window_title, text, standard_buttons, parent)
    font = QFont()
    font.setBold(False)
    msg_box.setFont(font)
    msg_box.setInformativeText(info_message)
    msg_box.setDetailedText(detailed_message)
    if len(check_box_text) > 0:
        msg_box.setCheckBox(QCheckBox(check_box_text, msg_box))
    # Automatically expand the details
    if expand_details:
        for b in msg_box.buttons():
            if msg_box.buttonRole(b) == QMessageBox.ActionRole:
                b.click()
                break
    return msg_box, msg_box.exec()


class DownloadDialog(QDialog):
    """
    Class for downloading some file

    :param parent: parent widget
    :param url: url to file
    :param path: path where file should be saved
    :param name: how file should be renamed
    :param expected_file_size: (optional) expected file size in bytes; needed for progressbar if total file size can not be determined on download
    """

    def __init__(self, parent, url: str, path: str, name: str, expected_file_size: int = -1):
        super().__init__(parent)

        self.url = url
        self.path = path
        self.name = name
        self.expected_file_size = expected_file_size

        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint)
        self.setWindowTitle('Missing documentation PDF')

        # Layout
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.layout.addWidget(QLabel(f'The documentation PDF "{self.name}" could not be found.\nYou can download it automatically'))

        self.hlDownload = QHBoxLayout()
        self.downloadFile = QPushButton('Download PDF', self)
        self.downloadFile.setToolTip('Downloads the documentation PDF and saves it in its default directory')
        self.downloadFile.clicked.connect(self.tryDownloadFile)
        self.hlDownload.addWidget(self.downloadFile)
        self.downloadProgress = QProgressBar(self)
        self.downloadProgress.setToolTip('Download progress')
        self.hlDownload.addWidget(self.downloadProgress)
        self.downloadStatus = QLabel('', self)
        self.downloadStatus.setToolTip('The status of the download progress')
        self.hlDownload.addWidget(self.downloadStatus)
        self.layout.addLayout(self.hlDownload)

        self.labelMan = QLabel(f'Alternatively, you can manually download it from <a href="{self.url}">{urlparse(url).netloc}</a>,<br> place it in the default documentation folder, and rename it to "{self.name}".')
        self.labelMan.setOpenExternalLinks(True)
        self.layout.addWidget(self.labelMan)

        self.hlFolder = QHBoxLayout()
        self.openFolder = QPushButton('Open folder', self)
        self.openFolder.setToolTip('Open the default documentation folder in the file explorer')
        self.openFolder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.path)))
        self.hlFolder.addWidget(self.openFolder)
        self.hlFolder.addStretch(1)
        self.layout.addLayout(self.hlFolder)

        self.hlClose = QHBoxLayout()
        self.hlClose.addStretch(1)
        self.closeDialog = QPushButton('Close', self)
        self.closeDialog.setToolTip('Close this dialog window')
        self.closeDialog.clicked.connect(self.accept)
        self.hlClose.addWidget(self.closeDialog)
        self.layout.addLayout(self.hlClose)

    def updateProgress(self, block_num, block_size, total_size):
        """Updates the progressbar"""
        if total_size == -1:
            if self.expected_file_size == -1:
                self.downloadProgress.setValue(100)
            total_size = self.expected_file_size
        downloaded = (block_num * block_size) / total_size
        self.downloadProgress.setValue(int(downloaded * 100))

    def tryDownloadFile(self):
        """Tries to download the file"""
        urlretrieve(self.url, f'{self.path}/{self.name}', reporthook=self.updateProgress)
        self.downloadProgress.setValue(100)
