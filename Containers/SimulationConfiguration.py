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
from typing import Union, TYPE_CHECKING
from os import path

from Simulations.SimulationsList import SimulationsList

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
    :param base_save_folder: (optional) general save folder
    :param save_folder: (optional) specific save folder
    """

    def __init__(self, title: str, program: int, folder: str, binary: str,
                 version: str = 'unknown', base_save_folder: str = '', save_folder: str = ''):
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
        self.is_active = False
        self.unsaved_changes = False
        self.base_save_folder = base_save_folder
        self.save_folder = save_folder

    def edit(self, title: str, folder: str, binary: str, version: str, base_save_folder: str):
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

    def save(self, no_config=False) -> dict:
        """
        Returns a dictionary of its contents that can be used for saving and loading this configuration

        :param no_config: if no_config is True, base_save_folder and save_folder will not be stored
        """

        save_dict = {
            'title': str(self.title),
            'program': str(self.program_name),
            'folder': str(self.folder),
            'binary': str(self.binary),
            'version': str(self.version)
        }

        if not no_config:
            save_dict.update({
                'base_save_folder': str(self.base_save_folder),
                'save_folder': str(self.save_folder)
            })

        return save_dict

    @staticmethod
    def load(settings: dict) -> Union[SimulationConfiguration, bool]:
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
        if not isinstance(folder, str) or not path.exists(folder):
            return False

        binary = settings.get('binary')
        if not isinstance(binary, str) or not path.exists(binary):
            return False

        version = settings.get('version')
        if not isinstance(version, str):
            version = 'unknown'

        base_save_folder = settings.get('base_save_folder')
        if not isinstance(base_save_folder, str) or not path.exists(base_save_folder):
            base_save_folder = ''

        save_folder = settings.get('save_folder')
        if not isinstance(save_folder, str) or not path.exists(save_folder):
            save_folder = ''

        sc = SimulationConfiguration(title, program_idx, folder, binary, version)
        sc.base_save_folder = base_save_folder
        sc.save_folder = save_folder

        return sc
