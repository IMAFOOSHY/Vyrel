"""Command-line entry point and REPL for Vyrel.

Usage::

    python3 -m vyrel path/to/program.vyr
    python3 -m vyrel             # starts a REPL

The CLI lexes + parses + interprets the file.  Errors are printed with the
source line and a caret via :func:`vyrel.errors.format_error`.  The REPL
evaluates one expression or statement at a time against a single persistent
:class:`Interpreter` (so `let x = 1` in one line is visible in the next).

The REPL strips trailing newlines before evaluating; multi-line blocks (e.g.
`if ... end`) must be entered on one line unless the user asks for a
multi-line mode (not implemented in Phase 4).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

from .errors import VyrelError, format_error
from .interpreter import Interpreter
from .parser import parse


USAGE = "usage: python3 -m vyrel [file.vyr]"


def run_file(path: str) -> int:
    """Run a .vyr file.  Returns the process exit code."""
    p = Path(path)
    try:
        source = p.read_text(encoding="utf-8")
    except OSError as e:
        print(f"error: cannot read {path}: {e}", file=sys.stderr)
        return 1

    try:
        program = parse(source)
    except VyrelError as e:
        print(format_error(e, source), file=sys.stderr)
        return 1

    try:
        Interpreter().run(program)
    except VyrelError as e:
        print(format_error(e, source), file=sys.stderr)
        return 1
    return 0


def run_repl() -> int:
    """Start the interactive REPL.  Returns the process exit code."""
    interp = Interpreter()
    print("Vyrel REPL — type 'exit' or Ctrl-D to quit.")
    while True:
        try:
            line = input("vyrel> ")
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            continue

        if line.strip() in ("exit", "quit"):
            return 0
        if line.strip() == "":
            continue

        try:
            program = parse(line + "\n")
            # Execute statements except the last; if the last is an
            # expression statement, print its value.
            from . import ast_nodes as ast
            body = program.body
            if not body:
                continue
            for stmt in body[:-1]:
                interp.exec_block((stmt,))
            last = body[-1]
            if isinstance(last, ast.ExprStmt):
                value = interp.eval_expr(last.expr)
                if value is not None:
                    # Reuse the interpreter's str() for consistency.
                    from .interpreter import _stringify
                    print(_stringify(value, interp))
            else:
                interp.exec_block((last,))
        except VyrelError as e:
            print(format_error(e, line))
        except (Exception, KeyboardInterrupt) as e:  # pragma: no cover
            print(f"error: {e}")


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if len(argv) == 0:
        return run_repl()
    if len(argv) == 1 and argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    if len(argv) == 1:
        return run_file(argv[0])
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
