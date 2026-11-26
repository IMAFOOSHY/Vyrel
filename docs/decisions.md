# Decisions log

This file records every interpretation call, ambiguity resolution, or
spec deviation approved by the project owner. Per the project rules, these
are *not* applied silently — each entry explains what was ambiguous, what
was chosen, and why.

---

## 2026-11-26 — `InterpPart` shape (Phase 1)

**Spec text:** "`Token.value` … parsed Python value for INT/FLOAT/STRING;
list of `str | InterpPart` for TEMPLATE; raw text otherwise."

**Ambiguity:** The spec does not define `InterpPart`'s fields.

**Chosen shape:**

```python
@dataclass(frozen=True)
class InterpPart:
    text: str     # raw source of the interpolated expression
    line: int     # 1-based line of its first non-space char
    column: int   # 1-based column of its first non-space char

---

## 2026-11-26 — Interpreter semantics (Phase 3)

The following semantics are not fully pinned by the spec and are hereby
recorded.

### `d.key` fallback on dicts

`d.key` first tries instance/module attribute lookup; on a plain `dict` it
falls back to `d["key"]`.  Rationale: the spec explicitly says
`d.key == d["key"]`.

### Bare-ident dict keys

In a dict literal `{a: 1, b: 2}`, a key that is a bare `Ident` evaluates to
the **string** of its name (`"a"`, `"b"`).  Any other key expression is
evaluated normally.  This matches the spec's `{a: 1, b: 2}` syntax tour.

### Implicit `self`

Every method receives the instance as an implicit first argument; user
signatures do not list `self`.  `init` is called automatically on
instantiation; if absent, calling `Class(args)` with non-empty `args`
raises.

### `super.m()`

`super` inside a method resolves to the superclass's method `m` and calls
it with the current `self`.  Only single inheritance is supported (per
spec).

### `/` always float; `//` preserves int-ness

`7 / 2` is `3.5` (float); `7 // 2` is `3` (int); `7.0 // 2` is `3.0`
(float).  Matches spec.

### `and` / `or` return operands

Short-circuit; return the actual operand, not a coerced bool.  Matches
spec ("and/or return operands").

### `for` semantics

* `for x in list/str` → `x` is the element.
* `for x in dict` → `x` is the key.
* `for k, v in dict` → `k, v` are the key/value pair.
* `for i, v in list/str` → `i` is the index, `v` is the element.

**Note:** the spec only explicitly says `for x in it` and
`for k, v in dict`.  Iterating a list with two variables (`for i, v in
[10, 20]`) is an extension adopted here for convenience; documented so it
isn't a surprise.  If unwanted, restrict in Phase 4.

### Call-depth limit

`MAX_CALL_DEPTH = 1000`.  Exceeding it raises `VyrelRuntimeError` with a
plain-English message, not Python's `RecursionError`.

### Exceptions

`throw value` can throw any Vyrel value.  `catch e` binds `e` to the
thrown value directly (no wrapper).  `finally` always runs, even when the
try/catch body returns or throws further.

### `to_string()`

If a class defines `to_string()`, it is used by `str()`, `print`, and
template interpolation.  Otherwise instance display is
`<ClassName instance>`.

### `import` in Phase 3

Only `math` is available.  `import gfx` raises "not available until
Phase 4".  Importing `.vyr` files raises "not yet supported (Phase 4+)".

### `ParseError` duplication

`vyrel/parser.py` defines its own `ParseError` while
`vyrel/errors.py` also defines one.  They are distinct classes; both are
subclasses of `VyrelError`.  Tests import from `vyrel.parser`.  A Phase 4
cleanup can collapse them into one.

**Status:** All awaiting project-owner confirmation.
