"""Test runner for the Vyrel reference implementation.

Discovers and runs every ``test_*.py`` under ``tests/`` using the standard
library's :mod:`unittest`.  Never requires a display, network, or root.

Usage:
    python3 tests/run_tests.py            # run everything
    python3 tests/run_tests.py -v         # verbose
    python3 tests/run_tests.py test_lexer # only matching modules
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


def main(argv: list[str]) -> int:
    # Make the repository root importable so ``import vyrel`` works regardless
    # of the caller's cwd.  ``tests/run_tests.py`` lives one level below root.
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    loader = unittest.TestLoader()
    tests_dir = Path(__file__).resolve().parent

    # Optional positional filter: ``python3 tests/run_tests.py test_lexer``.
    pattern = "test_*.py"
    if len(argv) > 1 and not argv[1].startswith("-"):
        name = argv[1]
        if not name.endswith(".py"):
            name = f"{name}.py" if not name.startswith("test_") else f"{name}"
        pattern = name

    suite = loader.discover(str(tests_dir), pattern=pattern, top_level_dir=str(repo_root))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
