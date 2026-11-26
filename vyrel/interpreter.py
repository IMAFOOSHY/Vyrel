"""Tree-walking interpreter for Vyrel.

Evaluates a :class:`vyrel.ast_nodes.Program` against an
:class:`Environment` (lexical scoping, closures, ``let``/``const``).
Provides builtins, a stdlib registry (core/collections/strings/files/math/gfx
in Phase 5 batch A), classes/instances with implicit ``self`` and ``super``,
exceptions (``throw``/``try``/``catch``/``finally``), and a call-depth limit
of 1000.

Interpretation calls not pinned by the spec are documented in
``docs/DECISIONS.md``.
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional, Tuple

from . import ast_nodes as ast
from .errors import VyrelRuntimeError

# Our MAX_CALL_DEPTH check must fire before Python's own RecursionError.
if sys.getrecursionlimit() < 10000:
    sys.setrecursionlimit(10000)


# --------------------------------------------------------------------------- #
# Internal control-flow signals                                               #
# --------------------------------------------------------------------------- #


class _ReturnSignal(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


class _BreakSignal(Exception):
    pass


class _ContinueSignal(Exception):
    pass


class _ThrownValue(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


# --------------------------------------------------------------------------- #
# Environment                                                                 #
# --------------------------------------------------------------------------- #


class _Binding:
    __slots__ = ("value", "is_const")

    def __init__(self, value: Any, is_const: bool) -> None:
        self.value = value
        self.is_const = is_const


class Environment:
    """Lexical scope chain used by the interpreter."""

    __slots__ = ("parent", "bindings", "name")

    def __init__(
        self, parent: Optional["Environment"] = None, name: str = "",
    ) -> None:
        self.parent = parent
        self.bindings: Dict[str, _Binding] = {}
        self.name = name

    def define(self, name: str, value: Any, *, is_const: bool = False) -> None:
        self.bindings[name] = _Binding(value, is_const)

    def get(self, name: str) -> Any:
        env: Optional[Environment] = self
        while env is not None:
            b = env.bindings.get(name)
            if b is not None:
                return b.value
            env = env.parent
        raise VyrelRuntimeError(f"undefined variable '{name}'")

    def has(self, name: str) -> bool:
        env: Optional[Environment] = self
        while env is not None:
            if name in env.bindings:
                return True
            env = env.parent
        return False

    def assign(self, name: str, value: Any) -> None:
        env: Optional[Environment] = self
        while env is not None:
            b = env.bindings.get(name)
            if b is not None:
                if b.is_const:
                    raise VyrelRuntimeError(
                        f"cannot reassign constant '{name}'"
                    )
                b.value = value
                return
            env = env.parent
        raise VyrelRuntimeError(f"undefined variable '{name}'")


# --------------------------------------------------------------------------- #
# User-defined value wrappers                                                 #
# --------------------------------------------------------------------------- #


class VyrelFunction:
    __slots__ = ("params", "body", "closure", "name")

    def __init__(
        self,
        params: Tuple[ast.Param, ...],
        body: Tuple[ast.Stmt, ...],
        closure: Environment,
        name: str,
    ) -> None:
        self.params = params
        self.body = body
        self.closure = closure
        self.name = name


class VyrelLambda:
    __slots__ = ("params", "body", "closure", "name")

    def __init__(
        self,
        params: Tuple[ast.Param, ...],
        body: ast.Expr,
        closure: Environment,
        name: str = "<lambda>",
    ) -> None:
        self.params = params
        self.body = body
        self.closure = closure
        self.name = name


class VyrelClass:
    __slots__ = ("name", "superclass", "methods")

    def __init__(
        self,
        name: str,
        superclass: Optional["VyrelClass"],
        methods: Dict[str, VyrelFunction],
    ) -> None:
        self.name = name
        self.superclass = superclass
        self.methods = methods

    def find_method(self, name: str) -> Optional[VyrelFunction]:
        cls: Optional[VyrelClass] = self
        while cls is not None:
            m = cls.methods.get(name)
            if m is not None:
                return m
            cls = cls.superclass
        return None


class VyrelInstance:
    __slots__ = ("cls", "fields")

    def __init__(self, cls: VyrelClass) -> None:
        self.cls = cls
        self.fields: Dict[str, Any] = {}


class VyrelModule:
    __slots__ = ("name", "attrs")

    def __init__(self, name: str, attrs: Dict[str, Any]) -> None:
        self.name = name
        self.attrs = attrs


class _BoundMethod:
    __slots__ = ("fn", "instance")

    def __init__(self, fn: VyrelFunction, instance: VyrelInstance) -> None:
        self.fn = fn
        self.instance = instance


class _SuperProxy:
    __slots__ = ("instance",)

    def __init__(self, instance: VyrelInstance) -> None:
        self.instance = instance


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _truthy(value: Any) -> bool:
    if value is None or value is False:
        return False
    if value is True:
        return True
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, (str, list, dict)):
        return len(value) > 0
    return True


def _type_name(value: Any) -> str:
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, (VyrelFunction, VyrelLambda)):
        return "function"
    if isinstance(value, VyrelClass):
        return "class"
    if isinstance(value, VyrelInstance):
        return "instance"
    if isinstance(value, VyrelModule):
        return "module"
    return "native"


def _stringify(value: Any, interp: "Optional[Interpreter]" = None) -> str:
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, float):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, VyrelInstance):
        to_string = value.cls.find_method("to_string")
        if to_string is not None and interp is not None:
            result = interp._call_function(to_string, [], instance=value)
            return _stringify(result, interp)
        return f"<{value.cls.name} instance>"
    if isinstance(value, list):
        return "[" + ", ".join(_stringify(v, interp) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(
            f"{_stringify(k, interp)}: {_stringify(v, interp)}"
            for k, v in value.items()
        ) + "}"
    return str(value)


def _eq(a: Any, b: Any) -> bool:
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    return a == b


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# --------------------------------------------------------------------------- #
# The interpreter                                                             #
# --------------------------------------------------------------------------- #


class Interpreter:
    MAX_CALL_DEPTH = 1000

    def __init__(self) -> None:
        self.globals = Environment(name="<global>")
        self._depth = 0
        self._install_builtins()

    def run(self, program: ast.Program) -> None:
        self._exec_block(program.body, self.globals)

    def eval_expr(self, expr: ast.Expr, env: Optional[Environment] = None) -> Any:
        if env is None:
            env = self.globals
        return self._eval(expr, env)

    def exec_block(self, stmts: Tuple[ast.Stmt, ...]) -> None:
        self._exec_block(stmts, self.globals)

    # ------------------------------------------------------------------ #
    # Builtins                                                           #
    # ------------------------------------------------------------------ #

    def _install_builtins(self) -> None:
        def _print(*args: Any) -> None:
            print(" ".join(_stringify(a, self) for a in args))

        def _range(*args: int) -> List[int]:
            return list(range(*args))

        def _len(x: Any) -> int:
            try:
                return len(x)
            except TypeError:
                raise VyrelRuntimeError(
                    f"cannot get length of {_type_name(x)}"
                )

        def _to_str(x: Any = "") -> str:
            return _stringify(x, self)

        def _to_int(x: Any = 0) -> int:
            if isinstance(x, bool):
                return int(x)
            if isinstance(x, (int, float, str)):
                try:
                    return int(x)
                except (TypeError, ValueError):
                    pass
            raise VyrelRuntimeError(
                f"cannot convert {_type_name(x)} to int"
            )

        def _to_float(x: Any = 0.0) -> float:
            if isinstance(x, (int, float, str)):
                try:
                    return float(x)
                except (TypeError, ValueError):
                    pass
            raise VyrelRuntimeError(
                f"cannot convert {_type_name(x)} to float"
            )

        def _to_bool(x: Any = False) -> bool:
            return _truthy(x)

        def _type_of(x: Any = None) -> str:
            return _type_name(x)

        builtins: Tuple[Tuple[str, Any], ...] = (
            ("print", _print),
            ("range", _range),
            ("len", _len),
            ("str", _to_str),
            ("int", _to_int),
            ("float", _to_float),
            ("bool", _to_bool),
            ("abs", abs),
            ("min", min),
            ("max", max),
            ("round", round),
            ("type", _type_of),
        )
        for name, value in builtins:
            self.globals.define(name, value, is_const=True)

    # ------------------------------------------------------------------ #
    # Statements                                                         #
    # ------------------------------------------------------------------ #

    def _exec_block(self, stmts: Tuple[ast.Stmt, ...], env: Environment) -> None:
        for stmt in stmts:
            self._exec_stmt(stmt, env)

    def _exec_stmt(self, stmt: ast.Stmt, env: Environment) -> None:
        if isinstance(stmt, ast.ExprStmt):
            self._eval(stmt.expr, env)
            return

        if isinstance(stmt, ast.LetStmt):
            value = self._eval(stmt.value, env)
            env.define(stmt.name, value, is_const=stmt.is_const)
            return

        if isinstance(stmt, ast.AssignStmt):
            value = self._eval(stmt.value, env)
            if stmt.op != "=":
                current = self._read_target(stmt.target, env)
                value = self._apply_binop(
                    stmt.op[0], current, value,
                    stmt.target.line, stmt.target.column,
                )
            self._write_target(stmt.target, value, env)
            return

        if isinstance(stmt, ast.ReturnStmt):
            value = self._eval(stmt.value, env) if stmt.value is not None else None
            raise _ReturnSignal(value)

        if isinstance(stmt, ast.BreakStmt):
            raise _BreakSignal()

        if isinstance(stmt, ast.ContinueStmt):
            raise _ContinueSignal()

        if isinstance(stmt, ast.IfStmt):
            for cond, body in stmt.branches:
                if _truthy(self._eval(cond, env)):
                    self._exec_block(body, env)
                    return
            if stmt.else_body:
                self._exec_block(stmt.else_body, env)
            return

        if isinstance(stmt, ast.WhileStmt):
            while _truthy(self._eval(stmt.condition, env)):
                try:
                    self._exec_block(stmt.body, env)
                except _ContinueSignal:
                    continue
                except _BreakSignal:
                    break
            return

        if isinstance(stmt, ast.ForStmt):
            self._exec_for(stmt, env)
            return

        if isinstance(stmt, ast.ThrowStmt):
            raise _ThrownValue(self._eval(stmt.value, env))

        if isinstance(stmt, ast.TryStmt):
            self._exec_try(stmt, env)
            return

        if isinstance(stmt, ast.MatchStmt):
            self._exec_match(stmt, env)
            return

        if isinstance(stmt, ast.FunctionDecl):
            env.define(stmt.name, VyrelFunction(
                stmt.params, stmt.body, env, stmt.name,
            ))
            return

        if isinstance(stmt, ast.ClassDecl):
            superclass: Optional[VyrelClass] = None
            if stmt.superclass is not None:
                sup = env.get(stmt.superclass)
                if not isinstance(sup, VyrelClass):
                    raise VyrelRuntimeError(
                        f"'{stmt.superclass}' is not a class",
                        line=stmt.line, column=stmt.column,
                    )
                superclass = sup
            methods: Dict[str, VyrelFunction] = {}
            for m in stmt.methods:
                methods[m.name] = VyrelFunction(m.params, m.body, env, m.name)
            env.define(stmt.name, VyrelClass(stmt.name, superclass, methods))
            return

        if isinstance(stmt, ast.ImportStmt):
            if stmt.is_file:
                raise VyrelRuntimeError(
                    "importing .vyr files is not yet supported",
                    line=stmt.line, column=stmt.column,
                )
            mod = self._load_builtin_module(stmt.module, stmt.line, stmt.column)
            name = stmt.alias if stmt.alias is not None else stmt.module
            env.define(name, mod)
            return

        if isinstance(stmt, ast.FromImportStmt):
            if stmt.is_file:
                raise VyrelRuntimeError(
                    "importing .vyr files is not yet supported",
                    line=stmt.line, column=stmt.column,
                )
            mod = self._load_builtin_module(stmt.module, stmt.line, stmt.column)
            for orig, alias in stmt.names:
                if orig not in mod.attrs:
                    raise VyrelRuntimeError(
                        f"module '{stmt.module}' has no name '{orig}'",
                        line=stmt.line, column=stmt.column,
                    )
                env.define(alias if alias else orig, mod.attrs[orig])
            return

        raise VyrelRuntimeError(
            f"internal: unknown statement {type(stmt).__name__}",
        )

    def _exec_for(self, stmt: ast.ForStmt, env: Environment) -> None:
        iterable = self._eval(stmt.iterable, env)
        items: List[Tuple[Any, Any]] = []
        if isinstance(iterable, dict):
            for k, v in iterable.items():
                if stmt.key_name is None:
                    items.append((None, k))
                else:
                    items.append((k, v))
        elif isinstance(iterable, (list, str)):
            for i, v in enumerate(iterable):
                if stmt.key_name is None:
                    items.append((None, v))
                else:
                    items.append((i, v))
        else:
            raise VyrelRuntimeError(
                f"cannot iterate over {_type_name(iterable)}",
                line=stmt.line, column=stmt.column,
            )
        for k, v in items:
            if stmt.key_name is not None:
                env.define(stmt.key_name, k)
            env.define(stmt.value_name, v)
            try:
                self._exec_block(stmt.body, env)
            except _ContinueSignal:
                continue
            except _BreakSignal:
                break

    def _exec_try(self, stmt: ast.TryStmt, env: Environment) -> None:
        try:
            try:
                self._exec_block(stmt.body, env)
            except _ThrownValue as t:
                if stmt.catch_name is None:
                    raise
                env.define(stmt.catch_name, t.value)
                self._exec_block(stmt.catch_body, env)
        finally:
            if stmt.finally_body:
                self._exec_block(stmt.finally_body, env)

    def _exec_match(self, stmt: ast.MatchStmt, env: Environment) -> None:
        subject = self._eval(stmt.subject, env)
        for arm in stmt.arms:
            for pat in arm.patterns:
                if _eq(subject, pat):
                    self._exec_block(arm.body, env)
                    return
        if stmt.else_body:
            self._exec_block(stmt.else_body, env)

    def _read_target(self, target: ast.Expr, env: Environment) -> Any:
        if isinstance(target, ast.Ident):
            return env.get(target.name)
        if isinstance(target, ast.Attr):
            return self._eval_attr(target, env)
        if isinstance(target, ast.Index):
            return self._index(
                self._eval(target.target, env),
                self._eval(target.index, env),
                target,
            )
        raise VyrelRuntimeError(
            "internal: invalid assignment target",
            line=target.line, column=target.column,
        )

    def _write_target(self, target: ast.Expr, value: Any, env: Environment) -> None:
        if isinstance(target, ast.Ident):
            env.assign(target.name, value)
            return
        if isinstance(target, ast.Attr):
            obj = self._eval(target.target, env)
            if isinstance(obj, VyrelInstance):
                obj.fields[target.name] = value
                return
            if isinstance(obj, dict):
                obj[target.name] = value
                return
            raise VyrelRuntimeError(
                f"cannot set attribute '{target.name}' on {_type_name(obj)}",
                line=target.line, column=target.column,
            )
        if isinstance(target, ast.Index):
            obj = self._eval(target.target, env)
            idx = self._eval(target.index, env)
            try:
                obj[idx] = value
            except (TypeError, KeyError, IndexError):
                raise VyrelRuntimeError(
                    f"cannot assign to {_type_name(obj)}[...]",
                    line=target.line, column=target.column,
                )
            return
        raise VyrelRuntimeError(
            "internal: invalid assignment target",
            line=target.line, column=target.column,
        )

    # ------------------------------------------------------------------ #
    # Expressions                                                        #
    # ------------------------------------------------------------------ #

    def _eval(self, expr: ast.Expr, env: Environment) -> Any:
        if isinstance(expr, ast.IntLit):
            return expr.value
        if isinstance(expr, ast.FloatLit):
            return expr.value
        if isinstance(expr, ast.StringLit):
            return expr.value
        if isinstance(expr, ast.BoolLit):
            return expr.value
        if isinstance(expr, ast.NilLit):
            return None
        if isinstance(expr, ast.TemplateExpr):
            return self._eval_template(expr, env)
        if isinstance(expr, ast.Ident):
            return env.get(expr.name)
        if isinstance(expr, ast.SelfExpr):
            return env.get("self")
        if isinstance(expr, ast.ListLit):
            return [self._eval(e, env) for e in expr.items]
        if isinstance(expr, ast.DictLit):
            d: Dict[Any, Any] = {}
            for k, v in expr.entries:
                if isinstance(k, ast.Ident):
                    key: Any = k.name
                else:
                    key = self._eval(k, env)
                d[key] = self._eval(v, env)
            return d
        if isinstance(expr, ast.UnaryOp):
            operand = self._eval(expr.operand, env)
            if expr.op == "-":
                if not _is_number(operand):
                    raise VyrelRuntimeError(
                        f"cannot negate {_type_name(operand)}",
                        line=expr.line, column=expr.column,
                    )
                return -operand
            if expr.op == "not":
                return not _truthy(operand)
            raise VyrelRuntimeError(
                f"internal: unknown unary {expr.op!r}",
                line=expr.line, column=expr.column,
            )
        if isinstance(expr, ast.BinaryOp):
            return self._eval_binary(expr, env)
        if isinstance(expr, ast.Index):
            return self._index(
                self._eval(expr.target, env),
                self._eval(expr.index, env),
                expr,
            )
        if isinstance(expr, ast.Slice):
            return self._eval_slice(expr, env)
        if isinstance(expr, ast.Attr):
            return self._eval_attr(expr, env)
        if isinstance(expr, ast.Call):
            return self._eval_call(expr, env)
        if isinstance(expr, ast.Lambda):
            return VyrelLambda(expr.params, expr.body, env)
        raise VyrelRuntimeError(
            f"internal: unknown expression {type(expr).__name__}",
        )

    def _eval_template(self, expr: ast.TemplateExpr, env: Environment) -> str:
        out: List[str] = []
        for part in expr.parts:
            if isinstance(part, str):
                out.append(part)
            else:
                out.append(_stringify(self._eval(part, env), self))
        return "".join(out)

    def _eval_slice(self, expr: ast.Slice, env: Environment) -> Any:
        target = self._eval(expr.target, env)
        lo = self._eval(expr.lower, env) if expr.lower is not None else None
        hi = self._eval(expr.upper, env) if expr.upper is not None else None
        try:
            return target[lo:hi]
        except TypeError:
            raise VyrelRuntimeError(
                f"cannot slice {_type_name(target)}",
                line=expr.line, column=expr.column,
            )

    def _eval_attr(self, expr: ast.Attr, env: Environment) -> Any:
        obj = self._eval(expr.target, env)

        if isinstance(obj, _SuperProxy):
            superclass = obj.instance.cls.superclass
            if superclass is None:
                raise VyrelRuntimeError(
                    f"class '{obj.instance.cls.name}' has no superclass",
                    line=expr.line, column=expr.column,
                )
            method = superclass.find_method(expr.name)
            if method is None:
                raise VyrelRuntimeError(
                    f"superclass '{superclass.name}' has no method "
                    f"'{expr.name}'",
                    line=expr.line, column=expr.column,
                )
            return _BoundMethod(method, obj.instance)

        if isinstance(obj, VyrelInstance):
            if expr.name in obj.fields:
                return obj.fields[expr.name]
            method = obj.cls.find_method(expr.name)
            if method is not None:
                return _BoundMethod(method, obj)
            raise VyrelRuntimeError(
                f"'{obj.cls.name}' has no attribute '{expr.name}'",
                line=expr.line, column=expr.column,
            )
        if isinstance(obj, VyrelModule):
            if expr.name in obj.attrs:
                return obj.attrs[expr.name]
            raise VyrelRuntimeError(
                f"module '{obj.name}' has no attribute '{expr.name}'",
                line=expr.line, column=expr.column,
            )
        if isinstance(obj, dict):
            if expr.name in obj:
                return obj[expr.name]
            raise VyrelRuntimeError(
                f"key '{expr.name}' not found in dict",
                line=expr.line, column=expr.column,
            )
        if hasattr(obj, expr.name):
            return getattr(obj, expr.name)
        raise VyrelRuntimeError(
            f"cannot read attribute '{expr.name}' from {_type_name(obj)}",
            line=expr.line, column=expr.column,
        )

    def _index(self, target: Any, index: Any, node: ast.Node) -> Any:
        try:
            return target[index]
        except (TypeError, KeyError, IndexError):
            raise VyrelRuntimeError(
                f"cannot index {_type_name(target)} with {_type_name(index)}",
                line=node.line, column=node.column,
            )

    def _eval_call(self, expr: ast.Call, env: Environment) -> Any:
        func = self._eval(expr.func, env)
        args = [self._eval(a, env) for a in expr.args]
        return self._call_value(func, args, expr.line, expr.column)

    def _call_value(
        self, func: Any, args: List[Any], line: int, column: int,
    ) -> Any:
        if isinstance(func, VyrelFunction):
            return self._call_function(func, args)
        if isinstance(func, VyrelLambda):
            return self._call_lambda(func, args)
        if isinstance(func, _BoundMethod):
            return self._call_function(func.fn, args, instance=func.instance)
        if isinstance(func, VyrelClass):
            return self._instantiate(func, args, line, column)
        if callable(func):
            try:
                return func(*args)
            except VyrelRuntimeError:
                raise
            except Exception as exc:
                # Stdlib functions raise StdlibError; convert to a Vyrel
                # runtime error carrying the call site's position.
                try:
                    from .stdlib._util import StdlibError
                except Exception:
                    StdlibError = ()  # type: ignore
                if isinstance(exc, StdlibError):
                    raise VyrelRuntimeError(
                        str(exc), line=line, column=column,
                    ) from None
                raise
        raise VyrelRuntimeError(
            f"{_type_name(func)} is not callable",
            line=line, column=column,
        )

    def _instantiate(
        self, cls: VyrelClass, args: List[Any], line: int, column: int,
    ) -> Any:
        inst = VyrelInstance(cls)
        init = cls.find_method("init")
        if init is not None:
            self._call_function(init, args, instance=inst)
        elif args:
            raise VyrelRuntimeError(
                f"class '{cls.name}' has no init() but was called with "
                f"{len(args)} argument(s)",
                line=line, column=column,
            )
        return inst

    def _call_function(
        self,
        fn: VyrelFunction,
        args: List[Any],
        instance: Optional[VyrelInstance] = None,
    ) -> Any:
        self._depth += 1
        if self._depth > self.MAX_CALL_DEPTH:
            self._depth -= 1
            raise VyrelRuntimeError(
                f"maximum call depth ({self.MAX_CALL_DEPTH}) exceeded",
            )
        try:
            frame = Environment(fn.closure, name=fn.name)
            if instance is not None:
                frame.define("self", instance)
                if instance.cls.superclass is not None:
                    frame.define("super", _SuperProxy(instance))
            self._bind_params(frame, fn.params, args, fn.name)
            try:
                self._exec_block(fn.body, frame)
            except _ReturnSignal as r:
                return r.value
            return None
        finally:
            self._depth -= 1

    def _call_lambda(self, fn: VyrelLambda, args: List[Any]) -> Any:
        self._depth += 1
        if self._depth > self.MAX_CALL_DEPTH:
            self._depth -= 1
            raise VyrelRuntimeError(
                f"maximum call depth ({self.MAX_CALL_DEPTH}) exceeded",
            )
        try:
            frame = Environment(fn.closure, name=fn.name)
            self._bind_params(frame, fn.params, args, fn.name)
            return self._eval(fn.body, frame)
        finally:
            self._depth -= 1

    def _bind_params(
        self,
        frame: Environment,
        params: Tuple[ast.Param, ...],
        args: List[Any],
        fn_name: str,
    ) -> None:
        if len(args) > len(params):
            raise VyrelRuntimeError(
                f"function '{fn_name}' expects {len(params)} argument(s), "
                f"got {len(args)}",
            )
        for i, p in enumerate(params):
            if i < len(args):
                frame.define(p.name, args[i])
            elif p.default is not None:
                frame.define(
                    p.name,
                    self._eval(p.default, frame.parent or self.globals),
                )
            else:
                raise VyrelRuntimeError(
                    f"function '{fn_name}' is missing argument '{p.name}'",
                )

    def _eval_binary(self, expr: ast.BinaryOp, env: Environment) -> Any:
        op = expr.op

        if op == "and":
            left = self._eval(expr.left, env)
            if not _truthy(left):
                return left
            return self._eval(expr.right, env)
        if op == "or":
            left = self._eval(expr.left, env)
            if _truthy(left):
                return left
            return self._eval(expr.right, env)

        left = self._eval(expr.left, env)
        right = self._eval(expr.right, env)
        return self._apply_binop(op, left, right, expr.line, expr.column)

    def _apply_binop(
        self, op: str, left: Any, right: Any, line: int, column: int,
    ) -> Any:
        if op == "+":
            if isinstance(left, str) and isinstance(right, str):
                return left + right
            if _is_number(left) and _is_number(right):
                return left + right
            if isinstance(left, list) and isinstance(right, list):
                return left + right
            raise VyrelRuntimeError(
                f"cannot add a {_type_name(left)} and a {_type_name(right)}",
                line=line, column=column,
            )

        if op == "-":
            if _is_number(left) and _is_number(right):
                return left - right
            raise VyrelRuntimeError(
                f"cannot subtract a {_type_name(right)} from a "
                f"{_type_name(left)}",
                line=line, column=column,
            )

        if op == "*":
            if _is_number(left) and _is_number(right):
                return left * right
            if isinstance(left, str) and isinstance(right, int):
                return left * right
            if isinstance(left, int) and isinstance(right, str):
                return left * right
            raise VyrelRuntimeError(
                f"cannot multiply a {_type_name(left)} by a "
                f"{_type_name(right)}",
                line=line, column=column,
            )

        if op == "/":
            if _is_number(left) and _is_number(right):
                if right == 0:
                    raise VyrelRuntimeError(
                        "cannot divide by zero",
                        line=line, column=column,
                    )
                return left / right
            raise VyrelRuntimeError(
                f"cannot divide a {_type_name(left)} by a "
                f"{_type_name(right)}",
                line=line, column=column,
            )

        if op == "//":
            if _is_number(left) and _is_number(right):
                if right == 0:
                    raise VyrelRuntimeError(
                        "cannot divide by zero",
                        line=line, column=column,
                    )
                return left // right
            raise VyrelRuntimeError(
                f"cannot divide a {_type_name(left)} by a "
                f"{_type_name(right)}",
                line=line, column=column,
            )

        if op == "%":
            if _is_number(left) and _is_number(right):
                if right == 0:
                    raise VyrelRuntimeError(
                        "cannot modulo by zero",
                        line=line, column=column,
                    )
                return left % right
            raise VyrelRuntimeError(
                f"cannot compute {_type_name(left)} % {_type_name(right)}",
                line=line, column=column,
            )

        if op == "**":
            if _is_number(left) and _is_number(right):
                return left ** right
            raise VyrelRuntimeError(
                f"cannot raise a {_type_name(left)} to a {_type_name(right)}",
                line=line, column=column,
            )

        if op == "==":
            return _eq(left, right)
        if op == "!=":
            return not _eq(left, right)
        if op == "<":
            try:
                return left < right
            except TypeError:
                raise VyrelRuntimeError(
                    f"cannot compare {_type_name(left)} and "
                    f"{_type_name(right)} with '<'",
                    line=line, column=column,
                )
        if op == "<=":
            try:
                return left <= right
            except TypeError:
                raise VyrelRuntimeError(
                    f"cannot compare {_type_name(left)} and "
                    f"{_type_name(right)} with '<='",
                    line=line, column=column,
                )
        if op == ">":
            try:
                return left > right
            except TypeError:
                raise VyrelRuntimeError(
                    f"cannot compare {_type_name(left)} and "
                    f"{_type_name(right)} with '>'",
                    line=line, column=column,
                )
        if op == ">=":
            try:
                return left >= right
            except TypeError:
                raise VyrelRuntimeError(
                    f"cannot compare {_type_name(left)} and "
                    f"{_type_name(right)} with '>='",
                    line=line, column=column,
                )
        if op == "in":
            try:
                return left in right
            except TypeError:
                raise VyrelRuntimeError(
                    f"cannot check if a {_type_name(left)} is in a "
                    f"{_type_name(right)}",
                    line=line, column=column,
                )

        raise VyrelRuntimeError(
            f"internal: unknown operator {op!r}",
            line=line, column=column,
        )

    # ------------------------------------------------------------------ #
    # Stdlib registry                                                    #
    # ------------------------------------------------------------------ #

    def _load_builtin_module(
        self, name: str, line: int, column: int,
    ) -> VyrelModule:
        from . import stdlib as _stdlib

        def _call_fn(fn_value: Any, args: list) -> Any:
            return self._call_value(fn_value, args, line, column)

        attrs = _stdlib.load_module(name, call_fn=_call_fn)
        if attrs is None:
            raise VyrelRuntimeError(
                f"unknown module '{name}'",
                line=line, column=column,
            )
        return VyrelModule(name, attrs)
