"""
Profile of the start of the GUI: imports, main window with a simulation tab for every example (saves/*/example_*) and
showing the window. Writes the times of the phases and the slowest functions (cProfile) to a report.

    python tests/startup_profile.py                         report in tests/startup_profile.txt
    python tests/startup_profile.py --output FILE --top 50

The GUI starts as for a user with these configurations (autosave.json, the save folders of the examples are loaded),
the simulation programs are not needed (empty stand-in program folders). The settings and saves of the user are not
used. Also run by tests/test_startup.py (the report of the last test run is tests/startup_profile.txt).
"""

import cProfile
import io
import json
import os
import pstats
import shutil
import sys
import tempfile
import time
from argparse import ArgumentParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# program of the examples: (program name, folder of the examples, version, name of the stand-in binary)
PROGRAMS = [
    ('SDTrimSP', ROOT / 'saves' / 'SDTrimSP', '7.07', 'SDTrimSP.exe'),
    ('TRIDYN', ROOT / 'saves' / 'TRIDYN', '2022', 'tridyn.exe'),
]


def prepareConfigurations(temp: Path) -> int:
    """Copies the examples, creates stand-in program folders and writes the configurations, returns the number of tabs"""

    configurations = []
    for program, examples, version, binary_name in PROGRAMS:
        folder = temp / 'programs' / program
        folder.mkdir(parents=True)
        binary = folder / binary_name
        binary.write_bytes(b'')
        for example in sorted(examples.glob('example_*')):
            save_folder = temp / 'saves' / program / example.name
            shutil.copytree(example, save_folder)
            configurations.append({
                'title': f'{program} {example.name}', 'program': program, 'folder': str(folder), 'binary': str(binary),
                'version': version, 'scan_enabled': False, 'base_save_folder': '', 'save_folder': str(save_folder), 'scan': {}
            })
    config_folder = temp / 'saves' / 'config'
    config_folder.mkdir(parents=True, exist_ok=True)
    (config_folder / 'autosave.json').write_text(json.dumps(configurations), encoding='utf-8')
    return len(configurations)


def report(profile: cProfile.Profile, phases: list, tabs: int, top: int) -> str:
    """Text of the report: times of the phases, slowest functions of the GUI (cumulative) and of all code (own time)"""

    lines = [f'Start of the GUI with {tabs} simulation tabs (python {sys.version.split()[0]}, {sys.platform})', '']
    for name, seconds in phases:
        lines.append(f'{name:<45} {seconds:6.2f} s')
    lines.append(f'{"total":<45} {sum(seconds for _, seconds in phases):6.2f} s')

    root = str(ROOT).replace('\\', '/')
    for title, sort, restriction in (
        (f'Slowest functions of the GUI (cumulative time, top {top})', 'cumulative', root.split('/')[-1] + r'[\\/](?!\.venv)'),
        (f'Functions with the most own time (all code, top {top})', 'tottime', ''),
    ):
        stream = io.StringIO()
        stats = pstats.Stats(profile, stream=stream).strip_dirs() if not restriction else pstats.Stats(profile, stream=stream)
        stats.sort_stats(sort).print_stats(*([restriction, top] if restriction else [top]))
        text = stream.getvalue().replace(str(ROOT) + os.sep, '').replace(root + '/', '')
        lines += ['', '=' * 120, title, '=' * 120, text[text.find('   ncalls'):].rstrip()]
    return '\n'.join(lines) + '\n'


def main() -> int:
    parser = ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument('--output', default=str(Path(__file__).resolve().parent / 'startup_profile.txt'), help='file of the report')
    parser.add_argument('--top', type=int, default=40, help='number of functions in the lists')
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix='bca_startup_') as temp_name:
        temp = Path(temp_name)
        tabs = prepareConfigurations(temp)
        phases = []
        profile = cProfile.Profile()

        start = time.perf_counter()
        profile.enable()
        from PyQt6.QtCore import QSettings
        from PyQt6.QtWidgets import QApplication
        import assets.resources  # noqa: F401 (registers resources)
        from Utility.GlobalConf import GlobalConf
        import Pages.MainWindow
        profile.disable()
        phases.append(('imports', time.perf_counter() - start))

        # settings and saves of the report (not of the user), message boxes would block
        GlobalConf.settings = QSettings(str(temp / 'settings.ini'), QSettings.Format.IniFormat)
        GlobalConf.save_path = temp / 'saves'
        GlobalConf.theme = 'system'
        # the stand-in program folders have no element tables (warning "do not show again")
        GlobalConf.skip_element_info = True
        import Utility.Dialogs
        import Pages.ProgramPage
        import Pages.ConfigurationPage
        from PyQt6.QtWidgets import QCheckBox, QMessageBox
        for module in (Utility.Dialogs, Pages.MainWindow, Pages.ProgramPage, Pages.ConfigurationPage):
            setattr(module, 'showMessageBox', lambda *a, **k: (type('Box', (), {'checkBox': lambda self: QCheckBox()})(),
                                                               QMessageBox.StandardButton.Ok))

        start = time.perf_counter()
        profile.enable()
        app = QApplication.instance() or QApplication(sys.argv)
        window = Pages.MainWindow.MainWindow(app)
        profile.disable()
        phases.append((f'main window with {tabs} simulation tabs', time.perf_counter() - start))
        created = len([sc for sc in window.simulation_configs if sc.tab_widget is not None])

        start = time.perf_counter()
        profile.enable()
        window.show()
        for _ in range(20):
            app.processEvents()
        profile.disable()
        phases.append(('showing the window (events)', time.perf_counter() - start))

        text = report(profile, phases, created, args.top)
        Path(args.output).write_text(text, encoding='utf-8')
        print(text[:text.find('=' * 120)].rstrip())
        print(f'\nReport: {args.output}')

        window.close()
        window.deleteLater()
        app.processEvents()
        if created != tabs:
            print(f'ERROR: {created} of {tabs} simulation tabs were created')
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
