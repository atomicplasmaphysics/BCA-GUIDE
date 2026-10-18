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

## Installation

### Installation with Python

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

### Download (without Python)

The GUI is available as program that runs without Python on the
[releases page](https://github.com/atomicplasmaphysics/BCA-GUIDE/releases/latest) (*Assets*, the changes of each version are
listed in [CHANGELOG.md](CHANGELOG.md)), the programs are not part
of the code of the repository:

| System                      | File                     | Start                                                          |
|-----------------------------|--------------------------|----------------------------------------------------------------|
| Windows 10/11 (64 bit)      | `BCA-GUIDE_windows.zip`  | unpack, `BCA-GUIDE_windows/BCA-GUIDE.exe`                      |
| Linux (x86-64, glibc 2.35+) | `BCA-GUIDE_linux.tar.gz` | `tar -xzf BCA-GUIDE_linux.tar.gz`, `BCA-GUIDE_linux/BCA-GUIDE` |
| macOS (Apple silicon)       | `BCA-GUIDE_mac.zip`      | unpack, `BCA-GUIDE_mac/BCA-GUIDE.app`                          |

Keep the folder together (the program needs the folder `_internal` next to it). The programs are not signed: Windows
may show a SmartScreen warning (*More info* > *Run anyway*), macOS refuses to open the app the first time (right click >
*Open*, or `xattr -cr BCA-GUIDE.app`). The simulation programs (SDTrimSP, TRIDYN) are not included, they are configured
in the GUI as described in the [manual](#manual).

### Building the program without Python
The programs of the releases are built with [PyInstaller](https://pyinstaller.org/en/stable/). After executing
`python setup/pyinstaller.py` (needs the packages in `requirements-dev.txt`), the folder `BCA-GUIDE_windows`,
`BCA-GUIDE_linux` or `BCA-GUIDE_mac` with the program is created in the main folder (`--archive` also packs it as on the
releases page, `--onefile` creates a single file instead, which starts about 2 s slower because it unpacks itself at
every start). The script then starts the program once with `--self-test` (without showing the window): it checks that
the simulation modules, the images and the manual of the GUI are found. The simulation programs are not part of it.
For further information read the description of the `setup/pyinstaller.py` file.

Releases: pushing a version tag (e.g. `git tag v1.6.01 && git push origin v1.6.01`) starts the workflow
`.github/workflows/release.yml`, which builds the programs on Windows, Linux and macOS, tests them with `--self-test` and
attaches the archives to a GitHub release of the tag. *Run workflow* of the workflow *Release* (tab *Actions*) only
builds and tests them, the archives are then downloads of the run.

## Examples

Examples are provided in the `saves` folder (only the `example_*` folders are part of the repository, the other
simulations in `saves` stay local; the simulations of the tests are in `tests/saves`).

Further examples for SDTrimSP (created with SDTrimSP 7.07, they can be opened with every version) are in `saves/SDTrimSP`:

- `example_01_Ar_on_Au`: 2 keV Ar on Au at 60deg, sputter yields, distributions of reflected and sputtered particles and
  the energy distribution in the target
- `example_02_D_on_W_dynamic`: 1 keV D on W, dynamic simulation (concentrations and surface level over the fluence)
- `example_03_Ar_on_SiO2_Si_trajectories`: 1 keV Ar on a SiO2 layer on Si, trajectories of projectiles and recoils
  (2D, 3D and animated, also as GIF, which is saved in the background while the GUI stays usable)
- `example_04_He_on_W_energy_distribution`: He on W with an energy distribution from `energy.inp`
- `example_05_Ar_on_Si_angle_sweep`: 500 eV Ar on Si, angles of incidence from 0deg to 80deg
- `example_06_Ar_on_W_crystal` and `example_07_Ar_on_W_amorphous`: 2 keV Ar on crystalline (bcc, 100) and amorphous W

The same systems for TRIDYN 2022 are in `saves/TRIDYN` (`example_01_Ar_on_Au`, `example_02_D_on_W_dynamic` with D as H
of mass 2.014, `example_03_Ar_on_SiO2_Si`, `example_07_Ar_on_W_amorphous`; TRIDYN has no energy distributions from files,
angle sweeps and crystals).

Open them with the *Open* button of a simulation tab and select the `input.json` of the example.
The results of several examples (also of SDTrimSP versions or parameter scans) can be compared with
*Simulation* > *Compare simulations...*.

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
- *Simulation* > *Run all tabs* runs all tabs, the others wait in a queue. At most *Simultaneous simulations* (preferences,
  by default the number of processor cores minus 2) simulations of all tabs run at the same time, also the simulations of
  parameter scans. The simulations run with a lower priority than the GUI. The status bar shows the progress of all
  simulations and an estimate of the remaining time.
- Parameter scan: the scan button (slider icon) in the toolbar of a simulation tab enables the scan. The input fields
  that can be scanned get a small mark in their upper left corner, a click on it opens a popup for several values (a
  linear or logarithmic range or entered directly), the field then shows its values. A scan is a series of simulations
  in which any number of parameters are varied at once (all combinations), in SDTrimSP and TRIDYN: energy, angle,
  azimuthal angle, starting depth, charge and fraction (with several species) of the beam species, element parameters
  (surface binding, displacement, cutoff and bulk binding energy, heat of formation, inelastic correction and loss
  model, density, mass, maximum atomic fraction and its action), atomic fractions of the first layer, target thickness,
  segments, thin film thickness and global density, the sheath potential, the numeric simulation settings (e.g.
  fluence, number of histories; not the number of threads and the output frequencies) and the models of the simulation
  settings (interaction potential, integration method, surface binding model, electronic stopping mode of TRIDYN; the
  popup of a combo box selects its choices). The number of simulations includes the other versions. The menu of the scan button adds other
  versions of the program (other configurations, the menu stays open to select several), lists the scanned parameters
  (a click removes the values of one, also of fields that are currently hidden) and resets the scan. *Run* writes each
  simulation into a subfolder of the folder of the simulation, the scan is described in `scan.json`: *Open* also
  accepts `scan.json` and opens the scan again, each subfolder can be opened as single simulation. With the scan,
  *Files preview* shows the files of a selected simulation of the scan, *Run status* the state and output of each
  simulation, *Output files* the files of a selected simulation and *Parameter scan results* compares the results of
  the scan.
- *Simulation* > *Compare simulations...* shows the results of several simulations (or of a scan) in a table and plots:
  lines over one parameter (one line for each value of the other parameters or for fixed values) or 2D maps over two
  parameters. The plotted data can be exported as CSV.
- The colors of the plots follow the palette in `Utility/Styles.py` (12 colors, then lighter and darker versions).
- The additional settings of SDTrimSP are checked against the parameters that the installed version reads (namelist
  `TRI_INP` in `src/work.F90` if the source code is installed, otherwise `doc/tri.inp.txt`, otherwise a built-in list);
  unknown parameters are underlined.

## Development

Linting with [ruff](https://docs.astral.sh/ruff/) (`ruff check .`) and type checking with [mypy](https://mypy-lang.org)
(`mypy`, configured in `mypy.ini`, also the functions without type annotations) also run in the continuous integration
(`.github/workflows/ci.yml`) together with the tests on Windows and Linux. Failed tests are shown as annotations on the
summary page of a run (`setup/junit_annotations.py`).

Structure of the project:

- `main.py`: starts the GUI
- `Pages`: main window (`MainWindow.py`), configuration page, simulation tabs, parameter scan and comparison
- `Simulations`: the simulation programs (SDTrimSP, TRIDYN), found at runtime by `SimulationsList.py`
- `TableWidgets`, `Containers`: tables of the input and the data classes of the arguments
- `Utility`: global configuration (`GlobalConf.py`), styles and colors (`Styles.py`), icons, layouts, dialogs, ...
- `assets`: images of the window, the about dialog and the splash screen (compiled into `assets/resources.py` with
  `python setup/build_resources.py`, sources in `assets/source`); the manual of the GUI is `BCA-GUIDE_manual.pdf`
- `setup`: building the resources and the program without Python (PyInstaller), annotations of failed tests in the CI

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

Start time: `tests/test_startup.py` starts the GUI with a simulation tab for every example and writes the times of the
phases (imports, main window, showing the window) and the slowest functions (cProfile) to `tests/startup_profile.txt`
(also a download of each test job of the continuous integration). The profile can also be created without the tests:

```
python tests/startup_profile.py                     # report in tests/startup_profile.txt
python tests/startup_profile.py --top 80 --output profile.txt
```

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
