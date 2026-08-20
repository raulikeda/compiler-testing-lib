"""The backend contract: an emitter over the typed IR.

:class:`IREmitter` walks the IR (:mod:`..ir.nodes`) and renders text.  The
traversal, precedence-driven parenthesization, shim bookkeeping and the
defect-passthrough path are implemented here once; the vocabulary a
concrete backend must cover is the IR's — small, stable, and independent
of the course language.  Defaults spell a neutral C-family syntax, so a
backend overrides only its deltas:

* tables — ``TYPES``, ``BINOPS``/``UNOPS`` (keyed by IR op names),
  ``PRECEDENCE``, ``CASTS``, ``PRINTF``, ``READ_INT``, ``SHIMS``;
* shape hooks — ``spell_declare``, ``spell_scope``, ``spell_if``,
  ``spell_while``, ``spell_func``, ``spell_struct``, ``spell_global``,
  ``assemble`` (whole file);
* defect strategy — ``phase_for``, ``PARSE_MARKER``, ``defect_program``,
  and the strict hooks (``spell_check``, ``spell_assign_unresolved``,
  ``const_*``) for targets laxer than the course type system.

Statement methods return lists of lines; expression methods return
:class:`Emitted` (text plus binding info).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..diagnostics import (Defect, ErrorCategory as C, ParseDefect, Phase,
                           SemanticDefect)
from ..ir import lower, nodes as ir
from ..semantic import types as T
from ..versions import LanguageLevel
from .passthrough import render_tokens


@dataclass
class Emitted:
    """A rendered expression: its text plus how tightly it binds."""
    text: str
    op: Optional[str] = None     # IR binary op if compound, else None
    unary: bool = False


class IREmitter:
    # -- identity / toolchain ---------------------------------------------
    name = "abstract"
    ext = ""
    build_template: str | None = None   # e.g. "go build -o {exe_file} {src_file}"
    run_template = ""                   # e.g. "{exe_file}" / "julia {src_file}"
    docker_image = ""

    # -- spelling tables (C-family defaults; keyed by IR names) ------------
    INDENT = "\t"
    TYPES: dict[str, str] = {"int": "int", "str": "str", "bool": "bool",
                             "float": "float", "void": ""}
    BOOL_LITS = ("true", "false")
    BINOPS: dict[str, str] = {
        "add": "{left} + {right}", "sub": "{left} - {right}",
        "mul": "{left} * {right}", "div_int": "{left} / {right}",
        "div_float": "{left} / {right}",
        "eq": "{left} == {right}", "lt": "{left} < {right}",
        "gt": "{left} > {right}", "and_": "{left} && {right}",
        "or_": "{left} || {right}", "xor": "{left} ^ {right}",
        "pow": "__pow({left}, {right})",
        "concat": "__concat({left}, {right})",
    }
    UNOPS: dict[str, str] = {"neg": "-{operand}", "pos": "+{operand}",
                             "not_": "!{operand}", "fact": "__fact({operand})"}
    PRECEDENCE: dict[str, int] = {"or_": 1, "and_": 2, "eq": 3, "lt": 3,
                                  "gt": 3, "add": 4, "sub": 4, "xor": 4,
                                  "div_int": 5, "div_float": 5, "mul": 5}
    ASSOCIATIVE = ("add", "mul", "and_", "or_")
    CASTS: dict[str, str] = {"to_int": "__toInt({operand})",
                             "to_float": "__toFloat({operand})",
                             "to_str": "__str({operand})",
                             "to_bool": "__toBool({operand})",
                             "bool_to_int": "__b2i({operand})"}
    TERNARY = "__tern({cond}, {then}, {other})"
    PRINTF = "__print({value})"
    READ_INT = "__scanf()"
    CALL = "{func}({args})"
    FIELD = "{obj}.{name}"

    SHIMS: dict[str, str] = {}
    FEATURE_SHIMS: dict[str, tuple[str, ...]] = {}

    def __init__(self, level: LanguageLevel):
        self.level = level
        self.used: set[str] = set()

    # -- small utilities ---------------------------------------------------
    def use(self, *keys: str) -> None:
        self.used.update(keys)

    def feature(self, key: str) -> None:
        self.used.add(key)
        self.used.update(self.FEATURE_SHIMS.get(key, ()))

    def quote(self, text: str) -> str:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def indent(self, lines: list[str]) -> list[str]:
        return [self.INDENT + line if line else line for line in lines]

    def type_of(self, ir_type) -> str:
        if T.is_struct(ir_type):
            return ir_type.name
        return self.TYPES.get(ir_type, str(ir_type))

    def prelude(self) -> list[str]:
        lines: list[str] = []
        for key, text in self.SHIMS.items():
            if key in self.used:
                lines.extend(text.splitlines())
                lines.append("")
        return lines

    @staticmethod
    def assigned_globals(func: ir.FuncDef) -> list[str]:
        """Names of globals a function assigns (some targets must declare
        them)."""
        found: set[str] = set()

        def walk(stmts):
            for stmt in stmts:
                if isinstance(stmt, ir.Assign) \
                        and isinstance(stmt.target, ir.GlobalRef):
                    found.add(stmt.target.name)
                for attr in ("then", "other", "body"):
                    inner = getattr(stmt, attr, None)
                    if isinstance(inner, list):
                        walk(inner)

        walk(func.body)
        return sorted(found)

    # ======================================================================
    # entry
    # ======================================================================
    def translate(self, program, source: str) -> tuple[str, Optional[Phase]]:
        defect = program.defect
        if defect is not None and not isinstance(defect, SemanticDefect):
            return (self._passthrough(defect, source), self.phase_for(defect))
        module = lower(program, self.level)
        code = self.emit_module(module)
        phase = self.phase_for(defect) if defect is not None else None
        return code, phase

    # -- passthrough for lexically/syntactically broken programs -----------
    PARSE_MARKER: str | None = None
    EMPTY_DEFECT = "()"

    def spell_token(self, tok) -> str | None:
        return None                   # None = keep the original lexeme

    def lex_defect_text(self, source: str) -> str:
        return source.rstrip("\n")    # invalid characters speak for themselves

    def prepro_defect_text(self, source: str) -> str:
        return source.rstrip("\n")

    def defect_program(self, text: str) -> str:
        raise NotImplementedError

    def phase_for(self, defect: Defect) -> Phase:
        raise NotImplementedError

    def _passthrough(self, defect: Defect, source: str) -> str:
        if isinstance(defect, ParseDefect):
            text = render_tokens(defect.tail_tokens,
                                 error_index=defect.error_index,
                                 marker=self.PARSE_MARKER,
                                 spell=self.spell_token)
        elif defect.category is C.PREPRO_INVALID_DEFINE:
            text = self.prepro_defect_text(source)
        else:
            text = self.lex_defect_text(source)
        if not text.strip():
            text = self.EMPTY_DEFECT
        return self.defect_program(text)

    # ======================================================================
    # module
    # ======================================================================
    def emit_module(self, module: ir.Module) -> str:
        decls: list[str] = []
        for struct in module.structs:
            decls.extend(self.spell_struct(struct))
        for const in module.consts:
            decls.extend(self.spell_const(const))
        for glob in module.globals:
            init = self.expr(glob.init).text if glob.init is not None else None
            decls.extend(self.spell_global(glob, init))
        for func in module.funcs:
            decls.extend(self.spell_func(func, self.stmts(func.body)))
        return self.assemble(module, decls)

    def assemble(self, module: ir.Module, decls: list[str]) -> str:
        raise NotImplementedError

    # ======================================================================
    # statements
    # ======================================================================
    def stmts(self, body: list) -> list[str]:
        lines: list[str] = []
        for stmt in body:
            method = getattr(self, f"stmt_{type(stmt).__name__}")
            lines.extend(method(stmt))
        return lines

    def stmt_DeclareLocal(self, node: ir.DeclareLocal) -> list[str]:
        init = self.expr(node.init).text if node.init is not None else None
        return self.spell_declare(node, init)

    def stmt_Assign(self, node: ir.Assign) -> list[str]:
        expr = self.expr(node.expr).text
        if isinstance(node.target, ir.UnresolvedRef):
            return self.spell_assign_unresolved(node.target.name, expr)
        if isinstance(node.target, ir.ConstRef):
            return self.spell_assign_const(node.target.name, expr)
        return [f"{self.expr(node.target).text} = {expr}"]

    def stmt_Print(self, node: ir.Print) -> list[str]:
        self.feature("printf")
        return [self.PRINTF.format(value=self.expr(node.expr).text)]

    def stmt_ExprStmt(self, node: ir.ExprStmt) -> list[str]:
        return [self.expr(node.expr).text]

    def stmt_If(self, node: ir.If) -> list[str]:
        return self.spell_if(self.expr(node.cond).text,
                             self.stmts(node.then),
                             self.stmts(node.other)
                             if node.other is not None else None)

    def stmt_While(self, node: ir.While) -> list[str]:
        return self.spell_while(self.expr(node.cond).text,
                                self.stmts(node.body))

    def stmt_Scope(self, node: ir.Scope) -> list[str]:
        return self.spell_scope(self.stmts(node.body))

    def stmt_Return(self, node: ir.Return) -> list[str]:
        if node.expr is None:
            return ["return"]
        return [f"return {self.expr(node.expr).text}"]

    # -- shape hooks (C-family defaults) -----------------------------------
    def spell_declare(self, node: ir.DeclareLocal,
                      init: str | None) -> list[str]:
        decl = f"{self.type_of(node.type)} {node.name}"
        if init is not None:
            decl += f" = {init}"
        return [decl]

    def spell_assign_unresolved(self, name: str, expr: str) -> list[str]:
        return [f"{name} = {expr}"]

    def spell_assign_const(self, name: str, expr: str) -> list[str]:
        return [f"{name} = {expr}"]

    def spell_if(self, cond: str, then: list[str],
                 other: list[str] | None) -> list[str]:
        out = [f"if {cond} {{", *self.indent(then)]
        if other is not None:
            out += ["} else {", *self.indent(other)]
        return out + ["}"]

    def spell_while(self, cond: str, body: list[str]) -> list[str]:
        return [f"while {cond} {{", *self.indent(body), "}"]

    def spell_scope(self, body: list[str]) -> list[str]:
        return ["{", *self.indent(body), "}"]

    def spell_func(self, func: ir.FuncDef, body: list[str]) -> list[str]:
        params = ", ".join(f"{self.type_of(t)} {n}" for n, t in func.params)
        ret = self.type_of(func.ret)
        head = f"{ret} {func.name}({params})".strip()
        return [f"{head} {{", *self.indent(body), "}", ""]

    def spell_struct(self, struct: ir.StructDef) -> list[str]:
        rows = [f"{self.type_of(t)} {n}" for n, t in struct.fields]
        return [f"struct {struct.name} {{", *self.indent(rows), "}", ""]

    def spell_global(self, glob: ir.GlobalDef,
                     init: str | None) -> list[str]:
        decl = f"{self.type_of(glob.type)} {glob.name}"
        if init is not None:
            decl += f" = {init}"
        return [decl]

    def spell_const(self, const: ir.ConstDef) -> list[str]:
        return [f"const {const.name} = {self.expr(const.init).text}"]

    def const_read(self, name: str) -> str:
        return name

    # -- strict check: targets laxer than the course override --------------
    def spell_check(self, expected, operand: str) -> str:
        return operand      # statically-typed targets fail natively

    # ======================================================================
    # expressions
    # ======================================================================
    def expr(self, node: ir.IRNode) -> Emitted:
        method = getattr(self, f"expr_{type(node).__name__}")
        return method(node)

    def expr_IntConst(self, node: ir.IntConst) -> Emitted:
        return Emitted(str(node.value))

    def expr_FloatConst(self, node: ir.FloatConst) -> Emitted:
        return Emitted(node.lexeme)

    def expr_StrConst(self, node: ir.StrConst) -> Emitted:
        return Emitted(self.quote(node.value))

    def expr_BoolConst(self, node: ir.BoolConst) -> Emitted:
        return Emitted(self.BOOL_LITS[0 if node.value else 1])

    def expr_LocalRef(self, node: ir.LocalRef) -> Emitted:
        return Emitted(node.name)

    expr_GlobalRef = expr_LocalRef
    expr_UnresolvedRef = expr_LocalRef

    def expr_ConstRef(self, node: ir.ConstRef) -> Emitted:
        return Emitted(self.const_read(node.name))

    def expr_FieldRef(self, node: ir.FieldRef) -> Emitted:
        return Emitted(self.FIELD.format(obj=node.obj, name=node.fieldname))

    def expr_ReadInt(self, node: ir.ReadInt) -> Emitted:
        self.feature("scanf")
        return Emitted(self.READ_INT)

    def expr_Call(self, node: ir.Call) -> Emitted:
        args = ", ".join(self.expr(a).text for a in node.args)
        return Emitted(self.CALL.format(func=node.name, args=args))

    def expr_Ternary(self, node: ir.Ternary) -> Emitted:
        self.feature("ternary")
        return Emitted(self.TERNARY.format(cond=self.expr(node.cond).text,
                                           then=self.expr(node.then).text,
                                           other=self.expr(node.other).text))

    def expr_Cast(self, node: ir.Cast) -> Emitted:
        self.feature(node.kind)
        return Emitted(self.CASTS[node.kind].format(
            operand=self.expr(node.operand).text))

    def expr_CheckType(self, node: ir.CheckType) -> Emitted:
        return Emitted(self.spell_check(node.expected,
                                        self.expr(node.operand).text))

    def expr_Unary(self, node: ir.Unary) -> Emitted:
        operand = self.expr(node.operand)
        text = operand.text
        if operand.op is not None or operand.unary:
            text = f"({text})"
        if node.op == "fact":
            self.feature("fact")
            return Emitted(self.UNOPS["fact"].format(operand=text))
        return Emitted(self.UNOPS[node.op].format(operand=text), unary=True)

    def expr_Binary(self, node: ir.Binary) -> Emitted:
        left = self._operand(node.left, node.op, is_right=False)
        right = self._operand(node.right, node.op, is_right=True)
        self.feature(node.op)
        return Emitted(self.BINOPS[node.op].format(left=left, right=right),
                       op=node.op)

    def _operand(self, child: ir.IRNode, parent_op: str,
                 is_right: bool) -> str:
        emitted = self.expr(child)
        if emitted.unary:
            return f"({emitted.text})"
        if emitted.op is None:
            return emitted.text
        prec = self.PRECEDENCE
        if emitted.op not in prec or parent_op not in prec:
            return emitted.text       # call-rendered operators are atomic
        child_prec, parent_prec = prec[emitted.op], prec[parent_op]
        same_op_chain = (emitted.op == parent_op and not is_right
                         and parent_op in self.ASSOCIATIVE)
        if child_prec < parent_prec or (child_prec == parent_prec
                                        and not same_op_chain):
            return f"({emitted.text})"
        return emitted.text
