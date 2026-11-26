"""Vyrel `strings` module — string utilities.

Registered under the Vyrel module name ``"strings"``.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ._util import StdlibError, as_str


def _upper(s: Any) -> str:
    return as_str(s).upper()


def _lower(s: Any) -> str:
    return as_str(s).lower()


def _trim(s: Any) -> str:
    return as_str(s).strip()


def _split(s: Any, sep: Any = None) -> List[str]:
    text = as_str(s)
    if sep is None:
        return text.split()
    return text.split(as_str(sep))


def _join(sep: Any, items: Any) -> str:
    if not isinstance(items, list):
        raise StdlibError("join() needs a list")
    return as_str(sep).join(as_str(x) for x in items)


def _replace(s: Any, old: Any, new: Any) -> str:
    return as_str(s).replace(as_str(old), as_str(new))


def _starts_with(s: Any, prefix: Any) -> bool:
    return as_str(s).startswith(as_str(prefix))


def _ends_with(s: Any, suffix: Any) -> bool:
    return as_str(s).endswith(as_str(suffix))


def _find(s: Any, sub: Any) -> int:
    return as_str(s).find(as_str(sub))


def _slice(s: Any, start: int, end: Any = None) -> str:
    text = as_str(s)
    if end is None:
        return text[start:]
    return text[start:end]


def _repeat(s: Any, n: int) -> str:
    return as_str(s) * int(n)


def _chars(s: Any) -> List[str]:
    return list(as_str(s))


def _format(fmt: Any, d: Any) -> str:
    """Substitute ``{key}`` in ``fmt`` with values from dict ``d``.

    We deliberately do NOT support arbitrary Python format syntax — only
    simple ``{key}`` substitution — so behavior is predictable and Vyrel
    templates (`"x={x}"`) remain the primary formatting mechanism.
    """
    text = as_str(fmt)
    if not isinstance(d, dict):
        raise StdlibError("format() needs a dict as the second argument")
    out = text
    for k, v in d.items():
        if not isinstance(k, str):
            raise StdlibError("format() dict keys must be strings")
        out = out.replace("{" + k + "}", str(v))
    return out


def attrs() -> Dict[str, Any]:
    return {
        "upper": _upper,
        "lower": _lower,
        "trim": _trim,
        "split": _split,
        "join": _join,
        "replace": _replace,
        "starts_with": _starts_with,
        "ends_with": _ends_with,
        "find": _find,
        "slice": _slice,
        "repeat": _repeat,
        "chars": _chars,
        "format": _format,
    }
