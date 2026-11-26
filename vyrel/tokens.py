"""Token types and the :class:`Token` dataclass for the Vyrel lexer.

Design choice (spec-permitted): rather than allocating a distinct ``TokenType``
member for every keyword, the lexer emits a single ``KEYWORD`` token type and
the parser looks keywords up in the :data:`KEYWORDS` table to decide how to
treat them.  This keeps the enum compact and makes the keyword set trivial to
extend later.  Keyword tokens carry the keyword text in ``value``.

``Token.value`` conventions
---------------------------
* INT / FLOAT: the parsed Python ``int`` / ``float``.
* STRING:      the *decoded* Python ``str`` (escapes already resolved).
* TEMPLATE:    a list whose items are either plain ``str`` pieces or
               :class:`InterpPart` records; see :class:`InterpPart`.
* KEYWORD:     the keyword itself as a ``str`` (identical to ``text``).
* Everything else (operators, punctuation, IDENT, NEWLINE, EOF):
               the raw source text of the token.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Union


class TokenType(Enum):
    """Every token kind the Vyrel lexer can produce."""

    # --- literals -------------------------------------------------------
    INT = auto()
    FLOAT = auto()
    STRING = auto()
    TEMPLATE = auto()  # a string literal that contains {interpolation}

    # --- identifiers & keywords ----------------------------------------
    IDENT = auto()
    KEYWORD = auto()  # value is the keyword text; see KEYWORDS

    # --- arithmetic / comparison / logical operators -------------------
    PLUS = auto()            # +
    MINUS = auto()           # -
    STAR = auto()            # *
    SLASH = auto()           # /
    DOUBLE_SLASH = auto()    # //
    PERCENT = auto()         # %
    DOUBLE_STAR = auto()     # **
    EQ = auto()              # ==
    NOT_EQ = auto()          # !=
    LT = auto()              # <
    LE = auto()              # <=
    GT = auto()              # >
    GE = auto()              # >=
    AND = auto()             # keyword 'and' is a KEYWORD; this is a reserved
                             # slot kept for symmetry/documentation only.
    OR = auto()              # (same note as AND)
    NOT = auto()             # (same note as AND)

    # --- assignment -----------------------------------------------------
    ASSIGN = auto()          # =
    PLUS_ASSIGN = auto()     # +=
    MINUS_ASSIGN = auto()    # -=
    STAR_ASSIGN = auto()     # *=
    SLASH_ASSIGN = auto()    # /=
    PERCENT_ASSIGN = auto()  # %=
    ARROW = auto()           # =>

    # --- punctuation ----------------------------------------------------
    LPAREN = auto()          # (
    RPAREN = auto()          # )
    LBRACKET = auto()        # [
    RBRACKET = auto()        # ]
    LBRACE = auto()          # {
    RBRACE = auto()          # }
    COMMA = auto()           # ,
    COLON = auto()           # :
    DOT = auto()             # .

    # --- structural -----------------------------------------------------
    NEWLINE = auto()
    EOF = auto()


#: All Vyrel keywords.  The lexer consults this set to classify identifiers;
#: keyword tokens are emitted as ``TokenType.KEYWORD`` with ``value`` set to the
#: keyword text.
KEYWORDS = frozenset({
    "let", "const", "fn", "return",
    "if", "then", "elif", "else", "end",
    "while", "for", "in", "do", "break", "continue",
    "try", "catch", "finally", "throw",
    "and", "or", "not", "true", "false", "nil",
    "class", "extends", "self", "super",
    "import", "from", "as", "match", "case",
})


@dataclass(frozen=True)
class InterpPart:
    """One ``{expr}`` interpolation segment inside a TEMPLATE token.

    The lexer does not parse the inner expression; it stores the raw text plus
    the 1-based line/column of its first non-space character (in the original
    source), so the parser can later lex & parse it with accurate positions.

    Attributes:
        text:   Raw source text of the interpolated expression (trimmed of
                leading/trailing ASCII spaces at the boundaries; interior
                whitespace is preserved verbatim).
        line:   1-based line of the expression's first character.
        column: 1-based column of the expression's first character.
    """

    text: str
    line: int
    column: int


#: The value type stored on a TEMPLATE token.
TemplateValue = List[Union[str, InterpPart]]


@dataclass
class Token:
    """A single lexed token.

    Attributes:
        type:   The :class:`TokenType` of this token.
        value:  Parsed Python value for INT/FLOAT/STRING/TEMPLATE; raw source
                text otherwise (see module docstring for details).
        line:   1-based line number where the token starts.
        column: 1-based column number where the token starts.
        text:   The exact raw source text of the token (empty for NEWLINE/EOF).
    """

    type: TokenType
    value: object
    line: int
    column: int
    text: str = ""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"Token({self.type.name}, {self.value!r}, "
            f"line={self.line}, col={self.column})"
        )
