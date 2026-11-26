"""Unit tests for :mod:`vyrel.lexer`.

Covers every token type, every operator, keyword-vs-identifier classification,
comment handling, newline suppression inside brackets, template scanning
(including nested braces and nested strings), every documented error case with
exact positions, and two full sample programs (1.1 syntax tour and 3.4
spinning cube) that must tokenize without raising.
"""

from __future__ import annotations

import unittest
from typing import List

from vyrel.errors import LexError, VyrelError, format_error
from vyrel.lexer import Lexer
from vyrel.tokens import InterpPart, Token, TokenType


def lex(src: str) -> List[Token]:
    return Lexer(src).tokenize()


def types(src: str) -> List[TokenType]:
    return [t.type for t in lex(src)]


#: Mapping used only by test_punctuation to compare opener TokenTypes.
_OPENER_NAME = {"(": "LPAREN", "[": "LBRACKET", "{": "LBRACE"}


class TestTokenTypesAndOperators(unittest.TestCase):
    """Every token kind and every operator maps to the correct TokenType."""

    def test_int(self) -> None:
        toks = lex("42")
        self.assertEqual(toks[0].type, TokenType.INT)
        self.assertEqual(toks[0].value, 42)

    def test_float(self) -> None:
        toks = lex("3.14")
        self.assertEqual(toks[0].type, TokenType.FLOAT)
        self.assertAlmostEqual(toks[0].value, 3.14)

    def test_int_underscores(self) -> None:
        self.assertEqual(lex("1_000_000")[0].value, 1_000_000)

    def test_string(self) -> None:
        toks = lex('"hello"')
        self.assertEqual(toks[0].type, TokenType.STRING)
        self.assertEqual(toks[0].value, "hello")

    def test_single_quote_string(self) -> None:
        self.assertEqual(lex("'hi'")[0].value, "hi")

    def test_string_escapes(self) -> None:
        toks = lex(r'"a\nb\tc\\d\"e\0f"')
        self.assertEqual(toks[0].value, 'a\nb\tc\\d"e\0f')

    def test_template_token(self) -> None:
        toks = lex('"fps={fps}"')
        self.assertEqual(toks[0].type, TokenType.TEMPLATE)
        parts = toks[0].value
        self.assertEqual(parts[0], "fps=")
        self.assertIsInstance(parts[1], InterpPart)
        self.assertEqual(parts[1].text, "fps")

    def test_ident_vs_keyword(self) -> None:
        toks = lex("letter let")
        self.assertEqual(toks[0].type, TokenType.IDENT)
        self.assertEqual(toks[0].value, "letter")
        self.assertEqual(toks[1].type, TokenType.KEYWORD)
        self.assertEqual(toks[1].value, "let")

    def test_all_operators(self) -> None:
        cases = {
            "+": TokenType.PLUS,
            "-": TokenType.MINUS,
            "*": TokenType.STAR,
            "/": TokenType.SLASH,
            "//": TokenType.DOUBLE_SLASH,
            "%": TokenType.PERCENT,
            "**": TokenType.DOUBLE_STAR,
            "==": TokenType.EQ,
            "!=": TokenType.NOT_EQ,
            "<": TokenType.LT,
            "<=": TokenType.LE,
            ">": TokenType.GT,
            ">=": TokenType.GE,
            "=": TokenType.ASSIGN,
            "+=": TokenType.PLUS_ASSIGN,
            "-=": TokenType.MINUS_ASSIGN,
            "*=": TokenType.STAR_ASSIGN,
            "/=": TokenType.SLASH_ASSIGN,
            "%=": TokenType.PERCENT_ASSIGN,
            "=>": TokenType.ARROW,
        }
        for text, tt in cases.items():
            with self.subTest(op=text):
                toks = lex(f"x {text} y")
                self.assertEqual(toks[1].type, tt, f"op {text!r}")

    def test_punctuation(self) -> None:
        # Openers and separators appear alone; closers must be probed with a
        # matching opener, since an unbalanced closer is (correctly) a LexError.
        cases = {
            "(": TokenType.LPAREN,
            "[": TokenType.LBRACKET,
            "{": TokenType.LBRACE,
            ",": TokenType.COMMA,
            ":": TokenType.COLON,
            ".": TokenType.DOT,
        }
        for text, tt in cases.items():
            with self.subTest(punct=text):
                toks = lex(f"a {text} b")
                self.assertEqual(toks[1].type, tt, f"punct {text!r}")

        closer_cases = {
            "(": (")", TokenType.RPAREN),
            "[": ("]", TokenType.RBRACKET),
            "{": ("}", TokenType.RBRACE),
        }
        for opener, (closer, tt) in closer_cases.items():
            with self.subTest(closer=closer):
                toks = lex(f"{opener} {closer}")
                self.assertEqual(
                    toks[0].type,
                    getattr(TokenType, _OPENER_NAME[opener]),
                    f"opener {opener!r}",
                )
                self.assertEqual(toks[1].type, tt, f"closer {closer!r}")


class TestNewlinesAndComments(unittest.TestCase):
    def test_newline_between_statements(self) -> None:
        toks = lex("let x = 1\nlet y = 2\n")
        self.assertEqual(
            types("let x = 1\nlet y = 2\n"),
            [
                TokenType.KEYWORD, TokenType.IDENT, TokenType.ASSIGN,
                TokenType.INT, TokenType.NEWLINE,
                TokenType.KEYWORD, TokenType.IDENT, TokenType.ASSIGN,
                TokenType.INT, TokenType.NEWLINE,
                TokenType.EOF,
            ],
        )
        # Exactly one NEWLINE before EOF.
        self.assertEqual(toks[-2].type, TokenType.NEWLINE)
        self.assertEqual(toks[-1].type, TokenType.EOF)

    def test_multiline_list_suppresses_newlines(self) -> None:
        src = "let xs = [\n  1,\n  2,\n  3\n]\n"
        tts = types(src)
        self.assertNotIn(
            TokenType.NEWLINE,
            tts[tts.index(TokenType.LBRACKET):
                tts.index(TokenType.RBRACKET) + 1],
        )

    def test_blank_and_comment_lines_collapse(self) -> None:
        src = "let x = 1\n\n# comment\n   # indented\n\nlet y = 2\n"
        tts = types(src)
        # Two statements -> exactly two NEWLINE tokens before EOF.
        self.assertEqual(tts.count(TokenType.NEWLINE), 2)

    def test_crlf_normalized(self) -> None:
        toks = lex("let x = 1\r\nlet y = 2\r\n")
        # No stray '\r' anywhere.
        for t in toks:
            self.assertNotIn("\r", str(t.text))

    def test_final_newline_guaranteed(self) -> None:
        toks = lex("let x = 1")
        self.assertEqual(toks[-2].type, TokenType.NEWLINE)
        self.assertEqual(toks[-1].type, TokenType.EOF)


class TestTemplates(unittest.TestCase):
    def test_template_nested_parens(self) -> None:
        toks = lex('"{round(win.fps)}"')
        self.assertEqual(toks[0].type, TokenType.TEMPLATE)
        self.assertEqual(toks[0].value[0].text, "round(win.fps)")

    def test_template_escaped_braces(self) -> None:
        toks = lex(r'"\{literal\}"')
        # No interpolation -> plain STRING.
        self.assertEqual(toks[0].type, TokenType.STRING)
        self.assertEqual(toks[0].value, "{literal}")

    def test_template_nested_string_literal(self) -> None:
        toks = lex('"x={\'a}b\'}"')
        self.assertEqual(toks[0].type, TokenType.TEMPLATE)
        self.assertEqual(toks[0].value[1].text, "'a}b'")

    def test_template_multiple_parts(self) -> None:
        toks = lex('"a{x}b{y}c"')
        parts = toks[0].value
        self.assertEqual(parts[0], "a")
        self.assertEqual(parts[1].text, "x")
        self.assertEqual(parts[2], "b")
        self.assertEqual(parts[3].text, "y")
        self.assertEqual(parts[4], "c")

    def test_template_leading_and_trailing(self) -> None:
        toks = lex('"{x}"')
        parts = toks[0].value
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].text, "x")


class TestNumbersErrors(unittest.TestCase):
    def test_reject_trailing_dot(self) -> None:
        with self.assertRaises(LexError) as ctx:
            lex("1.")
        self.assertIsInstance(ctx.exception, VyrelError)
        self.assertIn("'.' must be followed by a digit", ctx.exception.message)

    def test_reject_leading_dot(self) -> None:
        with self.assertRaises(LexError):
            lex(".5")

    def test_reject_bad_underscores(self) -> None:
        for src in ("1__2", "1_", "_1"):  # '_1' will lex as IDENT, not number
            with self.subTest(src=src):
                if src == "_1":
                    # '_1' is a valid identifier per Vyrel rules; assert that.
                    self.assertEqual(lex(src)[0].type, TokenType.IDENT)
                else:
                    with self.assertRaises(LexError):
                        lex(src)


class TestErrorsWithPositions(unittest.TestCase):
    def _pos(self, src: str) -> tuple:
        with self.assertRaises(LexError) as ctx:
            lex(src)
        return ctx.exception.line, ctx.exception.column

    def test_unterminated_string(self) -> None:
        line, col = self._pos('let s = "abc')
        self.assertEqual((line, col), (1, 9))

    def test_bad_escape(self) -> None:
        line, col = self._pos(r'"a\q"')
        # Backslash is at column 3 (1-based, after opening quote at col 1).
        self.assertEqual((line, col), (1, 3))

    def test_unknown_character(self) -> None:
        line, col = self._pos("let x = @")
        self.assertEqual((line, col), (1, 9))

    def test_unmatched_closing(self) -> None:
        line, col = self._pos("let x = )")
        self.assertEqual((line, col), (1, 9))

    def test_unbalanced_open_bracket_at_eof(self) -> None:
        # A '(' that is never closed is fine for the lexer: it just suppresses
        # newlines.  The parser will report the structural error.  But an
        # unmatched '{' that begins an interpolation must error.
        with self.assertRaises(LexError):
            lex('"x={y"')

    def test_empty_interp(self) -> None:
        line, col = self._pos('"a{}b"')
        self.assertEqual((line, col), (1, 3))

    def test_format_error_snippet(self) -> None:
        src = 'let s = "abc'
        try:
            lex(src)
        except LexError as e:
            out = format_error(e, src)
            self.assertIn("line 1", out)
            self.assertIn('let s = "abc', out)
            self.assertIn("^", out)
        else:  # pragma: no cover
            self.fail("expected LexError")


class TestSamplePrograms(unittest.TestCase):
    """The two canonical sample programs must tokenize without error."""

    def test_syntax_tour_1_1(self) -> None:
        src = (
            "# Vyrel syntax tour\n"
            "let name = \"Vyrel\"\n"
            "const VERSION = 1\n"
            "let nums = [1, 2, 3]\n"
            "let totals = {a: 1, b: 2}\n"
            "fn greet(who = \"world\") do\n"
            "  return \"hello, {who}!\"\n"
            "end\n"
            "class Vec2\n"
            "  fn init(x, y) do\n"
            "    self.x = x\n"
            "    self.y = y\n"
            "  end\n"
            "  fn length() do\n"
            "    return (self.x ** 2 + self.y ** 2) ** 0.5\n"
            "  end\n"
            "end\n"
            "let v = Vec2(3, 4)\n"
            "if v.length() > 4 then\n"
            "  print(\"long\")\n"
            "elif v.length() == 4 then\n"
            "  print(\"short\")\n"
            "else\n"
            "  print(\"other\")\n"
            "end\n"
            "for i in nums do\n"
            "  print(i)\n"
            "end\n"
            "try\n"
            "  throw \"oops\"\n"
            "catch e\n"
            "  print(e)\n"
            "finally\n"
            "  print(\"done\")\n"
            "end\n"
        )
        toks = lex(src)
        self.assertEqual(toks[-1].type, TokenType.EOF)

    def test_spinning_cube_3_4(self) -> None:
        src = (
            "# Spinning cube demo\n"
            "import gfx\n"
            "let angle = 0.0\n"
            "let verts = [\n"
            "  [-1, -1, -1], [ 1, -1, -1], [ 1,  1, -1], [-1,  1, -1],\n"
            "  [-1, -1,  1], [ 1, -1,  1], [ 1,  1,  1], [-1,  1,  1]\n"
            "]\n"
            "let edges = [\n"
            "  [0,1],[1,2],[2,3],[3,0],\n"
            "  [4,5],[5,6],[6,7],[7,4],\n"
            "  [0,4],[1,5],[2,6],[3,7]\n"
            "]\n"
            "while true do\n"
            "  gfx.clear(0, 0, 0)\n"
            "  let ca = cos(angle)\n"
            "  let sa = sin(angle)\n"
            "  let proj = []\n"
            "  for v in verts do\n"
            "    let x = v[0] * ca - v[2] * sa\n"
            "    let z = v[0] * sa + v[2] * ca\n"
            "    let y = v[1]\n"
            "    let f = 4.0 / (4.0 + z)\n"
            "    proj.append([240 + x * 120 * f, 180 + y * 120 * f])\n"
            "  end\n"
            "  for e in edges do\n"
            "    let a = proj[e[0]]\n"
            "    let b = proj[e[1]]\n"
            "    gfx.line(a[0], a[1], b[0], b[1], 0, 255, 0)\n"
            "  end\n"
            "  gfx.present()\n"
            "  angle += 0.02\n"
            "end\n"
        )
        toks = lex(src)
        self.assertEqual(toks[-1].type, TokenType.EOF)
        # Sanity: there is at least one TEMPLATE-worthy string? None here,
        # but this asserts the program parses at the *lex* level cleanly.
        self.assertTrue(len(toks) > 50)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
