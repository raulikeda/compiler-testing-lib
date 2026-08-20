"""Phase 3 — semantic analysis (a Visitor over the source AST).

Checks what the course reference compilers check, phrased how they phrase
it, and stops at the first violation: the resulting
:class:`~..diagnostics.SemanticDefect` wraps the offending (well-formed)
node inside an otherwise intact tree, so back ends can translate the whole
program and make it fail natively at the equivalent point.

For the expression-mode stages (v0.0-v1.2, x1.x) the reference "semantic
phase" is simply evaluation, so the analyzer folds the constant expression
and reports what evaluation would report (division by zero, factorial of a
negative number).

The reference's diagnostics vary per check site and stage — assignment
mismatches say "Incompatible types", comparisons "Incompatible Types",
``- * /`` arithmetic "Incompatible Type", an undefined variable is
"Identifier not found" except in v2.2 ("Variable not found"), and an
assignment to an undeclared name in v2.3 says "Function not found".  These
are cloned deliberately; the corpus is the oracle.
"""

from __future__ import annotations

from typing import Optional

from ..diagnostics import ErrorCategory as C, SemanticDefect
from ..syntax import ast
from ..syntax.visitor import Visitor
from ..versions import LanguageLevel
from . import types as T
from .symbols import Scope, Symbol


class SemanticError(Exception):
    def __init__(self, defect: SemanticDefect):
        super().__init__(defect.message)
        self.defect = defect


def _trunc_div(a: int, b: int) -> int:
    """C-style integer division: truncation toward zero."""
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


class SemanticAnalyzer(Visitor):
    def __init__(self, level: LanguageLevel):
        self.level = level
        self.scope = Scope()
        self.current_function: Optional[Symbol] = None
        self._in_decl_init = False

    # -- public entry ------------------------------------------------------
    def analyze(self, program: ast.Program) -> Optional[SemanticDefect]:
        if program.defect is not None:
            return None  # an earlier phase already diagnosed this program
        try:
            if program.expr_mode:
                self._evaluate(program.items[0])
            elif self.level.functions:
                self._analyze_declarations(program)
            else:
                for item in program.items:
                    self.visit(item)
        except SemanticError as err:
            program.defect = err.defect
            return err.defect
        return None

    # -- diagnostics -------------------------------------------------------
    def _fail(self, message: str, node: ast.Node,
              category: C = C.SEM_INCOMPATIBLE_TYPES, **detail):
        tag = "[Semantic] " if self.level.bracket_tags else ""
        raise SemanticError(SemanticDefect(
            category=category, message=f"{tag}{message}",
            line=node.line, col=node.col, node=node, detail=detail))

    def _undefined(self, node: ast.Node, name: str):
        # the reference phrases an unresolved name by context: declaration
        # initializers say "Variable not found", everywhere else says
        # "Identifier not found"
        message = ("Variable not found"
                   if self.level.types and self._in_decl_init
                   else "Identifier not found")
        self._fail(message, node, category=C.SEM_UNDEFINED_VAR, name=name)

    # ======================================================================
    # Expression mode: the semantic phase of v0.0-v1.2/x1.x is evaluation
    # ======================================================================
    def _evaluate(self, node: ast.Node) -> int:
        if isinstance(node, ast.IntLit):
            return node.value
        if isinstance(node, ast.UnOp):
            value = self._evaluate(node.operand)
            return -value if node.op == "-" else value
        if isinstance(node, ast.PostOp):
            value = self._evaluate(node.operand)
            if value < 0:
                self._fail("Factorial is not defined for negative numbers",
                           node, category=C.SEM_NEG_FACTORIAL)
            result = 1
            for i in range(2, value + 1):
                result *= i
            return result
        if isinstance(node, ast.BinOp):
            left = self._evaluate(node.left)
            right = self._evaluate(node.right)
            if node.op == "+":
                return left + right
            if node.op == "-":
                return left - right
            if node.op == "*":
                return left * right
            if node.op == "/":
                if right == 0:
                    self._fail("Division by zero", node,
                               category=C.SEM_DIV_ZERO)
                return _trunc_div(left, right)
            if node.op == "^":
                return left ^ right
            if node.op == "**":
                return left ** right
        raise AssertionError(f"unexpected expr-mode node {node!r}")

    # ======================================================================
    # Program mode
    # ======================================================================
    def _analyze_declarations(self, program: ast.Program) -> None:
        # two passes: register every function/struct/global first (bodies
        # may call functions declared later), then check bodies
        for item in program.items:
            if isinstance(item, ast.FuncDecl):
                self.scope.declare(Symbol(
                    name=item.name, kind="func", ret_type=item.ret_type,
                    params=[(p.par_type, p.name) for p in item.params]))
            elif isinstance(item, ast.StructDecl):
                struct_t = T.StructType(
                    name=item.name,
                    fields=tuple((f.name, f.field_type) for f in item.fields))
                self.scope.declare(Symbol(name=item.name, kind="struct",
                                          type=struct_t))

        main = self.scope.resolve("main")
        if main is None or main.kind != "func":
            message = ("Undefined function main" if not program.items
                       else "Missing function main")
            self._fail(message, program, category=C.SEM_UNDEFINED_MAIN)

        for item in program.items:
            if isinstance(item, ast.VarDecl):
                self.visit(item)                   # global variable
            elif isinstance(item, ast.FuncDecl):
                self._check_function(item)

    def _check_function(self, decl: ast.FuncDecl) -> None:
        outer, self.current_function = self.scope, self.scope.resolve(decl.name)
        self.scope = outer.child()
        for par_type, name in self.current_function.params:
            self.scope.declare(Symbol(name=name, type=self._named_type(par_type)))
        for stmt in decl.body.stmts:
            self.visit(stmt)
        self.scope, self.current_function = outer, None

    def _named_type(self, name: str):
        if name in T.SCALARS:
            return name
        sym = self.scope.resolve(name)
        return sym.type if sym is not None and sym.kind == "struct" else name

    # -- statements --------------------------------------------------------
    def visit_NoOp(self, node: ast.NoOp):
        pass

    def visit_Block(self, node: ast.Block):
        if self.level.types:
            outer, self.scope = self.scope, self.scope.child()
            for stmt in node.stmts:
                self.visit(stmt)
            self.scope = outer
        else:
            for stmt in node.stmts:
                self.visit(stmt)

    def visit_VarDecl(self, node: ast.VarDecl):
        init_type = None
        if node.init is not None:
            self._in_decl_init = True
            try:
                init_type = self.expr_type(node.init)
            finally:
                self._in_decl_init = False
        if node.is_struct:
            struct_sym = self.scope.resolve(node.var_type)
            var_type = (struct_sym.type if struct_sym is not None
                        and struct_sym.kind == "struct" else None)
            if var_type is None:
                self._undefined(node, node.var_type)
        elif node.is_const:
            var_type = init_type if init_type is not None else T.INT
        else:
            var_type = node.var_type if self.level.types else T.INT
        if not self.scope.declare(Symbol(
                name=node.name, type=var_type,
                kind="const" if node.is_const else "var")):
            self._fail("Variable Already Declared", node,
                       category=C.SEM_VAR_REDECLARED, name=node.name)
        if init_type is not None and not node.is_const:
            self._check_assignment(node, var_type, init_type,
                                   value_node=node.init)

    def visit_Assign(self, node: ast.Assign):
        value_type = self.expr_type(node.expr)
        target = node.target
        if isinstance(target, ast.FieldAccess):
            field_type = self._field_type(target)
            self._check_assignment(node, field_type, value_type,
                                   value_node=node.expr)
            return
        sym = self.scope.resolve(target.name)
        if sym is None:
            if self.level.types:
                if self.level.functions:
                    # v2.3 reference quirk: an out-of-scope assignment
                    # target is reported as "Function not found"
                    self._fail("Function not found", node,
                               category=C.SEM_UNDEFINED_VAR, name=target.name)
                self._undefined(node, target.name)
            # untyped stages: assignment declares the variable
            self.scope.declare(Symbol(name=target.name, type=T.INT))
            return
        if sym.kind == "const":
            self._fail(f"Variable {sym.name} can not be changed", node,
                       category=C.SEM_CONST_REASSIGN, name=sym.name)
        if T.is_struct(sym.type):
            self._fail("Wrong Assignment to struct variable", node,
                       category=C.SEM_STRUCT_ASSIGN)
        if self.level.types:
            self._check_assignment(node, sym.type, value_type,
                                   value_node=node.expr)

    def _check_assignment(self, node: ast.Node, target_type, value_type,
                          value_node: ast.Node = None):
        if T.is_struct(value_type):
            self._fail("Wrong Assignment from struct variable", node,
                       category=C.SEM_STRUCT_ASSIGN)
        if target_type == value_type:
            return
        if self.level.floats and T.FLOAT in (target_type, value_type):
            self._fail(f"Unexpected type {T.spelled(value_type)} assigned "
                       f"to {T.spelled(target_type)} variable", node,
                       lhs_type=target_type, rhs_type=value_type)
        # reference quirks, cloned: a compound (binary) value phrases the
        # mismatch in the singular, and the str <- bool path prints untagged
        if isinstance(value_node, ast.BinOp):
            self._fail("Incompatible Type", node,
                       lhs_type=target_type, rhs_type=value_type)
        if target_type == T.STR and value_type == T.BOOL:
            raise SemanticError(SemanticDefect(
                category=C.SEM_INCOMPATIBLE_TYPES,
                message="Incompatible types",   # sic: the reference omits the tag here
                line=node.line, col=node.col, node=node,
                detail={"lhs_type": target_type, "rhs_type": value_type}))
        self._fail("Incompatible types", node,
                   lhs_type=target_type, rhs_type=value_type)

    def _field_type(self, access: ast.FieldAccess):
        sym = self.scope.resolve(access.obj.name)
        if sym is None:
            self._undefined(access, access.obj.name)
        if not T.is_struct(sym.type):
            self._fail("Wrong Assignment to struct variable", access,
                       category=C.SEM_STRUCT_ASSIGN)
        field_type = sym.type.field_type(access.fieldname)
        if field_type is None:
            self._fail(f"Attribute not found in struct: {access.fieldname}",
                       access, category=C.SEM_STRUCT_ATTR,
                       struct=sym.type.name, attr=access.fieldname)
        return field_type

    def visit_Printf(self, node: ast.Printf):
        self.expr_type(node.expr)

    def visit_ExprStmt(self, node: ast.ExprStmt):
        expr = node.expr
        if isinstance(expr, ast.Call):
            self._check_call(expr, as_statement=True)
        else:
            self.expr_type(expr)

    def visit_If(self, node: ast.If):
        self._check_condition(node.cond)
        self.visit(node.then)
        if node.other is not None:
            self.visit(node.other)

    def visit_While(self, node: ast.While):
        self._check_condition(node.cond)
        self.visit(node.body)

    def visit_For(self, node: ast.For):
        self.visit(node.init)
        self._check_condition(node.cond)
        self.visit(node.step)
        self.visit(node.body)

    def visit_Return(self, node: ast.Return):
        value_type = self.expr_type(node.expr)
        func = self.current_function
        if func is not None and self.level.types:
            if value_type != func.ret_type:
                self._fail("Wrong func return type", node,
                           category=C.SEM_RETURN_TYPE,
                           declared=func.ret_type, actual=value_type)

    def _check_condition(self, cond: ast.Node):
        cond_type = self.expr_type(cond)
        if self.level.types and cond_type != T.BOOL:
            self._fail("Incompatible Type", cond)

    # -- expressions -------------------------------------------------------
    def expr_type(self, node: ast.Node):
        """Type an expression; in untyped stages everything is int and only
        name resolution plus literal division by zero are checked.

        As a side effect the computed type is annotated on the node
        (``node.sem_type``) for backends that need it (e.g. Julia's choice
        of ``÷`` vs ``/``)."""
        result = self._expr_type(node)
        node.sem_type = result
        return result

    def _expr_type(self, node: ast.Node):
        if isinstance(node, ast.IntLit):
            return T.INT
        if isinstance(node, ast.FloatLit):
            return T.FLOAT
        if isinstance(node, ast.StrLit):
            return T.STR
        if isinstance(node, ast.BoolLit):
            return T.BOOL
        if isinstance(node, ast.Scanf):
            return T.INT
        if isinstance(node, ast.Ident):
            sym = self.scope.resolve(node.name)
            if sym is None:
                self._undefined(node, node.name)
            return sym.type
        if isinstance(node, ast.FieldAccess):
            return self._field_type(node)
        if isinstance(node, ast.Cast):
            self.expr_type(node.operand)
            return node.target_type
        if isinstance(node, ast.Call):
            return self._check_call(node, as_statement=False)
        if isinstance(node, ast.Ternary):
            self._check_condition(node.cond)
            then_type = self.expr_type(node.then)
            self.expr_type(node.other)
            return then_type
        if isinstance(node, ast.UnOp):
            return self._unop_type(node)
        if isinstance(node, ast.PostOp):
            self.expr_type(node.operand)
            return T.INT
        if isinstance(node, ast.BinOp):
            return self._binop_type(node)
        raise AssertionError(f"unexpected expression node {node!r}")

    def _unop_type(self, node: ast.UnOp):
        operand_type = self.expr_type(node.operand)
        if not self.level.types:
            return T.INT
        if node.op == "!":
            if operand_type != T.BOOL:
                self._fail("Incompatible Types", node)
            return T.BOOL
        if not T.is_numeric(operand_type):
            self._fail("Incompatible Type", node)
        return operand_type

    def _binop_type(self, node: ast.BinOp):
        left = self.expr_type(node.left)
        right = self.expr_type(node.right)
        op = node.op

        if op == "/" and isinstance(node.right, ast.IntLit) \
                and node.right.value == 0:
            self._fail("Division by zero", node, category=C.SEM_DIV_ZERO)

        if not self.level.types:
            return T.INT

        if T.is_struct(left) or T.is_struct(right):
            self._fail("Wrong Assignment from struct variable", node,
                       category=C.SEM_STRUCT_ASSIGN)

        if op == "$":
            return T.STR
        if op in ("==", "<", ">"):
            if left != right:
                self._fail("Incompatible Types", node,
                           lhs_type=left, rhs_type=right)
            return T.BOOL
        if op in ("&&", "||"):
            if left != T.BOOL or right != T.BOOL:
                self._fail("Incompatible Types", node,
                           lhs_type=left, rhs_type=right)
            return T.BOOL

        # arithmetic + - * / (also ^ ** in expr-mode-derived levels)
        if T.is_numeric(left) and T.is_numeric(right):
            return T.FLOAT if T.FLOAT in (left, right) else T.INT
        if self.level.floats:
            self._fail(f"Diffenrent types in binary operation: "  # sic
                       f"{T.spelled(left)} and {T.spelled(right)}", node,
                       lhs_type=left, rhs_type=right)
        if op == "+":
            self._fail("Incompatible Types", node,
                       lhs_type=left, rhs_type=right)
        self._fail("Incompatible Type", node, lhs_type=left, rhs_type=right)

    def _check_call(self, node: ast.Call, as_statement: bool):
        sym = self.scope.resolve(node.name)
        if sym is None or sym.kind != "func":
            if as_statement:
                self._fail("Undefined variable (function)", node,
                           category=C.SEM_UNDEFINED_VAR, name=node.name)
            self._fail("Function not found", node,
                       category=C.SEM_FUNC_NOT_FOUND, name=node.name)
        if len(node.args) != len(sym.params):
            self._fail("Number of args wrong", node,
                       category=C.SEM_ARG_COUNT, expected=len(sym.params),
                       actual=len(node.args))
        for arg, (par_type, _name) in zip(node.args, sym.params):
            arg_type = self.expr_type(arg)
            if self.level.types and arg_type != self._named_type(par_type):
                self._fail("Wrong arg type", node, category=C.SEM_ARG_TYPE,
                           expected=par_type, actual=arg_type)
        return sym.ret_type
