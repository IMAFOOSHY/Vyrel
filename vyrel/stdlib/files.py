"""Vyrel `files` module — UTF-8 file I/O and directory listing.

Registered under the Vyrel module name ``"files"``.  Cross-platform by
construction: ``pathlib`` everywhere, UTF-8 always, no shell-outs, no
distro-specific behavior.

Safety model (documented in DECISIONS): reads and writes are allowed from
any path the user explicitly names.  There is no chroot/sandbox — Vyrel is
a beginner language that runs with the user's own permissions.  We refuse
nothing except malformed arguments.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from ._util import StdlibError, as_str


def _read(path: Any) -> str:
    p = Path(as_str(path))
    try:
        return p.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise StdlibError(f"file not found: {p}")
    except OSError as e:
        raise StdlibError(f"cannot read {p}: {e}")


def _write(path: Any, text: Any) -> None:
    p = Path(as_str(path))
    try:
        p.write_text(as_str(text), encoding="utf-8")
    except OSError as e:
        raise StdlibError(f"cannot write {p}: {e}")


def _append(path: Any, text: Any) -> None:
    p = Path(as_str(path))
    try:
        with p.open("a", encoding="utf-8") as f:
            f.write(as_str(text))
    except OSError as e:
        raise StdlibError(f"cannot append to {p}: {e}")


def _exists(path: Any) -> bool:
    return Path(as_str(path)).exists()


def _listdir(path: Any = ".") -> List[str]:
    p = Path(as_str(path))
    if not p.is_dir():
        raise StdlibError(f"not a directory: {p}")
    try:
        return sorted(child.name for child in p.iterdir())
    except OSError as e:
        raise StdlibError(f"cannot list {p}: {e}")


def _mkdir(path: Any) -> None:
    p = Path(as_str(path))
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise StdlibError(f"cannot create directory {p}: {e}")


def _remove(path: Any) -> None:
    p = Path(as_str(path))
    try:
        p.unlink()
    except FileNotFoundError:
        raise StdlibError(f"file not found: {p}")
    except OSError as e:
        raise StdlibError(f"cannot remove {p}: {e}")


def _read_lines(path: Any) -> List[str]:
    return _read(path).splitlines()


def _write_lines(path: Any, lines: Any) -> None:
    if not isinstance(lines, list):
        raise StdlibError("write_lines() needs a list of strings")
    _write(path, "\n".join(as_str(x) for x in lines))


def _size(path: Any) -> int:
    p = Path(as_str(path))
    try:
        return p.stat().st_size
    except FileNotFoundError:
        raise StdlibError(f"file not found: {p}")
    except OSError as e:
        raise StdlibError(f"cannot stat {p}: {e}")


def attrs() -> Dict[str, Any]:
    return {
        "read": _read,
        "write": _write,
        "append": _append,
        "exists": _exists,
        "listdir": _listdir,
        "mkdir": _mkdir,
        "remove": _remove,
        "read_lines": _read_lines,
        "write_lines": _write_lines,
        "size": _size,
    }
