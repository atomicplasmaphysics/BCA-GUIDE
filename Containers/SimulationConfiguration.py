from __future__ import annotations
from typing import Any, Dict, Literal, Optional, Union, TYPE_CHECKING
from pathlib import Path

from PyQt6.QtCore import QDir

from Utility.GlobalConf import GlobalConf

from Simulations.SimulationsList import SimulationsList

from Utility.Functions import pathToStr, bestVersion

# avoiding circular import, but still get type hinting functionality
if TYPE_CHECKING:
    from Pages.ProgramPage import SimulationPage


class SimulationConfiguration:
    """
    Class that stores the configuration for a simulation program

    :param title: title of simulation
    :param program: simulation program
    :param folder: path to main folder for simulation
    :param binary: path to binary file for simulation
    :param version: version number of simulation
    :param base_save_folder: (optional) general save folder, if None the default save folder from the preferences is used
    :param save_folder: (optional) specific save folder
    """

    def __init__(
        self,
        title: str,
        program: int,
        folder: Path,
        binary: Path,
        version: str = 'unknown',
        base_save_folder: Path | None = None,
        save_folder: Path | None = None
    ):
        # Get list of simulations
        sim_list = SimulationsList()
        assert(program in range(len(sim_list.simulation_program_list)))

        self.title = title
        self.program = program
        self.program_class = sim_list.simulation_program_list[program]
        self.evaluation_class = sim_list.simulation_evaluation_list[program]
        self.program_name = sim_list.simulation_program_names[program]
        self.program_description = sim_list.simulation_program_description[program]
        self.program_logo = sim_list.simulation_program_logo[program]
        self.folder = folder
        self.binary = binary
        self.version = version
        self.tab_widget: Union[SimulationPage, None] = None
        self.changed = True
        self.has_settings = False
        self.running = False
        self.progress = 0
        self.is_active = False
        self.unsaved_changes = False
        self.base_save_folder = base_save_folder
        self.save_folder = save_folder
        # version found in the folder, if it differs from the version (see load)
        self.detected_version: Optional[str] = None
        # parameter scan of the tab: shown, its settings and its folder (see ParameterScanPage.state)
        self.scan_enabled = False
        self.scan_state: dict = {}

    def edit(self, title: str, folder: Path, binary: Path, version: str, base_save_folder: Path | None):
        """
        Sets main parameters of simulation

        :param title: title of simulation
        :param folder: path to main folder for simulation
        :param binary: path to binary file for simulation
        :param version: version number of simulation
        :param base_save_folder: specific save folder
        """

        self.title = title
        self.folder = folder
        self.binary = binary
        self.version = version
        self.base_save_folder = base_save_folder
        self.changed = True

    def getBaseSaveFolder(self) -> Path:
        """Returns the base save folder of this configuration, or the default save folder from the preferences if none is set"""

        if self.base_save_folder is not None:
            return self.base_save_folder
        return GlobalConf.save_path / self.program_class.SaveFolder

    def save(self, no_config=False) -> dict:
        """
        Returns a dictionary of its contents that can be used for saving and loading this configuration

        :param no_config: if no_config is True, base_save_folder and save_folder will not be stored
        """

        save_dict: Dict[str, Any] = {
            'title': str(self.title),
            'program': str(self.program_name),
            'folder': pathToStr(self.folder),
            'binary': pathToStr(self.binary),
            'version': str(self.version)
        }

        # current settings of the parameter scan of the tab
        if self.tab_widget is not None:
            self.scan_enabled, self.scan_state = self.tab_widget.scanState()
        save_dict['scan_enabled'] = bool(self.scan_enabled)

        if not no_config:
            save_dict.update({
                'base_save_folder': pathToStr(self.base_save_folder),
                'save_folder': pathToStr(self.save_folder),
                'scan': self.scan_state
            })

        return save_dict

    @staticmethod
    def load(settings: dict) -> Union[SimulationConfiguration, Literal[False]]:
        """
        Returns a SimulationConfiguration from the settings-dictionary that is created by save() or False if not possible

        :param settings: dictionary with settings
        """

        program = settings.get('program')
        title = settings.get('title')
        if not isinstance(program, str) or not isinstance(title, str):
            return False

        if program not in SimulationsList().simulation_program_names:
            return False

        program_idx = SimulationsList().simulation_program_names.index(program)
        if program_idx < 0:
            return False

        folder = settings.get('folder')
        if not isinstance(folder, str):
            return False
        folder = Path(folder)
        if not folder.is_dir():
            return False

        binary = settings.get('binary')
        if not isinstance(binary, str):
            return False
        binary = Path(binary)
        if not binary.is_file():
            return False

        version = settings.get('version')
        if not isinstance(version, str):
            version = 'unknown'

        # empty paths (and "." of older versions) mean no folder
        base_save_folder = settings.get('base_save_folder')
        if isinstance(base_save_folder, str) and base_save_folder.strip() not in ('', '.'):
            base_save_folder = Path(base_save_folder)
            if not base_save_folder.is_dir():
                base_save_folder = None
        else:
            base_save_folder = None

        save_folder = settings.get('save_folder')
        if isinstance(save_folder, str) and save_folder.strip() not in ('', '.'):
            save_folder = Path(save_folder)
            if not save_folder.is_dir():
                save_folder = None
        else:
            save_folder = None

        # base save folders that equal an automatic default are not stored, so that the preferences are used
        if base_save_folder is not None:
            save_folder_name = SimulationsList().simulation_program_list[program_idx].SaveFolder
            default_folders = [GlobalConf.save_path / save_folder_name, Path(QDir.currentPath()) / 'saves' / save_folder_name]
            if any(base_save_folder.resolve() == default_folder.resolve() for default_folder in default_folders):
                base_save_folder = None

        # version detected in the folder: old version groups (e.g. "6.01, 6.06") are replaced, a different version group is
        # only remembered (the user decides whether it is changed)
        program_class = SimulationsList().simulation_program_list[program_idx]
        detected_version = None
        versions = list(getattr(program_class, 'Versions', []) or [])
        if versions:
            try:
                version_name = program_class.getVersionName(folder, binary)
            except Exception:
                version_name = False
            index, exact = bestVersion(versions, version_name) if isinstance(version_name, str) and version_name else (-1, False)
            if version not in versions:
                if index < 0:
                    index, exact = bestVersion(versions, version)
                if index >= 0:
                    version = versions[index]
            elif index >= 0 and exact and versions[index] != version:
                detected_version = versions[index]

        sc = SimulationConfiguration(title, program_idx, folder, binary, version)
        sc.base_save_folder = base_save_folder
        sc.save_folder = save_folder
        sc.detected_version = detected_version
        sc.scan_enabled = settings.get('scan_enabled') is True
        scan_state = settings.get('scan')
        sc.scan_state = scan_state if isinstance(scan_state, dict) else {}

        return sc
