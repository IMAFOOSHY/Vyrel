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

---

## 2026-11-26 — `gfx` API surface (Phase 4)

**Spec text:** shows `gfx.clear`, `gfx.line`, `gfx.present`, and pixel
coordinates. Does not enumerate the full API.

**Chosen API:**
- `gfx.open(title, width, height)` — create the window (idempotent)
- `gfx.clear(r, g, b)` — clear to a color
- `gfx.pixel(x, y, r, g, b)` — set a pixel
- `gfx.line(x1, y1, x2, y2, r, g, b)` — line segment
- `gfx.rect(x, y, w, h, r, g, b, fill=True)` — rectangle
- `gfx.text(x, y, text, r, g, b)` — text, top-left anchored
- `gfx.present()` — flush + pump events (typically called once per frame)
- `gfx.poll()` — pump events without drawing
- `gfx.closed()` — whether the window was closed
- `gfx.delay(ms)` — sleep while pumping events (frame pacing)
- `gfx.width()` / `gfx.height()` — window size

**Coordinates:** 1-based pixel coordinates, origin top-left.
**Colors:** 3-tuples `(r, g, b)` each `0..255`; clamped by the backend.

**Status:** Awaiting confirmation; expandable in a later phase.

---

## 2026-11-26 — The `gfx` loop is driven by user code (Phase 4)

Tkinter owns the event loop when a window is open. Therefore the interpreter
does **not** call `mainloop()`. Instead:

* `gfx.present()` schedules `update_idletasks()` + `update()`, so drawing
  appears immediately.
* `gfx.poll()` / `gfx.delay(ms)` pump events.
* User programs use `while true do … gfx.present() … end` (as in the
  spec's spinning-cube example) to drive the loop.

`gfx.closed()` is expected to be checked by the user to break out when the
window is closed; the interpreter does not forcibly abort the program.

**Status:** Awaiting confirmation.

---

## 2026-11-26 — tkinter imports are lazy (Phase 4)

`vyrel/gfx/tk_backend.py` imports `tkinter` **inside methods**, never at
module import time. This is required by the spec and lets the full test
suite run with **no display** (the tests install a headless stub backend).
It also means `import vyrel.gfx` works on machines without tkinter.

**Status:** Per spec.

---

## 2026-11-26 — REPL evaluation model (Phase 4)

The REPL keeps a single :class:`Interpreter` across lines (so `let x = 1`
persists). Each line is lexed/parsed as one program. Statements run in
order; if the last statement is an expression statement, its value is
printed. Multi-line blocks must be entered on one line in Phase 4 (a
multi-line mode can be added later).

**Status:** Awaiting confirmation.

---

## 2026-11-26 — CLI error reporting (Phase 4)

Any `VyrelError` (Lex, Parse, Runtime) is rendered with the source line and
a caret via :func:`vyrel.errors.format_error`, printed to **stderr**, and
causes exit code **1**. File-not-found and usage errors also return 1 / 2
respectively. Successful runs return 0.

**Status:** Standard Unix convention; documented for clarity.

---

## 2026-11-26 — `vyrel-fs` fork planned (Phase 13+)

After Phase 10 completes the beginner version, a fork named **`vyrel-fs`**
("Vyrel Fast & Strong") will be created as a sibling package `vyrel_fs/`.
The beginner version (`vyrel/`) remains pure Python, stdlib only, and
Crostini-compatible forever. `vyrel-fs`:

* Shares lexer/parser/ast_nodes/stdlib with `vyrel/` where identical.
* Adds a bytecode VM (`compiler.py` + `vm.py`) for 3–10x speed.
* Adds diverse stdlib (os, re, async, subprocess, threads).
* Adds a native C renderer (`_native/renderer.c`) — no pure-Python fallback
  required, because Crostini compatibility is explicitly waived for the fork.
* Adds language extensions (comprehensions, ternaries, optional types).
* Ships as `python3 -m vyrel_fs` alongside `python3 -m vyrel`.

Compatibility contract: any `.vyr` program in the *shared subset* runs
identically under both interpreters, verified by `tests/test_compatibility.py`.
Divergence (extra features) is one-way: beginner programs run on the fork,
but fork programs that use extensions may not run on the beginner version.

**Status:** Confirmed by project owner. To be built after Phase 10.
