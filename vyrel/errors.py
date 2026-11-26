"""Error hierarchy and beginner-friendly error formatting for Vyrel.

All Vyrel errors derive from :class:`VyrelError`.  Each error carries an
optional 1-based ``line`` (and ``column`` where available) so the CLI and REPL
can print precise diagnostics.  Messages are deliberately phrased in plain
English because the language targets beginners.

The :func:`format_error` helper renders an error alongside the offending source
line with a caret pointing at the column, e.g.::

    Error (line 7): cannot add a string and a number
       7 | let x = "hi" + 3
         |              ^
"""

from __future__ import annotations

from typing import Optional


class VyrelError(Exception):
    """Base class for every error raised by the Vyrel implementation.

    Attributes:
        message: Human-readable, plain-English description of the problem.
        line:    1-based source line the error occurred on, if known.
        column:  1-based source column the error occurred at, if known.
    """

    #: Short tag shown before the message, e.g. "Error", "Syntax error".
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
        """Return a one-line message with position info, if any."""
        if self.line is None:
            return f"{self.kind}: {self.message}"
        return f"{self.kind} (line {self.line}): {self.message}"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self._render_plain()


class LexError(VyrelError):
    """Raised by the lexer for malformed source (bad characters, strings, etc.)."""

    kind = "Syntax error"


def format_error(err: VyrelError, source: str) -> str:
    """Render ``err`` with the source line and a caret at the error column.

    Args:
        err:    The error to render.  Must be a :class:`VyrelError`.
        source: The complete source text that produced the error.

    Returns:
        A multi-line string suitable for printing to a terminal.  If the error
        has no line information, only the header line is returned.  If the line
        number is out of range for ``source``, the header line is returned
        without a snippet (rather than crashing).
    """
    header = err._render_plain()  # deliberately shared with __str__
    if err.line is None:
        return header

    # ``source`` may or may not end with a trailing newline; normalize for
    # splitting so that the last line is still addressable.
    lines = source.splitlines()
    if err.line < 1 or err.line > len(lines):
        return header

    line_text = lines[err.line - 1]

    # Build the gutter with a width that fits the largest line number we show.
    gutter_width = len(str(err.line))
    gutter = " " * gutter_width
    out = [header, f"  {err.line:>{gutter_width}} | {line_text}"]

    if err.column is not None and err.column >= 1:
        # Clamp the caret to just past the end of the line if the column is
        # somehow out of range (defensive: the lexer should never do this).
        caret_col = min(err.column, len(line_text) + 1)
        out.append(f"  {gutter} | {' ' * (caret_col - 1)}^")

    return "\n".join(out)
