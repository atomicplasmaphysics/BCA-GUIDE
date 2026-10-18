# TODO

Open ideas, known limitations and suggestions for BCA-GUIDE. Done items are removed (see the git history).

## Known limitations

- [ ] Loading a `tri.inp` that sets `ioutput_part` writes it twice (once from the output options, once from the
      additional settings). SDTrimSP uses the last one, so the result is correct, but the file is confusing.
      An input field for the number of logged particles would be cleaner.
- [ ] The trajectory plot shows the initial target structure; in dynamic simulations the layers change.
- [ ] SDTrimSP 6.01/6.06 do not write the recoil generation into the trajectory files, all recoils of a species get
      one color.
- [ ] The creation time of recoils (trajectory animation) is reconstructed from the nearest point of the previous
      generation (SDTrimSP since 6.09 starts the time of each recoil at 0), it is approximate.
- [ ] The run warnings use an estimate of the path length (ZBL nuclear and Lindhard-Scharff/Bethe electronic stopping),
      the transmission warning for SDTrimSP 7.00/7.01 can be too cautious for heavy targets.
- [ ] TRIDYN: the GUI always requests some lists of particles (`outl incd rang scat ...`), so runs from the GUI write
      more files than the original input. A complete set of output checkboxes (code exists, commented out) would allow
      to choose them.
- [ ] TRIDYN in the GUI has no energy distributions (`irrd`), angle sweeps or crystals, therefore there are no TRIDYN
      versions of the SDTrimSP examples 4, 5 and 6.
- [ ] Miller indices of layers in `layer.inp` (SDTrimSP 7.02+) must have the form [1, 0...1, 0...1]. The GUI marks other
      indices and suggests the equivalent index for cubic crystals; an automatic conversion (also for non-cubic
      crystals) would be more convenient.
- [ ] Polycrystals (Miller index (0 0 0)) are only possible in SDTrimSP without a layer file and only for the first
      crystal. With several layers each layer with crystal needs an orientation. Input files of colleagues with crystals
      in layers would help to check the crystal options of the GUI.

- [ ] The download of the SDTrimSP documentation (IPP report 2019-02 on pure.mpg.de) is refused by the server (HTTP 403).
      SDTrimSP 7.05 and 7.07 come without pdf, the GUI opens the documentation of another installed version instead; a
      current download link (e.g. of the IPP report 2024-06 that comes with 7.00) would be better.
- [ ] tbsp_ascii (tabulated stopping power as text file, since 7.07) is not shown in the GUI, tbsp.db is always used
      (same data). A loaded tri.inp with tbsp_ascii = .true. is written with tbsp_binary.

## Build

- [ ] macOS with Intel processors: the release only contains an Apple silicon (arm64) build (macos-latest), an
      additional build on an Intel runner (or a universal2 build) would be needed.
- [ ] Start time: the simulation tabs are created at the start (about 0.15 s per tab, see tests/startup_profile.txt),
      they could be created when they are opened for the first time.

## Simulation results

- [ ] Plots of the matrices with logarithmic energies (`lmatout_log_energ`) and over the azimuthal angle (`meagb_*`).
- [ ] Save plot settings (e.g. of the trajectories) as templates; the 3D view of the trajectories could also be rotated
      during the GIF export.
- [ ] Comparison of simulations: overlay of the 2D maps (energy distribution, matrices) as difference plots.
- [ ] Parameter scans: values from a file or from a list of complete parameter sets (instead of all combinations), and
      an adaptive refinement of the values where the yield changes strongly.
- [ ] Parameter scans: rerun only the failed (or not run) simulations of a scan, scans over the layers of the target
      (thickness and composition of each layer, the first layer can already be scanned).
- [ ] Parameter scans: undo/redo of the values, and a list of the scans of a folder (scan.json is overwritten by a new
      scan in the same folder).
- [ ] Parameter scans: the calculation method (static/dynamic) and the distributions of energies and angles (e.g. the
      sheath potential is only shown for Maxwellian distributions) could also be scanned.
- [ ] Parameter scans: an entry of the scan menu could also jump to the field of the parameter (switch to the simulation
      settings, scroll to the row) and open its popup, instead of only removing the values.
- [ ] Animation export: cancel button and a progress bar for the GIF export (now the status bar shows the frame), and
      MP4 export for long cascades (smaller files than GIF).
- [ ] Comparison of simulations: fits (e.g. of the energy dependence of the yield) and the comparison with
      experimental data from a file.

## Simulation setup

- [ ] Frozen first columns also for the target structure table.
- [ ] Undo/redo for the tables.

## Simulation programs

- [ ] Report to the developers of SDTrimSP:
  - the layered crystal cases of 7.07 (`case/Ar_*_layer_crystal`) and `case/C_WC_diff` have a `layer.inp` without the
    header `!`/`#` that 7.07 requires, they do not run;
  - the depth of origin of sputtered atoms (`morigin_ex_bs.dat`, `morigin_ex_ts.dat`) is only summed over the projectile
    species (`gsum_stat.F90`: `mor_ex_bs(..., 1:ncp_proj)`), so it is always 0 for target atoms in 7.07;
  - `E_distr_*.dat` write `dist_ny` instead of `dist_nz` as third dimension in the header;
  - the energy distribution in the target (`lenergy_distr`) crashes energy and angle sweeps ("allocatable array is
    already allocated"), the GUI warns before the run;
  - in sweeps the energy or angle is appended to the title (`write(title, ...)` with A80), titles with more than about
    70 characters stop the simulation (exit code 66), the GUI shortens the title of sweeps to 65 characters.
- [ ] Run `tests/test_case_comparison.py` with more cases (`BCA_TEST_CASE_PROJECTILES=1000000`, takes hours) and with the
      full TRIDYN samples (`BCA_TEST_TRIDYN_FULL=1`).
- [ ] Remote runs (SSH, MPI builds of SDTrimSP).

## Project

- [ ] Update the manual (https://doi.org/10.34726/3526) with the new features: distribution editor, trajectories
      (3D, animation), energy distributions and matrices, parameter scans, comparison of simulations, "Run all" queue,
      run warnings, automatic search of simulations, crystals from `table.crystal`, examples.
- [ ] Stricter type checking: `check_untyped_defs` and annotations of the remaining functions (mypy only checks
      annotated functions), then `disallow_untyped_defs` for new modules.
