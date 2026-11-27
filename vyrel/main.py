"""Vyrel CLI — file runner and REPL dispatch.

Usage::

    python3 -m vyrel                       # start the REPL
    python3 -m vyrel program.vyr           # run a file
    python3 -m vyrel --tokens program.vyr  # dump the token stream
    python3 -m vyrel --ast program.vyr     # dump the AST
    python3 -m vyrel --version             # print the version
    python3 -m vyrel --help                # print usage

Errors are rendered with the source line and caret, printed to stderr, and
result in exit code 1.  Missing files and bad usage return exit code 1 or 2
respectively.  Successful runs return 0.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

from .errors import VyrelError, format_error
from .interpreter import Interpreter
from .lexer import Lexer
from .parser import parse


VERSION = "0.1.0"


def _print_tokens(source: str) -> int:
    """Print the token stream, one token per line, to stdout."""
    try:
        tokens = Lexer(source).tokenize()
    except VyrelError as e:
        print(format_error(e, source), file=sys.stderr)
        return 1
    for tok in tokens:
        print(f"{tok.line:>4}:{tok.column:<4} {tok.type.name:<14} "
              f"{_render_value(tok.value)!r}")
    return 0


def _render_value(value: object) -> object:
    """Compact rendering of a token value for --tokens output."""
    from .tokens import InterpPart
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(repr(item))
            elif isinstance(item, InterpPart):
                parts.append(f"<expr {item.text!r}>")
            else:
                parts.append(repr(item))
        return "TEMPLATE[" + ", ".join(parts) + "]"
    return value


def _dump_ast(node: object, indent: int = 0) -> None:
    """Pretty-print an AST node as an indented tree."""
    from dataclasses import fields

    from . import ast_nodes as ast

    def _is_tree(v: object) -> bool:
        if isinstance(v, (ast.Node, ast.Param, ast.MatchArm)):
            return True
        if isinstance(v, (list, tuple)) and len(v) > 0:
            return any(
                isinstance(x, (ast.Node, ast.Param, ast.MatchArm))
                or isinstance(x, (list, tuple))
                for x in v
            )
        return False

    pad = "  " * indent

    if isinstance(node, (ast.Param, ast.MatchArm)):
        print(f"{pad}{type(node).__name__}")
        for f in fields(node):
            v = getattr(node, f.name)
            if _is_tree(v):
                print(f"{pad}  {f.name}:")
                _dump_ast(v, indent + 2)
            else:
                print(f"{pad}  {f.name} = {v!r}")
        return

    if isinstance(node, (list, tuple)):
        for item in node:
            _dump_ast(item, indent)
        return

    if isinstance(node, ast.Node):
        print(f"{pad}{type(node).__name__}")
        for f in fields(node):
            v = getattr(node, f.name)
            if _is_tree(v):
                print(f"{pad}  {f.name}:")
                _dump_ast(v, indent + 2)
            else:
                print(f"{pad}  {f.name} = {v!r}")
        return

    print(f"{pad}{node!r}")


def _print_ast(source: str) -> int:
    try:
        program = parse(source)
    except VyrelError as e:
        print(format_error(e, source), file=sys.stderr)
        return 1
    _dump_ast(program)
    return 0


def run_file(path: str) -> int:
    """Run a .vyr file.  Returns the process exit code."""
    p = Path(path)
    try:
        source = p.read_text(encoding="utf-8")
    except OSError as e:
        print(f"error: cannot read {path}: {e}", file=sys.stderr)
        return 1

    try:
        program = parse(source)
    except VyrelError as e:
        print(format_error(e, source), file=sys.stderr)
        return 1

    try:
        Interpreter().run(program)
    except VyrelError as e:
        print(format_error(e, source), file=sys.stderr)
        return 1
    return 0


USAGE = """\
usage: python3 -m vyrel [options] [file.vyr]

Run a Vyrel program, or start the REPL if no file is given.

options:
  --tokens FILE    dump the token stream to stdout
  --ast FILE       dump the AST to stdout
  --version        print the version and exit
  -h, --help       print this message and exit
"""


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        from .repl import run_repl
        return run_repl()

    if argv[0] in ("-h", "--help"):
        print(USAGE, end="")
        return 0

    if argv[0] == "--version":
        print(f"vyrel {VERSION}")
        return 0

    if argv[0] == "--tokens":
        if len(argv) != 2:
            print("error: --tokens needs exactly one file", file=sys.stderr)
            return 2
        source = _read_or_report(argv[1])
        if source is None:
            return 1
        return _print_tokens(source)

    if argv[0] == "--ast":
        if len(argv) != 2:
            print("error: --ast needs exactly one file", file=sys.stderr)
            return 2
        source = _read_or_report(argv[1])
        if source is None:
            return 1
        return _print_ast(source)

    if len(argv) == 1:
        return run_file(argv[0])

    print("error: too many arguments", file=sys.stderr)
    print(USAGE, end="", file=sys.stderr)
    return 2


def _read_or_report(path: str) -> Optional[str]:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as e:
        print(f"error: cannot read {path}: {e}", file=sys.stderr)
        return None


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
