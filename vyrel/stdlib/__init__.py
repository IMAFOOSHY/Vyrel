"""Builtin stdlib modules for Vyrel.

Each module here is a plain Python object with a ``NAME`` and an ``attrs``
dict mapping Vyrel-visible names to callables or values.  The interpreter
loads these via :func:`load_module`.  Phase 4 ships ``math`` and ``gfx``.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from . import gfx as _gfx


#: name -> dict of attributes (functions, constants, etc.)
_MODULES: Dict[str, Dict[str, Any]] = {
    "math": {},       # populated in interpreter.py (keeps math backend-free)
    "gfx": _gfx.attrs(),
}


def load_module(name: str) -> Optional[Dict[str, Any]]:
    """Return a dict of the module's attributes, or None if unknown."""
    return _MODULES.get(name)
