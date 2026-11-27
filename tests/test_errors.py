"""Tests for :mod:`vyrel.errors` and the snippet formatter."""

from __future__ import annotations

import unittest

from vyrel.errors import (
    LexError,
    ParseError,
    VyrelError,
    VyrelRuntimeError,
    format_error,
    format_error_with_snippet,
)


class TestErrorHierarchy(unittest.TestCase):
    def test_all_subclass_vyrel_error(self) -> None:
        for cls in (LexError, ParseError, VyrelRuntimeError):
            self.assertTrue(issubclass(cls, VyrelError))

    def test_render_plain_with_position(self) -> None:
        err = VyrelError("boom", line=3, column=7)
        self.assertIn("line 3", str(err))
        self.assertIn("boom", str(err))

    def test_render_plain_without_position(self) -> None:
        err = VyrelError("boom")
        self.assertNotIn("line", str(err))
        self.assertIn("boom", str(err))

    def test_kind_is_prefix(self) -> None:
        self.assertIn("Syntax error", str(LexError("x", line=1)))
        self.assertIn("Error", str(VyrelRuntimeError("x", line=1)))


class TestFormatError(unittest.TestCase):
    def test_single_line(self) -> None:
        src = 'let x = "hi" + 1'
        err = VyrelRuntimeError("cannot add", line=1, column=15)
        out = format_error(err, src)
        self.assertIn("cannot add", out)
        self.assertIn(src, out)
        self.assertIn("^", out)

    def test_no_position(self) -> None:
        err = VyrelError("boom")
        self.assertEqual(format_error(err, ""), "Error: boom")

    def test_position_out_of_range(self) -> None:
        err = VyrelError("boom", line=99)
        out = format_error(err, "one line")
        self.assertIn("boom", out)
        self.assertNotIn("|", out)


class TestFormatErrorWithSnippet(unittest.TestCase):
    def test_includes_context(self) -> None:
        src = (
            "line one\n"
            "line two\n"
            "line three\n"
            "line four\n"
            "line five\n"
        )
        err = VyrelRuntimeError("boom", line=3, column=1)
        out = format_error_with_snippet(err, src)
        self.assertIn("line one", out)
        self.assertIn("line two", out)
        self.assertIn("line three", out)
        self.assertIn("line four", out)
        self.assertIn("line five", out)

    def test_marks_error_line(self) -> None:
        # The caret is only printed when a column is available; supply one
        # so the formatter has a target to point at.
        src = "a\nb\nc\nd\ne\n"
        err = VyrelRuntimeError("boom", line=3, column=1)
        out = format_error_with_snippet(err, src)
        self.assertIn("> 3 |", out)
        self.assertIn("^", out)

    def test_marks_error_line_no_column(self) -> None:
        # Without a column, the line is marked but no caret is shown.
        src = "a\nb\nc\nd\ne\n"
        err = VyrelRuntimeError("boom", line=3)
        out = format_error_with_snippet(err, src)
        self.assertIn("> 3 |", out)
        self.assertNotIn("^", out)

    def test_clamps_at_file_start(self) -> None:
        src = "a\nb\nc\n"
        err = VyrelRuntimeError("boom", line=1)
        out = format_error_with_snippet(err, src)
        self.assertNotIn("-1", out)

    def test_clamps_at_file_end(self) -> None:
        src = "a\nb\nc\n"
        err = VyrelRuntimeError("boom", line=3)
        out = format_error_with_snippet(err, src)
        self.assertNotIn("4 |", out)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
