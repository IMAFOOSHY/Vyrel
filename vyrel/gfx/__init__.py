"""Graphics backend registry.

Only ``tk_backend`` exists in Phase 4.  The backend is chosen lazily so that
importing :mod:`vyrel.gfx` never requires tkinter (and never requires a
display).
"""

from __future__ import annotations

from typing import Optional


_backend = None


def get_backend():
    """Return (and lazily construct) the current graphics backend."""
    global _backend
    if _backend is None:
        from .tk_backend import TkBackend
        _backend = TkBackend()
    return _backend


def reset_backend() -> None:
    """Close and clear the current backend (used by tests)."""
    global _backend
    if _backend is not None:
        try:
            _backend.close()
        except Exception:
            pass
        _backend = None


def set_backend(backend) -> None:
    """Install a custom backend (used by tests to avoid a display)."""
    global _backend
    if _backend is not None:
        try:
            _backend.close()
        except Exception:
            pass
    _backend = backend
