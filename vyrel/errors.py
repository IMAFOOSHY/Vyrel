"""Error hierarchy and beginner-friendly error formatting for Vyrel.

All Vyrel errors derive from :class:`VyrelError`.  Each error carries an
optional 1-based ``line`` (and ``column`` where available) so the CLI and REPL
can print precise diagnostics.  Messages are phrased in plain English because
the language targets beginners.

Two formatting helpers:

* :func:`format_error` renders the offending source line with a caret.
* :func:`format_error_with_snippet` renders *two lines before and after* the
  error for more context.  Used by the CLI for file runs; the REPL uses the
  simpler one because its input is often one line.
"""

from __future__ import annotations

from typing import Optional


class VyrelError(Exception):
    """Base class for every error raised by the Vyrel implementation."""

    kind: str = "Error"

    def __init__(
        self,
        message: str,
        line: Optional[int] = None,
        column: Optional[int] = None,
    ) -> None:
        self.message = message
        self.line = line
        self.column = column
        super().__init__(self._render_plain())

    def _render_plain(self) -> str:
        if self.line is None:
            return f"{self.kind}: {self.message}"
        return f"{self.kind} (line {self.line}): {self.message}"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self._render_plain()


class LexError(VyrelError):
    """Raised by the lexer for malformed source."""

    kind = "Syntax error"


class ParseError(VyrelError):
    """Raised by the parser for malformed programs."""

    kind = "Syntax error"


class VyrelRuntimeError(VyrelError):
    """Raised by the interpreter at runtime."""

    kind = "Error"


def _render_snippet(
    header: str,
    source: str,
    line: Optional[int],
    column: Optional[int],
    *,
    context: int,
) -> str:
    """Render ``header`` with ``context`` lines of source around ``line``."""
    if line is None:
        return header

    lines = source.splitlines()
    if line < 1 or line > len(lines):
        return header

    start = max(1, line - context)
    end = min(len(lines), line + context)
    gutter_width = len(str(end))

    out = [header]
    for ln in range(start, end + 1):
        text = lines[ln - 1]
        marker = ">" if ln == line else " "
        out.append(f"  {marker} {ln:>{gutter_width}} | {text}")
        if ln == line and column is not None and column >= 1:
            caret_col = min(column, len(text) + 1)
            out.append(
                f"    {' ' * gutter_width} | {' ' * (caret_col - 1)}^"
            )
    return "\n".join(out)


def format_error(err: VyrelError, source: str) -> str:
    """Render ``err`` with one line of source and a caret."""
    return _render_snippet(
        err._render_plain(), source, err.line, err.column, context=0,
    )


def format_error_with_snippet(err: VyrelError, source: str) -> str:
    """Render ``err`` with two lines of source context before and after."""
    return _render_snippet(
        err._render_plain(), source, err.line, err.column, context=2,
    )
