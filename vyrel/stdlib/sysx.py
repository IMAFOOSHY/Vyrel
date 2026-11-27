"""Vyrel `sys` module (internally ``sysx`` to avoid shadowing).

Registered under the Vyrel module name ``"sys"``.

Read-only access to environment variables and process info.  There is
deliberately no ``exit`` builtin here — the REPL/CLI owns process exit — and
no ``argv`` because Vyrel is invoked through the CLI which doesn't forward
argv into the program (that can come in a later phase if desired).
"""

from __future__ import annotations

import os
import sys as _sys
from typing import Any, Dict

from ._util import StdlibError, as_str


def attrs() -> Dict[str, Any]:
    def _env(name: Any, default: Any = None) -> Any:
        return os.environ.get(as_str(name, "name"), default)

    def _has_env(name: Any) -> bool:
        return as_str(name, "name") in os.environ

    def _version() -> str:
        return _sys.version.split()[0]

    def _platform() -> str:
        return _sys.platform

    def _getenv_all() -> Dict[str, str]:
        return dict(os.environ)

    return {
        "env": _env,
        "has_env": _has_env,
        "version": _version,
        "platform": _platform,
        "env_all": _getenv_all,
    }
