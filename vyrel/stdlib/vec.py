"""Vyrel `vec` module — 2D/3D vector helpers.

Registered under the Vyrel module name ``"vec"``.

Vectors are plain Vyrel lists: ``[x, y]`` or ``[x, y, z]``.  All functions
are pure (do not mutate their inputs) and return new lists.  Designed to
pair with the Phase 8–9 gfx3d work but usable anywhere.
"""

from __future__ import annotations

import math as _math
from typing import Any, Dict, List

from ._util import StdlibError, as_list, as_number


def _coords(v: Any, min_len: int, name: str = "v") -> List[float]:
    lst = as_list(v, name)
    if len(lst) < min_len:
        raise StdlibError(
            f"{name} must have at least {min_len} components, "
            f"got {len(lst)}"
        )
    return [as_number(x) for x in lst]


def _make2(x: float, y: float) -> List[float]:
    return [x, y]


def _make3(x: float, y: float, z: float) -> List[float]:
    return [x, y, z]


def attrs() -> Dict[str, Any]:
    def _add(a: Any, b: Any) -> List[float]:
        n = min(len(as_list(a)), len(as_list(b)))
        if n < 2:
            raise StdlibError("add() needs vectors of length >= 2")
        av, bv = _coords(a, n), _coords(b, n)
        return [av[i] + bv[i] for i in range(n)]

    def _sub(a: Any, b: Any) -> List[float]:
        n = min(len(as_list(a)), len(as_list(b)))
        if n < 2:
            raise StdlibError("sub() needs vectors of length >= 2")
        av, bv = _coords(a, n), _coords(b, n)
        return [av[i] - bv[i] for i in range(n)]

    def _scale(v: Any, k: Any) -> List[float]:
        s = as_number(k)
        return [x * s for x in _coords(v, 2)]

    def _dot(a: Any, b: Any) -> float:
        av, bv = as_list(a), as_list(b)
        if len(av) != len(bv):
            raise StdlibError("dot() needs vectors of equal length")
        return sum(as_number(x) * as_number(y) for x, y in zip(av, bv))

    def _cross(a: Any, b: Any) -> List[float]:
        av = _coords(a, 3)
        bv = _coords(b, 3)
        return [
            av[1] * bv[2] - av[2] * bv[1],
            av[2] * bv[0] - av[0] * bv[2],
            av[0] * bv[1] - av[1] * bv[0],
        ]

    def _length(v: Any) -> float:
        return _math.hypot(*_coords(v, 2))

    def _normalize(v: Any) -> List[float]:
        coords = _coords(v, 2)
        n = _math.hypot(*coords)
        if n == 0:
            raise StdlibError("normalize() on zero-length vector")
        return [x / n for x in coords]

    def _dist(a: Any, b: Any) -> float:
        d = _sub(a, b)
        return _math.hypot(*d)

    return {
        "vec2": _make2,
        "vec3": _make3,
        "add": _add,
        "sub": _sub,
        "scale": _scale,
        "dot": _dot,
        "cross": _cross,
        "length": _length,
        "normalize": _normalize,
        "dist": _dist,
    }
