"""Vyrel `collections` module — list/dict utilities.

Registered under the Vyrel module name ``"collections"``.  Functions that
take a callable (``map``, ``filter``, ``each``, ``reduce``) receive it as a
Vyrel function value; the interpreter injects a ``call_fn`` so stdlib code
can invoke it without importing the interpreter (Rule 4).

Note: we deliberately do NOT pre-check callables with Python's ``callable()``
— Vyrel function values (:class:`VyrelLambda`, :class:`VyrelFunction`) are
not Python-callable, and the interpreter's ``_call_value`` already produces
a beginner-friendly error if a non-callable is passed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ._util import CallFn, StdlibError, as_list, call


def _make(call_fn: Optional[CallFn]) -> Dict[str, Any]:
    def _len(x: Any) -> int:
        if isinstance(x, (list, str, dict)):
            return len(x)
        raise StdlibError("len() needs a list, string, or dict")

    def _push(lst: Any, value: Any) -> None:
        as_list(lst).append(value)

    def _pop(lst: Any) -> Any:
        lst = as_list(lst)
        if not lst:
            raise StdlibError("pop() on empty list")
        return lst.pop()

    def _first(lst: Any) -> Any:
        lst = as_list(lst)
        if not lst:
            raise StdlibError("first() on empty list")
        return lst[0]

    def _last(lst: Any) -> Any:
        lst = as_list(lst)
        if not lst:
            raise StdlibError("last() on empty list")
        return lst[-1]

    def _slice(lst: Any, start: int, end: Optional[int] = None) -> List[Any]:
        lst = as_list(lst)
        if end is None:
            return list(lst[start:])
        return list(lst[start:end])

    def _reverse(lst: Any) -> List[Any]:
        return list(reversed(as_list(lst)))

    def _sort(lst: Any) -> List[Any]:
        items = list(as_list(lst))
        try:
            items.sort()
        except TypeError:
            raise StdlibError("cannot sort a list with mixed types")
        return items

    def _contains(x: Any, item: Any) -> bool:
        if isinstance(x, (list, str, dict)):
            return item in x
        raise StdlibError("contains() needs a list, string, or dict")

    def _keys(d: Any) -> List[Any]:
        if not isinstance(d, dict):
            raise StdlibError("keys() needs a dict")
        return list(d.keys())

    def _values(d: Any) -> List[Any]:
        if not isinstance(d, dict):
            raise StdlibError("values() needs a dict")
        return list(d.values())

    def _items(d: Any) -> List[List[Any]]:
        if not isinstance(d, dict):
            raise StdlibError("items() needs a dict")
        return [[k, v] for k, v in d.items()]

    def _get(d: Any, key: Any, default: Any = None) -> Any:
        if not isinstance(d, dict):
            raise StdlibError("get() needs a dict")
        return d.get(key, default)

    def _has(d: Any, key: Any) -> bool:
        if not isinstance(d, dict):
            raise StdlibError("has() needs a dict")
        return key in d

    def _map(lst: Any, fn: Any) -> List[Any]:
        items = list(as_list(lst))
        return [call(call_fn, fn, [x]) for x in items]

    def _filter(lst: Any, fn: Any) -> List[Any]:
        items = list(as_list(lst))
        return [x for x in items if call(call_fn, fn, [x])]

    def _each(lst: Any, fn: Any) -> None:
        items = list(as_list(lst))
        for x in items:
            call(call_fn, fn, [x])

    def _reduce(lst: Any, fn: Any, initial: Any = None) -> Any:
        items = list(as_list(lst))
        if initial is None and not items:
            raise StdlibError("reduce() on empty list with no initial value")
        if initial is None:
            acc = items[0]
            rest = items[1:]
        else:
            acc = initial
            rest = items
        for x in rest:
            acc = call(call_fn, fn, [acc, x])
        return acc

    return {
        "len": _len,
        "push": _push,
        "pop": _pop,
        "first": _first,
        "last": _last,
        "slice": _slice,
        "reverse": _reverse,
        "sort": _sort,
        "contains": _contains,
        "keys": _keys,
        "values": _values,
        "items": _items,
        "get": _get,
        "has": _has,
        "map": _map,
        "filter": _filter,
        "each": _each,
        "reduce": _reduce,
    }


def attrs(call_fn: Optional[CallFn] = None) -> Dict[str, Any]:
    return _make(call_fn)
