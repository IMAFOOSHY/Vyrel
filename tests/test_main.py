"""Tests for the CLI entry point and REPL, and the gfx facade.

These tests never open a window: they install a headless stub backend so
`gfx.*` calls can be verified without a display.
"""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from vyrel import gfx
from vyrel.main import main, run_file, run_repl


class _StubBackend:
    """In-memory backend that records calls instead of drawing."""

    def __init__(self) -> None:
        self.calls = []
        self._open = False
        self._closed = True
        self._w = 0
        self._h = 0

    def open(self, title, width, height):
        self.calls.append(("open", title, width, height))
        self._open = True
        self._closed = False
        self._w, self._h = width, height

    def close(self):
        self._open = False
        self._closed = True

    def width(self):
        return self._w

    def height(self):
        return self._h

    def closed(self):
        return self._closed

    def clear(self, r, g, b):
        self.calls.append(("clear", r, g, b))

    def pixel(self, x, y, r, g, b):
        self.calls.append(("pixel", x, y, r, g, b))

    def line(self, x1, y1, x2, y2, r, g, b):
        self.calls.append(("line", x1, y1, x2, y2, r, g, b))

    def rect(self, x, y, w, h, r, g, b, *, fill=True):
        self.calls.append(("rect", x, y, w, h, r, g, b, fill))

    def text(self, x, y, text, r, g, b):
        self.calls.append(("text", x, y, text, r, g, b))

    def present(self):
        self.calls.append(("present",))

    def poll(self):
        self.calls.append(("poll",))

    def delay(self, ms):
        self.calls.append(("delay", ms))


class TestGfxFacade(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = _StubBackend()
        gfx.set_backend(self.backend)

    def tearDown(self) -> None:
        gfx.reset_backend()

    def test_open_clear(self) -> None:
        attrs = __import__("vyrel.stdlib.gfx", fromlist=["attrs"]).attrs()
        attrs["open"]("hi", 100, 50)
        attrs["clear"](1, 2, 3)
        self.assertEqual(self.backend.calls[0], ("open", "hi", 100, 50))
        self.assertEqual(self.backend.calls[1], ("clear", 1, 2, 3))

    def test_line(self) -> None:
        attrs = __import__("vyrel.stdlib.gfx", fromlist=["attrs"]).attrs()
        attrs["line"](0, 0, 10, 10, 255, 0, 0)
        self.assertEqual(self.backend.calls[-1], ("line", 0, 0, 10, 10, 255, 0, 0))


class TestRunFile(unittest.TestCase):
    def test_runs_simple_file(self) -> None:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".vyr", delete=False, encoding="utf-8",
        ) as f:
            f.write('print("hi")\n')
            path = f.name
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = run_file(path)
            self.assertEqual(code, 0)
            self.assertEqual(buf.getvalue(), "hi\n")
        finally:
            Path(path).unlink()

    def test_reports_parse_error(self) -> None:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".vyr", delete=False, encoding="utf-8",
        ) as f:
            f.write('let = 1\n')
            path = f.name
        try:
            err_buf = io.StringIO()
            old_stderr = sys.stderr
            sys.stderr = err_buf
            try:
                code = run_file(path)
            finally:
                sys.stderr = old_stderr
            self.assertEqual(code, 1)
            self.assertIn("line 1", err_buf.getvalue())
        finally:
            Path(path).unlink()

    def test_reports_runtime_error(self) -> None:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".vyr", delete=False, encoding="utf-8",
        ) as f:
            f.write('"a" + 1\n')
            path = f.name
        try:
            err_buf = io.StringIO()
            old_stderr = sys.stderr
            sys.stderr = err_buf
            try:
                code = run_file(path)
            finally:
                sys.stderr = old_stderr
            self.assertEqual(code, 1)
            self.assertIn("cannot add", err_buf.getvalue())
        finally:
            Path(path).unlink()

    def test_missing_file(self) -> None:
        err_buf = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = err_buf
        try:
            code = run_file("/tmp/does_not_exist_vyrel_xyz.vyr")
        finally:
            sys.stderr = old_stderr
        self.assertEqual(code, 1)
        self.assertIn("cannot read", err_buf.getvalue())


class TestRepl(unittest.TestCase):
    def test_repl_exit(self) -> None:
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("exit\n")
            stdin_path = f.name
        try:
            from io import StringIO
            stdin_buf = StringIO(open(stdin_path).read())
            old_stdin = sys.stdin
            sys.stdin = stdin_buf
            try:
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = run_repl()
                self.assertEqual(code, 0)
            finally:
                sys.stdin = old_stdin
        finally:
            Path(stdin_path).unlink()

    def test_repl_echoes_expression(self) -> None:
        from io import StringIO
        stdin_buf = StringIO("1 + 2\nexit\n")
        old_stdin = sys.stdin
        sys.stdin = stdin_buf
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                run_repl()
            out = buf.getvalue()
            self.assertIn("3", out)
        finally:
            sys.stdin = old_stdin


class TestMainEntry(unittest.TestCase):
    def test_no_args_starts_repl(self) -> None:
        # We can't actually block on input; just confirm the dispatch
        # doesn't crash by patching run_repl.
        import vyrel.main as m
        called = {"n": 0}
        def fake_repl() -> int:
            called["n"] += 1
            return 0
        old = m.run_repl
        m.run_repl = fake_repl
        try:
            self.assertEqual(m.main([]), 0)
        finally:
            m.run_repl = old
        self.assertEqual(called["n"], 1)

    def test_help(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("usage", buf.getvalue().lower())

    def test_too_many_args(self) -> None:
        err_buf = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = err_buf
        try:
            code = main(["a.vyr", "b.vyr"])
        finally:
            sys.stderr = old_stderr
        self.assertEqual(code, 2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
