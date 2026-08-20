"""Phase 4 — the Emitter: walks the source AST once, for every language.

This is the single copy of the translation machinery.  It decides *what*
to emit (traversal, scoping, which node is the diagnosed defect, when a
variable is first assigned, when a printed expression is boolean); the
:class:`~.spec.LanguageSpec` decides *how it is spelled*.  Adding a
target language never touches this file.

Parenthesization is structure-driven: the source tree is authoritative,
and a child expression is wrapped whenever the target language's
precedence table would regroup it (unary operands inside binaries are
always wrapped — Julia's ``^`` binds tighter than unary minus).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..diagnostics import (Defect, ErrorCategory as C, ParseDefect, Phase,
                           SemanticDefect)
from ..syntax import ast
from ..syntax.visitor import Visitor
from .passthrough import render_tokens
from .spec import LanguageSpec


@dataclass
class Emitted:
    """A translated expression: its text plus how tightly it binds."""
    text: str
    op: Optional[str] = None     # source operator if a binary, else None
    unary: bool = False


class Emitter(Visitor):
    def __init__(self, spec: LanguageSpec):
        self.spec = spec
        self.level = spec.level
        self._sem: Optional[SemanticDefect] = None
        self._declared: set[str] = set()      # untyped stages: seen names
        self._const_names: set[str] = set()
        self._hoisted: list[str] = []         # lines a spec hoists to top level
        self._global_names: set[str] = set()
        self._assigned: set[str] = set()      # per-function assigned names

    # ======================================================================
    # entry
    # ======================================================================
    def emit(self, program: ast.Program, source: str) -> tuple[str, Optional[Phase]]:
        defect = program.defect
        if defect is not None and not isinstance(defect, SemanticDefect):
            return (self._emit_defect_passthrough(defect, source),
                    self.spec.phase_for(defect))
        self._sem = defect
        code = self._emit_program(program)
        phase = self.spec.phase_for(defect) if defect is not None else None
        return code, phase

    def _emit_defect_passthrough(self, defect: Defect, source: str) -> str:
        spec = self.spec
        if isinstance(defect, ParseDefect):
            text = render_tokens(defect.tail_tokens,
                                 error_index=defect.error_index,
                                 marker=spec.PARSE_MARKER,
                                 spell=spec.spell_token)
        elif defect.category is C.PREPRO_INVALID_DEFINE:
            text = spec.prepro_defect_text(source)
        else:
            text = spec.lex_defect_text(source)
        if not text.strip():
            text = spec.EMPTY_DEFECT
        return spec.defect_program(text)

    def _emit_program(self, program: ast.Program) -> str:
        spec = self.spec
        decls: list[str] = []
        main_body: Optional[list[str]] = None
        if program.expr_mode:
            value = self.expr(program.items[0]).text
            spec.feature("printf")
            main_body = spec.expr_stmt(spec.PRINTF.format(value=value))
        elif self.level.functions:
            self._global_names = {item.name for item in program.items
                                  if isinstance(item, ast.VarDecl)}
            for item in program.items:
                if isinstance(item, ast.VarDecl):
                    init = (self._checked_init(item)
                            if item.init is not None else None)
                    decls.extend(spec.global_var(item.name, item.var_type,
                                                 init))
                elif isinstance(item, ast.StructDecl):
                    decls.extend(self.visit(item))
                else:
                    decls.extend(self._function(item))
        else:
            main_body = []
            for stmt in program.items:
                main_body.extend(self.visit(stmt))
        return spec.program(self._hoisted + decls, main_body)

    def _function(self, decl: ast.FuncDecl) -> list[str]:
        self._declared = {p.name for p in decl.params}
        self._assigned = set()
        body = self._stmt_lines(decl.body.stmts)
        assigned_globals = sorted(self._assigned & self._global_names)
        return self.spec.function(
            decl.name, [(p.name, p.par_type) for p in decl.params],
            decl.ret_type, body, assigned_globals)

    def _stmt_lines(self, stmts: list) -> list[str]:
        lines: list[str] = []
        for stmt in stmts:
            lines.extend(self.visit(stmt))
        return lines

    # ======================================================================
    # statements (each visit returns lines)
    # ======================================================================
    def visit_NoOp(self, node: ast.NoOp) -> list[str]:
        return []

    def visit_Block(self, node: ast.Block) -> list[str]:
        return self.spec.block(self._stmt_lines(node.stmts),
                               scoped=self.level.types)

    def _is_defect(self, node: ast.Node, *categories: C) -> bool:
        return (self._sem is not None and self._sem.node is node
                and (not categories or self._sem.category in categories))

    def _checked_init(self, decl: ast.VarDecl) -> str:
        expr = self.expr(decl.init).text
        if self._is_defect(decl, C.SEM_INCOMPATIBLE_TYPES):
            expr = self.spec.check_assigned(
                self._sem.detail.get("lhs_type", decl.var_type), expr)
        return expr

    def visit_VarDecl(self, node: ast.VarDecl) -> list[str]:
        if node.is_const:
            self._const_names.add(node.name)
            init = self.expr(node.init).text
            self._hoisted.extend(self.spec.const_topdecl(node.name, init))
            return self.spec.const_decl(node.name, init)
        self._declared.add(node.name)
        init = self._checked_init(node) if node.init is not None else None
        return self.spec.var_decl(node.name, node.var_type, init,
                                  is_struct=node.is_struct)

    def visit_Assign(self, node: ast.Assign) -> list[str]:
        expr = self.expr(node.expr).text
        if self._is_defect(node, C.SEM_INCOMPATIBLE_TYPES):
            expr = self.spec.check_assigned(
                self._sem.detail.get("lhs_type", "int"), expr)
        if isinstance(node.target, ast.FieldAccess):
            target = self.spec.FIELD.format(obj=node.target.obj.name,
                                            name=node.target.fieldname)
            return self.spec.assign(target, expr, declares=False)
        name = node.target.name
        if self._is_defect(node, C.SEM_UNDEFINED_VAR):
            return self.spec.assign_undeclared(name, expr)
        if name in self._const_names:
            return self.spec.const_assign(name, expr)
        self._assigned.add(name)
        declares = (not self.level.types and name not in self._declared)
        if declares:
            self._declared.add(name)
        return self.spec.assign(name, expr, declares=declares)

    _BOOL_OPS = {"==", "<", ">", "&&", "||"}

    def _is_boolean_expr(self, node: ast.Node) -> bool:
        return (isinstance(node, ast.BoolLit)
                or (isinstance(node, ast.BinOp) and node.op in self._BOOL_OPS)
                or (isinstance(node, ast.UnOp) and node.op == "!"))

    def visit_Printf(self, node: ast.Printf) -> list[str]:
        spec = self.spec
        value = self.expr(node.expr).text
        if self.level.bools_as_ints and self._is_boolean_expr(node.expr):
            spec.feature("b2i")
            value = spec.PRINT_BOOL_AS_INT.format(value=value)
        spec.feature("printf")
        return spec.expr_stmt(spec.PRINTF.format(value=value))

    def visit_ExprStmt(self, node: ast.ExprStmt) -> list[str]:
        return self.spec.expr_stmt(self.expr(node.expr).text)

    def visit_If(self, node: ast.If) -> list[str]:
        return self.spec.if_(
            self.expr(node.cond).text,
            self._stmt_lines(node.then.stmts),
            self._stmt_lines(node.other.stmts)
            if node.other is not None else None)

    def visit_While(self, node: ast.While) -> list[str]:
        return self.spec.while_(self.expr(node.cond).text,
                                self._stmt_lines(node.body.stmts))

    def visit_For(self, node: ast.For) -> list[str]:
        return self.spec.for_(self.visit(node.init),
                              self.expr(node.cond).text,
                              self.visit(node.step),
                              self.visit(node.body))

    def visit_Return(self, node: ast.Return) -> list[str]:
        expr = self.expr(node.expr).text
        if self._is_defect(node, C.SEM_RETURN_TYPE):
            expr = self.spec.check_assigned(
                self._sem.detail.get("declared", "int"), expr)
        return self.spec.return_(expr)

    def visit_StructDecl(self, node: ast.StructDecl) -> list[str]:
        return self.spec.struct(node.name,
                                [(f.name, f.field_type)
                                 for f in node.fields])

    # ======================================================================
    # expressions (each returns an Emitted)
    # ======================================================================
    def expr(self, node: ast.Node) -> Emitted:
        return self.visit(node)

    def visit_IntLit(self, node: ast.IntLit) -> Emitted:
        return Emitted(str(node.value))

    def visit_FloatLit(self, node: ast.FloatLit) -> Emitted:
        return Emitted(node.lexeme)

    def visit_StrLit(self, node: ast.StrLit) -> Emitted:
        return Emitted(self.spec.quote(node.value))

    def visit_BoolLit(self, node: ast.BoolLit) -> Emitted:
        return Emitted(self.spec.BOOL_LITS[0 if node.value else 1])

    def visit_Ident(self, node: ast.Ident) -> Emitted:
        if node.name in self._const_names:
            return Emitted(self.spec.const_read(node.name))
        return Emitted(node.name)

    def visit_FieldAccess(self, node: ast.FieldAccess) -> Emitted:
        return Emitted(self.spec.FIELD.format(obj=node.obj.name,
                                              name=node.fieldname))

    def visit_Scanf(self, node: ast.Scanf) -> Emitted:
        self.spec.feature("scanf")
        return Emitted(self.spec.SCANF)

    def visit_Call(self, node: ast.Call) -> Emitted:
        args = ", ".join(self.expr(a).text for a in node.args)
        return Emitted(self.spec.CALL.format(func=node.name, args=args))

    def visit_Ternary(self, node: ast.Ternary) -> Emitted:
        self.spec.feature("ternary")
        return Emitted(self.spec.TERNARY.format(
            cond=self.expr(node.cond).text,
            then=self.expr(node.then).text,
            other=self.expr(node.other).text))

    def visit_Cast(self, node: ast.Cast) -> Emitted:
        operand = self.expr(node.operand)
        self.spec.feature(f"cast:{node.target_type}")
        template = self.spec.cast_template(node.target_type, node.operand)
        return Emitted(template.format(operand=operand.text))

    def visit_UnOp(self, node: ast.UnOp) -> Emitted:
        operand = self.expr(node.operand)
        text = operand.text
        if operand.op is not None or operand.unary:
            text = f"({text})"
        return Emitted(self.spec.UNOPS[node.op].format(operand=text),
                       unary=True)

    def visit_PostOp(self, node: ast.PostOp) -> Emitted:
        self.spec.feature("fact")
        operand = self.expr(node.operand)
        text = operand.text
        if operand.op is not None or operand.unary:
            text = f"({text})"
        return Emitted(self.spec.FACTORIAL.format(operand=text))

    def visit_BinOp(self, node: ast.BinOp) -> Emitted:
        left = self.expr(node.left)
        right = self.expr(node.right)
        left_text = self._parenthesize(left, node.op, is_right=False)
        right_text = self._parenthesize(right, node.op, is_right=True)
        if self._is_defect(node, C.SEM_INCOMPATIBLE_TYPES):
            left_text, right_text = self._checked_operands(
                node, left_text, right_text)
        op_key = node.op
        if node.op == "/" and self._is_float_division(node):
            op_key = "/float" if "/float" in self.spec.BINOPS else "/"
        self.spec.feature(node.op)
        template = self.spec.BINOPS[op_key]
        return Emitted(template.format(left=left_text, right=right_text),
                       op=node.op)

    def _is_float_division(self, node: ast.BinOp) -> bool:
        return "float" in (getattr(node.left, "sem_type", None),
                           getattr(node.right, "sem_type", None))

    def _parenthesize(self, child: Emitted, parent_op: str,
                      is_right: bool) -> str:
        if child.unary:
            return f"({child.text})"
        if child.op is None:
            return child.text
        prec = self.spec.PRECEDENCE
        # operators a spec renders as calls have no precedence entry: atomic
        if child.op not in prec or parent_op not in prec:
            return child.text
        child_prec, parent_prec = prec[child.op], prec[parent_op]
        same_op_chain = (child.op == parent_op and not is_right
                         and parent_op in self.spec.ASSOCIATIVE)
        if child_prec < parent_prec or (child_prec == parent_prec
                                        and not same_op_chain):
            return f"({child.text})"
        return child.text

    def _checked_operands(self, node: ast.BinOp, left: str,
                          right: str) -> tuple[str, str]:
        """Route the diagnosed mismatched operand through the spec's strict
        check (a no-op for languages whose native translation already
        fails)."""
        lhs = self._sem.detail.get("lhs_type")
        rhs = self._sem.detail.get("rhs_type")
        if lhs is None or rhs is None:
            return left, right      # e.g. a non-bool condition: fails natively
        if node.op in ("&&", "||"):
            expected = "bool"
        elif node.op in ("==", "<", ">"):
            expected = lhs          # the reference compares against the left type
        else:
            expected = "int" if "int" in (lhs, rhs) else lhs
        if rhs != expected:
            return left, self.spec.check_operand(expected, right)
        return self.spec.check_operand(expected, left), right
