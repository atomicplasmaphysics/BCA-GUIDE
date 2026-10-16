# BCA-GUIDE
*Copyright(C) 2022, Alexander Redl, Paul S. Szabo, David Weichselbaum, Herbert Biber, Christian Cupak, Andreas Mutzke, Wolfhard Möller, Richard A. Wilhelm, Friedrich Aumayr*

The ***B*inary *C*ollision *A*pproximation *G*raphical *U*ser *I*nterface for *D*isplaying and *E*xecution of simulations)** is an extension of the [**GUI for SDTrimSP**](https://github.com/psszabo/SDTrimSP-GUI) (P. S. Szabo, et al. Nucl. Instrum. Meth. Phys. Res. B (2022), https://doi.org/10.1016/j.nimb.2022.04.008).
Thus, the layout and functionality of this GUI are similar but improved.
A detailed manual for the BCA-GUIDE is provided in the document `BCA-GUIDE_maual.pdf` (https://doi.org/10.34726/3526).

The BCA-GUIDE is freely available and distributed under the GPLv3 licence.
As a condition of free usage, the manuscript of the GUI for SDTrimSP by Szabo, et al. (https://doi.org/10.1016/j.nimb.2022.04.008) and the manual of the BCA-GUIDE by A. Redl, et al. (https://doi.org/10.34726/3526) must be cited in any publication that presents results obtained with help of this GUI.

## Currently supported BCA-codes

- [SDTrimSP](https://www.ipp.mpg.de): contact [A. Mutzke](mailto://aam@ipp.mpg.de) for the latest version
- [TRIDYN 2022](https://www.hzdr.de/): contact [W. Möller](mailto://w.moeller@hzdr.de) for the latest version

Place the downloaded BCA-codes in the `Simulation Programs` folder

## Examples

Basic examples are provided in the `saves` folder:

- Argon beam on Tungsten target (`Ar_on_W`)
- Hydrogen and Argon beam on layered Iron and Tungsten target under 60deg (`H_Ar_on_Fe_W_60deg`)

Further examples for SDTrimSP (created with SDTrimSP 7.07, they can be opened with every version) are in `saves/SDTrimSP`:

- `example_01_Ar_on_Au`: 2 keV Ar on Au at 60deg, sputter yields, distributions of reflected and sputtered particles and
  the energy distribution in the target
- `example_02_D_on_W_dynamic`: 1 keV D on W, dynamic simulation (concentrations and surface level over the fluence)
- `example_03_Ar_on_SiO2_Si_trajectories`: 1 keV Ar on a SiO2 layer on Si, trajectories of projectiles and recoils
  (2D, 3D and animated, also as GIF)
- `example_04_He_on_W_energy_distribution`: He on W with an energy distribution from `energy.inp`
- `example_05_Ar_on_Si_angle_sweep`: 500 eV Ar on Si, angles of incidence from 0deg to 80deg
- `example_06_Ar_on_W_crystal` and `example_07_Ar_on_W_amorphous`: 2 keV Ar on crystalline (bcc, 100) and amorphous W

The same systems for TRIDYN 2022 are in `saves/TRIDYN` (`example_01_Ar_on_Au`, `example_02_D_on_W_dynamic` with D as H
of mass 2.014, `example_03_Ar_on_SiO2_Si`, `example_07_Ar_on_W_amorphous`; TRIDYN has no energy distributions from files,
angle sweeps and crystals).

Open them with the *Open* button of a simulation tab and select the `input.json` of the example.
The results of several examples (also of SDTrimSP versions or parameter scans) can be compared with
*Simulation* > *Compare simulations...*.

## Installation

The GUI needs [Python](https://www.python.org/downloads/) 3.10 or newer with following packages installed:

```
Package     minimum version   tested version
----------- ----------------- --------------
PyQt6       6.5.0             6.10.2
matplotlib  3.5.3             3.10.7
numpy       1.23.2            2.4.3
scipy       1.9.1             1.17.1
pillow      (with matplotlib) 12.0.0   (export of animations as GIF)
```

and is tested for following Python versions and systems
```
Version     System
----------- --------
3.13.1      Windows 11 (all tests including the simulation runs)
3.10, 3.13  Windows and Linux (continuous integration without simulation programs)
```
Older versions of the BCA-GUIDE were also used with Python 3.7 to 3.11 on Windows, Linux and macOS.

All packages can be installed using
```bash
>> pip install -r requirements.txt
```

To execute the GUI, download all files from this repository and execute the `main.py` file from the console.
```bash
>> python3 main.py
```

### Alternative Installation
If one wishes to execute the GUI without calling it from the console, [PyInstaller](https://pyinstaller.org/en/stable/) can be used to compile all needed python files into one executable.
After executing the `setup\pyinstaller.py` file (same packages and package PyInstaller are needed), a `BCA-GUIDE.exe` will be created in the main folder.
For further information read the description of the `setup\pyinstaller.py` file.

## Manual

Quick instructions and a detailed manual can be found inside the GUI in the *Help* menu.

### Set up simulation configuration

Upon opening the GUI, the *Configurations* tab needs to be configured for the desired simulation.

All installed simulations can be added at once with the *Search* button of the *Configurations* tab: select a folder
(e.g. `Simulation Programs`), all simulations in it and its subfolders are added with their binary and version.
Single simulations are configured manually as described below.

#### Example: configure TRIDYN 2022

1) Provide a title in the *Configuration title* field, e.g. **"TRIDYN 22"**.
2) Select **TRIDYN 2022** in the list of *Simulation programs*.
3) Select version **2022** in the list of *Simulation versions*.
4) Select the *Simulation folder* of TRIDYN 2022: `Simulation Programs\TRIDYN\Tridyn2022`
5) The *Simulation binary* of TRIDYN 2022 is selected automatically: `...\tridyn2022w.exe` (Windows) or `...\tridyn2022l` (Linux). Otherwise, select it manually
6) Check that the *Detected simulation* reads **TRIDYN 2022**
7) Confirm and add the new configuration by pressing *Save configuration*

#### Example: configure SDTrimSP (version 6.01 for Windows)

1) Provide a title in the *Configuration title* field, e.g. **"SDTrimSP v6.01"**.
2) Select **SDTrimSP** in the list of *Simulation programs*.
3) Select **6.01** in the list of *Simulation versions*.
4) Select the *Simulation folder* of SDTrimSP v.6.01: `Simulation Programs\SDTrimSP\SDTrimSP_6.01_Windows`
5) The *Simulation binary* of SDTrimSP v.6.01 is selected automatically: `...\bin\windows.SEQ\SDTRIM.SP.6.01x64.exe`. Otherwise, select it manually
6) Check that the *Detected simulation* reads **SDTrimSP v.6.01**
7) Confirm and add the new configuration by pressing *Save configuration*

### Running simulations

- *Run* in the toolbar of a simulation tab runs it. Before the run, the GUI warns about parameters that the simulation
  accepts, but that might give wrong results, fail or create very large files (e.g. Lindhard-Scharff/Oen-Robinson above
  their validity, transmission in SDTrimSP 7.00/7.01, trajectory and matrix files); the user decides whether it runs.
- *Simulation* > *Run all tabs* runs all tabs with at most *Simultaneous simulations* at the same time (input field in the
  *Simulation* menu and in the preferences), the others wait in a queue. The status bar shows the progress of all
  simulations and an estimate of the remaining time.
- *Simulation* > *Parameter scan of current tab...* runs a series of simulations in which one parameter is varied
  (energy or angle of a beam species, fluence, number of histories, target thickness or the version, i.e. other
  configurations of the same program) and compares the results in a table and plots.
- The additional settings of SDTrimSP are checked against the parameters that the installed version reads (namelist
  `TRI_INP` in `src/work.F90` if the source code is installed, otherwise `doc/tri.inp.txt`, otherwise a built-in list);
  unknown parameters are underlined.

## Development

Linting with [ruff](https://docs.astral.sh/ruff/) (`ruff check .`) and type checking with [mypy](https://mypy-lang.org)
(`mypy`, configured in `mypy.ini`) also run in the continuous integration (`.github/workflows/ci.yml`) together with the
tests on Windows and Linux.

## Tests

The tests are found in the folder `tests` and need the packages in `requirements-dev.txt` (`pip install -r requirements-dev.txt`).
The GUI is tested without showing windows; the settings and saves of the user are not changed.
The tests run in parallel processes (pytest-xdist), add `-n 0` to run them in one process.

```
python -m pytest                                    # all tests except the simulation runs
python -m pytest --simulations -n 20                # also runs simulations with every program found in "Simulation Programs"
python -m pytest --simulations -n 20 --simulation-data tests/simulation_data   # keeps the simulation outputs
python -m pytest tests/test_simulation_data.py --simulation-data tests/simulation_data   # checks kept outputs in the GUI
python -m pytest --simulations -n 20 --test-dir=D:/BCA-GUIDE/tests   # all files of the tests in another folder or drive
```

With `--test-dir=DIR` (with `=`, otherwise pytest treats DIR as test folder; or the environment variable `BCA_TEST_DIR`) the temporary files of the tests are created in
`DIR/tmp` and the simulation runs are kept in `DIR/simulation_data` (instead of the temporary folder of the system drive).

`tests/test_case_comparison.py` runs the test cases that come with SDTrimSP (folder `case`) directly with their version
and through the GUI (the GUI loads the input files of the case, writes its own input files and runs them) and checks
that both runs give identical results. Cases with more than `BCA_TEST_CASE_PROJECTILES` projectiles (default 20000)
are skipped. The same is done for the samples of TRIDYN 2022 (`TRIDYN2022_sample.ZIP`); the fluence of the dynamic
sample is reduced, unless `BCA_TEST_TRIDYN_FULL=1` is set (takes hours).

`tests/test_json_import.py` loads the `input.json` of every example into every installed version of SDTrimSP and into
TRIDYN (and vice versa) and checks that loading never fails and that only parameters are written that the version reads.

The simulation runs vary the input (energies from 10 eV to 1 GeV, angles, sweeps, angle and energy distributions,
distributions from files (energy.inp, angle.inp, ene_ang.inp), Maxwellian distributions, dynamic mode, potentials,
integration methods, surface binding models, further element parameters, output options including trajectories and
energy distributions, crystals and layered crystals) and check that all outputs of each simulation version can be shown
and plotted in the GUI. Known problems of the simulation programs are marked as expected failures.

Longer runs can be configured with environment variables:
`BCA_TEST_PROJECTILES` (number of projectiles, default 1000), `BCA_TEST_SEED` (random seed),
`BCA_TEST_TIMEOUT` (seconds per simulation, default 900) and `BCA_TEST_ALL_VARIANTS=1` (all variants for every version,
otherwise only for the newest one).

## Third-party resources

- Icons: [Lucide](https://lucide.dev) (ISC License, Copyright (c) Lucide Contributors 2022, portions Copyright (c) Cole Bemis 2013-2022 as part of Feather (MIT))
