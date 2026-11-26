"""Public ``gfx`` module for Vyrel.

This is a thin facade over :mod:`vyrel.gfx`.  It exposes a beginner-friendly
2D drawing API::

    gfx.open("hello", 640, 480)
    gfx.clear(0, 0, 0)
    gfx.line(0, 0, 639, 479, 255, 255, 255)
    gfx.present()
    while not gfx.closed() do
        gfx.poll()
        gfx.delay(16)
    end

All coordinates are pixel coordinates in the window; the origin is
top-left.  Colors are ``(r, g, b)`` each 0..255.
"""

from __future__ import annotations

from typing import Any, Dict


def attrs() -> Dict[str, Any]:
    """Return the mapping the interpreter installs into a `gfx` module."""
    from ..gfx import get_backend

    def _open(title: str = "Vyrel", width: int = 640, height: int = 480) -> None:
        get_backend().open(title, int(width), int(height))

    def _clear(r: int = 0, g: int = 0, b: int = 0) -> None:
        get_backend().clear(int(r), int(g), int(b))

    def _pixel(x: int, y: int, r: int, g: int, b: int) -> None:
        get_backend().pixel(int(x), int(y), int(r), int(g), int(b))

    def _line(x1: int, y1: int, x2: int, y2: int,
              r: int, g: int, b: int) -> None:
        get_backend().line(int(x1), int(y1), int(x2), int(y2),
                           int(r), int(g), int(b))

    def _rect(x: int, y: int, w: int, h: int,
              r: int, g: int, b: int, *, fill: bool = True) -> None:
        get_backend().rect(int(x), int(y), int(w), int(h),
                           int(r), int(g), int(b), fill=fill)

    def _text(x: int, y: int, text: str,
              r: int = 255, g: int = 255, b: int = 255) -> None:
        get_backend().text(int(x), int(y), str(text), int(r), int(g), int(b))

    def _present() -> None:
        get_backend().present()

    def _poll() -> None:
        get_backend().poll()

    def _closed() -> bool:
        return get_backend().closed()

    def _delay(ms: int = 16) -> None:
        get_backend().delay(int(ms))

    def _width() -> int:
        return get_backend().width()

    def _height() -> int:
        return get_backend().height()

    return {
        "open": _open,
        "clear": _clear,
        "pixel": _pixel,
        "line": _line,
        "rect": _rect,
        "text": _text,
        "present": _present,
        "poll": _poll,
        "closed": _closed,
        "delay": _delay,
        "width": _width,
        "height": _height,
    }
