"""Vyrel `json` module (internally ``jsonx`` to avoid shadowing).

Registered under the Vyrel module name ``"json"``.

Conversions are lossy in the same ways Python's ``json`` is: tuples become
lists, dicts with non-string keys raise.  We accept only JSON-representable
Vyrel values on the encode side.  On the decode side, we return plain
Vyrel values (dict/list/str/int/float/bool/nil).
"""

from __future__ import annotations

import json as _json
from typing import Any, Dict

from ._util import StdlibError, as_str


def _validate(value: Any, depth: int = 0) -> Any:
    """Reject non-JSON Vyrel values before handing to the C encoder."""
    if depth > 200:
        raise StdlibError("json: nesting too deep")
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_validate(v, depth + 1) for v in value]
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise StdlibError("json: dict keys must be strings")
            out[k] = _validate(v, depth + 1)
        return out
    raise StdlibError(
        f"json: cannot encode value of type "
        f"{type(value).__name__}"
    )


def attrs() -> Dict[str, Any]:
    def _encode(value: Any, pretty: Any = False) -> str:
        clean = _validate(value)
        if pretty:
            return _json.dumps(clean, indent=2, ensure_ascii=False)
        return _json.dumps(clean, ensure_ascii=False)

    def _decode(text: Any) -> Any:
        try:
            return _json.loads(as_str(text, "text"))
        except _json.JSONDecodeError as e:
            raise StdlibError(f"json: {e.msg} at line {e.lineno} "
                              f"column {e.colno}")

    return {
        "encode": _encode,
        "decode": _decode,
    }
