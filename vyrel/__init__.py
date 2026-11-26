"""Vyrel language package.

This package contains the reference tree-walking interpreter for the Vyrel
language (file extension ``.vyr``).  The package is organized into strictly
one-way layers to keep the codebase approachable for beginners and to make
each layer independently testable:

    errors  -> tokens -> lexer -> parser -> interpreter -> main/repl

Phase 1 (this delivery) implements the ``errors``, ``tokens``, and ``lexer``
layers only.  Later phases add ``ast_nodes``, ``parser``, ``interpreter``,
``stdlib``, and ``gfx``.

Public re-exports
-----------------
``VyrelError``, ``LexError`` and ``format_error`` are surfaced here so user
code and the CLI can import them without digging into submodules.
"""

from __future__ import annotations

from .errors import LexError, VyrelError, format_error

__all__ = ["VyrelError", "LexError", "format_error"]

# Version is informational only; the language spec is the source of truth.
__version__ = "0.1.0-phase1"
