"""Vyrel `time` module (internally ``timex`` to avoid shadowing).

Registered under the Vyrel module name ``"time"``.

All times are POSIX seconds (float).  Wall clock via ``time.time()``,
monotonic timer via ``time.monotonic()`` (for measuring elapsed time safely),
``time.sleep(seconds)`` for pausing.  Formatting uses ``strftime`` with a
fixed format string so output is cross-platform.
"""

from __future__ import annotations

import time as _time
from typing import Any, Dict

from ._util import StdlibError, as_number


def attrs() -> Dict[str, Any]:
    def _now() -> float:
        return _time.time()

    def _monotonic() -> float:
        return _time.monotonic()

    def _sleep(seconds: Any) -> None:
        s = as_number(seconds, "seconds")
        if s < 0:
            raise StdlibError("sleep() needs a non-negative number")
        _time.sleep(s)

    def _format(ts: Any = None, fmt: Any = "%Y-%m-%d %H:%M:%S") -> str:
        t = _time.time() if ts is None else as_number(ts, "timestamp")
        try:
            return _time.strftime(str(fmt), _time.localtime(t))
        except (OSError, ValueError) as e:
            raise StdlibError(f"cannot format time: {e}")

    return {
        "now": _now,
        "monotonic": _monotonic,
        "sleep": _sleep,
        "format": _format,
    }
