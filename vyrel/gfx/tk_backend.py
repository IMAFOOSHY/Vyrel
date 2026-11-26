"""Tkinter-based graphics backend.

``tkinter`` is imported **lazily**, inside methods, so that:
* importing this module never requires a display,
* the test suite (which uses a headless stub backend) never loads tkinter,
* Phase 1–3 tests keep running on systems without tkinter installed.

The backend owns a single Tk root and canvas.  `present()` schedules a Tk
`update_idletasks()` + `update()` so drawing shows immediately; `poll()`
does a non-blocking `update()`; `delay(ms)` pumps events for that many ms.
"""

from __future__ import annotations

from typing import Any


class TkBackend:
    """Tk implementation of the graphics backend interface."""

    def __init__(self) -> None:
        self._root: Any = None
        self._canvas: Any = None
        self._width = 0
        self._height = 0
        self._closed = True

    # ------------------------------------------------------------------ #
    # Lifecycle                                                          #
    # ------------------------------------------------------------------ #

    def open(self, title: str, width: int, height: int) -> None:
        import tkinter  # lazy: not imported unless a window is opened

        if self._root is not None:
            # Already open; just raise and continue.
            self._root.deiconify()
            self._root.lift()
            return

        self._root = tkinter.Tk()
        self._root.title(title)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._canvas = tkinter.Canvas(
            self._root, width=width, height=height, highlightthickness=0,
        )
        self._canvas.pack()
        self._width = width
        self._height = height
        self._closed = False

        # Defer the first update so the window is visible before drawing.
        self._root.update_idletasks()
        self._root.update()

    def close(self) -> None:
        if self._root is not None:
            try:
                self._root.destroy()
            except Exception:
                pass
            self._root = None
            self._canvas = None
            self._closed = True

    def _on_close(self) -> None:
        self._closed = True

    # ------------------------------------------------------------------ #
    # Properties                                                         #
    # ------------------------------------------------------------------ #

    def width(self) -> int:
        return self._width

    def height(self) -> int:
        return self._height

    def closed(self) -> bool:
        return self._closed

    # ------------------------------------------------------------------ #
    # Drawing                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _color(r: int, g: int, b: int) -> str:
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _ensure_open(self) -> None:
        if self._root is None:
            self.open("Vyrel", 640, 480)

    def clear(self, r: int, g: int, b: int) -> None:
        self._ensure_open()
        self._canvas.delete("all")
        self._canvas.configure(bg=self._color(r, g, b))

    def pixel(self, x: int, y: int, r: int, g: int, b: int) -> None:
        self._ensure_open()
        self._canvas.create_rectangle(x, y, x + 1, y + 1,
                                      outline=self._color(r, g, b),
                                      fill=self._color(r, g, b))

    def line(self, x1: int, y1: int, x2: int, y2: int,
             r: int, g: int, b: int) -> None:
        self._ensure_open()
        self._canvas.create_line(x1, y1, x2, y2, fill=self._color(r, g, b))

    def rect(self, x: int, y: int, w: int, h: int,
             r: int, g: int, b: int, *, fill: bool = True) -> None:
        self._ensure_open()
        color = self._color(r, g, b)
        self._canvas.create_rectangle(
            x, y, x + w, y + h,
            outline=color,
            fill=color if fill else "",
        )

    def text(self, x: int, y: int, text: str, r: int, g: int, b: int) -> None:
        self._ensure_open()
        self._canvas.create_text(x, y, text=text, fill=self._color(r, g, b),
                                 anchor="nw")

    # ------------------------------------------------------------------ #
    # Event loop                                                         #
    # ------------------------------------------------------------------ #

    def present(self) -> None:
        self._ensure_open()
        self._root.update_idletasks()
        self._root.update()

    def poll(self) -> None:
        self._ensure_open()
        self._root.update_idletasks()
        self._root.update()

    def delay(self, ms: int) -> None:
        self._ensure_open()
        # Pump events in small slices so the window stays responsive.
        remaining = max(0, int(ms))
        slice_ms = 16
        while remaining > 0:
            self._root.update()
            self._root.after(min(slice_ms, remaining))
            remaining -= slice_ms
