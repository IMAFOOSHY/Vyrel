"""Vyrel `math` module (internally ``mathx`` to avoid shadowing Python's math).

Registered under the Vyrel module name ``"math"``.  The interpreter's
builtin loader also injects these attrs onto the module it hands out, so
existing Phase 3 programs that did ``import math`` and used `math.sqrt`
continue to work without change.
"""

from __future__ import annotations

import math as _math
from typing import Any, Dict

from ._util import StdlibError, as_number


def _sqrt(x: Any) -> float:
    v = as_number(x)
    if v < 0:
        raise StdlibError("sqrt() needs a non-negative number")
    return _math.sqrt(v)


def _floor(x: Any) -> int:
    return int(_math.floor(as_number(x)))


def _ceil(x: Any) -> int:
    return int(_math.ceil(as_number(x)))


def _round(x: Any, digits: int = 0) -> float:
    return round(as_number(x), int(digits))


def _pow(a: Any, b: Any) -> float:
    return _math.pow(as_number(a), as_number(b))


def _log(x: Any, base: Any = None) -> float:
    v = as_number(x)
    if v <= 0:
        raise StdlibError("log() needs a positive number")
    if base is None:
        return _math.log(v)
    b = as_number(base)
    if b <= 0 or b == 1:
        raise StdlibError("log() base must be positive and not 1")
    return _math.log(v, b)


def _clamp(x: Any, lo: Any, hi: Any) -> float:
    v, a, b = as_number(x), as_number(lo), as_number(hi)
    if a > b:
        a, b = b, a
    return max(a, min(b, v))


def attrs() -> Dict[str, Any]:
    return {
        "pi": _math.pi,
        "e": _math.e,
        "tau": _math.tau,
        "inf": _math.inf,
        "nan": _math.nan,
        "sqrt": _sqrt,
        "cos": _math.cos,
        "sin": _math.sin,
        "tan": _math.tan,
        "acos": _math.acos,
        "asin": _math.asin,
        "atan": _math.atan,
        "atan2": _math.atan2,
        "hypot": _math.hypot,
        "floor": _floor,
        "ceil": _ceil,
        "round": _round,
        "abs": abs,
        "pow": _pow,
        "log": _log,
        "exp": _math.exp,
        "clamp": _clamp,
    }
