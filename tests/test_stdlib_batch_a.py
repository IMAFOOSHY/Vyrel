"""Tests for Phase 5 stdlib batch A: core, collections, strings, files, math."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vyrel.errors import VyrelRuntimeError
from vyrel.interpreter import Interpreter
from vyrel.parser import parse


def run(src: str) -> None:
    Interpreter().run(parse(src))


def eval_one(src: str):
    from vyrel import ast_nodes as ast
    prog = parse(src + "\n")
    interp = Interpreter()
    for stmt in prog.body[:-1]:
        interp.exec_block((stmt,))
    last = prog.body[-1]
    return interp.eval_expr(last.expr) if isinstance(last, ast.ExprStmt) else None


class TestCoreModule(unittest.TestCase):
    def test_type_checks(self) -> None:
        self.assertTrue(eval_one('import core\ncore.is_int(3)'))
        self.assertFalse(eval_one('import core\ncore.is_int(3.0)'))
        self.assertTrue(eval_one('import core\ncore.is_number(3.0)'))
        self.assertTrue(eval_one('import core\ncore.is_nil(nil)'))
        self.assertTrue(eval_one('import core\ncore.is_str("x")'))
        self.assertTrue(eval_one('import core\ncore.is_list([])'))
        self.assertTrue(eval_one('import core\ncore.is_dict({})'))
        self.assertTrue(eval_one('import core\ncore.is_function(print)'))

    def test_type_of(self) -> None:
        self.assertEqual(eval_one('import core\ncore.type_of(1)'), "int")
        self.assertEqual(eval_one('import core\ncore.type_of(1.5)'), "float")
        self.assertEqual(eval_one('import core\ncore.type_of("x")'), "str")
        self.assertEqual(eval_one('import core\ncore.type_of(nil)'), "nil")
        self.assertEqual(eval_one('import core\ncore.type_of(true)'), "bool")

    def test_conversions(self) -> None:
        self.assertEqual(eval_one('import core\ncore.to_int("42")'), 42)
        self.assertAlmostEqual(eval_one('import core\ncore.to_float("3.5")'), 3.5)
        self.assertEqual(eval_one('import core\ncore.to_str(42)'), "42")
        self.assertEqual(eval_one('import core\ncore.to_list("abc")'), ["a", "b", "c"])

    def test_to_list_from_dict(self) -> None:
        self.assertEqual(
            eval_one('import core\ncore.to_list({a: 1, b: 2})'),
            ["a", "b"],
        )

    def test_coalesce(self) -> None:
        self.assertEqual(eval_one('import core\ncore.coalesce(nil, 3, 5)'), 3)
        self.assertEqual(eval_one('import core\ncore.coalesce(nil, nil)'), None)


class TestCollectionsModule(unittest.TestCase):
    def test_len(self) -> None:
        self.assertEqual(eval_one('import collections\ncollections.len([1,2,3])'), 3)
        self.assertEqual(eval_one('import collections\ncollections.len("abc")'), 3)
        self.assertEqual(eval_one('import collections\ncollections.len({a: 1})'), 1)

    def test_push_pop(self) -> None:
        self.assertEqual(
            eval_one('import collections\nlet xs = [1,2]\ncollections.push(xs, 3)\nxs'),
            [1, 2, 3],
        )
        self.assertEqual(
            eval_one('import collections\nlet xs = [1,2,3]\ncollections.pop(xs)'),
            3,
        )

    def test_first_last(self) -> None:
        self.assertEqual(eval_one('import collections\ncollections.first([9,8,7])'), 9)
        self.assertEqual(eval_one('import collections\ncollections.last([9,8,7])'), 7)

    def test_sort(self) -> None:
        self.assertEqual(
            eval_one('import collections\ncollections.sort([3,1,2])'),
            [1, 2, 3],
        )

    def test_reverse(self) -> None:
        self.assertEqual(
            eval_one('import collections\ncollections.reverse([1,2,3])'),
            [3, 2, 1],
        )

    def test_dict_helpers(self) -> None:
        self.assertEqual(
            eval_one('import collections\ncollections.keys({a: 1, b: 2})'),
            ["a", "b"],
        )
        self.assertEqual(
            eval_one('import collections\ncollections.values({a: 1, b: 2})'),
            [1, 2],
        )
        self.assertEqual(
            eval_one('import collections\ncollections.get({a: 1}, "a", 0)'),
            1,
        )
        self.assertTrue(
            eval_one('import collections\ncollections.has({a: 1}, "a")'),
        )

    def test_map(self) -> None:
        src = 'import collections\ncollections.map([1,2,3], fn(x) => x * 2)'
        self.assertEqual(eval_one(src), [2, 4, 6])

    def test_filter(self) -> None:
        src = 'import collections\ncollections.filter([1,2,3,4], fn(x) => x % 2 == 0)'
        self.assertEqual(eval_one(src), [2, 4])

    def test_reduce(self) -> None:
        src = 'import collections\ncollections.reduce([1,2,3], fn(a, b) => a + b, 0)'
        self.assertEqual(eval_one(src), 6)


class TestStringsModule(unittest.TestCase):
    def test_case(self) -> None:
        self.assertEqual(eval_one('import strings\nstrings.upper("abc")'), "ABC")
        self.assertEqual(eval_one('import strings\nstrings.lower("ABC")'), "abc")

    def test_trim(self) -> None:
        self.assertEqual(eval_one('import strings\nstrings.trim("  x  ")'), "x")

    def test_split_join(self) -> None:
        self.assertEqual(
            eval_one('import strings\nstrings.split("a,b,c", ",")'),
            ["a", "b", "c"],
        )
        self.assertEqual(
            eval_one('import strings\nstrings.join("-", ["a","b","c"])'),
            "a-b-c",
        )

    def test_replace(self) -> None:
        self.assertEqual(
            eval_one('import strings\nstrings.replace("abcabc", "a", "x")'),
            "xbcxbc",
        )

    def test_starts_ends(self) -> None:
        self.assertTrue(eval_one('import strings\nstrings.starts_with("hello", "he")'))
        self.assertTrue(eval_one('import strings\nstrings.ends_with("hello", "lo")'))

    def test_find(self) -> None:
        self.assertEqual(eval_one('import strings\nstrings.find("hello", "ll")'), 2)
        self.assertEqual(eval_one('import strings\nstrings.find("hello", "zz")'), -1)

    def test_chars(self) -> None:
        self.assertEqual(eval_one('import strings\nstrings.chars("abc")'), ["a","b","c"])

    def test_format(self) -> None:
        # Braces are escaped so the lexer produces a STRING, not a TEMPLATE.
        src = 'import strings\nstrings.format("hi \\{name\\}!", {name: "Vyrel"})'
        self.assertEqual(eval_one(src), "hi Vyrel!")


class TestFilesModule(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _path(self, name: str) -> str:
        return str(Path(self._tmpdir.name) / name)

    def test_write_then_read(self) -> None:
        p = self._path("a.txt")
        src = f'import files\nfiles.write("{p}", "hello")\nfiles.read("{p}")'
        self.assertEqual(eval_one(src), "hello")

    def test_append(self) -> None:
        p = self._path("b.txt")
        src = (
            f'import files\n'
            f'files.write("{p}", "a")\n'
            f'files.append("{p}", "b")\n'
            f'files.read("{p}")'
        )
        self.assertEqual(eval_one(src), "ab")

    def test_exists(self) -> None:
        p = self._path("c.txt")
        self.assertFalse(eval_one(f'import files\nfiles.exists("{p}")'))
        src = f'import files\nfiles.write("{p}", "")\nfiles.exists("{p}")'
        self.assertTrue(eval_one(src))

    def test_listdir(self) -> None:
        p1 = self._path("d.txt")
        p2 = self._path("e.txt")
        src = (
            f'import files\n'
            f'files.write("{p1}", "")\n'
            f'files.write("{p2}", "")\n'
            f'files.listdir("{self._tmpdir.name}")'
        )
        names = eval_one(src)
        self.assertIn("d.txt", names)
        self.assertIn("e.txt", names)

    def test_read_lines(self) -> None:
        p = self._path("f.txt")
        src = f'import files\nfiles.write("{p}", "a\\nb\\nc")\nfiles.read_lines("{p}")'
        self.assertEqual(eval_one(src), ["a", "b", "c"])

    def test_write_lines(self) -> None:
        p = self._path("g.txt")
        src = (
            f'import files\n'
            f'files.write_lines("{p}", ["a", "b"])\n'
            f'files.read("{p}")'
        )
        self.assertEqual(eval_one(src), "a\nb")

    def test_size(self) -> None:
        p = self._path("h.txt")
        src = f'import files\nfiles.write("{p}", "abc")\nfiles.size("{p}")'
        self.assertEqual(eval_one(src), 3)

    def test_read_missing_errors(self) -> None:
        p = self._path("missing.txt")
        with self.assertRaises(Exception):
            run(f'import files\nfiles.read("{p}")')


class TestMathModule(unittest.TestCase):
    def test_constants(self) -> None:
        self.assertAlmostEqual(eval_one("import math\nmath.pi"), 3.14159, places=4)
        self.assertAlmostEqual(eval_one("import math\nmath.e"), 2.71828, places=4)

    def test_sqrt(self) -> None:
        self.assertAlmostEqual(eval_one("import math\nmath.sqrt(9)"), 3.0)

    def test_trig(self) -> None:
        self.assertAlmostEqual(eval_one("import math\nmath.sin(0)"), 0.0)
        self.assertAlmostEqual(eval_one("import math\nmath.cos(0)"), 1.0)

    def test_floor_ceil(self) -> None:
        self.assertEqual(eval_one("import math\nmath.floor(2.9)"), 2)
        self.assertEqual(eval_one("import math\nmath.ceil(2.1)"), 3)

    def test_round(self) -> None:
        self.assertEqual(eval_one("import math\nmath.round(2.567, 2)"), 2.57)

    def test_clamp(self) -> None:
        self.assertEqual(eval_one("import math\nmath.clamp(5, 0, 3)"), 3)
        self.assertEqual(eval_one("import math\nmath.clamp(-1, 0, 3)"), 0)

    def test_log(self) -> None:
        self.assertAlmostEqual(eval_one("import math\nmath.log(math.e)"), 1.0)

    def test_unknown_module_errors(self) -> None:
        with self.assertRaises(VyrelRuntimeError):
            run("import not_a_real_module")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
