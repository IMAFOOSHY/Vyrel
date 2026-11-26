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
