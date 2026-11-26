"""Recursive-descent parser for Vyrel.

Consumes the token list produced by :class:`vyrel.lexer.Lexer` and produces an
AST of :mod:`vyrel.ast_nodes` nodes.  Follows the EBNF in spec section 2,
using precedence-climbing for binary operators.

Design choices documented in ``docs/DECISIONS.md``:

* ``fn(x) => expr`` (arrow form) is valid anywhere an expression is allowed.
* Block-form ``fn … end`` is valid only as a declaration; a block-form
  function used as a *value* is not yet supported (see DECISIONS).
* Binary operator precedence (high to low):
    **  (right-assoc)
    unary - not
    * / // %
    + -
    == != < <= > >= in
    and
    or
* ``match`` arms use ``then`` (per the quick reference), not ``=>``.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from . import ast_nodes as ast
from .errors import VyrelError
from .lexer import Lexer
from .tokens import InterpPart, Token, TokenType


class ParseError(VyrelError):
    """Raised by the parser for malformed programs."""

    kind = "Syntax error"


# --------------------------------------------------------------------------- #
# Small helpers                                                               #
# --------------------------------------------------------------------------- #


def _is_kw(tok: Token, text: str) -> bool:
    return tok.type is TokenType.KEYWORD and tok.value == text


class Parser:
    """Recursive-descent parser.

    Usage::

        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse_program()
    """

    def __init__(self, tokens: List[Token]) -> None:
        self.tokens = tokens
        self.pos = 0
        # Tracks whether a block-form ``fn`` is currently allowed.  Reserved
        # for future use; Phase 2 rejects block-form fn-as-value entirely.
        self._allow_block_fn = False

    # ------------------------------------------------------------------ #
    # Token cursor                                                       #
    # ------------------------------------------------------------------ #

    def _peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx >= len(self.tokens):
            return self.tokens[-1]  # EOF
        return self.tokens[idx]

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.type is not TokenType.EOF:
            self.pos += 1
        return tok

    def _check(self, tt: TokenType) -> bool:
        return self._peek().type is tt

    def _check_kw(self, text: str) -> bool:
        return _is_kw(self._peek(), text)

    def _match(self, tt: TokenType) -> Optional[Token]:
        if self._check(tt):
            return self._advance()
        return None

    def _match_kw(self, text: str) -> Optional[Token]:
        if self._check_kw(text):
            return self._advance()
        return None

    def _expect(self, tt: TokenType, what: str) -> Token:
        tok = self._peek()
        if tok.type is not tt:
            raise ParseError(
                f"expected {what}, found {self._describe(tok)}",
                line=tok.line, column=tok.column,
            )
        return self._advance()

    def _expect_kw(self, text: str) -> Token:
        tok = self._peek()
        if not _is_kw(tok, text):
            raise ParseError(
                f"expected '{text}', found {self._describe(tok)}",
                line=tok.line, column=tok.column,
            )
        return self._advance()

    @staticmethod
    def _describe(tok: Token) -> str:
        if tok.type is TokenType.EOF:
            return "end of file"
        if tok.type is TokenType.NEWLINE:
            return "end of line"
        if tok.type is TokenType.KEYWORD:
            return f"'{tok.value}'"
        if tok.text:
            return f"'{tok.text}'"
        return tok.type.name.lower()

    # ------------------------------------------------------------------ #
    # Statement-level newline handling                                   #
    # ------------------------------------------------------------------ #

    def _skip_newlines(self) -> None:
        while self._check(TokenType.NEWLINE):
            self._advance()

    def _at_block_end(self) -> bool:
        return self._check(TokenType.EOF) or self._check_kw("end") \
            or self._check_kw("elif") or self._check_kw("else") \
            or self._check_kw("catch") or self._check_kw("finally") \
            or self._check_kw("case")

    def _parse_block(self) -> Tuple[ast.Stmt, ...]:
        """Parse statements until a block terminator (``end``/``elif``/...)."""
        stmts: List[ast.Stmt] = []
        self._skip_newlines()
        while not self._at_block_end():
            stmts.append(self._parse_statement())
            self._skip_newlines()
        return tuple(stmts)

    # ------------------------------------------------------------------ #
    # Top level                                                          #
    # ------------------------------------------------------------------ #

    def parse_program(self) -> ast.Program:
        start = self._peek()
        body: List[ast.Stmt] = []
        self._skip_newlines()
        while not self._check(TokenType.EOF):
            body.append(self._parse_statement())
            self._skip_newlines()
        return ast.Program(body=tuple(body), line=start.line, column=start.column)

    # ------------------------------------------------------------------ #
    # Statements                                                         #
    # ------------------------------------------------------------------ #

    def _parse_statement(self) -> ast.Stmt:
        tok = self._peek()

        if tok.type is TokenType.KEYWORD:
            kw = tok.value
            if kw in ("let", "const"):
                return self._parse_let()
            if kw == "return":
                return self._parse_return()
            if kw == "break":
                self._advance()
                return ast.BreakStmt(line=tok.line, column=tok.column)
            if kw == "continue":
                self._advance()
                return ast.ContinueStmt(line=tok.line, column=tok.column)
            if kw == "if":
                return self._parse_if()
            if kw == "while":
                return self._parse_while()
            if kw == "for":
                return self._parse_for()
            if kw == "throw":
                self._advance()
                val = self._parse_expr()
                return ast.ThrowStmt(value=val, line=tok.line, column=tok.column)
            if kw == "try":
                return self._parse_try()
            if kw == "match":
                return self._parse_match()
            if kw == "fn":
                return self._parse_function_decl()
            if kw == "class":
                return self._parse_class_decl()
            if kw == "import":
                return self._parse_import()
            if kw == "from":
                return self._parse_from_import()
            # Fall through to expression statement for keyword-led expression.

        # Try simple/compound assignment: IDENT/Attr/Index followed by '=' or
        # compound-assign.  Parse an expression then check the next token.
        expr = self._parse_expr()
        nxt = self._peek()
        if nxt.type in (
            TokenType.ASSIGN, TokenType.PLUS_ASSIGN, TokenType.MINUS_ASSIGN,
            TokenType.STAR_ASSIGN, TokenType.SLASH_ASSIGN,
            TokenType.PERCENT_ASSIGN,
        ):
            op_map = {
                TokenType.ASSIGN: "=",
                TokenType.PLUS_ASSIGN: "+=",
                TokenType.MINUS_ASSIGN: "-=",
                TokenType.STAR_ASSIGN: "*=",
                TokenType.SLASH_ASSIGN: "/=",
                TokenType.PERCENT_ASSIGN: "%=",
            }
            if not isinstance(expr, (ast.Ident, ast.Index, ast.Attr)):
                raise ParseError(
                    "cannot assign to this expression",
                    line=nxt.line, column=nxt.column,
                )
            self._advance()
            value = self._parse_expr()
            return ast.AssignStmt(
                target=expr, op=op_map[nxt.type], value=value,
                line=expr.line, column=expr.column,
            )
        return ast.ExprStmt(expr=expr, line=expr.line, column=expr.column)

    def _parse_let(self) -> ast.LetStmt:
        kw_tok = self._advance()
        is_const = kw_tok.value == "const"
        name_tok = self._expect(TokenType.IDENT, "a variable name")
        self._expect(TokenType.ASSIGN, "'='")
        value = self._parse_expr()
        return ast.LetStmt(
            name=name_tok.value, value=value, is_const=is_const,
            line=kw_tok.line, column=kw_tok.column,
        )

    def _parse_return(self) -> ast.ReturnStmt:
        kw_tok = self._advance()
        if self._check(TokenType.NEWLINE) or self._check(TokenType.EOF) \
                or self._at_block_end():
            return ast.ReturnStmt(value=None, line=kw_tok.line, column=kw_tok.column)
        val = self._parse_expr()
        return ast.ReturnStmt(value=val, line=kw_tok.line, column=kw_tok.column)

    def _parse_if(self) -> ast.IfStmt:
        kw_tok = self._advance()
        branches: List[Tuple[ast.Expr, Tuple[ast.Stmt, ...]]] = []
        cond = self._parse_expr()
        self._expect_kw("then")
        body = self._parse_block()
        branches.append((cond, body))
        while self._check_kw("elif"):
            self._advance()
            c = self._parse_expr()
            self._expect_kw("then")
            b = self._parse_block()
            branches.append((c, b))
        else_body: Tuple[ast.Stmt, ...] = ()
        if self._check_kw("else"):
            self._advance()
            else_body = self._parse_block()
        self._expect_kw("end")
        return ast.IfStmt(
            branches=tuple(branches), else_body=else_body,
            line=kw_tok.line, column=kw_tok.column,
        )

    def _parse_while(self) -> ast.WhileStmt:
        kw_tok = self._advance()
        cond = self._parse_expr()
        self._expect_kw("do")
        body = self._parse_block()
        self._expect_kw("end")
        return ast.WhileStmt(
            condition=cond, body=body,
            line=kw_tok.line, column=kw_tok.column,
        )

    def _parse_for(self) -> ast.ForStmt:
        kw_tok = self._advance()
        first = self._expect(TokenType.IDENT, "a loop variable name")
        key_name: Optional[str] = None
        value_name = first.value
        if self._match(TokenType.COMMA):
            key_name = first.value
            second = self._expect(TokenType.IDENT, "a second loop variable")
            value_name = second.value
        self._expect_kw("in")
        it = self._parse_expr()
        self._expect_kw("do")
        body = self._parse_block()
        self._expect_kw("end")
        return ast.ForStmt(
            key_name=key_name, value_name=value_name, iterable=it, body=body,
            line=kw_tok.line, column=kw_tok.column,
        )

    def _parse_try(self) -> ast.TryStmt:
        kw_tok = self._advance()
        body = self._parse_block()
        catch_name: Optional[str] = None
        catch_body: Tuple[ast.Stmt, ...] = ()
        if self._check_kw("catch"):
            self._advance()
            name_tok = self._expect(TokenType.IDENT, "an error variable name")
            catch_name = name_tok.value
            catch_body = self._parse_block()
        finally_body: Tuple[ast.Stmt, ...] = ()
        if self._check_kw("finally"):
            self._advance()
            finally_body = self._parse_block()
        self._expect_kw("end")
        if catch_name is None and not finally_body:
            raise ParseError(
                "a 'try' block needs at least a 'catch' or a 'finally'",
                line=kw_tok.line, column=kw_tok.column,
            )
        return ast.TryStmt(
            body=body, catch_name=catch_name, catch_body=catch_body,
            finally_body=finally_body,
            line=kw_tok.line, column=kw_tok.column,
        )

    def _parse_match(self) -> ast.MatchStmt:
        kw_tok = self._advance()
        subject = self._parse_expr()
        self._skip_newlines()
        arms: List[ast.MatchArm] = []
        else_body: Tuple[ast.Stmt, ...] = ()
        while self._check_kw("case"):
            case_tok = self._advance()
            patterns: List[object] = []
            while True:
                patterns.append(self._parse_pattern_literal())
                if not self._match(TokenType.COMMA):
                    break
            self._expect_kw("then")
            body = self._parse_block()
            arms.append(ast.MatchArm(
                patterns=tuple(patterns), body=body,
                line=case_tok.line, column=case_tok.column,
            ))
            self._skip_newlines()
        if self._check_kw("else"):
            self._advance()
            else_body = self._parse_block()
            self._skip_newlines()
        self._expect_kw("end")
        if not arms:
            raise ParseError(
                "'match' needs at least one 'case'",
                line=kw_tok.line, column=kw_tok.column,
            )
        return ast.MatchStmt(
            subject=subject, arms=tuple(arms), else_body=else_body,
            line=kw_tok.line, column=kw_tok.column,
        )

    def _parse_pattern_literal(self) -> object:
        """Match patterns are literal values only (int/float/str/bool/nil)."""
        tok = self._peek()
        if tok.type is TokenType.INT or tok.type is TokenType.FLOAT:
            self._advance()
            return tok.value
        if tok.type is TokenType.STRING:
            self._advance()
            return tok.value
        if _is_kw(tok, "true"):
            self._advance()
            return True
        if _is_kw(tok, "false"):
            self._advance()
            return False
        if _is_kw(tok, "nil"):
            self._advance()
            return None
        raise ParseError(
            "expected a literal value (number, string, true, false, nil)",
            line=tok.line, column=tok.column,
        )

    def _parse_function_decl(self) -> ast.FunctionDecl:
        fn_tok = self._advance()
        name_tok = self._expect(TokenType.IDENT, "a function name")
        params = self._parse_params()
        body = self._parse_block()
        self._expect_kw("end")
        return ast.FunctionDecl(
            name=name_tok.value, params=params, body=body,
            line=fn_tok.line, column=fn_tok.column,
        )

    def _parse_class_decl(self) -> ast.ClassDecl:
        cls_tok = self._advance()
        name_tok = self._expect(TokenType.IDENT, "a class name")
        superclass: Optional[str] = None
        if self._match_kw("extends"):
            sup_tok = self._expect(TokenType.IDENT, "a superclass name")
            superclass = sup_tok.value
        self._skip_newlines()
        methods: List[ast.FunctionDecl] = []
        while not self._check_kw("end") and not self._check(TokenType.EOF):
            if not self._check_kw("fn"):
                tok = self._peek()
                raise ParseError(
                    "expected 'fn' (a method declaration) or 'end'",
                    line=tok.line, column=tok.column,
                )
            methods.append(self._parse_function_decl())
            self._skip_newlines()
        self._expect_kw("end")
        return ast.ClassDecl(
            name=name_tok.value, superclass=superclass, methods=tuple(methods),
            line=cls_tok.line, column=cls_tok.column,
        )

    def _parse_import(self) -> ast.ImportStmt:
        import_tok = self._advance()
        tok = self._peek()
        if tok.type is TokenType.IDENT:
            self._advance()
            module = tok.value
            is_file = False
        elif tok.type is TokenType.STRING:
            self._advance()
            module = tok.value
            is_file = True
        else:
            raise ParseError(
                "expected a module name or a file path after 'import'",
                line=tok.line, column=tok.column,
            )
        alias: Optional[str] = None
        if self._match_kw("as"):
            alias_tok = self._expect(TokenType.IDENT, "an alias name")
            alias = alias_tok.value
        return ast.ImportStmt(
            module=module, is_file=is_file, alias=alias,
            line=import_tok.line, column=import_tok.column,
        )

    def _parse_from_import(self) -> ast.FromImportStmt:
        from_tok = self._advance()
        tok = self._peek()
        if tok.type is TokenType.IDENT:
            self._advance()
            module = tok.value
            is_file = False
        elif tok.type is TokenType.STRING:
            self._advance()
            module = tok.value
            is_file = True
        else:
            raise ParseError(
                "expected a module name or a file path after 'from'",
                line=tok.line, column=tok.column,
            )
        self._expect_kw("import")
        names: List[Tuple[str, Optional[str]]] = []
        while True:
            name_tok = self._expect(TokenType.IDENT, "an imported name")
            alias: Optional[str] = None
            if self._match_kw("as"):
                alias_tok = self._expect(TokenType.IDENT, "an alias name")
                alias = alias_tok.value
            names.append((name_tok.value, alias))
            if not self._match(TokenType.COMMA):
                break
        return ast.FromImportStmt(
            module=module, is_file=is_file, names=tuple(names),
            line=from_tok.line, column=from_tok.column,
        )

    # ------------------------------------------------------------------ #
    # Parameters                                                         #
    # ------------------------------------------------------------------ #

    def _parse_params(self) -> Tuple[ast.Param, ...]:
        self._expect(TokenType.LPAREN, "'('")
        params: List[ast.Param] = []
        if not self._check(TokenType.RPAREN):
            while True:
                name_tok = self._expect(TokenType.IDENT, "a parameter name")
                default: Optional[ast.Expr] = None
                if self._match(TokenType.ASSIGN):
                    default = self._parse_expr()
                params.append(ast.Param(
                    name=name_tok.value, default=default,
                    line=name_tok.line, column=name_tok.column,
                ))
                if not self._match(TokenType.COMMA):
                    break
        self._expect(TokenType.RPAREN, "')'")
        return tuple(params)

    # ------------------------------------------------------------------ #
    # Expressions — precedence-climbing                                  #
    # ------------------------------------------------------------------ #

    def _parse_expr(self) -> ast.Expr:
        return self._parse_or()

    def _parse_or(self) -> ast.Expr:
        left = self._parse_and()
        while self._check_kw("or"):
            tok = self._advance()
            right = self._parse_and()
            left = ast.BinaryOp(
                op="or", left=left, right=right,
                line=tok.line, column=tok.column,
            )
        return left

    def _parse_and(self) -> ast.Expr:
        left = self._parse_not()
        while self._check_kw("and"):
            tok = self._advance()
            right = self._parse_not()
            left = ast.BinaryOp(
                op="and", left=left, right=right,
                line=tok.line, column=tok.column,
            )
        return left

    def _parse_not(self) -> ast.Expr:
        if self._check_kw("not"):
            tok = self._advance()
            operand = self._parse_not()
            return ast.UnaryOp(
                op="not", operand=operand,
                line=tok.line, column=tok.column,
            )
        return self._parse_comparison()

    _COMPARISON_TYPES = {
        TokenType.EQ: "==",
        TokenType.NOT_EQ: "!=",
        TokenType.LT: "<",
        TokenType.LE: "<=",
        TokenType.GT: ">",
        TokenType.GE: ">=",
    }

    def _parse_comparison(self) -> ast.Expr:
        left = self._parse_additive()
        while True:
            tok = self._peek()
            if tok.type in self._COMPARISON_TYPES:
                self._advance()
                op = self._COMPARISON_TYPES[tok.type]
                right = self._parse_additive()
                left = ast.BinaryOp(
                    op=op, left=left, right=right,
                    line=tok.line, column=tok.column,
                )
            elif _is_kw(tok, "in"):
                self._advance()
                right = self._parse_additive()
                left = ast.BinaryOp(
                    op="in", left=left, right=right,
                    line=tok.line, column=tok.column,
                )
            else:
                break
        return left

    def _parse_additive(self) -> ast.Expr:
        left = self._parse_multiplicative()
        while self._check(TokenType.PLUS) or self._check(TokenType.MINUS):
            tok = self._advance()
            op = "+" if tok.type is TokenType.PLUS else "-"
            right = self._parse_multiplicative()
            left = ast.BinaryOp(
                op=op, left=left, right=right,
                line=tok.line, column=tok.column,
            )
        return left

    def _parse_multiplicative(self) -> ast.Expr:
        left = self._parse_unary()
        while True:
            tok = self._peek()
            if tok.type in (TokenType.STAR, TokenType.SLASH,
                            TokenType.DOUBLE_SLASH, TokenType.PERCENT):
                self._advance()
                op_map = {
                    TokenType.STAR: "*",
                    TokenType.SLASH: "/",
                    TokenType.DOUBLE_SLASH: "//",
                    TokenType.PERCENT: "%",
                }
                right = self._parse_unary()
                left = ast.BinaryOp(
                    op=op_map[tok.type], left=left, right=right,
                    line=tok.line, column=tok.column,
                )
            else:
                break
        return left

    def _parse_unary(self) -> ast.Expr:
        if self._check(TokenType.MINUS):
            tok = self._advance()
            operand = self._parse_unary()
            return ast.UnaryOp(
                op="-", operand=operand,
                line=tok.line, column=tok.column,
            )
        return self._parse_power()

    def _parse_power(self) -> ast.Expr:
        # '**' is right-associative: a ** b ** c == a ** (b ** c).
        base = self._parse_postfix()
        if self._check(TokenType.DOUBLE_STAR):
            tok = self._advance()
            exponent = self._parse_unary()  # right-assoc + allow -exp
            return ast.BinaryOp(
                op="**", left=base, right=exponent,
                line=tok.line, column=tok.column,
            )
        return base

    def _parse_postfix(self) -> ast.Expr:
        expr = self._parse_primary()
        while True:
            tok = self._peek()
            if tok.type is TokenType.LPAREN:
                expr = self._parse_call(expr)
            elif tok.type is TokenType.LBRACKET:
                expr = self._parse_index_or_slice(expr)
            elif tok.type is TokenType.DOT:
                self._advance()
                name_tok = self._expect(TokenType.IDENT, "an attribute name")
                expr = ast.Attr(
                    target=expr, name=name_tok.value,
                    line=tok.line, column=tok.column,
                )
            else:
                break
        return expr

    def _parse_call(self, func: ast.Expr) -> ast.Call:
        lp = self._expect(TokenType.LPAREN, "'('")
        args: List[ast.Expr] = []
        if not self._check(TokenType.RPAREN):
            while True:
                args.append(self._parse_expr())
                if not self._match(TokenType.COMMA):
                    break
                if self._check(TokenType.RPAREN):
                    break
        self._expect(TokenType.RPAREN, "')'")
        return ast.Call(
            func=func, args=tuple(args),
            line=lp.line, column=lp.column,
        )

    def _parse_index_or_slice(self, target: ast.Expr) -> ast.Expr:
        lb = self._expect(TokenType.LBRACKET, "'['")
        lower: Optional[ast.Expr] = None
        if not self._check(TokenType.COLON):
            lower = self._parse_expr()
        if self._match(TokenType.COLON):
            upper: Optional[ast.Expr] = None
            if not self._check(TokenType.RBRACKET):
                upper = self._parse_expr()
            self._expect(TokenType.RBRACKET, "']'")
            return ast.Slice(
                target=target, lower=lower, upper=upper,
                line=lb.line, column=lb.column,
            )
        if lower is None:
            raise ParseError(
                "empty index '[]' is not allowed",
                line=lb.line, column=lb.column,
            )
        self._expect(TokenType.RBRACKET, "']'")
        return ast.Index(
            target=target, index=lower,
            line=lb.line, column=lb.column,
        )

    def _parse_primary(self) -> ast.Expr:
        tok = self._peek()

        # Literals ---------------------------------------------------
        if tok.type is TokenType.INT:
            self._advance()
            return ast.IntLit(value=tok.value, line=tok.line, column=tok.column)
        if tok.type is TokenType.FLOAT:
            self._advance()
            return ast.FloatLit(value=tok.value, line=tok.line, column=tok.column)
        if tok.type is TokenType.STRING:
            self._advance()
            return ast.StringLit(value=tok.value, line=tok.line, column=tok.column)
        if tok.type is TokenType.TEMPLATE:
            self._advance()
            return self._build_template(tok)

        # Keyword literals ------------------------------------------
        if _is_kw(tok, "true"):
            self._advance()
            return ast.BoolLit(value=True, line=tok.line, column=tok.column)
        if _is_kw(tok, "false"):
            self._advance()
            return ast.BoolLit(value=False, line=tok.line, column=tok.column)
        if _is_kw(tok, "nil"):
            self._advance()
            return ast.NilLit(line=tok.line, column=tok.column)
        if _is_kw(tok, "self"):
            self._advance()
            return ast.SelfExpr(line=tok.line, column=tok.column)

        # Identifiers ------------------------------------------------
        if tok.type is TokenType.IDENT:
            self._advance()
            return ast.Ident(name=tok.value, line=tok.line, column=tok.column)

        # Grouping ---------------------------------------------------
        if tok.type is TokenType.LPAREN:
            self._advance()
            inner = self._parse_expr()
            self._expect(TokenType.RPAREN, "')'")
            return inner

        # List literal -----------------------------------------------
        if tok.type is TokenType.LBRACKET:
            return self._parse_list_literal()

        # Dict literal -----------------------------------------------
        if tok.type is TokenType.LBRACE:
            return self._parse_dict_literal()

        # Lambda (arrow form) ----------------------------------------
        if _is_kw(tok, "fn"):
            return self._parse_fn_expr()

        raise ParseError(
            f"unexpected {self._describe(tok)}",
            line=tok.line, column=tok.column,
        )

    def _build_template(self, tok: Token) -> ast.TemplateExpr:
        """Convert a TEMPLATE token's InterpPart entries into Expr nodes."""
        parts: List[object] = []
        for item in tok.value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, InterpPart):
                inner_tokens = Lexer(item.text).tokenize()
                sub = Parser(inner_tokens)
                expr = sub._parse_expr()
                sub._skip_newlines()
                if not sub._check(TokenType.EOF):
                    raise ParseError(
                        f"unexpected {sub._describe(sub._peek())} "
                        f"in template interpolation",
                        line=item.line, column=item.column,
                    )
                parts.append(expr)
            else:  # pragma: no cover - defensive
                raise ParseError(
                    "internal: malformed template part",
                    line=tok.line, column=tok.column,
                )
        return ast.TemplateExpr(
            parts=tuple(parts), line=tok.line, column=tok.column,
        )

    def _parse_list_literal(self) -> ast.ListLit:
        lb = self._advance()
        items: List[ast.Expr] = []
        if not self._check(TokenType.RBRACKET):
            while True:
                items.append(self._parse_expr())
                if not self._match(TokenType.COMMA):
                    break
                if self._check(TokenType.RBRACKET):
                    break
        self._expect(TokenType.RBRACKET, "']'")
        return ast.ListLit(items=tuple(items), line=lb.line, column=lb.column)

    def _parse_dict_literal(self) -> ast.DictLit:
        lb = self._advance()
        entries: List[Tuple[ast.Expr, ast.Expr]] = []
        if not self._check(TokenType.RBRACE):
            while True:
                key = self._parse_expr()
                self._expect(TokenType.COLON, "':'")
                val = self._parse_expr()
                entries.append((key, val))
                if not self._match(TokenType.COMMA):
                    break
                if self._check(TokenType.RBRACE):
                    break
        self._expect(TokenType.RBRACE, "'}'")
        return ast.DictLit(entries=tuple(entries), line=lb.line, column=lb.column)

    def _parse_fn_expr(self) -> ast.Expr:
        """Parse ``fn(params) => expr``.  Block-form ``fn … end`` as a value
        is not supported in Phase 2 (see DECISIONS.md)."""
        fn_tok = self._advance()
        params = self._parse_params()

        if self._check(TokenType.ARROW):
            self._advance()
            body = self._parse_expr()
            return ast.Lambda(
                params=params, body=body,
                line=fn_tok.line, column=fn_tok.column,
            )

        raise ParseError(
            "block-form 'fn ... end' as a value is not yet supported; use "
            "'fn(...) => expr' or a top-level 'fn name(...) ... end'",
            line=fn_tok.line, column=fn_tok.column,
        )


def parse(source: str) -> ast.Program:
    """Convenience: lex + parse a full source string."""
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse_program()
