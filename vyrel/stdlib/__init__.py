"""Builtin stdlib modules for Vyrel.

Module registry.  Each entry provides a callable ``attrs(call_fn=...)`` that
returns a dict of Vyrel-visible names.  The interpreter calls ``load_module``
with a ``call_fn`` closure so stdlib code can invoke Vyrel function values
without importing the interpreter (Rule 4).

Phase 5 batch A ships: core, collections, strings, files, math, gfx.
Phase 5 batch B will add: random, time, sys, json, net, vec.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from . import collections as _collections
from . import core as _core
from . import files as _files
from . import gfx as _gfx
from . import mathx as _mathx
from . import strings as _strings


#: A callback the interpreter supplies: call a Vyrel callable with args.
CallFn = Callable[[Any, list], Any]


def load_module(name: str, call_fn: Optional[CallFn] = None) -> Optional[Dict[str, Any]]:
    """Return a dict of the module's attributes, or None if unknown."""
    if name == "core":
        return _core.attrs()
    if name == "collections":
        return _collections.attrs(call_fn)
    if name == "strings":
        return _strings.attrs()
    if name == "files":
        return _files.attrs()
    if name == "math":
        return _mathx.attrs()
    if name == "gfx":
        return _gfx.attrs()
    # Phase 5 batch B adds: random, time, sys, json, net, vec.
    return None
