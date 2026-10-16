# TODO

Open ideas, known limitations and suggestions for BCA-GUIDE. Done items are removed (see the git history).

## Known limitations

- [ ] SDTrimSP 6.06 shares the version group "6.01, 6.06" with 6.01, but 6.06 supports the inelastic loss model 7 (LZ7)
      and uses it as default. The GUI offers only the models of 6.01 and writes `inel0 = 3` instead of 7, so the results
      of 6.06 cases differ (see `tests/test_case_comparison.py`). A separate version group for 6.06 would fix this.
- [ ] Loading a `tri.inp` that sets `ioutput_part` writes it twice (once from the output options, once from the
      additional settings). SDTrimSP uses the last one, so the result is correct, but the file is confusing.
      An input field for the number of logged particles would be cleaner.
- [ ] With a layer file the GUI writes `qu` as the mean composition of the layers. SDTrimSP uses `qu` then only to
      estimate the depth of the dynamic relaxation (TTDYN), loaded values of `qu` are not kept.
- [ ] `iq0 = -2` (layer file with chemical erosion, `lchem_ch`) is written as `iq0 = -1`.
- [ ] Layer files that cover fewer segments than `nqx`: SDTrimSP fills the rest with the first layer, the GUI extends
      the last layer.
- [ ] The trajectory plot shows the initial target structure; in dynamic simulations the layers change.
- [ ] SDTrimSP 6.01/6.06 do not write the recoil generation into the trajectory files, all recoils get one color.
- [ ] Projectiles that leave the target at the bottom abort SDTrimSP 7.00/7.01 ("invalid case for flag").
      The GUI explains the error after the run; a warning before the run (thin target, high energy) would be better.

## Simulation results

- [ ] 3D view of the trajectories (rotatable), optionally colored by energy or species instead of the generation.
- [ ] Animation of the cascade using the times of the trajectory points (`ptime`).
- [ ] Compare several simulations in one plot (e.g. sputter yields of different versions, energies or targets).
- [ ] Export the data of every plot as CSV (some plots have no export yet) and save plot settings as templates.
- [ ] Plot the energy distribution in the target (`lenergy_distr`, `E_distr_*.dat`) as a 2D map.

## Simulation setup

- [ ] Non-blocking warnings before the run: Lindhard-Scharff/Oen-Robinson outside their validity
      (E < 25 · Z^(4/3) · M keV), transmission in SDTrimSP 7.00/7.01, very large output files (trajectories, matrices).
- [ ] Parameter scans: run a series of simulations with one parameter varied (energy, angle, fluence, version) and
      collect the results in one table/plot.
- [ ] Frozen first columns also for the target structure table.
- [ ] Undo/redo for the tables.
- [ ] Check the additional settings against the parameter list of the version (`doc/tri.inp.txt`) and mark unknown ones.
- [ ] Queue for "Run all": limit the number of simulations that run at the same time.
- [ ] Estimated remaining time in the progress bar.

## Simulation programs

- [ ] Report to the developers of SDTrimSP: the layered crystal cases of 7.07 (`case/Ar_*_layer_crystal`) and
      `case/C_WC_diff` have a `layer.inp` without the header `!`/`#` that 7.07 requires, they do not run.
- [ ] Run `tests/test_case_comparison.py` with more cases (`BCA_TEST_CASE_PROJECTILES=1000000`, takes hours) and
      check the remaining differences.

- [ ] Comparison of TRIDYN runs with the samples of TRIDYN (`TRIDYN2022_sample.ZIP`), like the SDTrimSP test cases.
- [ ] Examples for TRIDYN with the same systems as the SDTrimSP examples.
- [ ] Remote runs (SSH, MPI builds of SDTrimSP).

## Project

- [ ] Update the manual (https://doi.org/10.34726/3526) with the new features: distribution editor, trajectories,
      automatic search of simulations, crystals from `table.crystal`, examples.
- [ ] Continuous integration (e.g. GitHub Actions): tests without simulations on Windows and Linux, PyInstaller build.
- [ ] Type checking (mypy) and linting (e.g. ruff) in the continuous integration.
- [ ] Update the supported Python and package versions in the readme.
