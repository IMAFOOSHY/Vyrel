"""Vyrel `core` module — miscellaneous, always-useful helpers.

Registered under the Vyrel module name ``"core"``.  Nothing here is exotic:
type checks, safe conversions, iteration helpers, stringification.  These
complement the language-level builtins (``print``, ``len``, …), they don't
replace them.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ._util import StdlibError, as_int, as_str


def _is_nil(x: Any) -> bool:
    return x is None


def _is_bool(x: Any) -> bool:
    return isinstance(x, bool)


def _is_int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _is_float(x: Any) -> bool:
    return isinstance(x, float)


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _is_str(x: Any) -> bool:
    return isinstance(x, str)


def _is_list(x: Any) -> bool:
    return isinstance(x, list)


def _is_dict(x: Any) -> bool:
    return isinstance(x, dict)


def _is_function(x: Any) -> bool:
    return callable(x)


def _type_of(x: Any) -> str:
    if x is None:
        return "nil"
    if isinstance(x, bool):
        return "bool"
    if isinstance(x, int):
        return "int"
    if isinstance(x, float):
        return "float"
    if isinstance(x, str):
        return "str"
    if isinstance(x, list):
        return "list"
    if isinstance(x, dict):
        return "dict"
    if callable(x):
        return "function"
    return "value"


def _to_str(x: Any = "") -> str:
    # Kept simple: only safe conversions.  The interpreter's _stringify is
    # richer (knows about instances and to_string), but stdlib must not
    # depend on the interpreter.  Use the builtin `str(x)` for that case.
    if x is None:
        return "nil"
    if x is True:
        return "true"
    if x is False:
        return "false"
    return str(x)


def _to_int(x: Any = 0) -> int:
    return as_int(x)


def _to_float(x: Any = 0.0) -> float:
    if isinstance(x, bool):
        return float(x)
    if isinstance(x, (int, float, str)):
        try:
            return float(x)
        except (TypeError, ValueError):
            pass
    raise StdlibError(f"cannot convert {_type_of(x)} to float")


def _to_list(x: Any) -> List[Any]:
    if isinstance(x, list):
        return list(x)
    if isinstance(x, str):
        return list(x)
    if isinstance(x, dict):
        return list(x.keys())
    raise StdlibError(f"cannot convert {_type_of(x)} to list")


def _coalesce(*args: Any) -> Any:
    for a in args:
        if a is not None:
            return a
    return None


def attrs() -> Dict[str, Any]:
    return {
        "is_nil": _is_nil,
        "is_bool": _is_bool,
        "is_int": _is_int,
        "is_float": _is_float,
        "is_number": _is_number,
        "is_str": _is_str,
        "is_list": _is_list,
        "is_dict": _is_dict,
        "is_function": _is_function,
        "type_of": _type_of,
        "to_str": _to_str,
        "to_int": _to_int,
        "to_float": _to_float,
        "to_list": _to_list,
        "coalesce": _coalesce,
    }
