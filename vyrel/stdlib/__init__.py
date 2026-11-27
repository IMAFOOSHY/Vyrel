"""Builtin stdlib modules for Vyrel.

Module registry.  Each entry provides a callable ``attrs(call_fn=...)`` that
returns a dict of Vyrel-visible names.  The interpreter calls ``load_module``
with a ``call_fn`` closure so stdlib code can invoke Vyrel function values
without importing the interpreter (Rule 4).

Phase 5 ships: core, collections, strings, files, math, gfx, random, time,
sys, json, net, vec.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from . import collections as _collections
from . import core as _core
from . import files as _files
from . import gfx as _gfx
from . import jsonx as _jsonx
from . import mathx as _mathx
from . import netx as _netx
from . import randomx as _randomx
from . import strings as _strings
from . import sysx as _sysx
from . import timex as _timex
from . import vec as _vec


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
    if name == "random":
        return _randomx.attrs()
    if name == "time":
        return _timex.attrs()
    if name == "sys":
        return _sysx.attrs()
    if name == "json":
        return _jsonx.attrs()
    if name == "net":
        return _netx.attrs()
    if name == "vec":
        return _vec.attrs()
    return None
