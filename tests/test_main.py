"""Tests for the CLI (:mod:`vyrel.main`)."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from vyrel.main import VERSION, main, run_file


def _write_temp(text: str, suffix: str = ".vyr") -> str:
    f = tempfile.NamedTemporaryFile(
        "w", suffix=suffix, delete=False, encoding="utf-8",
    )
    f.write(text)
    f.close()
    return f.name


def _run_capture_main(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class TestRunFile(unittest.TestCase):
    def test_runs_simple_file(self) -> None:
        p = _write_temp('print("hi")\n')
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = run_file(p)
            self.assertEqual(code, 0)
            self.assertEqual(buf.getvalue(), "hi\n")
        finally:
            Path(p).unlink()

    def test_reports_parse_error(self) -> None:
        p = _write_temp('let = 1\n')
        try:
            err = io.StringIO()
            old = sys.stderr
            sys.stderr = err
            try:
                code = run_file(p)
            finally:
                sys.stderr = old
            self.assertEqual(code, 1)
            self.assertIn("line 1", err.getvalue())
        finally:
            Path(p).unlink()

    def test_reports_runtime_error(self) -> None:
        p = _write_temp('"a" + 1\n')
        try:
            err = io.StringIO()
            old = sys.stderr
            sys.stderr = err
            try:
                code = run_file(p)
            finally:
                sys.stderr = old
            self.assertEqual(code, 1)
            self.assertIn("cannot add", err.getvalue())
        finally:
            Path(p).unlink()

    def test_missing_file(self) -> None:
        err = io.StringIO()
        old = sys.stderr
        sys.stderr = err
        try:
            code = run_file("/tmp/does_not_exist_vyrel_xyz.vyr")
        finally:
            sys.stderr = old
        self.assertEqual(code, 1)
        self.assertIn("cannot read", err.getvalue())


class TestTokensFlag(unittest.TestCase):
    def test_dumps_tokens(self) -> None:
        p = _write_temp("let x = 1\n")
        try:
            code, out, _ = _run_capture_main(["--tokens", p])
            self.assertEqual(code, 0)
            self.assertIn("KEYWORD", out)
            self.assertIn("IDENT", out)
            self.assertIn("INT", out)
            self.assertIn("EOF", out)
        finally:
            Path(p).unlink()

    def test_tokens_needs_file(self) -> None:
        code, _, _ = _run_capture_main(["--tokens"])
        self.assertEqual(code, 2)


class TestAstFlag(unittest.TestCase):
    def test_dumps_ast(self) -> None:
        p = _write_temp("let x = 1 + 2\n")
        try:
            code, out, _ = _run_capture_main(["--ast", p])
            self.assertEqual(code, 0)
            self.assertIn("Program", out)
            self.assertIn("LetStmt", out)
            self.assertIn("BinaryOp", out)
        finally:
            Path(p).unlink()

    def test_ast_needs_file(self) -> None:
        code, _, _ = _run_capture_main(["--ast"])
        self.assertEqual(code, 2)


class TestVersionAndHelp(unittest.TestCase):
    def test_version(self) -> None:
        code, out, _ = _run_capture_main(["--version"])
        self.assertEqual(code, 0)
        self.assertIn(VERSION, out)
        self.assertIn("vyrel", out)

    def test_help(self) -> None:
        code, out, _ = _run_capture_main(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("usage", out.lower())
        self.assertIn("--tokens", out)
        self.assertIn("--ast", out)

    def test_short_help(self) -> None:
        code, out, _ = _run_capture_main(["-h"])
        self.assertEqual(code, 0)
        self.assertIn("usage", out.lower())


class TestCliDispatch(unittest.TestCase):
    def test_no_args_starts_repl(self) -> None:
        # Patch run_repl so we don't block on stdin.
        import vyrel.main as m
        called = {"n": 0}
        orig = sys.modules.get("vyrel.repl")
        # Patch the function that main() imports lazily.
        import vyrel.repl as r
        orig_run = r.run_repl

        def fake() -> int:
            called["n"] += 1
            return 0

        r.run_repl = fake
        try:
            code, _, _ = _run_capture_main([])
        finally:
            r.run_repl = orig_run
        self.assertEqual(code, 0)
        self.assertEqual(called["n"], 1)

    def test_too_many_args(self) -> None:
        code, _, err = _run_capture_main(["a.vyr", "b.vyr"])
        self.assertEqual(code, 2)
        self.assertIn("too many", err)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
