"""GoTransformer: course AST → Go AST.

Valid programs become idiomatic-enough Go; the one systematic concession
is a ``_ = x`` blank use after every local declaration, because Go rejects
declared-and-not-used variables and the course language does not.

Semantic defects need no special casing at all: the faithful typed
translation (``var x int = "abc"``, a call with too few arguments, a
constant zero divisor, an undeclared name) is precisely what makes
``go build`` fail natively.  Lexical/syntactic defects short-circuit to
token passthrough — any C-shaped token soup is invalid Go, and bare
expression statements are illegal, so no failure marker is ever needed.
"""

from __future__ import annotations

from ...diagnostics import Defect, ErrorCategory as C, ParseDefect, Phase
from ...syntax import ast
from ..passthrough import render_tokens
from ..target import Raw
from ..transformer import Transformer
from . import nodes as go
from .prelude import SHIMS

TYPE_MAP = {"int": "int", "str": "string", "bool": "bool",
            "float": "float64", "void": ""}


def _quote(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


class GoTransformer(Transformer):
    def __init__(self, level):
        super().__init__(level)
        self._declared: set[str] = set()   # untyped stages: names already ':='-declared

    # -- program assembly (Template Method hooks) --------------------------
    def build_program(self, program: ast.Program) -> go.GoFile:
        decls: list = []
        if program.expr_mode:
            self.used_features.add("println")
            body = go.GoBlock(stmts=[go.GoExprStmt(expr=go.GoCall(
                func="fmt.Println", args=[self.visit(program.items[0])]))])
            decls.append(go.GoFunc(name="main", body=body))
        elif self.level.functions:
            for item in program.items:
                if isinstance(item, ast.VarDecl):
                    node = self.visit(item)
                    node.blank_use = False        # globals may be unused in Go
                    decls.append(node)
                else:
                    decls.append(self.visit(item))
        else:
            stmts = [self.visit(s) for s in program.items]
            body = go.GoBlock(stmts=[s for s in stmts if s is not None])
            decls.append(go.GoFunc(name="main", body=body))
        return self._assemble(decls)

    def _assemble(self, decls: list) -> go.GoFile:
        imports: set[str] = set()
        prelude: list = []
        if "println" in self.used_features:
            imports.add("fmt")
        for feature, (needs, source) in SHIMS.items():
            if feature in self.used_features:
                imports.update(needs)
                prelude.append(Raw(text=source))
        return go.GoFile(imports=sorted(imports), prelude=prelude,
                         decls=decls)

    def transform_defect(self, defect: Defect, program: ast.Program,
                         source: str) -> go.GoFile:
        if isinstance(defect, ParseDefect):
            text = render_tokens(defect.tail_tokens)
        else:
            # lexical/preprocessor defects: the source itself carries the
            # invalid characters — keep them verbatim
            text = source.rstrip("\n")
        if not text.strip():
            # an empty expression program: the equivalent flaw is an
            # expression with no operand
            text = "()"
        body = go.GoBlock(stmts=[Raw(text=text)])
        return go.GoFile(decls=[go.GoFunc(name="main", body=body)])

    def declared_phase(self, program: ast.Program) -> Phase | None:
        defect = program.defect
        if defect is None:
            return None
        if defect.category is C.SEM_NEG_FACTORIAL:
            return Phase.RUN            # __fact panics when called
        return Phase.BUILD              # everything else fails `go build`

    # -- statements --------------------------------------------------------
    def visit_NoOp(self, node: ast.NoOp):
        return None

    def visit_Block(self, node: ast.Block) -> go.GoBlock:
        stmts = [self.visit(s) for s in node.stmts]
        return go.GoBlock(stmts=[s for s in stmts if s is not None])

    def visit_VarDecl(self, node: ast.VarDecl):
        init = self.visit(node.init) if node.init is not None else None
        if node.is_const:
            return go.GoConstDecl(name=node.name, init=init)
        go_type = TYPE_MAP.get(node.var_type, node.var_type)
        self._declared.add(node.name)
        return go.GoVarDecl(name=node.name, go_type=go_type, init=init)

    def visit_Assign(self, node: ast.Assign):
        expr = self.visit(node.expr)
        if isinstance(node.target, ast.FieldAccess):
            target = go.GoField(obj=go.GoName(name=node.target.obj.name),
                                name=node.target.fieldname)
            return go.GoAssign(target=target, expr=expr)
        name = node.target.name
        declare = (not self.level.types and name not in self._declared)
        if declare:
            self._declared.add(name)
        return go.GoAssign(target=go.GoName(name=name), expr=expr,
                           declare=declare, blank_use=declare)

    _BOOL_OPS = {"==", "<", ">", "&&", "||"}

    def _is_boolean_expr(self, node: ast.Node) -> bool:
        return (isinstance(node, ast.BoolLit)
                or (isinstance(node, ast.BinOp) and node.op in self._BOOL_OPS)
                or (isinstance(node, ast.UnOp) and node.op == "!"))

    def visit_Printf(self, node: ast.Printf):
        self.used_features.add("println")
        value = self.visit(node.expr)
        if self.level.bools_as_ints and self._is_boolean_expr(node.expr):
            self.used_features.add("b2i")
            value = go.GoCall(func="__b2i", args=[value])
        return go.GoExprStmt(expr=go.GoCall(func="fmt.Println", args=[value]))

    def visit_ExprStmt(self, node: ast.ExprStmt):
        return go.GoExprStmt(expr=self.visit(node.expr))

    def visit_If(self, node: ast.If) -> go.GoIf:
        return go.GoIf(cond=self.visit(node.cond),
                       then=self.visit(node.then),
                       other=self.visit(node.other)
                       if node.other is not None else None)

    def visit_While(self, node: ast.While) -> go.GoFor:
        return go.GoFor(cond=self.visit(node.cond),
                        body=self.visit(node.body))

    def visit_For(self, node: ast.For) -> go.GoFor:
        body = self.visit(node.body)
        if not isinstance(body, go.GoBlock):
            body = go.GoBlock(stmts=[body] if body is not None else [])
        return go.GoFor(init=self.visit(node.init), cond=self.visit(node.cond),
                        post=self.visit(node.step), body=body)

    def visit_Return(self, node: ast.Return) -> go.GoReturn:
        return go.GoReturn(expr=self.visit(node.expr))

    def visit_FuncDecl(self, node: ast.FuncDecl) -> go.GoFunc:
        self._declared = set(p.name for p in node.params)
        return go.GoFunc(
            name=node.name,
            params=[(p.name, TYPE_MAP.get(p.par_type, p.par_type))
                    for p in node.params],
            ret=TYPE_MAP.get(node.ret_type, node.ret_type),
            body=self.visit(node.body))

    def visit_StructDecl(self, node: ast.StructDecl) -> go.GoStruct:
        return go.GoStruct(
            name=node.name,
            fields=[(f.name, TYPE_MAP.get(f.field_type, f.field_type))
                    for f in node.fields])

    # -- expressions -------------------------------------------------------
    def visit_IntLit(self, node: ast.IntLit) -> go.GoLit:
        return go.GoLit(text=str(node.value))

    def visit_FloatLit(self, node: ast.FloatLit) -> go.GoLit:
        return go.GoLit(text=node.lexeme)

    def visit_StrLit(self, node: ast.StrLit) -> go.GoLit:
        return go.GoLit(text=_quote(node.value))

    def visit_BoolLit(self, node: ast.BoolLit) -> go.GoLit:
        return go.GoLit(text="true" if node.value else "false")

    def visit_Ident(self, node: ast.Ident) -> go.GoName:
        return go.GoName(name=node.name)

    def visit_FieldAccess(self, node: ast.FieldAccess) -> go.GoField:
        return go.GoField(obj=go.GoName(name=node.obj.name),
                          name=node.fieldname)

    def visit_Scanf(self, node: ast.Scanf) -> go.GoCall:
        self.used_features.add("scanf")
        return go.GoCall(func="__scanf")

    def visit_Call(self, node: ast.Call) -> go.GoCall:
        return go.GoCall(func=node.name,
                         args=[self.visit(a) for a in node.args])

    def visit_Ternary(self, node: ast.Ternary) -> go.GoCall:
        self.used_features.add("tern")
        return go.GoCall(func="__tern", args=[self.visit(node.cond),
                                              self.visit(node.then),
                                              self.visit(node.other)])

    def visit_Cast(self, node: ast.Cast):
        # runtime-typed cast helpers: the operand's static type is not
        # tracked here, and the course's (int) of a float rounds
        operand = self.visit(node.operand)
        feature, func = {"int": ("toInt", "__toInt"),
                         "float": ("toFloat", "__toFloat"),
                         "str": ("str", "__str"),
                         "bool": ("toBool", "__toBool")}[node.target_type]
        self.used_features.add(feature)
        return go.GoCall(func=func, args=[operand])

    def visit_UnOp(self, node: ast.UnOp) -> go.GoUn:
        return go.GoUn(op=node.op, operand=self.visit(node.operand))

    def visit_PostOp(self, node: ast.PostOp) -> go.GoCall:
        self.used_features.add("fact")
        return go.GoCall(func="__fact", args=[self.visit(node.operand)])

    def visit_BinOp(self, node: ast.BinOp):
        left, right = self.visit(node.left), self.visit(node.right)
        if node.op == "$":
            self.used_features.add("concat")
            return go.GoCall(func="__concat", args=[left, right])
        if node.op == "**":
            self.used_features.add("pow")
            return go.GoCall(func="__pow", args=[left, right])
        return go.GoBin(op=node.op, left=left, right=right)
