"""Lowering: analyzed source AST → typed IR.

Every course-language question is answered here, once, so backends never
see the source language:

* programs of every stage are normalized to a :class:`~.nodes.Module`
  whose entry point is a ``main`` :class:`~.nodes.FuncDef` (expression
  programs become ``main { print expr }``);
* names are resolved to local/global/const/field references — or an
  :class:`~.nodes.UnresolvedRef` when the course program used an
  undeclared name (the translation must fail natively there);
* operators are resolved (``/`` becomes ``div_int`` or ``div_float`` from
  operand types; ``$`` becomes ``concat``); ``for`` desugars to ``while``;
  untyped stages get their flat scoping and declare-on-first-assignment
  made explicit; v3.0's print-bools-as-ints becomes an explicit cast;
* the single diagnosed semantic defect, when the target could be laxer
  than the course, is materialized as an explicit :class:`~.nodes.CheckType`
  at the equivalent point.

Types are recomputed structurally during lowering (literals, declaration
records, function signatures), so even programs whose semantic analysis
stopped at a defect lower completely.
"""

from __future__ import annotations

from typing import Optional

from ..diagnostics import ErrorCategory as C, SemanticDefect
from ..semantic import types as T
from ..syntax import ast
from ..versions import LanguageLevel
from . import nodes as ir

_BINOPS = {"+": "add", "-": "sub", "*": "mul", "==": "eq", "<": "lt",
           ">": "gt", "&&": "and_", "||": "or_", "$": "concat",
           "^": "xor", "**": "pow"}
_UNOPS = {"-": "neg", "+": "pos", "!": "not_"}
_CASTS = {"int": "to_int", "float": "to_float", "str": "to_str",
          "bool": "to_bool"}


class Lowerer:
    def __init__(self, level: LanguageLevel,
                 defect: Optional[SemanticDefect] = None):
        self.level = level
        self.defect = defect
        self.scopes: list[dict] = [{}]       # name -> (kind, type)
        self.structs: dict[str, T.StructType] = {}
        self.funcs: dict[str, tuple[list, object]] = {}  # name -> (params, ret)
        self.consts: list[ir.ConstDef] = []

    # -- entry -------------------------------------------------------------
    def lower(self, program: ast.Program) -> ir.Module:
        if program.expr_mode:
            body = [ir.Print(expr=self.lower_expr(program.items[0]))]
            return ir.Module(funcs=[ir.FuncDef(name="main", ret="void",
                                               body=body)])
        if self.level.functions:
            return self._lower_declarations(program)
        body = self.lower_stmts(program.items)
        module = ir.Module(consts=self.consts,
                          funcs=[ir.FuncDef(name="main", ret="void",
                                            body=body)])
        return module

    def _lower_declarations(self, program: ast.Program) -> ir.Module:
        module = ir.Module()
        # first pass: signatures, struct types, global names (bodies may
        # use functions/globals declared later)
        for item in program.items:
            if isinstance(item, ast.StructDecl):
                struct_t = T.StructType(
                    name=item.name,
                    fields=tuple((f.name, f.field_type) for f in item.fields))
                self.structs[item.name] = struct_t
            elif isinstance(item, ast.FuncDecl):
                params = [(p.name, self._named_type(p.par_type))
                          for p in item.params]
                self.funcs[item.name] = (params, item.ret_type)
            elif isinstance(item, ast.VarDecl):
                self.scopes[0][item.name] = ("global",
                                             self._named_type(item.var_type))
        for item in program.items:
            if isinstance(item, ast.StructDecl):
                struct_t = self.structs[item.name]
                module.structs.append(ir.StructDef(
                    name=item.name, fields=list(struct_t.fields)))
            elif isinstance(item, ast.VarDecl):
                init = (self._checked_init(item)
                        if item.init is not None else None)
                module.globals.append(ir.GlobalDef(
                    name=item.name, type=self._named_type(item.var_type),
                    init=init))
            else:
                module.funcs.append(self._lower_function(item))
        module.consts = self.consts
        return module

    def _lower_function(self, decl: ast.FuncDecl) -> ir.FuncDef:
        params = self.funcs[decl.name][0]
        self.scopes.append({name: ("local", ptype)
                            for name, ptype in params})
        body = self.lower_stmts(decl.body.stmts)
        self.scopes.pop()
        return ir.FuncDef(name=decl.name, params=params, ret=decl.ret_type,
                          body=body)

    def _named_type(self, course_type: str):
        return self.structs.get(course_type, course_type)

    # -- scope helpers -----------------------------------------------------
    def _resolve(self, name: str):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def _declare(self, name: str, kind: str, var_type) -> None:
        self.scopes[-1][name] = (kind, var_type)

    def _is_defect(self, node: ast.Node, *categories: C) -> bool:
        return (self.defect is not None and self.defect.node is node
                and (not categories or self.defect.category in categories))

    # -- statements --------------------------------------------------------
    def lower_stmts(self, stmts: list) -> list:
        out: list = []
        for stmt in stmts:
            out.extend(self.lower_stmt(stmt))
        return out

    def lower_stmt(self, node: ast.Node) -> list:
        method = getattr(self, f"stmt_{type(node).__name__}")
        return method(node)

    def stmt_NoOp(self, node: ast.NoOp) -> list:
        return []

    def stmt_Block(self, node: ast.Block) -> list:
        if not self.level.types:
            # untyped stages: {} has no scoping semantics — inline
            return self.lower_stmts(node.stmts)
        self.scopes.append({})
        body = self.lower_stmts(node.stmts)
        self.scopes.pop()
        return [ir.Scope(body=body)]

    def _checked_init(self, decl: ast.VarDecl) -> ir.IRNode:
        init = self.lower_expr(decl.init)
        if self._is_defect(decl, C.SEM_INCOMPATIBLE_TYPES):
            expected = self.defect.detail.get("lhs_type", decl.var_type)
            init = ir.CheckType(expected=expected, operand=init,
                                type=expected)
        return init

    def stmt_VarDecl(self, node: ast.VarDecl) -> list:
        if node.is_const:
            init = self.lower_expr(node.init)
            self._declare(node.name, "const", init.type)
            self.consts.append(ir.ConstDef(name=node.name, init=init))
            return []
        var_type = self._named_type(node.var_type) if self.level.types \
            else "int"
        self._declare(node.name, "local", var_type)
        init = self._checked_init(node) if node.init is not None else None
        return [ir.DeclareLocal(name=node.name, type=var_type, init=init)]

    def stmt_Assign(self, node: ast.Assign) -> list:
        expr = self.lower_expr(node.expr)
        if self._is_defect(node, C.SEM_INCOMPATIBLE_TYPES):
            expected = self.defect.detail.get("lhs_type", "int")
            expr = ir.CheckType(expected=expected, operand=expr,
                                type=expected)
        if isinstance(node.target, ast.FieldAccess):
            return [ir.Assign(target=self._field_ref(node.target), expr=expr)]
        name = node.target.name
        resolved = self._resolve(name)
        if resolved is None:
            if not self.level.types:
                # untyped stages declare on first assignment (flat scope)
                self._declare(name, "local", "int")
                return [ir.DeclareLocal(name=name, type="int", init=expr)]
            return [ir.Assign(target=ir.UnresolvedRef(name=name), expr=expr)]
        kind, var_type = resolved
        ref_cls = {"local": ir.LocalRef, "global": ir.GlobalRef,
                   "const": ir.ConstRef}[kind]
        return [ir.Assign(target=ref_cls(name=name, type=var_type),
                          expr=expr)]

    def _field_ref(self, access: ast.FieldAccess) -> ir.FieldRef:
        resolved = self._resolve(access.obj.name)
        field_type = "int"
        if resolved is not None and T.is_struct(resolved[1]):
            field_type = resolved[1].field_type(access.fieldname) or "int"
        return ir.FieldRef(obj=access.obj.name, fieldname=access.fieldname,
                           type=field_type)

    def stmt_Printf(self, node: ast.Printf) -> list:
        expr = self.lower_expr(node.expr)
        if self.level.bools_as_ints and expr.type == T.BOOL:
            expr = ir.Cast(kind="bool_to_int", operand=expr, type="int")
        return [ir.Print(expr=expr)]

    def stmt_ExprStmt(self, node: ast.ExprStmt) -> list:
        return [ir.ExprStmt(expr=self.lower_expr(node.expr))]

    def stmt_If(self, node: ast.If) -> list:
        return [ir.If(cond=self.lower_expr(node.cond),
                      then=self.lower_stmts(node.then.stmts),
                      other=self.lower_stmts(node.other.stmts)
                      if node.other is not None else None)]

    def stmt_While(self, node: ast.While) -> list:
        return [ir.While(cond=self.lower_expr(node.cond),
                         body=self.lower_stmts(node.body.stmts))]

    def stmt_For(self, node: ast.For) -> list:
        # desugar: init; while cond { body; step }
        init = self.lower_stmt(node.init)
        cond = self.lower_expr(node.cond)
        step = self.lower_stmt(node.step)
        body = self.lower_stmt(node.body)
        return init + [ir.While(cond=cond, body=body + step)]

    def stmt_Return(self, node: ast.Return) -> list:
        expr = self.lower_expr(node.expr)
        if self._is_defect(node, C.SEM_RETURN_TYPE):
            expected = self.defect.detail.get("declared", "int")
            expr = ir.CheckType(expected=expected, operand=expr,
                                type=expected)
        return [ir.Return(expr=expr)]

    # -- expressions -------------------------------------------------------
    def lower_expr(self, node: ast.Node) -> ir.IRNode:
        method = getattr(self, f"expr_{type(node).__name__}")
        return method(node)

    def expr_IntLit(self, node: ast.IntLit) -> ir.IRNode:
        return ir.IntConst(value=node.value)

    def expr_FloatLit(self, node: ast.FloatLit) -> ir.IRNode:
        return ir.FloatConst(lexeme=node.lexeme)

    def expr_StrLit(self, node: ast.StrLit) -> ir.IRNode:
        return ir.StrConst(value=node.value)

    def expr_BoolLit(self, node: ast.BoolLit) -> ir.IRNode:
        return ir.BoolConst(value=node.value)

    def expr_Ident(self, node: ast.Ident) -> ir.IRNode:
        resolved = self._resolve(node.name)
        if resolved is None:
            return ir.UnresolvedRef(name=node.name)
        kind, var_type = resolved
        ref_cls = {"local": ir.LocalRef, "global": ir.GlobalRef,
                   "const": ir.ConstRef}[kind]
        return ref_cls(name=node.name, type=var_type)

    def expr_FieldAccess(self, node: ast.FieldAccess) -> ir.IRNode:
        return self._field_ref(node)

    def expr_Scanf(self, node: ast.Scanf) -> ir.IRNode:
        return ir.ReadInt()

    def expr_Call(self, node: ast.Call) -> ir.IRNode:
        signature = self.funcs.get(node.name)
        return ir.Call(name=node.name,
                       args=[self.lower_expr(a) for a in node.args],
                       type=signature[1] if signature else "int")

    def expr_Ternary(self, node: ast.Ternary) -> ir.IRNode:
        then = self.lower_expr(node.then)
        return ir.Ternary(cond=self.lower_expr(node.cond), then=then,
                          other=self.lower_expr(node.other), type=then.type)

    def expr_Cast(self, node: ast.Cast) -> ir.IRNode:
        return ir.Cast(kind=_CASTS[node.target_type],
                       operand=self.lower_expr(node.operand),
                       type=node.target_type)

    def expr_UnOp(self, node: ast.UnOp) -> ir.IRNode:
        operand = self.lower_expr(node.operand)
        op = _UNOPS[node.op]
        result = "bool" if op == "not_" else operand.type
        return ir.Unary(op=op, operand=operand, type=result)

    def expr_PostOp(self, node: ast.PostOp) -> ir.IRNode:
        return ir.Unary(op="fact", operand=self.lower_expr(node.operand))

    def expr_BinOp(self, node: ast.BinOp) -> ir.IRNode:
        left = self.lower_expr(node.left)
        right = self.lower_expr(node.right)
        if node.op == "/":
            floaty = "float" in (left.type, right.type)
            op = "div_float" if floaty else "div_int"
        else:
            op = _BINOPS[node.op]
        if op in ("eq", "lt", "gt", "and_", "or_"):
            result = "bool"
        elif op == "concat":
            result = "str"
        elif "float" in (left.type, right.type):
            result = "float"
        else:
            result = "int"
        if self._is_defect(node, C.SEM_INCOMPATIBLE_TYPES):
            left, right = self._checked_operands(node, left, right)
        return ir.Binary(op=op, left=left, right=right, type=result)

    def _checked_operands(self, node: ast.BinOp, left: ir.IRNode,
                          right: ir.IRNode):
        """Materialize the diagnosed operand mismatch as a CheckType on the
        offending side (targets laxer than the course need it explicit)."""
        lhs = self.defect.detail.get("lhs_type")
        rhs = self.defect.detail.get("rhs_type")
        if lhs is None or rhs is None:
            return left, right   # e.g. a non-bool condition: fails natively
        if node.op in ("&&", "||"):
            expected = "bool"
        elif node.op in ("==", "<", ">"):
            expected = lhs       # the reference compares against the left type
        else:
            expected = "int" if "int" in (lhs, rhs) else lhs
        if rhs != expected:
            return left, ir.CheckType(expected=expected, operand=right,
                                      type=expected)
        return ir.CheckType(expected=expected, operand=left,
                            type=expected), right


def lower(program: ast.Program, level: LanguageLevel) -> ir.Module:
    defect = program.defect if isinstance(program.defect, SemanticDefect) \
        else None
    return Lowerer(level, defect).lower(program)
