"""Unit tests for :mod:`vyrel.interpreter`."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from vyrel import ast_nodes as ast
from vyrel.errors import VyrelRuntimeError
from vyrel.interpreter import Interpreter
from vyrel.parser import parse


def run(src: str) -> None:
    Interpreter().run(parse(src))


def run_capture(src: str) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        Interpreter().run(parse(src))
    return buf.getvalue()


def eval_one(src: str):
    """Run all but the last top-level statement, then evaluate the last.

    If the last statement is an expression statement, its value is returned.
    Otherwise the statement runs and the result is None.
    """
    prog = parse(src + "\n")
    interp = Interpreter()
    if prog.body:
        for stmt in prog.body[:-1]:
            interp.exec_block((stmt,))
        last = prog.body[-1]
        if isinstance(last, ast.ExprStmt):
            return interp.eval_expr(last.expr)
        interp.exec_block((last,))
    return None


class TestLiterals(unittest.TestCase):
    def test_int(self) -> None:
        self.assertEqual(eval_one("42"), 42)

    def test_float(self) -> None:
        self.assertAlmostEqual(eval_one("3.14"), 3.14)

    def test_string(self) -> None:
        self.assertEqual(eval_one('"hi"'), "hi")

    def test_bool(self) -> None:
        self.assertTrue(eval_one("true"))
        self.assertFalse(eval_one("false"))

    def test_nil(self) -> None:
        self.assertIsNone(eval_one("nil"))

    def test_list(self) -> None:
        self.assertEqual(eval_one("[1, 2, 3]"), [1, 2, 3])

    def test_dict_bare_keys(self) -> None:
        self.assertEqual(eval_one("{a: 1, b: 2}"), {"a": 1, "b": 2})


class TestArithmetic(unittest.TestCase):
    def test_add_int(self) -> None:
        self.assertEqual(eval_one("2 + 3"), 5)

    def test_add_str(self) -> None:
        self.assertEqual(eval_one('"a" + "b"'), "ab")

    def test_add_mixed_fails(self) -> None:
        with self.assertRaises(VyrelRuntimeError) as ctx:
            eval_one('"a" + 1')
        self.assertIn("cannot add", str(ctx.exception))

    def test_sub(self) -> None:
        self.assertEqual(eval_one("10 - 4"), 6)

    def test_mul(self) -> None:
        self.assertEqual(eval_one("3 * 4"), 12)

    def test_div_is_float(self) -> None:
        result = eval_one("7 / 2")
        self.assertIsInstance(result, float)
        self.assertAlmostEqual(result, 3.5)

    def test_floordiv_int(self) -> None:
        result = eval_one("7 // 2")
        self.assertEqual(result, 3)
        self.assertIsInstance(result, int)

    def test_mod(self) -> None:
        self.assertEqual(eval_one("10 % 3"), 1)

    def test_pow_right_assoc(self) -> None:
        self.assertEqual(eval_one("2 ** 3 ** 2"), 512)

    def test_unary_minus(self) -> None:
        self.assertEqual(eval_one("-5 + 3"), -2)


class TestComparison(unittest.TestCase):
    def test_eq(self) -> None:
        self.assertTrue(eval_one("1 == 1"))
        self.assertFalse(eval_one("1 == 2"))

    def test_lt_le_gt_ge(self) -> None:
        self.assertTrue(eval_one("1 < 2"))
        self.assertTrue(eval_one("2 <= 2"))
        self.assertTrue(eval_one("3 > 2"))
        self.assertTrue(eval_one("3 >= 3"))

    def test_inequality(self) -> None:
        self.assertTrue(eval_one("1 != 2"))


class TestLogic(unittest.TestCase):
    def test_and_returns_operand(self) -> None:
        self.assertEqual(eval_one("1 and 2"), 2)
        self.assertEqual(eval_one("0 and 2"), 0)

    def test_or_returns_operand(self) -> None:
        self.assertEqual(eval_one("1 or 2"), 1)
        self.assertEqual(eval_one("0 or 2"), 2)

    def test_not(self) -> None:
        self.assertTrue(eval_one("not false"))
        self.assertFalse(eval_one("not true"))

    def test_truthiness(self) -> None:
        # Falsy values: `not X` must be True.
        for src in ("false", "nil", "0", "0.0", '""', "[]", "{}"):
            with self.subTest(src=src):
                self.assertTrue(eval_one(f"not {src}"))

    def test_truthy_other(self) -> None:
        # Truthy values: `not not X` must be True.
        for src in ("true", "1", '"hi"', "[0]", "{a: 1}"):
            with self.subTest(src=src):
                self.assertTrue(eval_one(f"not not {src}"))


class TestVariables(unittest.TestCase):
    def test_let_and_use(self) -> None:
        self.assertEqual(eval_one("let x = 5\nx"), 5)

    def test_const_reassign_fails(self) -> None:
        with self.assertRaises(VyrelRuntimeError) as ctx:
            run("const x = 1\nx = 2")
        self.assertIn("constant", str(ctx.exception))

    def test_assign_updates(self) -> None:
        self.assertEqual(eval_one("let x = 1\nx = 2\nx"), 2)

    def test_compound_assign(self) -> None:
        self.assertEqual(eval_one("let x = 1\nx += 10\nx"), 11)

    def test_undefined_var_fails(self) -> None:
        with self.assertRaises(VyrelRuntimeError) as ctx:
            eval_one("undefined_thing")
        self.assertIn("undefined", str(ctx.exception))


class TestControlFlow(unittest.TestCase):
    def test_if_true(self) -> None:
        src = 'let x = 0\nif true then\n  x = 1\nend\nx'
        self.assertEqual(eval_one(src), 1)

    def test_if_false_else(self) -> None:
        src = 'let x = 0\nif false then\n  x = 1\nelse\n  x = 2\nend\nx'
        self.assertEqual(eval_one(src), 2)

    def test_while(self) -> None:
        src = "let i = 0\nwhile i < 3 do\n  i = i + 1\nend\ni"
        self.assertEqual(eval_one(src), 3)

    def test_while_break(self) -> None:
        src = (
            "let i = 0\n"
            "while true do\n"
            "  i = i + 1\n"
            "  if i == 3 then\n"
            "    break\n"
            "  end\n"
            "end\n"
            "i"
        )
        self.assertEqual(eval_one(src), 3)

    def test_while_continue(self) -> None:
        src = (
            "let total = 0\n"
            "let i = 0\n"
            "while i < 5 do\n"
            "  i = i + 1\n"
            "  if i == 3 then\n"
            "    continue\n"
            "  end\n"
            "  total = total + i\n"
            "end\n"
            "total"
        )
        self.assertEqual(eval_one(src), 12)

    def test_for_list(self) -> None:
        src = (
            "let total = 0\n"
            "for x in [1, 2, 3] do\n"
            "  total = total + x\n"
            "end\n"
            "total"
        )
        self.assertEqual(eval_one(src), 6)

    def test_for_dict_kv(self) -> None:
        src = (
            "let total = 0\n"
            "for k, v in {a: 1, b: 2, c: 3} do\n"
            "  total = total + v\n"
            "end\n"
            "total"
        )
        self.assertEqual(eval_one(src), 6)


class TestFunctions(unittest.TestCase):
    def test_simple_call(self) -> None:
        src = "fn add(a, b)\n  return a + b\nend\nadd(2, 3)"
        self.assertEqual(eval_one(src), 5)

    def test_default_param(self) -> None:
        src = 'fn greet(name = "world")\n  return "hi " + name\nend\ngreet()'
        self.assertEqual(eval_one(src), "hi world")

    def test_too_many_args(self) -> None:
        src = "fn f(a)\n  return a\nend\nf(1, 2)"
        with self.assertRaises(VyrelRuntimeError):
            eval_one(src)

    def test_closure_captures(self) -> None:
        src = (
            "fn make_adder(n)\n"
            "  fn inner(x)\n"
            "    return x + n\n"
            "  end\n"
            "  return inner\n"
            "end\n"
            "let add5 = make_adder(5)\n"
            "add5(10)"
        )
        self.assertEqual(eval_one(src), 15)

    def test_lambda(self) -> None:
        src = "let f = fn(x) => x * 2\nf(7)"
        self.assertEqual(eval_one(src), 14)

    def test_recursion(self) -> None:
        src = (
            "fn fact(n)\n"
            "  if n <= 1 then\n"
            "    return 1\n"
            "  end\n"
            "  return n * fact(n - 1)\n"
            "end\n"
            "fact(5)"
        )
        self.assertEqual(eval_one(src), 120)

    def test_call_depth_limit(self) -> None:
        src = (
            "fn loop(n)\n"
            "  return loop(n + 1)\n"
            "end\n"
            "loop(0)"
        )
        with self.assertRaises(VyrelRuntimeError) as ctx:
            eval_one(src)
        self.assertIn("call depth", str(ctx.exception))


class TestStringsAndTemplates(unittest.TestCase):
    def test_template_interpolation(self) -> None:
        self.assertEqual(eval_one('let x = 5\n"x={x}"'), "x=5")

    def test_template_expression(self) -> None:
        self.assertEqual(eval_one('"sum={1 + 2}"'), "sum=3")

    def test_string_concat(self) -> None:
        self.assertEqual(eval_one('"a" + "b" + "c"'), "abc")

    def test_string_slice(self) -> None:
        self.assertEqual(eval_one('"hello"[1:3]'), "el")

    def test_string_negative_index(self) -> None:
        self.assertEqual(eval_one('"abc"[-1]'), "c")


class TestCollections(unittest.TestCase):
    def test_list_index(self) -> None:
        self.assertEqual(eval_one("[10, 20, 30][1]"), 20)

    def test_list_negative_index(self) -> None:
        self.assertEqual(eval_one("[10, 20, 30][-1]"), 30)

    def test_list_slice(self) -> None:
        self.assertEqual(eval_one("[1, 2, 3, 4][1:3]"), [2, 3])

    def test_dict_index(self) -> None:
        self.assertEqual(eval_one('{"a": 1}["a"]'), 1)

    def test_dict_attr_access(self) -> None:
        self.assertEqual(eval_one('let d = {a: 1}\nd.a'), 1)

    def test_in_operator(self) -> None:
        self.assertTrue(eval_one('"a" in {a: 1}'))
        self.assertTrue(eval_one("2 in [1, 2, 3]"))


class TestClasses(unittest.TestCase):
    def test_simple_class(self) -> None:
        src = (
            "class Vec2\n"
            "  fn init(x, y)\n"
            "    self.x = x\n"
            "    self.y = y\n"
            "  end\n"
            "end\n"
            "let v = Vec2(3, 4)\n"
            "v.x + v.y"
        )
        self.assertEqual(eval_one(src), 7)

    def test_method_call(self) -> None:
        src = (
            "class Counter\n"
            "  fn init()\n"
            "    self.n = 0\n"
            "  end\n"
            "  fn bump()\n"
            "    self.n = self.n + 1\n"
            "    return self.n\n"
            "  end\n"
            "end\n"
            "let c = Counter()\n"
            "c.bump()\n"
            "c.bump()"
        )
        self.assertEqual(eval_one(src), 2)

    def test_to_string(self) -> None:
        src = (
            "class P\n"
            "  fn init(n)\n"
            "    self.n = n\n"
            "  end\n"
            "  fn to_string()\n"
            "    return \"P({self.n})\"\n"
            "  end\n"
            "end\n"
            "str(P(7))"
        )
        self.assertEqual(eval_one(src), "P(7)")

    def test_super(self) -> None:
        src = (
            "class A\n"
            "  fn greet()\n"
            "    return \"A\"\n"
            "  end\n"
            "end\n"
            "class B extends A\n"
            "  fn greet()\n"
            "    return super.greet() + \"B\"\n"
            "  end\n"
            "end\n"
            "B().greet()"
        )
        self.assertEqual(eval_one(src), "AB")


class TestExceptions(unittest.TestCase):
    def test_throw_catch(self) -> None:
        src = (
            "let x = 0\n"
            "try\n"
            "  throw \"oops\"\n"
            "catch e\n"
            "  x = 1\n"
            "end\n"
            "x"
        )
        self.assertEqual(eval_one(src), 1)

    def test_catch_binds_value(self) -> None:
        src = (
            "let msg = \"\"\n"
            "try\n"
            "  throw \"oops\"\n"
            "catch e\n"
            "  msg = e\n"
            "end\n"
            "msg"
        )
        self.assertEqual(eval_one(src), "oops")

    def test_finally_runs(self) -> None:
        src = (
            "let x = 0\n"
            "try\n"
            "  x = 1\n"
            "finally\n"
            "  x = x + 10\n"
            "end\n"
            "x"
        )
        self.assertEqual(eval_one(src), 11)

    def test_throw_uncaught_propagates(self) -> None:
        with self.assertRaises(Exception):
            run('throw "unhandled"')


class TestMatch(unittest.TestCase):
    def test_match_hit(self) -> None:
        src = (
            "let x = 0\n"
            "match 2\n"
            "case 1 then\n"
            "  x = 10\n"
            "case 2, 3 then\n"
            "  x = 20\n"
            "else\n"
            "  x = 30\n"
            "end\n"
            "x"
        )
        self.assertEqual(eval_one(src), 20)

    def test_match_else(self) -> None:
        src = (
            "let x = 0\n"
            "match 99\n"
            "case 1 then\n"
            "  x = 10\n"
            "else\n"
            "  x = 99\n"
            "end\n"
            "x"
        )
        self.assertEqual(eval_one(src), 99)


class TestImports(unittest.TestCase):
    def test_import_math_sqrt(self) -> None:
        src = "import math\nmath.sqrt(9)"
        self.assertAlmostEqual(eval_one(src), 3.0)

    def test_from_math_import(self) -> None:
        src = "from math import sqrt\nsqrt(16)"
        self.assertAlmostEqual(eval_one(src), 4.0)

    def test_import_gfx_errors(self) -> None:
        with self.assertRaises(VyrelRuntimeError) as ctx:
            run("import gfx")
        self.assertIn("Phase 4", str(ctx.exception))


class TestBuiltins(unittest.TestCase):
    def test_print(self) -> None:
        self.assertEqual(run_capture('print("hi")'), "hi\n")

    def test_len(self) -> None:
        self.assertEqual(eval_one("len([1, 2, 3])"), 3)

    def test_range(self) -> None:
        self.assertEqual(eval_one("range(3)"), [0, 1, 2])

    def test_str_of_int(self) -> None:
        self.assertEqual(eval_one("str(42)"), "42")

    def test_type_name(self) -> None:
        self.assertEqual(eval_one("type(1)"), "int")
        self.assertEqual(eval_one('type("x")'), "str")


class TestSyntaxTour(unittest.TestCase):
    """A condensed version of the spec's section 1.1 syntax tour, end-to-end."""

    def test_tour(self) -> None:
        src = (
            "let name = \"Vyrel\"\n"
            "let nums = [1, 2, 3]\n"
            "let total = 0\n"
            "for n in nums do\n"
            "  total = total + n\n"
            "end\n"
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
            "print(greet(\"there\"))\n"
            "print(total)\n"
            "print(v.length())\n"
        )
        out = run_capture(src)
        self.assertIn("hello, there!", out)
        self.assertIn("6", out)
        self.assertIn("5", out)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
