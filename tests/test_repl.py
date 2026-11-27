"""Tests for :mod:`vyrel.repl`.

Tests never open a terminal: they patch ``sys.stdin`` with a StringIO and
capture stdout.  ``run_repl`` is exercised end-to-end.
"""

from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout


def run_repl_capture(lines: list[str]) -> str:
    """Run the REPL with ``lines`` as input, return captured stdout."""
    from vyrel.repl import run_repl

    stdin_buf = io.StringIO("\n".join(lines) + "\n")
    old_stdin = sys.stdin
    sys.stdin = stdin_buf
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            run_repl()
        return buf.getvalue()
    finally:
        sys.stdin = old_stdin


class TestReplBasics(unittest.TestCase):
    def test_exit_word(self) -> None:
        out = run_repl_capture(["exit"])
        self.assertIn("Vyrel REPL", out)

    def test_quit_word(self) -> None:
        out = run_repl_capture(["quit"])
        self.assertIn("Vyrel REPL", out)

    def test_ctrl_d(self) -> None:
        # Empty input + EOF
        out = run_repl_capture([])
        self.assertIn("Vyrel REPL", out)

    def test_expression_prints_value(self) -> None:
        out = run_repl_capture(["1 + 2", "exit"])
        self.assertIn("3", out)

    def test_statement_no_output(self) -> None:
        # `let x = 5` produces no printed value.  Check by looking only at
        # the region after the banner.
        out = run_repl_capture(["let x = 5", "exit"])
        after_banner = out.split("Blank line cancels.")[-1]
        # The only thing after the banner should be prompts, not "5".
        self.assertNotIn("\n5\n", after_banner)

    def test_persistent_state(self) -> None:
        out = run_repl_capture(["let x = 42", "x", "exit"])
        self.assertIn("42", out)

    def test_blank_lines_ignored(self) -> None:
        out = run_repl_capture(["", "", "exit"])
        self.assertIn("Vyrel REPL", out)


class TestReplMultiLine(unittest.TestCase):
    def test_if_block(self) -> None:
        # The REPL only echoes *top-level* expressions.  An `if` block's
        # body produces no output, so we verify the block executed by
        # checking a side effect via a trailing top-level expression.
        lines = [
            "let x = 0",
            "if 1 > 0 then",
            "  x = 42",
            "end",
            "x",
            "exit",
        ]
        out = run_repl_capture(lines)
        self.assertIn("42", out)

    def test_fn_block(self) -> None:
        lines = [
            "fn add(a, b)",
            "  return a + b",
            "end",
            "add(2, 3)",
            "exit",
        ]
        out = run_repl_capture(lines)
        self.assertIn("5", out)

    def test_class_block(self) -> None:
        lines = [
            "class P",
            "  fn init(n)",
            "    self.n = n",
            "  end",
            "end",
            "P(7).n",
            "exit",
        ]
        out = run_repl_capture(lines)
        self.assertIn("7", out)


class TestReplErrors(unittest.TestCase):
    def test_runtime_error_does_not_exit(self) -> None:
        out = run_repl_capture(['"a" + 1', "1 + 1", "exit"])
        self.assertIn("cannot add", out)
        self.assertIn("2", out)  # subsequent line still works

    def test_parse_error_reported(self) -> None:
        # A complete but malformed line: `let` needs an identifier.
        out = run_repl_capture(["let = 1", "exit"])
        self.assertIn("error", out.lower())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
