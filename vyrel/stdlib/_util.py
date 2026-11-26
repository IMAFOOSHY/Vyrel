"""Internal helpers shared by Vyrel stdlib modules.

This module contains only *internal* helpers — it is not itself a Vyrel
module and is not exposed to user code.  Its job is to centralize argument
coercion and error messages so every stdlib module reports failures the same
beginner-friendly way.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Optional

#: Signature of the callback the interpreter injects so stdlib code can call
#: Vyrel function values without importing the interpreter (Rule 4).
CallFn = Callable[[Any, list], Any]


class StdlibError(Exception):
    """Raised by stdlib helpers; the interpreter converts this to
    ``VyrelRuntimeError`` (so stdlib never imports ``vyrel.errors`` directly).
    """


def _describe(value: Any) -> str:
    if value is None:
        return "nil"
    if value is True or value is False:
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return "value"


def as_int(value: Any, name: str = "argument") -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            pass
    raise StdlibError(
        f"{name} must be an integer, got {_describe(value)}"
    )


def as_number(value: Any, name: str = "argument") -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            pass
    raise StdlibError(f"{name} must be a number, got {_describe(value)}")


def as_str(value: Any, name: str = "argument") -> str:
    if isinstance(value, str):
        return value
    raise StdlibError(f"{name} must be a string, got {_describe(value)}")


def as_list(value: Any, name: str = "argument") -> list:
    if isinstance(value, list):
        return value
    raise StdlibError(f"{name} must be a list, got {_describe(value)}")


def as_dict(value: Any, name: str = "argument") -> dict:
    if isinstance(value, dict):
        return value
    raise StdlibError(f"{name} must be a dict, got {_describe(value)}")


def as_seq(value: Any, name: str = "argument") -> Iterable[Any]:
    if isinstance(value, (list, str, dict)):
        return value
    raise StdlibError(
        f"{name} must be a list, string, or dict, got {_describe(value)}"
    )


def require_callable(fn: Any, name: str = "argument") -> Any:
    if not callable(fn):
        raise StdlibError(f"{name} must be a function")
    return fn


def call(call_fn: Optional[CallFn], fn: Any, args: list) -> Any:
    """Invoke a Vyrel-level callable through the interpreter's callback.

    If ``call_fn`` is None (which shouldn't happen at runtime), fall back to
    Python invocation so unit tests that pass a Python callable still work.
    """
    if call_fn is not None:
        return call_fn(fn, args)
    return fn(*args)
