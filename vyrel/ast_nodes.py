"""AST node definitions for Vyrel.

Every node is a frozen dataclass.  Nodes carry a ``line`` and ``column``
(1-based) for beginner-friendly error reporting.  Nodes are *pure data*: they
contain no methods beyond what dataclasses generate, and they import nothing
from later layers.

Two top-level unions:

* :data:`Expr`  — expression nodes (produce values when evaluated).
* :data:`Stmt`  — statement nodes (produce effects / control flow).

The parser returns :class:`Program` containing a list of ``Stmt``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple, Union


# --------------------------------------------------------------------------- #
# Base                                                                        #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Node:
    """Base for every AST node; carries a source position."""

    line: int
    column: int


# --------------------------------------------------------------------------- #
# Expressions                                                                 #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class IntLit(Node):
    value: int


@dataclass(frozen=True)
class FloatLit(Node):
    value: float


@dataclass(frozen=True)
class StringLit(Node):
    value: str


@dataclass(frozen=True)
class BoolLit(Node):
    value: bool


@dataclass(frozen=True)
class NilLit(Node):
    pass


@dataclass(frozen=True)
class TemplateExpr(Node):
    """A string with interpolation.  ``parts`` is a list of ``str`` (literal
    segments) and ``Expr`` (interpolated expressions).  The lexer produced
    ``InterpPart``; the parser re-lexed & parsed each into an ``Expr``."""

    parts: Tuple[Union[str, "Expr"], ...]


@dataclass(frozen=True)
class Ident(Node):
    name: str


@dataclass(frozen=True)
class SelfExpr(Node):
    pass


@dataclass(frozen=True)
class ListLit(Node):
    items: Tuple["Expr", ...]


@dataclass(frozen=True)
class DictLit(Node):
    """Dictionary literal.  Keys are arbitrary expressions (in practice,
    identifiers or string literals); the interpreter enforces hashability."""

    entries: Tuple[Tuple["Expr", "Expr"], ...]


@dataclass(frozen=True)
class UnaryOp(Node):
    op: str            # '-', 'not'
    operand: "Expr"


@dataclass(frozen=True)
class BinaryOp(Node):
    op: str            # '+', '-', '*', '/', '//', '%', '**',
                       # '==', '!=', '<', '<=', '>', '>=',
                       # 'and', 'or', 'in'
    left: "Expr"
    right: "Expr"


@dataclass(frozen=True)
class Index(Node):
    target: "Expr"
    index: "Expr"


@dataclass(frozen=True)
class Slice(Node):
    target: "Expr"
    lower: Optional["Expr"]
    upper: Optional["Expr"]


@dataclass(frozen=True)
class Attr(Node):
    target: "Expr"
    name: str


@dataclass(frozen=True)
class Call(Node):
    func: "Expr"
    args: Tuple["Expr", ...]


@dataclass(frozen=True)
class Lambda(Node):
    """A ``fn(x) => expr`` function-expression (arrow form only)."""

    params: Tuple["Param", ...]
    body: "Expr"


@dataclass(frozen=True)
class Param:
    """One function parameter.  ``default`` is None if no default was given."""

    name: str
    default: Optional["Expr"]
    line: int
    column: int


# --------------------------------------------------------------------------- #
# Statements                                                                  #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Program(Node):
    body: Tuple["Stmt", ...]


@dataclass(frozen=True)
class ExprStmt(Node):
    expr: "Expr"


@dataclass(frozen=True)
class LetStmt(Node):
    name: str
    value: "Expr"
    is_const: bool


@dataclass(frozen=True)
class AssignStmt(Node):
    """Simple assignment ``x = e`` or compound ``x += e`` etc.
    ``target`` is restricted to l-values: Ident, Index, Attr."""

    target: "Expr"
    op: str            # '=', '+=', '-=', '*=', '/=', '%='
    value: "Expr"


@dataclass(frozen=True)
class ReturnStmt(Node):
    value: Optional["Expr"]


@dataclass(frozen=True)
class BreakStmt(Node):
    pass


@dataclass(frozen=True)
class ContinueStmt(Node):
    pass


@dataclass(frozen=True)
class IfStmt(Node):
    branches: Tuple[Tuple["Expr", Tuple["Stmt", ...]], ...]
    else_body: Tuple["Stmt", ...]      # empty tuple if no else


@dataclass(frozen=True)
class WhileStmt(Node):
    condition: "Expr"
    body: Tuple["Stmt", ...]


@dataclass(frozen=True)
class ForStmt(Node):
    """``for x in it`` (key_name is None) or ``for k, v in d``."""

    key_name: Optional[str]
    value_name: str
    iterable: "Expr"
    body: Tuple["Stmt", ...]


@dataclass(frozen=True)
class ThrowStmt(Node):
    value: "Expr"


@dataclass(frozen=True)
class TryStmt(Node):
    body: Tuple["Stmt", ...]
    catch_name: Optional[str]
    catch_body: Tuple["Stmt", ...]      # empty if no catch
    finally_body: Tuple["Stmt", ...]    # empty if no finally


@dataclass(frozen=True)
class MatchArm:
    patterns: Tuple[Any, ...]           # literal values (int/float/str/bool/nil)
    body: Tuple["Stmt", ...]
    line: int
    column: int


@dataclass(frozen=True)
class MatchStmt(Node):
    subject: "Expr"
    arms: Tuple[MatchArm, ...]
    else_body: Tuple["Stmt", ...]


@dataclass(frozen=True)
class FunctionDecl(Node):
    name: str
    params: Tuple[Param, ...]
    body: Tuple["Stmt", ...]


@dataclass(frozen=True)
class ClassDecl(Node):
    name: str
    superclass: Optional[str]
    methods: Tuple["FunctionDecl", ...]


@dataclass(frozen=True)
class ImportStmt(Node):
    """``import math`` / ``import "file.vyr" as f``.

    ``module`` is the dotted name (e.g. ``"math"``) OR the file path string
    (e.g. ``"file.vyr"``).  ``alias`` is None if no ``as`` clause."""

    module: str
    is_file: bool
    alias: Optional[str]


@dataclass(frozen=True)
class FromImportStmt(Node):
    """``from math import sqrt`` / ``from "f.vyr" import a, b as c``."""

    module: str
    is_file: bool
    names: Tuple[Tuple[str, Optional[str]], ...]   # (name, alias_or_None)


# --------------------------------------------------------------------------- #
# Unions                                                                      #
# --------------------------------------------------------------------------- #

Expr = Union[
    IntLit, FloatLit, StringLit, BoolLit, NilLit, TemplateExpr,
    Ident, SelfExpr, ListLit, DictLit,
    UnaryOp, BinaryOp, Index, Slice, Attr, Call, Lambda,
]

Stmt = Union[
    ExprStmt, LetStmt, AssignStmt, ReturnStmt, BreakStmt, ContinueStmt,
    IfStmt, WhileStmt, ForStmt, ThrowStmt, TryStmt, MatchStmt,
    FunctionDecl, ClassDecl, ImportStmt, FromImportStmt,
]
