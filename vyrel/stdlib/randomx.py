"""Vyrel `random` module (internally ``randomx`` to avoid shadowing).

Registered under the Vyrel module name ``"random"``.

Per-interpreter determinism: each module-load creates a fresh
``random.Random(0)``, so two runs of the same program produce the same
sequence unless the user calls ``random.seed(n)``.  This makes beginner
programs reproducible and makes tests deterministic.

State is held on the module dict's ``__state__`` key so it lives exactly as
long as the imported module does (i.e., for the duration of one program).
"""

from __future__ import annotations

import random as _random
from typing import Any, Dict, List, Optional

from ._util import StdlibError, as_int, as_list, as_number


def attrs() -> Dict[str, Any]:
    rng = _random.Random(0)

    def _seed(n: Any = 0) -> None:
        rng.seed(as_int(n, "seed"))

    def _rand() -> float:
        return rng.random()

    def _randint(lo: Any, hi: Any) -> int:
        lo_i, hi_i = as_int(lo, "lo"), as_int(hi, "hi")
        if lo_i > hi_i:
            lo_i, hi_i = hi_i, lo_i
        return rng.randint(lo_i, hi_i)

    def _uniform(lo: Any, hi: Any) -> float:
        return rng.uniform(as_number(lo, "lo"), as_number(hi, "hi"))

    def _choice(items: Any) -> Any:
        items_l = as_list(items)
        if not items_l:
            raise StdlibError("choice() on empty list")
        return rng.choice(items_l)

    def _shuffle(items: Any) -> List[Any]:
        items_l = list(as_list(items))
        rng.shuffle(items_l)
        return items_l

    def _sample(items: Any, k: Any) -> List[Any]:
        items_l = as_list(items)
        k_i = as_int(k, "k")
        if k_i < 0 or k_i > len(items_l):
            raise StdlibError("sample() size out of range")
        return rng.sample(items_l, k_i)

    return {
        "seed": _seed,
        "random": _rand,
        "randint": _randint,
        "uniform": _uniform,
        "choice": _choice,
        "shuffle": _shuffle,
        "sample": _sample,
    }
