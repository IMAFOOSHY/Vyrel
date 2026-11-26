"""Error hierarchy and beginner-friendly error formatting for Vyrel.

All Vyrel errors derive from :class:`VyrelError`.  Each error carries an
optional 1-based ``line`` (and ``column`` where available) so the CLI and REPL
can print precise diagnostics.  Messages are phrased in plain English because
the language targets beginners.
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


def format_error(err: VyrelError, source: str) -> str:
    """Render ``err`` with the source line and a caret at the error column."""
    header = err._render_plain()
    if err.line is None:
        return header

    lines = source.splitlines()
    if err.line < 1 or err.line > len(lines):
        return header

    line_text = lines[err.line - 1]
    gutter_width = len(str(err.line))
    gutter = " " * gutter_width
    out = [header, f"  {err.line:>{gutter_width}} | {line_text}"]

    if err.column is not None and err.column >= 1:
        caret_col = min(err.column, len(line_text) + 1)
        out.append(f"  {gutter} | {' ' * (caret_col - 1)}^")

    return "\n".join(out)
