"""Start time of the GUI: profile of the start with a tab for every example (see startup_profile.py)"""

import subprocess
import sys
from pathlib import Path

from conftest import SAVES


def test_startup_profile(request):
    """
    Starts the GUI in a new process (imports included) and writes the report of the slowest functions to
    tests/startup_profile.txt (or DIR/startup_profile.txt with --test-dir=DIR). The time is not checked strictly (it
    depends on the computer), only that the start works and does not take minutes
    """

    test_dir = request.config.getoption('--test-dir')
    output = (Path(test_dir) if test_dir else Path(__file__).resolve().parent) / 'startup_profile.txt'
    output.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / 'startup_profile.py'), '--output', str(output)],
        capture_output=True, text=True, timeout=600
    )
    assert result.returncode == 0, result.stdout + result.stderr

    text = output.read_text(encoding='utf-8')
    tabs = len(list(SAVES.glob('*/example_*')))
    assert f'with {tabs} simulation tabs' in text and 'Slowest functions of the GUI' in text
    total = float(next(line for line in text.splitlines() if line.startswith('total')).split()[1])
    # 15 s before the previews of hidden tabs were drawn when shown (about 4 s now, slower computers in the CI)
    assert total < 60, text[:text.find('=' * 120)]
