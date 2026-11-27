"""Tests for Phase 5 stdlib batch B: random, time, sys, json, net, vec.

Network tests never touch the network: they install a file:// URL handler and
exercise `net.get` against a temp file.
"""

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


class TestRandomModule(unittest.TestCase):
    def test_seeded_deterministic(self) -> None:
        src = (
            "import random\n"
            "random.seed(42)\n"
            "let a = random.random()\n"
            "random.seed(42)\n"
            "let b = random.random()\n"
            "a == b"
        )
        self.assertTrue(eval_one(src))

    def test_randint_in_range(self) -> None:
        src = (
            "import random\n"
            "random.seed(0)\n"
            "let x = random.randint(1, 6)\n"
            "x >= 1 and x <= 6"
        )
        self.assertTrue(eval_one(src))

    def test_randint_bad_range_swaps(self) -> None:
        # Pass (10, 1); the implementation swaps to (1, 10).
        src = (
            "import random\n"
            "random.seed(0)\n"
            "let x = random.randint(10, 1)\n"
            "x >= 1 and x <= 10"
        )
        self.assertTrue(eval_one(src))

    def test_choice(self) -> None:
        src = 'import random\nrandom.seed(0)\nrandom.choice(["a","b","c"])'
        self.assertIn(eval_one(src), ["a", "b", "c"])

    def test_choice_empty_errors(self) -> None:
        with self.assertRaises(VyrelRuntimeError):
            run("import random\nrandom.choice([])")

    def test_shuffle_preserves_set(self) -> None:
        src = (
            "import random\n"
            "random.seed(0)\n"
            "import collections\n"
            "let xs = random.shuffle([1,2,3,4])\n"
            "collections.sort(xs) == [1,2,3,4]"
        )
        self.assertTrue(eval_one(src))

    def test_sample(self) -> None:
        src = (
            "import random\n"
            "random.seed(0)\n"
            "let xs = random.sample([1,2,3,4], 2)\n"
            "len(xs) == 2"
        )
        self.assertTrue(eval_one(src))


class TestTimeModule(unittest.TestCase):
    def test_now_returns_float(self) -> None:
        self.assertIsInstance(eval_one("import time\ntime.now()"), float)

    def test_monotonic_is_non_decreasing(self) -> None:
        src = (
            "import time\n"
            "let a = time.monotonic()\n"
            "let b = time.monotonic()\n"
            "b >= a"
        )
        self.assertTrue(eval_one(src))

    def test_sleep_tiny(self) -> None:
        run("import time\ntime.sleep(0.001)")

    def test_sleep_negative_errors(self) -> None:
        with self.assertRaises(VyrelRuntimeError):
            run("import time\ntime.sleep(-1)")

    def test_format_returns_str(self) -> None:
        out = eval_one('import time\ntime.format(0, "%Y")')
        self.assertIsInstance(out, str)
        self.assertEqual(len(out), 4)  # "1970" or "1969"


class TestSysModule(unittest.TestCase):
    def test_version_returns_str(self) -> None:
        out = eval_one("import sys\nsys.version()")
        self.assertIsInstance(out, str)
        self.assertIn(".", out)

    def test_platform(self) -> None:
        out = eval_one("import sys\nsys.platform()")
        self.assertIsInstance(out, str)
        self.assertTrue(len(out) > 0)

    def test_env_missing_returns_default(self) -> None:
        self.assertEqual(
            eval_one('import sys\nsys.env("__VYREL_NONEXISTENT_XYZ__", "fallback")'),
            "fallback",
        )

    def test_has_env(self) -> None:
        self.assertFalse(
            eval_one('import sys\nsys.has_env("__VYREL_NONEXISTENT_XYZ__")'),
        )


class TestJsonModule(unittest.TestCase):
    def test_encode_roundtrip(self) -> None:
        src = (
            "import json\n"
            "let s = json.encode([1, 2, 3])\n"
            "let v = json.decode(s)\n"
            "v == [1, 2, 3]"
        )
        self.assertTrue(eval_one(src))

    def test_encode_dict(self) -> None:
        src = (
            "import json\n"
            "let s = json.encode({a: 1, b: 2})\n"
            "let v = json.decode(s)\n"
            "v.a + v.b == 3"
        )
        self.assertTrue(eval_one(src))

    def test_encode_pretty(self) -> None:
        src = "import json\njson.encode([1, 2], true)"
        out = eval_one(src)
        self.assertIn("\n", out)

    def test_encode_bad_key_errors(self) -> None:
        with self.assertRaises(VyrelRuntimeError):
            run("import json\njson.encode({1: 2})")

    def test_decode_invalid_errors(self) -> None:
        with self.assertRaises(VyrelRuntimeError):
            run('import json\njson.decode("not json")')

    def test_decode_numbers(self) -> None:
        src = 'import json\njson.decode("42")'
        self.assertEqual(eval_one(src), 42)

    def test_decode_nested(self) -> None:
        # Braces inside the Vyrel string must be escaped (\{ \}) so the lexer
        # produces a plain STRING rather than a TEMPLATE.  Quotes inside the
        # Vyrel string are escaped with \" as usual.
        src = (
            "import json\n"
            'let v = json.decode("\\{\\"a\\": [1, 2]\\}")\n'
            "v.a[1]"
        )
        self.assertEqual(eval_one(src), 2)


class TestNetModule(unittest.TestCase):
    """Offline: use file:// URLs so no network is required."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _file_url(self, name: str, text: str) -> str:
        p = Path(self._tmpdir.name) / name
        p.write_text(text, encoding="utf-8")
        return p.as_uri()  # file:///...

    def test_get_file_url(self) -> None:
        url = self._file_url("hello.txt", "hello net")
        self.assertEqual(eval_one(f'import net\nnet.get("{url}")'), "hello net")

    def test_get_bad_scheme_errors(self) -> None:
        with self.assertRaises(VyrelRuntimeError):
            run('import net\nnet.get("ftp://example.invalid/x")')

    def test_get_missing_file_errors(self) -> None:
        url = (Path(self._tmpdir.name) / "does_not_exist.txt").as_uri()
        with self.assertRaises(VyrelRuntimeError):
            run(f'import net\nnet.get("{url}")')


class TestVecModule(unittest.TestCase):
    def test_vec2_vec3(self) -> None:
        self.assertEqual(eval_one("import vec\nvec.vec2(1, 2)"), [1, 2])
        self.assertEqual(eval_one("import vec\nvec.vec3(1, 2, 3)"), [1, 2, 3])

    def test_add(self) -> None:
        self.assertEqual(
            eval_one("import vec\nvec.add([1, 2], [3, 4])"),
            [4, 6],
        )

    def test_sub(self) -> None:
        self.assertEqual(
            eval_one("import vec\nvec.sub([4, 6], [1, 2])"),
            [3, 4],
        )

    def test_scale(self) -> None:
        self.assertEqual(eval_one("import vec\nvec.scale([1, 2], 3)"), [3, 6])

    def test_dot(self) -> None:
        self.assertEqual(eval_one("import vec\nvec.dot([1, 2], [3, 4])"), 11)

    def test_cross(self) -> None:
        self.assertEqual(
            eval_one("import vec\nvec.cross([1, 0, 0], [0, 1, 0])"),
            [0, 0, 1],
        )

    def test_length(self) -> None:
        self.assertAlmostEqual(
            eval_one("import vec\nvec.length([3, 4])"), 5.0,
        )

    def test_normalize(self) -> None:
        out = eval_one("import vec\nvec.normalize([3, 4])")
        self.assertAlmostEqual(out[0], 0.6, places=6)
        self.assertAlmostEqual(out[1], 0.8, places=6)

    def test_normalize_zero_errors(self) -> None:
        with self.assertRaises(VyrelRuntimeError):
            run("import vec\nvec.normalize([0, 0])")

    def test_dist(self) -> None:
        self.assertAlmostEqual(
            eval_one("import vec\nvec.dist([0, 0], [3, 4])"), 5.0,
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
