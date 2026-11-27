"""Vyrel REPL — interactive read-eval-print loop with multi-line blocks.

Design:
* Single persistent :class:`Interpreter` across lines, so ``let x = 1``
  persists to the next line.
* Multi-line blocks: if a line is a syntactically incomplete program (e.g.
  ``if x > 0 then`` with no ``end``), the REPL keeps reading lines and joins
  them with newlines until the program parses.  The prompt changes from
  ``vyrel>`` to ``...`` while in continuation mode.
* Expressions at the top level print their value (like Python's REPL).
  Statements don't print anything.
* ``exit`` or ``quit`` or ``Ctrl-D`` ends the session.  ``Ctrl-C`` cancels
  the current line or the current multi-line block.
* Uses ``readline`` if available, for history and cursor movement.
"""

from __future__ import annotations

import sys
from typing import Optional

from . import ast_nodes as ast
from .errors import VyrelError, format_error
from .interpreter import Interpreter, _stringify
from .lexer import Lexer
from .parser import parse
from .tokens import TokenType


BANNER = (
    "Vyrel REPL — type 'exit' or Ctrl-D to quit.\n"
    "Multi-line blocks: end with 'end'.  Blank line cancels.\n"
)


def _try_parse(source: str) -> Optional[ast.Program]:
    """Return the parsed program, or None if the source is incomplete."""
    try:
        return parse(source)
    except VyrelError:
        # Distinguish "incomplete" from "actually wrong": if the source
        # ends with an unclosed block or a `then`/`do`/`case`/`catch` that
        # we're still expecting more of, treat as incomplete.  Heuristic:
        # count keyword openers vs `end`.  This is beginner-friendly: any
        # parse error while balanced means we're done collecting lines.
        if _looks_incomplete(source):
            return None
        raise


def _looks_incomplete(source: str) -> bool:
    """Heuristic: does the source end inside an open block?"""
    openers = 0
    try:
        for tok in Lexer(source).tokenize():
            if tok.type is TokenType.KEYWORD:
                if tok.value in ("if", "while", "for", "fn", "class",
                                 "try", "match"):
                    openers += 1
                elif tok.value == "end":
                    openers -= 1
    except VyrelError:
        return False
    return openers > 0


def _evaluate(interp: Interpreter, source: str, original: str) -> None:
    """Parse and execute one complete REPL entry.

    Prints the value of a trailing expression statement, if any.  Reports
    errors against the accumulated source so positions are correct.
    """
    try:
        program = parse(source)
    except VyrelError as e:
        print(format_error(e, original))
        return

    body = program.body
    if not body:
        return

    try:
        # Execute all but the last statement.  If the last is an expression
        # statement, print its value; otherwise execute it as a statement.
        for stmt in body[:-1]:
            interp.exec_block((stmt,))
        last = body[-1]
        if isinstance(last, ast.ExprStmt):
            value = interp.eval_expr(last.expr)
            if value is not None:
                print(_stringify(value, interp))
        else:
            interp.exec_block((last,))
    except VyrelError as e:
        print(format_error(e, original))
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print()
    except Exception as e:
        # Last-resort catch: never crash the REPL.
        print(f"internal error: {type(e).__name__}: {e}")


def run_repl(interpreter: Optional[Interpreter] = None) -> int:
    """Start the REPL.  Returns the process exit code (always 0)."""
    # Enable history if readline is present.  Non-fatal if not.
    try:
        import readline  # noqa: F401  (enables history/cursor)
    except ImportError:
        pass

    interp = interpreter if interpreter is not None else Interpreter()
    print(BANNER)

    buffer: list[str] = []

    while True:
        prompt = "vyrel> " if not buffer else "... "
        try:
            line = input(prompt)
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            buffer.clear()
            continue

        if line.strip() in ("exit", "quit") and not buffer:
            return 0

        if not buffer and line.strip() == "":
            continue

        buffer.append(line)
        source = "\n".join(buffer) + "\n"

        try:
            program = _try_parse(source)
        except VyrelError as e:
            print(format_error(e, source))
            buffer.clear()
            continue

        if program is None:
            continue  # keep accumulating lines

        _evaluate(interp, source, source)
        buffer.clear()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_repl())
