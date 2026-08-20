"""Phase 2 — syntax analysis: recursive descent over the course grammar.

One method per grammar production, named after the course EBNF rules
(``parse_boolexpression``, ``parse_term``, ...).  The
:class:`~..versions.LanguageLevel` gates which productions exist, so the
same parser serves every stage and its diagnostics match what that stage's
reference compiler prints — including the reference's context-sensitive
message quirks (e.g. a missing ``}`` reports ``Missing CLOSE_BRA`` in an
``if`` block but ``Unexpected token EOF`` in a ``while`` block), which are
reproduced deliberately: the corpus is the oracle.

Error handling is panic-mode at its purest: the first violation aborts the
parse (course compilers stop at the first diagnostic).  The resulting
:class:`~..diagnostics.ParseDefect` keeps the whole token stream and the
index of the offending token, so backends can re-emit the program
token-faithfully with the native defect at the equivalent position.
"""

from __future__ import annotations

from ..diagnostics import ErrorCategory as C, ParseDefect
from ..lexical.tokens import Token, TokenKind as K
from ..versions import LanguageLevel
from . import ast


class ParseError(Exception):
    def __init__(self, defect: ParseDefect):
        super().__init__(defect.message)
        self.defect = defect


class Parser:
    def __init__(self, tokens: list[Token], level: LanguageLevel):
        self.tokens = tokens
        self.level = level
        self.pos = 0

    # -- token helpers -----------------------------------------------------
    @property
    def cur(self) -> Token:
        return self.tokens[self.pos]

    def at(self, *kinds: K) -> bool:
        return self.cur.kind in kinds

    def advance(self) -> Token:
        tok = self.cur
        if tok.kind is not K.EOF:
            self.pos += 1
        return tok

    # -- diagnostics -------------------------------------------------------
    def _fail(self, message: str, category: C = C.PARSE_UNEXPECTED_TOKEN,
              token: Token | None = None) -> ParseError:
        tok = token or self.cur
        tag = f"{category.phase_tag} " if self.level.bracket_tags else ""
        return ParseError(ParseDefect(
            category=category,
            message=f"{tag}{message}",
            line=tok.line, col=tok.col,
            found=tok,
            tail_tokens=self.tokens,
        ))

    def unexpected(self, expected: str | None = None,
                   token: Token | None = None) -> ParseError:
        tok = token or self.cur
        kind = "IDEN" if getattr(tok, "malformed", False) else str(tok.kind)
        suffix = f" (expected {expected})" if expected else ""
        return self._fail(f"Unexpected token {kind}{suffix}", token=tok)

    def missing(self, what: str) -> ParseError:
        return self._fail(f"Missing {what}", category=C.PARSE_MISSING_TOKEN)

    def _check_malformed(self) -> None:
        if getattr(self.cur, "malformed", False):
            raise self.unexpected()

    def _skip_newlines(self) -> None:
        while self.cur.kind is K.NEWLINE:
            self.advance()

    # -- entry -------------------------------------------------------------
    def parse(self) -> ast.Program:
        try:
            if self.level.expr_mode:
                return self._parse_expression_program()
            return self._parse_program()
        except ParseError as err:
            err.defect.error_index = min(self.pos, len(self.tokens) - 1)
            return ast.Program(defect=err.defect, expr_mode=self.level.expr_mode)

    # ======================================================================
    # Expression mode (v0.0 - v1.2, x1.x): the source is one expression
    # ======================================================================
    def _parse_expression_program(self) -> ast.Program:
        if self.level.expected_int_style:
            expr = self._parse_sum_of_ints()
            if not self.at(K.EOF):
                raise self.unexpected(expected="EOF")
        else:
            expr = self.parse_expression()
            if not self.at(K.EOF):
                raise self.unexpected()
        return ast.Program(items=[expr], expr_mode=True)

    def _parse_sum_of_ints(self) -> ast.Node:
        """v0.0/v1.0/x1.0 grammar: INT {(+|-) INT}, xor binding tighter."""
        node = self._parse_int_term()
        while self.at(K.PLUS, K.MINUS):
            op = self.advance()
            right = self._parse_int_term()
            node = ast.BinOp(op=op.lexeme, left=node, right=right,
                             line=op.line, col=op.col)
        return node

    def _parse_int_term(self) -> ast.Node:
        node = self._parse_int_literal()
        while self.level.xor and self.at(K.XOR):
            op = self.advance()
            right = self._parse_int_literal()
            node = ast.BinOp(op="^", left=node, right=right,
                             line=op.line, col=op.col)
        return node

    def _parse_int_literal(self) -> ast.Node:
        if not self.at(K.INT):
            raise self.unexpected(expected="INT")
        tok = self.advance()
        return ast.IntLit(value=int(tok.lexeme), line=tok.line, col=tok.col)

    # ======================================================================
    # Program mode (v2.0+)
    # ======================================================================
    def _parse_program(self) -> ast.Program:
        items: list = []
        if self.level.functions:
            self._skip_newlines()
            while not self.at(K.EOF):
                items.append(self._parse_top_declaration())
                self._skip_newlines()
        else:
            self._skip_newlines()
            while not self.at(K.EOF):
                if self.at(K.CLOSE_BRA):
                    raise self.unexpected(expected="EOF")
                items.append(self.parse_statement())
                self._skip_newlines()
        return ast.Program(items=items)

    # -- top level (v2.3+) -------------------------------------------------
    def _parse_top_declaration(self) -> ast.Node:
        self._check_malformed()
        if self.level.structs and self.at(K.STRUCT):
            return self._parse_struct_decl()
        if self.at(K.TYPE):
            return self._parse_func_or_global()
        if self.at(K.CLOSE_BRA):
            raise self.unexpected(expected="EOF")
        if self.at(K.IDEN):
            raise self._fail("Missing function type",
                             category=C.PARSE_MISSING_FUNC_TYPE)
        raise self.unexpected()

    def _parse_func_or_global(self) -> ast.Node:
        type_tok = self.advance()
        self._check_malformed()
        if not self.at(K.IDEN):
            raise self.unexpected()
        name_tok = self.advance()
        if self.at(K.OPEN_PAR):
            return self._parse_function(type_tok, name_tok)
        init = None
        if self.at(K.ASSIGN):
            self.advance()
            init = self.parse_bool_expression()
        self._expect_stmt_eol()
        return ast.VarDecl(var_type=type_tok.lexeme, name=name_tok.lexeme,
                           init=init, line=type_tok.line, col=type_tok.col)

    def _parse_function(self, type_tok: Token, name_tok: Token) -> ast.FuncDecl:
        self.advance()  # OPEN_PAR
        params: list = []
        if not self.at(K.CLOSE_PAR):
            params.append(self._parse_param())
            while self.at(K.COMMA):
                self.advance()
                params.append(self._parse_param())
        if not self.at(K.CLOSE_PAR):
            raise self.unexpected()
        self.advance()
        body = self._parse_block(ctx="braces")
        return ast.FuncDecl(ret_type=type_tok.lexeme, name=name_tok.lexeme,
                            params=params, body=body,
                            line=type_tok.line, col=type_tok.col)

    def _parse_param(self) -> ast.Param:
        if not self.at(K.TYPE):
            raise self.unexpected()
        type_tok = self.advance()
        self._check_malformed()
        if not self.at(K.IDEN):
            raise self.unexpected()
        name_tok = self.advance()
        return ast.Param(par_type=type_tok.lexeme, name=name_tok.lexeme,
                         line=type_tok.line, col=type_tok.col)

    def _parse_struct_decl(self) -> ast.StructDecl:
        struct_tok = self.advance()
        self._check_malformed()
        if not self.at(K.IDEN):
            raise self.unexpected()
        name_tok = self.advance()
        if not self.at(K.OPEN_BRA):
            raise self.unexpected()
        self.advance()
        fields: list = []
        self._skip_newlines()
        while self.at(K.TYPE):
            ftype = self.advance()
            self._check_malformed()
            if not self.at(K.IDEN):
                raise self.unexpected()
            fname = self.advance()
            if not self.at(K.EOL):
                self._raise_expected_eol()
            self.advance()
            fields.append(ast.StructField(field_type=ftype.lexeme,
                                          name=fname.lexeme,
                                          line=ftype.line, col=ftype.col))
            self._skip_newlines()
        if not self.at(K.CLOSE_BRA):
            raise self.unexpected()
        self.advance()
        if not self.at(K.EOL):
            self._raise_expected_eol()
        self.advance()
        return ast.StructDecl(name=name_tok.lexeme, fields=fields,
                              line=struct_tok.line, col=struct_tok.col)

    def _raise_expected_eol(self):
        # x2.3 reference phrases a missing ';' as "Unexpected token EOL"
        raise self._fail("Unexpected token EOL")

    # -- statements --------------------------------------------------------
    def parse_statement(self) -> ast.Node:
        self._check_malformed()
        tok = self.cur
        kind = tok.kind

        if kind is K.EOL or kind is K.NEWLINE:
            self.advance()
            return ast.NoOp(line=tok.line, col=tok.col)
        if kind is K.OPEN_BRA and self.level.blocks:
            return self._parse_block(ctx="braces", consume_open=True)
        if kind is K.IF:
            return self._parse_if()
        if kind is K.WHILE:
            return self._parse_while()
        if kind is K.FOR:
            return self._parse_for()
        if kind is K.ELSE:
            raise self._fail("Unexpected ELSE", category=C.PARSE_UNEXPECTED_ELSE)
        if kind is K.PRINT:
            return self._parse_printf()
        if kind is K.RETURN:
            return self._parse_return()
        if kind is K.TYPE:
            return self._parse_local_decl()
        if kind is K.STRUCT and self.level.structs:
            return self._parse_struct_var_decl()
        if kind is K.CONST and self.level.prepro:
            return self._parse_const_decl()
        if kind is K.IDEN:
            return self._parse_iden_statement()
        if kind is K.CLOSE_BRA:
            raise self.unexpected(expected="EOF")
        if self.level.prepro:
            # x2.0 reference falls back to an expression statement and then
            # phrases the failure as "Expected token EOL but found X"
            expr = self.parse_expression()
            if not self.at(K.EOL):
                raise self._fail(f"Expected token EOL but found {self.cur.kind}")
            self.advance()
            return ast.ExprStmt(expr=expr, line=tok.line, col=tok.col)
        raise self.unexpected()

    def _expect_stmt_eol(self) -> None:
        # a statement terminator is the ';' EOL specifically, not a NEWLINE
        if not self.at(K.EOL):
            raise self.unexpected()
        self.advance()

    def _parse_iden_statement(self) -> ast.Node:
        name_tok = self.advance()
        if self.at(K.ASSIGN):
            self.advance()
            expr = self.parse_bool_expression()
            self._expect_stmt_eol()
            return ast.Assign(
                target=ast.Ident(name=name_tok.lexeme,
                                 line=name_tok.line, col=name_tok.col),
                expr=expr, line=name_tok.line, col=name_tok.col)
        if self.at(K.DOT) and self.level.structs:
            self.advance()
            self._check_malformed()
            if not self.at(K.IDEN):
                raise self.unexpected()
            field_tok = self.advance()
            if not self.at(K.ASSIGN):
                raise self.unexpected()
            self.advance()
            expr = self.parse_bool_expression()
            self._expect_stmt_eol()
            target = ast.FieldAccess(
                obj=ast.Ident(name=name_tok.lexeme,
                              line=name_tok.line, col=name_tok.col),
                fieldname=field_tok.lexeme,
                line=name_tok.line, col=name_tok.col)
            return ast.Assign(target=target, expr=expr,
                              line=name_tok.line, col=name_tok.col)
        if self.at(K.OPEN_PAR) and self.level.functions:
            call = self._parse_call(name_tok, statement=True)
            self._expect_stmt_eol()
            return ast.ExprStmt(expr=call, line=name_tok.line, col=name_tok.col)
        if self.at(K.IDEN) and self.level.types:
            raise self._fail("Unexpected Identifier",
                             category=C.PARSE_UNEXPECTED_IDENTIFIER)
        raise self.unexpected()

    def _parse_local_decl(self) -> ast.Node:
        type_tok = self.advance()
        self._check_malformed()
        if not self.at(K.IDEN):
            raise self.unexpected()
        name_tok = self.advance()
        if self.at(K.OPEN_PAR) and self.level.functions:
            raise self._fail("Unexpected token FUNC or OPEN_PAR",
                             category=C.PARSE_NESTED_FUNCTION)
        init = None
        if self.at(K.ASSIGN):
            self.advance()
            init = self.parse_bool_expression()
        self._expect_stmt_eol()
        return ast.VarDecl(var_type=type_tok.lexeme, name=name_tok.lexeme,
                           init=init, line=type_tok.line, col=type_tok.col)

    def _parse_struct_var_decl(self) -> ast.VarDecl:
        struct_tok = self.advance()
        self._check_malformed()
        if not self.at(K.IDEN):
            raise self.unexpected()
        type_tok = self.advance()
        self._check_malformed()
        if not self.at(K.IDEN):
            raise self.unexpected()
        name_tok = self.advance()
        self._expect_stmt_eol()
        return ast.VarDecl(var_type=type_tok.lexeme, name=name_tok.lexeme,
                           is_struct=True, line=struct_tok.line,
                           col=struct_tok.col)

    def _parse_const_decl(self) -> ast.VarDecl:
        const_tok = self.advance()
        self._check_malformed()
        if not self.at(K.IDEN):
            raise self.unexpected()
        name_tok = self.advance()
        if not self.at(K.ASSIGN):
            raise self.unexpected()
        self.advance()
        init = self.parse_expression()
        self._expect_stmt_eol()
        return ast.VarDecl(name=name_tok.lexeme, init=init, is_const=True,
                           line=const_tok.line, col=const_tok.col)

    def _parse_printf(self) -> ast.Printf:
        print_tok = self.advance()
        if not self.at(K.OPEN_PAR):
            raise self.unexpected(expected="OPEN_PAR")
        self.advance()
        expr = self.parse_bool_expression()
        if not self.at(K.CLOSE_PAR):
            raise self.unexpected(expected="CLOSE_PAR")
        self.advance()
        self._expect_stmt_eol()
        return ast.Printf(expr=expr, line=print_tok.line, col=print_tok.col)

    def _parse_return(self) -> ast.Return:
        ret_tok = self.advance()
        expr = self.parse_bool_expression()
        self._expect_stmt_eol()
        return ast.Return(expr=expr, line=ret_tok.line, col=ret_tok.col)

    def _parse_if(self) -> ast.If:
        if_tok = self.advance()
        if not self.at(K.OPEN_PAR):
            raise self.missing("OPEN_PAR in If")
        self.advance()
        cond = self.parse_bool_expression()
        if not self.at(K.CLOSE_PAR):
            raise self.missing("CLOSE_PAR")
        self.advance()
        then = self._parse_block(ctx="if")
        other = None
        mark = self.pos
        self._skip_newlines()
        if self.at(K.ELSE):
            self.advance()
            other = self._parse_block(ctx="else")
        else:
            self.pos = mark
        return ast.If(cond=cond, then=then, other=other,
                      line=if_tok.line, col=if_tok.col)

    def _parse_while(self) -> ast.While:
        while_tok = self.advance()
        if not self.at(K.OPEN_PAR):
            raise self.missing("OPEN_PAR in While")
        self.advance()
        cond = self.parse_bool_expression()
        if not self.at(K.CLOSE_PAR):
            raise self.missing("CLOSE_PAR")
        self.advance()
        body = self._parse_block(ctx="while")
        return ast.While(cond=cond, body=body,
                         line=while_tok.line, col=while_tok.col)

    def _parse_for(self) -> ast.For:
        for_tok = self.advance()
        if not self.at(K.OPEN_PAR):
            raise self.missing("OPEN_PAR in For")
        self.advance()
        init = self._parse_for_assignment()
        self._expect_stmt_eol()
        cond = self.parse_bool_expression()
        self._expect_stmt_eol()
        step = self._parse_for_assignment()
        if not self.at(K.CLOSE_PAR):
            raise self.unexpected()
        self.advance()
        self._skip_newlines()
        body = self.parse_statement()
        return ast.For(init=init, cond=cond, step=step, body=body,
                       line=for_tok.line, col=for_tok.col)

    def _parse_for_assignment(self) -> ast.Assign:
        self._check_malformed()
        if not self.at(K.IDEN):
            raise self.unexpected()
        name_tok = self.advance()
        if not self.at(K.ASSIGN):
            raise self.unexpected()
        self.advance()
        expr = self.parse_bool_expression()
        return ast.Assign(target=ast.Ident(name=name_tok.lexeme,
                                           line=name_tok.line,
                                           col=name_tok.col),
                          expr=expr, line=name_tok.line, col=name_tok.col)

    # -- blocks ------------------------------------------------------------
    # The reference compiler's missing-brace diagnostics depend on which
    # construct owns the block; ``ctx`` reproduces that behavior verbatim.
    _BLOCK_MESSAGES = {
        "braces": (None, "unexpected-eof-expected"),   # bare block / func body
        "if": ("Missing OPEN_BRA", "Missing CLOSE_BRA"),
        "while": ("Missing OPEN_BRA", "Unexpected token EOF"),
        "else": ("Unexpected token EOF", "Unexpected token EOF"),
    }

    def _parse_block(self, ctx: str, consume_open: bool = False) -> ast.Block:
        open_msg, close_msg = self._BLOCK_MESSAGES[ctx]
        if ctx == "else" and not self.level.functions:
            close_msg = "Missing CLOSE_BRA"   # v2.1/v2.2 reference behavior
        self._skip_newlines()
        first = self.cur
        if not self.at(K.OPEN_BRA):
            if open_msg is None:
                raise self.unexpected(expected="OPEN_BRA")
            if open_msg.startswith("Missing"):
                raise self.missing(open_msg[len("Missing "):])
            raise self._fail(open_msg)
        self.advance()
        stmts: list = []
        self._skip_newlines()
        while not self.at(K.CLOSE_BRA):
            if self.at(K.EOF):
                if close_msg == "unexpected-eof-expected":
                    # reference quirk: in a plain-braces block the message
                    # depends on the last statement parsed before EOF
                    if stmts and isinstance(stmts[-1], ast.If):
                        raise self.missing("CLOSE_BRA")
                    if stmts and isinstance(stmts[-1], ast.While):
                        raise self._fail("Unexpected token EOF")
                    raise self.unexpected(expected="CLOSE_BRA")
                if close_msg.startswith("Missing"):
                    raise self.missing(close_msg[len("Missing "):])
                raise self._fail(close_msg)
            stmts.append(self.parse_statement())
            self._skip_newlines()
        self.advance()
        return ast.Block(stmts=stmts, line=first.line, col=first.col)

    # -- expressions -------------------------------------------------------
    def parse_bool_expression(self) -> ast.Node:
        if not self.level.blocks:
            node = self.parse_expression()
        else:
            node = self._parse_bool_term()
            while self.at(K.OR):
                op = self.advance()
                right = self._rhs(self._parse_bool_term)
                node = ast.BinOp(op="||", left=node, right=right,
                                 line=op.line, col=op.col)
        if self.level.for_ternary and self.at(K.QUESTION):
            q = self.advance()
            then = self.parse_bool_expression()
            if not self.at(K.COLON):
                raise self.unexpected()
            self.advance()
            other = self.parse_bool_expression()
            node = ast.Ternary(cond=node, then=then, other=other,
                               line=q.line, col=q.col)
        return node

    def _parse_bool_term(self) -> ast.Node:
        node = self._parse_rel_expression()
        while self.at(K.AND):
            op = self.advance()
            right = self._rhs(self._parse_rel_expression)
            node = ast.BinOp(op="&&", left=node, right=right,
                             line=op.line, col=op.col)
        return node

    def _parse_rel_expression(self) -> ast.Node:
        node = self.parse_expression()
        while self.at(K.EQUAL, K.LT, K.GT):
            op = self.advance()
            right = self._rhs(self.parse_expression)
            node = ast.BinOp(op=op.lexeme, left=node, right=right,
                             line=op.line, col=op.col)
        return node

    def _rhs(self, production) -> ast.Node:
        """Parse the right operand of a boolean/relational operator.

        The reference phrases a missing operand as "Missing Right
        Expression" — but only when the operand is missing outright (the
        error is at its very first token)."""
        start = self.pos
        try:
            return production()
        except ParseError as err:
            if (self.pos == start
                    and err.defect.category is C.PARSE_UNEXPECTED_TOKEN):
                raise self._fail("Missing Right Expression",
                                 category=C.PARSE_MISSING_RIGHT_EXPR) from None
            raise

    def parse_expression(self) -> ast.Node:
        node = self.parse_term()
        while self.at(K.PLUS, K.MINUS) or (self.level.types
                                           and self.at(K.CONCAT)):
            op = self.advance()
            right = self.parse_term()
            node = ast.BinOp(op=op.lexeme, left=node, right=right,
                             line=op.line, col=op.col)
        return node

    def parse_term(self) -> ast.Node:
        node = self.parse_factor()
        while self.at(K.MULT, K.DIV):
            op = self.advance()
            right = self.parse_factor()
            node = ast.BinOp(op=op.lexeme, left=node, right=right,
                             line=op.line, col=op.col)
        return node

    def parse_factor(self) -> ast.Node:
        tok = self.cur
        if self.at(K.PLUS, K.MINUS):
            self.advance()
            if self.at(K.EOF):
                # reference quirk: a unary with its operand cut off by EOF
                # reports the unary token itself ("Unexpected token PLUS")
                raise self.unexpected(token=tok)
            operand = self.parse_factor()
            return ast.UnOp(op=tok.lexeme, operand=operand,
                            line=tok.line, col=tok.col)
        if self.at(K.NOT):
            self.advance()
            operand = self._rhs(self.parse_factor)
            return ast.UnOp(op="!", operand=operand,
                            line=tok.line, col=tok.col)
        return self._parse_power()

    def _parse_power(self) -> ast.Node:
        node = self._parse_postfix()
        if self.level.power and self.at(K.POWER):
            op = self.advance()
            right = self.parse_factor()  # right-associative, binds unaries
            node = ast.BinOp(op="**", left=node, right=right,
                             line=op.line, col=op.col)
        return node

    def _parse_postfix(self) -> ast.Node:
        node = self._parse_primary()
        while self.level.factorial and self.at(K.FACT):
            op = self.advance()
            node = ast.PostOp(op="!", operand=node, line=op.line, col=op.col)
        return node

    def _parse_primary(self) -> ast.Node:
        # expression operands may continue past a line end; the ';' EOL is
        # never skipped (it must be reported, e.g. "v = ;")
        self._skip_newlines()
        self._check_malformed()
        tok = self.cur
        if self.at(K.INT):
            self.advance()
            return ast.IntLit(value=int(tok.lexeme), line=tok.line, col=tok.col)
        if self.at(K.FLOAT):
            self.advance()
            return ast.FloatLit(value=float(tok.lexeme), lexeme=tok.lexeme,
                                line=tok.line, col=tok.col)
        if self.at(K.STR):
            self.advance()
            return ast.StrLit(value=tok.lexeme, line=tok.line, col=tok.col)
        if self.at(K.BOOL):
            self.advance()
            return ast.BoolLit(value=tok.lexeme == "true",
                               line=tok.line, col=tok.col)
        if self.at(K.READ):
            self.advance()
            if not self.at(K.OPEN_PAR):
                raise self.missing("OPEN_PAR")
            self.advance()
            if not self.at(K.CLOSE_PAR):
                raise self.missing("CLOSE_PAR")
            self.advance()
            return ast.Scanf(line=tok.line, col=tok.col)
        if self.at(K.IDEN):
            self.advance()
            if self.at(K.OPEN_PAR) and self.level.functions:
                return self._parse_call(tok, statement=False)
            if self.at(K.DOT) and self.level.structs:
                self.advance()
                self._check_malformed()
                if not self.at(K.IDEN):
                    raise self.unexpected()
                field_tok = self.advance()
                return ast.FieldAccess(
                    obj=ast.Ident(name=tok.lexeme, line=tok.line, col=tok.col),
                    fieldname=field_tok.lexeme, line=tok.line, col=tok.col)
            return ast.Ident(name=tok.lexeme, line=tok.line, col=tok.col)
        if self.at(K.OPEN_PAR):
            self.advance()
            if self.level.floats and self.at(K.TYPE):
                type_tok = self.advance()
                if not self.at(K.CLOSE_PAR):
                    raise self.unexpected()
                self.advance()
                operand = self.parse_factor()
                return ast.Cast(target_type=type_tok.lexeme, operand=operand,
                                line=tok.line, col=tok.col)
            inner = self.parse_bool_expression()
            if not self.at(K.CLOSE_PAR):
                if self.level.statements:
                    raise self.missing("CLOSE_PAR")
                raise self.unexpected()
            self.advance()
            return inner
        raise self.unexpected()

    def _parse_call(self, name_tok: Token, statement: bool) -> ast.Call:
        self.advance()  # OPEN_PAR
        args: list = []
        if not self.at(K.CLOSE_PAR):
            args.append(self.parse_bool_expression())
            while self.at(K.COMMA):
                self.advance()
                args.append(self.parse_bool_expression())
        if not self.at(K.CLOSE_PAR):
            raise self.unexpected()
        self.advance()
        call = ast.Call(name=name_tok.lexeme, args=args,
                        line=name_tok.line, col=name_tok.col)
        call.is_statement = statement
        return call
