# Changelog

All notable changes of the BCA-GUIDE, newest first. The version is shown in the splash screen and in the about dialog
(`GlobalConf.version`). The programs without Python are attached to the
[releases](https://github.com/atomicplasmaphysics/BCA-GUIDE/releases) since v1.6.00.

## v1.6.05 (2026-10-20)

- SDTrimSP 6.09 and newer: inelastic loss model "auto" of each element (new default), SDTrimSP chooses the model itself
  (inel0 = -1: 4 for H, D, T, 5 for He, He3 and 7 (LZ7) for all other elements). inel0 is not written to tri.inp if all
  elements use it, otherwise -1 for these elements. Results are the same as with the models selected before
- SDTrimSP: a tri.inp without inel0 (e.g. the example He_Ni of SDTrimSP) or with inel0 = -1 is loaded with the
  automatic model and saved again without inel0, before the GUI added the models that SDTrimSP would choose
- The warnings before a run (validity of Lindhard-Scharff/Oen-Robinson, missing elements in tables/table3 and table4)
  use the model that SDTrimSP chooses for "auto"
- Tests: the case He_Ni of SDTrimSP 6.06 (12 GB of trajectory memory) runs one after the other with the other simulations
  that need a lot of memory, beside other runs it did not finish within the timeout

## v1.6.04 (2026-10-20)

- No more "QLayout: Attempting to add QLayout ... which already has a layout" messages at the start (layouts of the
  target preview, the crystal editor and its basis vectors were created with the page as parent)
- Simulation programs without executable flag (e.g. after unpacking or copying) are made executable before a run, before
  the run failed with "execve: Permission denied" (Linux, macOS)
- SDTrimSP: the same element as separate projectile and target species in a loaded tri.inp (e.g. "Cu", "Cu" of the case
  Cu_Cu_crystal) is kept separate, before it was grouped into one species (ncp changed, crystal.inp with two species
  did not fit anymore)
- SDTrimSP: an element in beam and target gets the maximum concentration (qumax) of the target table, before the value of
  the beam row was written (e.g. 0, SDTrimSP stopped with "qumax, to many limit for qumax")
- SDTrimSP before 7.00 (no crystals in the GUI): the crystal.inp of the user is kept (l_crystal in the additional
  settings), before it was removed when the input files were written and SDTrimSP 6.09 stopped with "End of file"
- SDTrimSP: warning before the run if the simulation has more elements than the installation is compiled for (ncpm in
  src/param.F90, e.g. 3 for SDTrimSP 6.01), SDTrimSP stops with "Cannot match namelist object name" then
- SDTrimSP: the tables take as many elements as the installation is compiled for (ncpm: 12 since 7.00, before 11), a
  tri.inp with more elements is loaded without them and a message (before the GUI crashed with "unexpected None")
- SDTrimSP: warning before the run if the inelastic loss model 4 (H, D, T) or 5 (He) is used and an element is missing in
  tables/table3 or table4 of the installation (e.g. C_a before 7.02, B10 and B11 in 6.09), SDTrimSP stops with "Bad real
  number" then
- SDTrimSP: serie.dat of sweeps with many elements (the list of elements continues in the next line) is read, before the
  results of a sweep with 11 elements could not be shown
- SDTrimSP 7.00 and 7.01: a tri.inp saved by the GUI without crystal (miller_ind = 0, 0, 0) is loaded without an
  additional setting miller_ind (before it was written twice after saving again)
- Tests: inputs of colleagues (tests/test-inputs/*.inp, not in the repository) are loaded, saved with the same values and
  run with all SDTrimSP versions (tests/test_test_inputs.py); --simulation-data is used as absolute path (the runs change
  the working directory, the folders of later runs were created inside earlier ones)
- Tests: test_simulation_data.py is skipped with --simulations (it checked folders that the parallel runs were
  replacing); simulations that need a lot of memory (trajectories of recoils) run one after the other (--dist loadgroup);
  the search test no longer expects SDTrimSP 6.09 without linux binaries; uninitialized output of SDTrimSP 6.06 is not
  compared; known problems of the linux builds (SDTrimSP 6.01/6.09 trajectory memory, 7.07 morigin_ex_bs.dat); the
  start checks for Qt layout warnings

## v1.6.03 (2026-10-18)

- TRIDYN: results of simulations with energies above 10^7 eV are shown again (issue #2): TRIDYN writes the energy as
  "**********" into *_indat.dat when it does not fit into its column, the GUI reported "Corrupted input files"
- TRIDYN: vacancies of the plot "Ion-induced damages" are calculated with the atomic density and the thickness of the
  segments (the column is given in dpa per fluence): the total per ion equals the number of TRIDYN (*_out.dat) and no
  longer depends on the segment thickness (before e.g. 46.8 instead of 29.6 vacancies per ion; comment of issue #3)

## v1.6.02 (2026-10-18)

- readme: download of the programs as first part of the installation, examples after it
- .gitignore: the simulation programs are not part of the repository

## v1.6.01 (2026-10-18)

- Splash screen with the current website of the institute (www.tuwien.at/phy/iap/app), taken over from v1.4.20 of the
  former branch PyQt6

## v1.6.00 (2026-10-18)

First release with downloads of the program for Windows, Linux and macOS (no Python needed).

- Programs without Python on the releases page: `BCA-GUIDE_windows.zip`, `BCA-GUIDE_linux.tar.gz` and
  `BCA-GUIDE_mac.zip` (Apple silicon), built and tested automatically for every version tag
- Faster start of the GUI: about 4 s instead of 15 s with 8 simulation tabs (the 3D crystal previews of hidden tabs
  are drawn when they are shown, slow imports only when needed)
- Profile of the start in the tests (`tests/startup_profile.py`): times of the start and the slowest functions
- Parameter scan of TRIDYN: beam fraction, maximum atomic fraction and its action, thin film thickness, global density
  and the electronic stopping mode (also beam fraction and maximum atomic fraction for SDTrimSP)
- Same order of the simulation programs on all systems (on Linux TRIDYN could be listed first)
- Results of simulations with deuterium or tritium can be shown without the tables of SDTrimSP
- The program is built as folder (`setup/pyinstaller.py`, starts about 2 s faster than a single file)

## v1.5 (2025-09 to 2026-10)

### v1.5.12 (2026-10-17)
- The manual of the GUI (`BCA-GUIDE_manual.pdf`) is in the main folder again

### v1.5.11 (2026-10-17)
- Parameter scan: starting depth and charge of the beam species, target segments, inelastic loss model, interaction
  potential, integration method and surface binding model; combo boxes are scanned over a list of their choices
- The number of simulations of a scan counts the tab's own version (selecting another version doubles it)
- Miller index (0 0 0) of a single crystalline layer is no longer marked as error (polycrystal)
- Documentation of SDTrimSP versions without pdf (7.05, 7.07) opens the documentation of another installed version, a
  failed download is shown instead of crashing
- Additional output options in two columns; the selection of the tabulated stopping power file is hidden (tbsp.db)
- Cleaner project structure (`assets`, `Utility/Styles.py`, `Pages/MainWindow.py`), only the examples are part of
  the repository, working executable with a self test (`main.py --self-test`), stricter type checks that found several
  bugs (segment thickness, "Save/Open/New all" without an open tab)

### v1.5.10 (2026-10-17)
- Any number of parameters can be scanned
- The scan menu lists the scanned parameters (a click removes one), "Reset the scan", stays open while versions are
  selected
- "Done!", "Aborted" and "ERROR" return to "Ready!" when an input changes
- The GIF export of the cascade animation runs in the background
- Smaller buttons in the output files, "Check" button of the additional settings with a tooltip

### v1.5.09 (2026-10-17)
- Parameter scan directly in the input fields: scannable fields have a small mark, a click opens a popup for several
  values (range or list), the field shows its values
- The simulations of a scan are subfolders of the simulation, `scan.json` describes the scan and can be opened again
- "Run status" tab with the state of each simulation of the scan, selectors for the simulation of the scan in the
  files preview and output files
- One limit of simultaneous simulations for all tabs, runs and scans (default: number of cores minus 2)

### v1.5.08 (2026-10-17)
- Parameter scan in each simulation tab with up to 5 parameters (all combinations), linear or logarithmic values,
  restored after a restart
- Comparison of simulations as lines over one parameter or 2D maps over two parameters, CSV export
- Color palette of the design, also for the layers of the target preview
- Simulations run with lower priority, the GUI stays responsive; window position and display are restored

### v1.5.07 (2026-10-16)
- Trajectories: 3D view, top view, coloring by species, recoil generation, energy or time, animation of the cascade
  with GIF export
- New plots: energy distribution in the target, maximum penetration depth, depth of origin of sputtered atoms,
  energy-polar angle matrices; every plot can be exported as CSV
- First parameter scans (energy, angle, fluence, histories, thickness, version) and comparison of simulations
- Warnings before a run (validity of the inelastic loss model, transmission in 7.00/7.01, large output files),
  "Run all" queue with remaining time in the status bar
- Additional settings of SDTrimSP are checked against the installed version
- TRIDYN: an element in beam and target is one species, Latin-1 input files, corrected layer thickness; TRIDYN examples

### v1.5.06 (2026-10-16)
- Plots of particle trajectories (`trajec_all.dat`)
- Composition tables: grouped energy columns, the first columns stay visible when scrolling
- "Search" finds all installed SDTrimSP and TRIDYN versions in a folder
- Better loading of `tri.inp`, `crystal.inp` and `layer.inp`; input files of the simulation folder are no longer
  deleted before a run
- Examples for first-time users in `saves/SDTrimSP/example_*`

### v1.5.05 (2026-10-16)
- Editor for distribution files (`energy.inp`, `angle.inp`, `ene_ang.inp`) with preview and import, file names and
  formats per SDTrimSP version
- New SDTrimSP parameters: azimuthal angle, starting depth, charge, inelastic correction, cutoff and bulk binding
  energy, heat of formation, isotope masses, trajectory and energy distribution output, random seed, sheath potential
- Reworked crystal editor, layered crystals in the target structure table

### v1.5.04 (2026-10-15)
- Themes: system, light, dark and SRIM, theme aware icons
- Progress bar with elapsed and remaining time
- Crystals from `table.crystal` for SDTrimSP 7.02+, new crystals also from CIF and VASP POSCAR files
- Options and defaults per SDTrimSP version according to its documentation
- The binary is selected automatically, versions are detected from the folder, configurations can be reordered by drag
  and drop
- Fixes for running detached on Windows, Linux and macOS; test suite (pytest)

### v1.5.02 - v1.5.03 (2026-10-15)
- Paths are handled with pathlib: fixes crashes when opening the working directory, documentation, output files,
  settings and input files

### v1.5.01 (2025-09-24)
- Improved reading of the SDTrimSP files `tri.inp` and `crystal.inp`

### v1.5.00 (2025-09-18)
- Support of SDTrimSP 7: crystals (crystal editor with 3D preview, crystal table, loading of crystal input files, no
  crystal file if no crystal is used), loading of SDTrimSP 6.09 settings in 7.00, standard plots for SDTrimSP 7
  (crystal support contributed by osang, 2024-2025)
- Refactored code, copyright information only in `main.py`

## v1.4 (2023-05 to 2024-01)

### v1.4.20 (2025-03-05, branch PyQt6, not part of v1.5)
- Current website of the institute on the splash screen (taken over in v1.6.01)
- No warnings for values of the SDTrimSP tables that cannot be converted (also in v1.5)

### v1.4.19 (2024-01-31)
- Inelastic loss model LZ7 of SDTrimSP 6.09+, selectable in the beam and target rows

### v1.4.17 - v1.4.18 (2024-01)
- "SRIM mode" in the help menu (sky background with clouds, since v1.5.04 the SRIM theme)
- Better splash screen

### v1.4.11 - v1.4.15 (2023-06 to 2023-07)
- Fixes for macOS
- Dialog functions merged into one module
- Better error handling: files opened as UTF-8 with replacement of invalid characters, colored log messages
- Damage depth plot of SDTrimSP works again

### v1.4.9 - v1.4.10 (2023-06-15)
- Icons in the file dialogs, improved preferences dialog
- Running detached on macOS, better progress of SDTrimSP
- Only the last clicked plot is calculated (faster plots)

### v1.4.4 - v1.4.8 (2023-06)
- Data analysis and plot preparation in a separate thread (the GUI stays responsive)
- New container for the plot settings
- Reading of files is protected against crashes
- Fix: starting simulations from the configuration tab no longer runs all simulations

### v1.4 - v1.4.3 (2023-05-31)
- Update from PyQt5 to PyQt6

## v1.3 (2023-01 to 2023-05)

### v1.3.13 (2023-05-04)
- Additional settings of SDTrimSP

### v1.3.12 (2023-03-23)
- Compatibility with the latest numpy version

### v1.3.11 (2023-01 to 2023-02)
- Manual of the GUI (`BCA-GUIDE_manual.pdf`), updated download links, PyInstaller script

### v1.3 - v1.3.10 (2023-01-27)
- First public version: GUI for SDTrimSP and TRIDYN (configurations of the installed programs, input of beam, target
  and settings, running simulations, output files and plots), example simulations
