# Code style of BCA-GUIDE

Rules for all Python code of the project (application and tests). The reference is the code of v1.5.02.

## Formatting

- Line length of 120 characters as guideline, not enforced. Long strings (messages, tooltips) stay on one line.
- If the parameters of a definition or call do not fit on one line, each parameter gets its own line:

```python
_, result = showMessageBox(
    self,
    QMessageBox.Icon.Warning,
    'Warning!',
    'All listed simulation configurations will be cleared.',
    standard_buttons=QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
)
```

- No random line breaks in the middle of an expression.
- Single quotes for strings (`'text'`), double quotes for docstrings (`"""Docstring"""`).
- Long functions are fine (e.g. building UI elements).
- Simple conditional expressions are fine (`x = a if c else b`), nested ones or multi-condition one-liners are not.

## Naming

- Functions and methods: `camelCase`
- Variables, parameters and attributes: `snake_case`
- Classes: `PascalCase`
- Global constants (used across the project, e.g. screen position, limits) are attributes of `GlobalConf`.
- Local constants (used by one class) are class attributes of that class (like `DefaultValues`, `Versions`).
- No module-level constants. Exception in the tests: shared paths and parameter lists (e.g. of
  `pytest.mark.parametrize`) may be module constants, since pytest needs them when the file is imported.

## Documentation

- No module docstrings, files start with the imports. Scripts (setup/, tests/startup_profile.py) and test files may
  start with a comment that describes them and how they are used.
- Every function and method has a docstring: a short description, then one `:param:` line per parameter (and `:return:`
  if not obvious). Functions without parameters get a one-line docstring.
- A blank line follows every docstring.

```python
def parseValues(text: str, integer: bool = False) -> list:
    """
    Returns the values of a comma separated text

    :param text: comma separated values
    :param integer: if values should be rounded to integers
    """

    values = []
```

## Comments

- The code should speak for itself, use few comments.
- Short lowercase comments only where they are essential, or to show where one is in a long function
  (e.g. `# get table contents`).
- A short 'why' comment (1-2 lines) for non-obvious parts: workarounds, bugs of the simulation programs, version
  differences.

## Type hints

- Use `typing`: `Optional[str]`, `Union[int, float]`, `List[Element]`, `Dict[str, float]`.
- Overridden Qt event handlers take `Optional[...]` like the PyQt6 stubs: `def paintEvent(self, event: Optional[QPaintEvent]):`

## Constants and options

- Options encoded as plain numbers or strings get named constants (or an `Enum`, like `Particle`) only where it helps:
  when a value is used in several places or its meaning is unclear.

## Errors and robustness

- Same pattern as v1.5.02:
  - `try` / `except` with specific exceptions (`FileNotFoundError`, `ValueError`, ...)
  - `logging.info` / `logging.debug` with the file or value that failed
  - return early (`return`, `return False`)
  - `showMessageBox` for messages to the user
- Validation of damaged or unknown input (input files, JSON, outputs, tables) is done in a few central, clearly named
  helper functions, not as scattered checks everywhere.

## Imports

- Three groups in this order, separated by two blank lines, and two blank lines between the imports and the code:
  1. standard library (`typing`, `pathlib`, ...), no blank lines between them
  2. external libraries, one block per library with a blank line between the blocks (`PyQt6.QtCore` and
     `PyQt6.QtWidgets` are one block, `numpy` the next one)
  3. own modules, one block per folder with a blank line between the blocks (`Utility`, `Containers`, ...)

```python
from typing import List, Optional
from pathlib import Path


from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

import numpy as np


from Utility.GlobalConf import GlobalConf
from Utility.Functions import isNumber

from Containers.Element import Element


class ...
```

- Imports that need code before them (e.g. a changed `sys.path` in scripts and tests) stay after that code.
- Import lines may be longer than 120 characters: an import up to about 150 characters stays on one line. Only longer
  import lists go in parentheses, with the lines filled up, not one name per line.
