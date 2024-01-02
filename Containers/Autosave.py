from json import dump

from PyQt6.QtCore import QDir, QFileInfo

from GlobalConf import GlobalConf

from MainWindow import MainWindow

from Utility.Dialogs import selectFileDialog


class Autosave:
    save_dict = ''

    def save(self, main_window: MainWindow, autosave: bool = False, no_config: bool = False):
        """
        Saves configuration file

        :param main_window: MainWindow of application
        :param autosave: (optional) if True, an autosave file will be generated
        :param no_config: (optional) if True, only programs without config will be saved
        """

        QDir().mkpath(f'{GlobalConf.save_path}/config')

        if autosave:
            save_file = f'{GlobalConf.save_path}/config/autosave.json'

        else:
            save_file = f'{GlobalConf.save_path}/config/config.json'
            save_file = selectFileDialog(
                main_window,
                True,
                'Save configuration file',
                save_file,
                file_filter='Configuration Files (*.json)'
            )
            folder = QFileInfo(save_file).canonicalPath()
            if len(folder) == 0:
                main_window.writeStatusBar('Saving configuration file aborted')
                return

        config = [sc.save(no_config=no_config) for sc in main_window.simulation_configs]

        with open(save_file, 'w', encoding='utf-8') as config_file:
            dump(config, config_file, indent=4)

        main_window.writeStatusBar('Saving configuration file successful')


def main():
    from PyQt6.QtWidgets import QMainWindow, QApplication
    from Containers.SimulationConfiguration import SimulationConfiguration

    class MainWindowx(QMainWindow):
        simulation_configs = [
            SimulationConfiguration(
                "SDTrimSP",
                0,
                "C:/Users/Alex/Uni/TU/Diplomarbeit/bca-sims/Simulation Programs/SDTrimSP/SDTrimSP_6.01_Windows",
                "C:/Users/Alex/Uni/TU/Diplomarbeit/bca-sims/Simulation Programs/SDTrimSP/SDTrimSP_6.01_Windows/bin/windows.SEQ/SDTRIM.SP.6.01x64.exe",
                "6.01, 6.06",
                "C:/Users/Alex/Uni/TU/Diplomarbeit/bca-sims/saves/SDTrimSP",
                "C:/Users/Alex/Uni/TU/Diplomarbeit/bca-sims/saves/SDTrimSP/Presentation_Ar_on_Fe_O"
            )
        ]

        @staticmethod
        def writeStatusBar(text):
            print(text)

    app = QApplication([])
    app.processEvents()

    main_window = MainWindowx()
    autosave = Autosave()
    print('before autosave')
    autosave.save(main_window)
    print('after autosave')

    app.exec()


if __name__ == '__main__':
    main()
