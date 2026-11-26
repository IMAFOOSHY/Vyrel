"""Unit tests for :mod:`vyrel.parser`."""

from __future__ import annotations

import unittest

from vyrel import ast_nodes as ast
from vyrel.lexer import Lexer
from vyrel.parser import ParseError, Parser, parse


def p(src: str) -> ast.Program:
    return parse(src)


def one(src: str) -> ast.Stmt:
    prog = p(src)
    assert len(prog.body) == 1, f"expected 1 stmt, got {len(prog.body)}"
    return prog.body[0]


class TestLiterals(unittest.TestCase):
    def test_int(self) -> None:
        stmt = one("42")
        self.assertIsInstance(stmt, ast.ExprStmt)
        self.assertIsInstance(stmt.expr, ast.IntLit)
        self.assertEqual(stmt.expr.value, 42)

    def test_float(self) -> None:
        stmt = one("3.14")
        self.assertIsInstance(stmt.expr, ast.FloatLit)
        self.assertAlmostEqual(stmt.expr.value, 3.14)

    def test_string(self) -> None:
        stmt = one('"hi"')
        self.assertIsInstance(stmt.expr, ast.StringLit)
        self.assertEqual(stmt.expr.value, "hi")

    def test_true_false_nil(self) -> None:
        self.assertTrue(p("true").body[0].expr.value)
        self.assertFalse(p("false").body[0].expr.value)
        self.assertIsInstance(p("nil").body[0].expr, ast.NilLit)

    def test_list(self) -> None:
        stmt = one("[1, 2, 3]")
        self.assertIsInstance(stmt.expr, ast.ListLit)
        self.assertEqual(len(stmt.expr.items), 3)

    def test_dict(self) -> None:
        stmt = one('{"a": 1, "b": 2}')
        self.assertIsInstance(stmt.expr, ast.DictLit)
        self.assertEqual(len(stmt.expr.entries), 2)

    def test_template(self) -> None:
        stmt = one('"x={1 + 2}"')
        self.assertIsInstance(stmt.expr, ast.TemplateExpr)
        parts = stmt.expr.parts
        self.assertEqual(parts[0], "x=")
        self.assertIsInstance(parts[1], ast.BinaryOp)


class TestStatements(unittest.TestCase):
    def test_let(self) -> None:
        stmt = one("let x = 1")
        self.assertIsInstance(stmt, ast.LetStmt)
        self.assertEqual(stmt.name, "x")
        self.assertFalse(stmt.is_const)

    def test_const(self) -> None:
        stmt = one("const x = 1")
        self.assertIsInstance(stmt, ast.LetStmt)
        self.assertTrue(stmt.is_const)

    def test_assign(self) -> None:
        stmt = one("x = 1")
        self.assertIsInstance(stmt, ast.AssignStmt)
        self.assertEqual(stmt.op, "=")
        self.assertIsInstance(stmt.target, ast.Ident)

    def test_compound_assign(self) -> None:
        for text, op in [("x += 1", "+="), ("x -= 1", "-="),
                         ("x *= 1", "*="), ("x /= 1", "/="),
                         ("x %= 1", "%=")]:
            with self.subTest(text=text):
                stmt = one(text)
                self.assertIsInstance(stmt, ast.AssignStmt)
                self.assertEqual(stmt.op, op)

    def test_if_elif_else(self) -> None:
        stmt = one(
            "if a then\n"
            "  b\n"
            "elif c then\n"
            "  d\n"
            "else\n"
            "  e\n"
            "end"
        )
        self.assertIsInstance(stmt, ast.IfStmt)
        self.assertEqual(len(stmt.branches), 2)
        self.assertEqual(len(stmt.else_body), 1)

    def test_while(self) -> None:
        stmt = one("while x do\n  y\nend")
        self.assertIsInstance(stmt, ast.WhileStmt)

    def test_for_simple(self) -> None:
        stmt = one("for x in xs do\n  y\nend")
        self.assertIsInstance(stmt, ast.ForStmt)
        self.assertIsNone(stmt.key_name)
        self.assertEqual(stmt.value_name, "x")

    def test_for_kv(self) -> None:
        stmt = one("for k, v in d do\n  y\nend")
        self.assertIsInstance(stmt, ast.ForStmt)
        self.assertEqual(stmt.key_name, "k")
        self.assertEqual(stmt.value_name, "v")

    def test_return(self) -> None:
        stmt = one("return 1")
        self.assertIsInstance(stmt, ast.ReturnStmt)
        self.assertIsNotNone(stmt.value)

    def test_return_bare(self) -> None:
        stmt = one("return")
        self.assertIsInstance(stmt, ast.ReturnStmt)
        self.assertIsNone(stmt.value)

    def test_break_continue(self) -> None:
        self.assertIsInstance(one("break"), ast.BreakStmt)
        self.assertIsInstance(one("continue"), ast.ContinueStmt)

    def test_throw(self) -> None:
        stmt = one("throw 1")
        self.assertIsInstance(stmt, ast.ThrowStmt)

    def test_try_catch_finally(self) -> None:
        stmt = one(
            "try\n"
            "  a\n"
            "catch e\n"
            "  b\n"
            "finally\n"
            "  c\n"
            "end"
        )
        self.assertIsInstance(stmt, ast.TryStmt)
        self.assertEqual(stmt.catch_name, "e")
        self.assertEqual(len(stmt.finally_body), 1)

    def test_try_needs_catch_or_finally(self) -> None:
        with self.assertRaises(ParseError):
            p("try\n  a\nend")

    def test_match(self) -> None:
        stmt = one(
            "match x\n"
            "case 1 then\n"
            "  a\n"
            "case 2, 3 then\n"
            "  b\n"
            "else\n"
            "  c\n"
            "end"
        )
        self.assertIsInstance(stmt, ast.MatchStmt)
        self.assertEqual(len(stmt.arms), 2)
        self.assertEqual(stmt.arms[1].patterns, (2, 3))


class TestFunctionsAndClasses(unittest.TestCase):
    def test_function_decl(self) -> None:
        stmt = one("fn f(a, b = 2)\n  return a\nend")
        self.assertIsInstance(stmt, ast.FunctionDecl)
        self.assertEqual(stmt.name, "f")
        self.assertEqual(len(stmt.params), 2)
        self.assertIsNotNone(stmt.params[1].default)

    def test_class(self) -> None:
        stmt = one(
            "class A extends B\n"
            "  fn init(x)\n"
            "    self.x = x\n"
            "  end\n"
            "  fn m()\n"
            "    return 1\n"
            "  end\n"
            "end"
        )
        self.assertIsInstance(stmt, ast.ClassDecl)
        self.assertEqual(stmt.name, "A")
        self.assertEqual(stmt.superclass, "B")
        self.assertEqual(len(stmt.methods), 2)

    def test_lambda_expr(self) -> None:
        stmt = one("let f = fn(x) => x + 1")
        self.assertIsInstance(stmt.value, ast.Lambda)
        self.assertEqual(len(stmt.value.params), 1)

    def test_block_fn_expr_at_statement_level(self) -> None:
        # Not yet supported — documented limitation for Phase 2.
        with self.assertRaises(ParseError):
            p("let f = fn(x)\n  return x\nend")


class TestImports(unittest.TestCase):
    def test_import(self) -> None:
        stmt = one("import math")
        self.assertIsInstance(stmt, ast.ImportStmt)
        self.assertEqual(stmt.module, "math")
        self.assertFalse(stmt.is_file)

    def test_import_as(self) -> None:
        stmt = one("import math as m")
        self.assertEqual(stmt.alias, "m")

    def test_import_file(self) -> None:
        stmt = one('import "file.vyr" as f')
        self.assertTrue(stmt.is_file)
        self.assertEqual(stmt.alias, "f")

    def test_from_import(self) -> None:
        stmt = one("from math import sqrt")
        self.assertIsInstance(stmt, ast.FromImportStmt)
        self.assertEqual(stmt.names, (("sqrt", None),))

    def test_from_import_as(self) -> None:
        stmt = one("from math import sqrt as s, cos")
        self.assertEqual(len(stmt.names), 2)
        self.assertEqual(stmt.names[0], ("sqrt", "s"))


class TestPrecedence(unittest.TestCase):
    def _binop(self, src: str) -> ast.Expr:
        return one(src).expr

    def test_arith_precedence(self) -> None:
        # 1 + 2 * 3 == 1 + (2 * 3)
        expr = self._binop("1 + 2 * 3")
        self.assertEqual(expr.op, "+")
        self.assertEqual(expr.right.op, "*")

    def test_power_right_assoc(self) -> None:
        # 2 ** 3 ** 4 == 2 ** (3 ** 4)
        expr = self._binop("2 ** 3 ** 4")
        self.assertEqual(expr.op, "**")
        self.assertEqual(expr.right.op, "**")

    def test_unary_minus(self) -> None:
        expr = self._binop("-x + y")
        self.assertEqual(expr.op, "+")
        self.assertIsInstance(expr.left, ast.UnaryOp)

    def test_comparison_chain_is_left_assoc(self) -> None:
        expr = self._binop("a < b < c")
        self.assertEqual(expr.op, "<")
        self.assertEqual(expr.left.op, "<")

    def test_and_or_precedence(self) -> None:
        # a or b and c == a or (b and c)
        expr = self._binop("a or b and c")
        self.assertEqual(expr.op, "or")
        self.assertEqual(expr.right.op, "and")

    def test_not(self) -> None:
        # 'not' is looser than comparisons: not (a == b).
        expr = self._binop("not a == b")
        self.assertIsInstance(expr, ast.UnaryOp)
        self.assertEqual(expr.op, "not")
        self.assertIsInstance(expr.operand, ast.BinaryOp)
        self.assertEqual(expr.operand.op, "==")


class TestPostfix(unittest.TestCase):
    def test_call(self) -> None:
        stmt = one("f(1, 2)")
        self.assertIsInstance(stmt.expr, ast.Call)
        self.assertEqual(len(stmt.expr.args), 2)

    def test_index(self) -> None:
        stmt = one("xs[0]")
        self.assertIsInstance(stmt.expr, ast.Index)

    def test_slice(self) -> None:
        stmt = one("xs[1:3]")
        self.assertIsInstance(stmt.expr, ast.Slice)
        self.assertIsNotNone(stmt.expr.lower)
        self.assertIsNotNone(stmt.expr.upper)

    def test_slice_open_lower(self) -> None:
        stmt = one("xs[:3]")
        self.assertIsNone(stmt.expr.lower)

    def test_slice_open_upper(self) -> None:
        stmt = one("xs[1:]")
        self.assertIsNone(stmt.expr.upper)

    def test_attr(self) -> None:
        stmt = one("win.fps")
        self.assertIsInstance(stmt.expr, ast.Attr)
        self.assertEqual(stmt.expr.name, "fps")

    def test_chained(self) -> None:
        stmt = one("a.b(1)[0]")
        # outermost is Index
        self.assertIsInstance(stmt.expr, ast.Index)
        self.assertIsInstance(stmt.expr.target, ast.Call)


class TestErrors(unittest.TestCase):
    def test_unexpected_token(self) -> None:
        with self.assertRaises(ParseError):
            p("let = 1")

    def test_unclosed_block(self) -> None:
        with self.assertRaises(ParseError):
            p("if x then\n  y")

    def test_bad_assign_target(self) -> None:
        with self.assertRaises(ParseError):
            p("1 = 2")

    def test_bad_index(self) -> None:
        with self.assertRaises(ParseError):
            p("xs[]")


class TestSamplePrograms(unittest.TestCase):
    def test_syntax_tour_parses(self) -> None:
        src = (
            "let nums = [1, 2, 3]\n"
            "let totals = {a: 1, b: 2}\n"
            "fn greet(who = \"world\")\n"
            "  return \"hello, {who}!\"\n"
            "end\n"
            "class Vec2\n"
            "  fn init(x, y)\n"
            "    self.x = x\n"
            "    self.y = y\n"
            "  end\n"
            "  fn length()\n"
            "    return (self.x ** 2 + self.y ** 2) ** 0.5\n"
            "  end\n"
            "end\n"
            "let v = Vec2(3, 4)\n"
        )
        prog = p(src)
        self.assertEqual(len(prog.body), 5)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
