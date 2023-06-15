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


from typing import List, Dict
from os import listdir, path
from sys import exit

from Simulations.Simulations import SimulationsInput, SimulationsOutput


class SimulationsList:
    """
    List of possible defined Simulation Programs
    """

    # private variables, used for initializing this class only once
    __instance = None
    __initialized = False

    # simulation programs
    simulation_program_list: List[SimulationsInput] = []
    simulation_program_versions: Dict = {}
    simulation_evaluation_list: List[SimulationsOutput] = []
    simulation_program_names = []
    simulation_program_description = []
    simulation_program_logo = []
    simulation_program_about = []
    input_files = []

    def __new__(cls):
        """
        Initialize this class only once, since its contents should never change
        """

        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self):
        """
        Only executes once. Instance will be saved in __instance
        """

        # initialize self only once
        if self.__initialized:
            return
        self.__initialized = True

        def hasattrs(cls, attrs: List[str]) -> bool:
            """Returns if given class has all attributes"""

            return all([hasattr(cls, attr) for attr in attrs])

        error = ''

        # loop over all simulation modules
        for module in listdir(path.dirname(__file__)):
            if module[-3:] != '.py' or module in ['Simulations.py', 'SimulationsList.py']:
                continue
            module = module[:-3]

            mod = __import__(f'Simulations.{module}', fromlist=[''])

            # check if SimulationInput and SimulationOutput classes are defined
            if hasattrs(mod, ['SimulationInput', 'SimulationOutput']):
                sim_inp = mod.SimulationInput
                sim_out = mod.SimulationOutput

                # check if SimulationInput and SimulationOutput classes are subclasses
                if not issubclass(sim_inp, SimulationsInput) or not issubclass(sim_out, SimulationsOutput):
                    error = f'Simulation module <{module}> was set up wrong. "SimulationInput" and "SimulationOutput" classes should inherit from classes with same names in "Simulations.py".'

                # check if simulation name is not already taken
                elif sim_inp.Name in SimulationsList.simulation_program_names:
                    error = f'Simulation module <{module}> can not be loaded. A simulation class with name "{sim_inp.Name}" already exists. Please change the name of the implemented simulation.'

                # append to general simulation programs variables
                else:
                    SimulationsList.simulation_program_list.append(mod.SimulationInput)
                    SimulationsList.simulation_evaluation_list.append(mod.SimulationOutput)
                    SimulationsList.simulation_program_names.append(mod.SimulationInput.Name)
                    SimulationsList.simulation_program_versions[mod.SimulationInput.Name] = mod.SimulationInput.Versions
                    SimulationsList.simulation_program_description.append(mod.SimulationInput.Description.strip())
                    SimulationsList.simulation_program_logo.append(mod.SimulationInput.Logo)
                    SimulationsList.simulation_program_about.append(mod.SimulationInput.About)
                    SimulationsList.input_files.append(mod.SimulationInput.InputFilename)

            else:
                error = f'Simulation module <{module}> was set up wrong, should contain "SimulationInput" and "SimulationOutput" classes.'

            # check if error occurred while loading this module
            if error:
                print(error)
                exit(error)
