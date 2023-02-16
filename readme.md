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

## Installation

The GUI needs [Python 3](https://www.python.org/downloads/) with following packages installed:

```
Package     Version
----------- --------
PyQt5       5.15.7
matplotlib  3.5.3
numpy       1.23.2
scipy       1.9.1
```

and is tested for following Python versions and systems
```
Version     System
----------- --------
3.7.1       Windows
3.8.2       Windows
3.8.10      Linux
3.10.0      Windows
3.10.0      macOS
3.11.0      Windows
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

#### Example: configure TRIDYN 2022

1) Provide a title in the *Configuration title* field, e.g. **"TRIDYN 22"**.
2) Select **TRIDYN 2022** in the list of *Simulation programs*.
3) Select version **2022** in the list of *Simulation versions*.
4) Select the *Simulation folder* of TRIDYN 2022: `Simulation Programs\TRIDYN\Tridyn2022`
5) Select the *Simulation binary* of TRIDYN 2022: `...\tridyn2022.exe` (Windows) or `...\tridyn2022l` (Linux)
6) Check that the *Detected simulation* reads **TRIDYN 2022**
7) Confirm and add the new configuration by pressing *Save configuration*

#### Example: configure SDTrimSP (version 6.01 for Windows)

1) Provide a title in the *Configuration title* field, e.g. **"SDTrimSP v6.01"**.
2) Select **SDTrimSP** in the list of *Simulation programs*.
3) Select **6.01, 6.06** in the list of *Simulation versions*.
4) Select the *Simulation folder* of SDTrimSP v.6.01: `Simulation Programs\SDTrimSP\SDTrimSP_6.01_Windows`
5) Select the *Simulation binary* of SDTrimSP v.6.01: `...\bin\windows.SEQ\SDTRIM.SP.6.01x64.exe`
6) Check that the *Detected simulation* reads **SDTrimSP v.6.01**
7) Confirm and add the new configuration by pressing *Save configuration*
