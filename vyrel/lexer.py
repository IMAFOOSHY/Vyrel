"""The Vyrel lexer (scanner).

Converts raw source text into a list of :class:`Token` objects.  Implements
all of spec section 2.1:

* Longest-match operator scanning (``**`` before ``*``, ``<=`` before ``<``,
  ``==``/``=>`` handled explicitly, compound-assign pairs, etc.).
* Newlines are significant statement terminators, but are *suppressed* while
  inside parentheses, brackets, or braces (``bracket_depth > 0``).
* Blank lines and comment-only lines collapse (no spurious NEWLINE tokens).
* Every program is guaranteed to end with exactly one NEWLINE (if the source
  does not already end in one) followed by EOF.
* ``\\r\\n`` and lone ``\\r`` are normalized to ``\\n`` before scanning.
* String escapes ``\\n \\t \\r \\\\ \\" \\' \\0`` and template-brace escapes
  ``\\{ \\}`` are honored.
* Integers allow single underscores between digits (``1_000_000``) but not
  leading/trailing/doubled underscores.
* ``1.`` and ``.5`` are rejected at the lexer level (spec 2.1).
* ``"`` or ``'`` strings containing unescaped ``{...}`` become TEMPLATE tokens;
  otherwise they become STRING tokens.  ``{{`` and ``}}`` are NOT special; use
  ``\\{`` / ``\\}`` for literal braces.
* Nested braces and nested string literals inside a ``{...}`` interpolation
  are scanned correctly.  Empty ``{}`` is a LexError.
* Every lexing problem raises :class:`LexError` with accurate line/column.

The lexer is a hand-written scanner with a small ``pos`` cursor and explicit
line/column tracking.  It has no dependencies on later layers.
"""

from __future__ import annotations

from typing import List, Optional

from .errors import LexError
from .tokens import (
    KEYWORDS,
    InterpPart,
    Token,
    TokenType,
)

#: Characters that open/close a bracket group (used for newline suppression).
_OPENERS = {"(": TokenType.LPAREN, "[": TokenType.LBRACKET, "{": TokenType.LBRACE}
_CLOSERS = {")": "(", "]": "[", "}": "{"}

#: Mapping of character escapes to their decoded value.  Used in both strings
#: and templates so ``"a\\nb"`` and ``"a\\nb {x}"`` decode identically.
_STRING_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "\\": "\\",
    '"': '"',
    "'": "'",
    "0": "\0",
    "{": "{",
    "}": "}",
}


class Lexer:
    """Hand-written lexer for Vyrel source text."""

    def __init__(self, source: str) -> None:
        # Normalize line endings so all downstream logic sees '\n' only.
        self.source = source.replace("\r\n", "\n").replace("\r", "\n")
        self.length = len(self.source)
        self.pos = 0
        self.line = 1
        self.column = 1

        self.tokens: List[Token] = []
        # Bracket stack for newline suppression and balanced-closer checks.
        # Each entry stores (opener_char, opener_line, opener_column).
        self.brackets: List[tuple[str, int, int]] = []

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #

    def tokenize(self) -> List[Token]:
        """Scan the entire source and return all tokens, ending with EOF."""
        while self.pos < self.length:
            ch = self.source[self.pos]

            if ch == "\n":
                self._handle_newline()
            elif ch in " \t":
                self._advance()  # skip horizontal whitespace
            elif ch == "#":
                self._skip_comment()
            elif ch.isdigit():
                self._scan_number()
            elif ch in ('"', "'"):
                self._scan_string(quote=ch)
            elif ch.isalpha() or ch == "_":
                self._scan_identifier_or_keyword()
            elif ch == "=":
                self._scan_equals()
            elif ch == "!":
                self._scan_bang()
            elif ch == "<":
                self._scan_lt()
            elif ch == ">":
                self._scan_gt()
            elif ch in "+-*/%":
                self._scan_arithmetic_or_assign(ch)
            elif ch in _OPENERS:
                self._scan_opener()
            elif ch in _CLOSERS:
                self._scan_closer()
            elif ch == ",":
                self._emit(TokenType.COMMA, ",", ch)
                self._advance()
            elif ch == ":":
                self._emit(TokenType.COLON, ":", ch)
                self._advance()
            elif ch == ".":
                # A number cannot start with '.': spec 2.1 rejects '.5'.
                if self._peek(1).isdigit():
                    raise LexError(
                        "malformed number: a number cannot start with '.' "
                        "(write '0.5' instead of '.5')",
                        line=self.line, column=self.column,
                    )
                self._emit(TokenType.DOT, ".", ch)
                self._advance()
            else:
                raise LexError(
                    f"unexpected character {ch!r}",
                    line=self.line,
                    column=self.column,
                )

        # Ensure the token stream ends with exactly one NEWLINE then EOF.
        if not self.tokens or self.tokens[-1].type is not TokenType.NEWLINE:
            # If the last token isn't a NEWLINE, synthesize one on the line
            # *after* the final token so blank trailing lines still resolve.
            self.tokens.append(
                Token(TokenType.NEWLINE, "\n", self.line, self.column, "\n")
            )

        self.tokens.append(Token(TokenType.EOF, "", self.line, self.column, ""))
        return self.tokens

    # ------------------------------------------------------------------ #
    # Cursor helpers                                                     #
    # ------------------------------------------------------------------ #

    def _advance(self, count: int = 1) -> None:
        """Advance the cursor by ``count`` characters, updating line/column."""
        for _ in range(count):
            if self.pos >= self.length:
                return
            if self.source[self.pos] == "\n":
                self.line += 1
                self.column = 1
            else:
                self.column += 1
            self.pos += 1

    def _peek(self, offset: int = 0) -> str:
        idx = self.pos + offset
        return self.source[idx] if idx < self.length else ""

    def _emit(self, tok_type: TokenType, value: object, text: str) -> None:
        """Append a token at the cursor's current position, then nothing."""
        self.tokens.append(
            Token(tok_type, value, self.line, self.column, text)
        )

    def _emit_consumed(
        self,
        tok_type: TokenType,
        value: object,
        start_line: int,
        start_col: int,
        start_pos: int,
    ) -> None:
        """Append a token for text already consumed between ``start_pos`` and
        the current cursor, with positions captured *before* consumption."""
        text = self.source[start_pos:self.pos]
        self.tokens.append(Token(tok_type, value, start_line, start_col, text))

    # ------------------------------------------------------------------ #
    # Newlines, whitespace, comments                                     #
    # ------------------------------------------------------------------ #

    def _handle_newline(self) -> None:
        """Emit a NEWLINE token unless suppressed by bracket depth."""
        if not self.brackets:
            # Collapse consecutive newlines: only emit if the previous token is
            # not already a NEWLINE (and not the very start of the stream).
            if self.tokens and self.tokens[-1].type is not TokenType.NEWLINE:
                self.tokens.append(
                    Token(TokenType.NEWLINE, "\n", self.line, self.column, "\n")
                )
        self._advance()

    def _skip_comment(self) -> None:
        """Skip from ``#`` through (but not including) the next newline."""
        while self.pos < self.length and self.source[self.pos] != "\n":
            self._advance()

    # ------------------------------------------------------------------ #
    # Numbers                                                            #
    # ------------------------------------------------------------------ #

    def _scan_number(self) -> None:
        """Scan an INT or FLOAT literal.

        Integers accept single underscores between digits.  Floats require at
        least one digit on both sides of the decimal point: ``1.`` and ``.5``
        are rejected here at the lexer level (spec 2.1).
        """
        start_pos, start_line, start_col = self.pos, self.line, self.column

        # Integer part with underscore rules.
        self._consume_digits(allow_underscores=True)
        self._validate_underscores(
            self.source[start_pos:self.pos], start_line, start_col
        )

        is_float = False

        # Decimal point: if the next char is '.', the one after it MUST be a
        # digit; otherwise "1." is malformed (spec 2.1: reject "1.").
        if self._peek() == ".":
            if self._peek(1).isdigit():
                is_float = True
                self._advance()  # consume '.'
                self._consume_digits(allow_underscores=True)
            else:
                raise LexError(
                    "malformed number: '.' must be followed by a digit",
                    line=self.line, column=self.column,
                )

        # Exponent (``e`` / ``E`` with optional sign and required digits).
        if self._peek() in ("e", "E"):
            nxt = self._peek(1)
            ok = nxt.isdigit() or (nxt in "+-" and self._peek(2).isdigit())
            if ok:
                is_float = True
                self._advance()  # 'e'
                if self._peek() in "+-":
                    self._advance()
                self._consume_digits(allow_underscores=True)

        raw = self.source[start_pos:self.pos]
        try:
            if is_float:
                value = float(raw.replace("_", ""))
                tok_type = TokenType.FLOAT
            else:
                value = int(raw.replace("_", ""))
                tok_type = TokenType.INT
        except ValueError as exc:  # pragma: no cover - defensive
            raise LexError(
                f"malformed number {raw!r}",
                line=start_line, column=start_col,
            ) from exc

        self.tokens.append(Token(tok_type, value, start_line, start_col, raw))

    def _consume_digits(self, *, allow_underscores: bool) -> str:
        """Consume a run of digits (and, if allowed, internal underscores).

        Underscores are accepted here only *between* digits; the caller is
        responsible for calling :meth:`_validate_underscores`.
        """
        start = self.pos
        while self.pos < self.length:
            ch = self.source[self.pos]
            if ch.isdigit():
                self._advance()
            elif allow_underscores and ch == "_":
                self._advance()
            else:
                break
        return self.source[start:self.pos]

    def _validate_underscores(self, raw: str, line: int, column: int) -> None:
        """Reject ``_1``, ``1_``, ``1__2``-style invalid integer groupings."""
        if not raw or "_" not in raw:
            return
        if raw[0] == "_" or raw[-1] == "_":
            raise LexError(
                "malformed number: underscores must be between digits",
                line=line, column=column,
            )
        prev = ""
        for ch in raw:
            if ch == "_" and (prev == "_" or prev == ""):
                raise LexError(
                    "malformed number: underscores must be between digits",
                    line=line, column=column,
                )
            prev = ch

    # ------------------------------------------------------------------ #
    # Identifiers and keywords                                           #
    # ------------------------------------------------------------------ #

    def _scan_identifier_or_keyword(self) -> None:
        start_pos, start_line, start_col = self.pos, self.line, self.column
        self._advance()  # first char is known alpha or '_'
        while self.pos < self.length:
            ch = self.source[self.pos]
            if ch.isalnum() or ch == "_":
                self._advance()
            else:
                break
        text = self.source[start_pos:self.pos]
        if text in KEYWORDS:
            self.tokens.append(
                Token(TokenType.KEYWORD, text, start_line, start_col, text)
            )
        else:
            self.tokens.append(
                Token(TokenType.IDENT, text, start_line, start_col, text)
            )

    # ------------------------------------------------------------------ #
    # Strings and templates                                              #
    # ------------------------------------------------------------------ #

    def _scan_string(self, quote: str) -> None:
        """Scan a quoted string literal; emit STRING or TEMPLATE."""
        start_pos, start_line, start_col = self.pos, self.line, self.column
        self._advance()  # opening quote

        parts: List[object] = []  # str | InterpPart
        buf: List[str] = []       # current literal segment
        has_interp = False

        def flush() -> None:
            if buf:
                parts.append("".join(buf))
                buf.clear()

        while True:
            if self.pos >= self.length:
                raise LexError(
                    "unterminated string literal",
                    line=start_line, column=start_col,
                )
            ch = self.source[self.pos]

            if ch == quote:
                self._advance()  # closing quote
                break

            if ch == "\n":
                raise LexError(
                    "unterminated string literal (newline before closing quote)",
                    line=start_line, column=start_col,
                )

            if ch == "\\":
                esc_line, esc_col = self.line, self.column
                self._advance()  # backslash
                if self.pos >= self.length:
                    raise LexError(
                        "unterminated string literal",
                        line=start_line, column=start_col,
                    )
                esc = self.source[self.pos]
                if esc not in _STRING_ESCAPES:
                    raise LexError(
                        f"unknown escape sequence '\\{esc}'",
                        line=esc_line, column=esc_col,
                    )
                buf.append(_STRING_ESCAPES[esc])
                self._advance()
                continue

            if ch == "{":
                if not self._has_matching_interp_brace():
                    raise LexError(
                        "unmatched '{' in string template",
                        line=self.line, column=self.column,
                    )
                has_interp = True
                flush()
                parts.append(self._scan_interp())
                continue

            buf.append(ch)
            self._advance()

        flush()

        raw_text = self.source[start_pos:self.pos]

        if has_interp:
            self.tokens.append(
                Token(TokenType.TEMPLATE, parts, start_line, start_col, raw_text)
            )
        else:
            value = "".join(p if isinstance(p, str) else "" for p in parts)
            self.tokens.append(
                Token(TokenType.STRING, value, start_line, start_col, raw_text)
            )

    def _has_matching_interp_brace(self) -> bool:
        """Cheap lookahead: is there a matching ``}`` ahead for this ``{``?"""
        depth = 0
        i = self.pos
        in_quote: Optional[str] = None
        while i < self.length:
            c = self.source[i]
            if in_quote is not None:
                if c == "\\":
                    i += 2
                    continue
                if c == in_quote:
                    in_quote = None
                i += 1
                continue
            if c in ("'", '"'):
                in_quote = c
                i += 1
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return True
            elif c == "\n":
                return False
            i += 1
        return False

    def _scan_interp(self) -> InterpPart:
        """Scan ``{ ... }`` interpolation content inside a template string."""
        open_line, open_col = self.line, self.column
        self._advance()  # consume '{'

        expr_line, expr_col = self.line, self.column
        start = self.pos
        depth = 1  # we're inside one '{'
        in_quote: Optional[str] = None

        while self.pos < self.length:
            c = self.source[self.pos]

            if in_quote is not None:
                if c == "\\":
                    self._advance()
                    if self.pos < self.length:
                        self._advance()
                    continue
                if c == "\n":
                    raise LexError(
                        "unterminated string literal inside template",
                        line=expr_line, column=expr_col,
                    )
                if c == in_quote:
                    in_quote = None
                self._advance()
                continue

            if c in ("'", '"'):
                in_quote = c
                self._advance()
                continue
            if c == "\n":
                raise LexError(
                    "unterminated '{' in string template",
                    line=open_line, column=open_col,
                )
            if c == "{":
                depth += 1
                self._advance()
                continue
            if c == "}":
                depth -= 1
                if depth == 0:
                    raw = self.source[start:self.pos]
                    leading = len(raw) - len(raw.lstrip())
                    stripped = raw.strip()
                    self._advance()  # consume '}'
                    if stripped == "":
                        raise LexError(
                            "empty '{}' interpolation in string template",
                            line=open_line, column=open_col,
                        )
                    return InterpPart(
                        text=stripped,
                        line=expr_line,
                        column=expr_col + leading,
                    )
                self._advance()
                continue
            self._advance()

        raise LexError(
            "unterminated '{' in string template",
            line=open_line, column=open_col,
        )

    # ------------------------------------------------------------------ #
    # Operators & punctuation (lookahead)                                #
    # ------------------------------------------------------------------ #

    def _scan_equals(self) -> None:
        start_line, start_col, start_pos = self.line, self.column, self.pos
        if self._peek(1) == "=":
            self._advance(2)
            self._emit_consumed(TokenType.EQ, "==", start_line, start_col, start_pos)
        elif self._peek(1) == ">":
            self._advance(2)
            self._emit_consumed(TokenType.ARROW, "=>", start_line, start_col, start_pos)
        else:
            self._advance()
            self._emit_consumed(TokenType.ASSIGN, "=", start_line, start_col, start_pos)

    def _scan_bang(self) -> None:
        start_line, start_col, start_pos = self.line, self.column, self.pos
        if self._peek(1) == "=":
            self._advance(2)
            self._emit_consumed(TokenType.NOT_EQ, "!=", start_line, start_col, start_pos)
        else:
            raise LexError(
                "unexpected character '!' (did you mean '!='?)",
                line=start_line, column=start_col,
            )

    def _scan_lt(self) -> None:
        start_line, start_col, start_pos = self.line, self.column, self.pos
        if self._peek(1) == "=":
            self._advance(2)
            self._emit_consumed(TokenType.LE, "<=", start_line, start_col, start_pos)
        else:
            self._advance()
            self._emit_consumed(TokenType.LT, "<", start_line, start_col, start_pos)

    def _scan_gt(self) -> None:
        start_line, start_col, start_pos = self.line, self.column, self.pos
        if self._peek(1) == "=":
            self._advance(2)
            self._emit_consumed(TokenType.GE, ">=", start_line, start_col, start_pos)
        else:
            self._advance()
            self._emit_consumed(TokenType.GT, ">", start_line, start_col, start_pos)

    def _scan_arithmetic_or_assign(self, ch: str) -> None:
        """Handle ``+ - * / %`` and their compound-assignment forms."""
        start_line, start_col, start_pos = self.line, self.column, self.pos
        two = self.source[self.pos:self.pos + 2]

        pair_map = {
            "**": TokenType.DOUBLE_STAR,
            "//": TokenType.DOUBLE_SLASH,
            "+=": TokenType.PLUS_ASSIGN,
            "-=": TokenType.MINUS_ASSIGN,
            "*=": TokenType.STAR_ASSIGN,
            "/=": TokenType.SLASH_ASSIGN,
            "%=": TokenType.PERCENT_ASSIGN,
        }
        if two in pair_map:
            self._advance(2)
            self._emit_consumed(pair_map[two], two, start_line, start_col, start_pos)
            return

        single_map = {
            "+": TokenType.PLUS,
            "-": TokenType.MINUS,
            "*": TokenType.STAR,
            "/": TokenType.SLASH,
            "%": TokenType.PERCENT,
        }
        self._advance()
        self._emit_consumed(single_map[ch], ch, start_line, start_col, start_pos)

    def _scan_opener(self) -> None:
        ch = self.source[self.pos]
        self._emit(_OPENERS[ch], ch, ch)
        self.brackets.append((ch, self.line, self.column))
        self._advance()

    def _scan_closer(self) -> None:
        ch = self.source[self.pos]
        if not self.brackets:
            raise LexError(
                f"unmatched closing '{ch}'",
                line=self.line, column=self.column,
            )
        opener, _oline, _ocol = self.brackets.pop()
        expected = _CLOSERS[ch]
        if opener != expected:
            raise LexError(
                f"mismatched closing '{ch}' (expected to close the "
                f"'{opener}' opened earlier)",
                line=self.line, column=self.column,
            )
        type_map = {
            ")": TokenType.RPAREN,
            "]": TokenType.RBRACKET,
            "}": TokenType.RBRACE,
        }
        self._emit(type_map[ch], ch, ch)
        self._advance()
