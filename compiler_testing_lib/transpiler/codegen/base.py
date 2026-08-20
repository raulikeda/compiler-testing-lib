"""The backend contract: one emitting class per IR node.

The IR (:mod:`..ir.nodes`) is pure, target-neutral data.  This module
gives every IR node a default *emitting* subclass with the same generic
name (``class While(ir.While)`` ...) spelling a neutral C-family syntax.
A backend module defines its :class:`Backend` (identity, type table,
shims, defect strategy) plus its own equivalents — ``class
While(base.While)`` — for exactly the nodes whose spelling differs.
Before emission, :func:`rebind` swaps each lowered node's class for the
backend's equivalent (node classes add behavior, never fields, which is
what makes the in-place swap sound).

Statement ``emit(ctx)`` returns a list of lines; expression ``emit(ctx)``
returns an :class:`Emitted` (text plus binding info, used for
precedence-driven parenthesization).  Cross-node state (which shims got
used, indentation, the backend's tables) rides in the :class:`Context`.
"""

from __future__ import annotations

import dataclasses
import inspect
from dataclasses import dataclass
from typing import Optional

from ..diagnostics import Defect, ErrorCategory as C, ParseDefect, Phase, SemanticDefect
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


class Context:
    """Emission state shared across nodes: the backend and its bookkeeping."""

    def __init__(self, backend: "Backend"):
        self.backend = backend
        self.level = backend.level

    # thin delegates, so node code reads naturally
    def use(self, *shims: str) -> None:
        self.backend.used.update(shims)

    def type_of(self, ir_type) -> str:
        return self.backend.type_of(ir_type)

    def quote(self, text: str) -> str:
        return self.backend.quote(text)

    def indent(self, lines: list[str]) -> list[str]:
        indent = self.backend.INDENT
        return [indent + line if line else line for line in lines]

    def stmts(self, body: list) -> list[str]:
        lines: list[str] = []
        for stmt in body:
            lines.extend(stmt.emit(self))
        return lines


class Backend:
    """A target language: identity, toolchain, tables, defect strategy.

    Node spellings live on the backend module's node classes; register the
    backend with ``@register`` and build its ``NODES`` table with
    ``node_table(__name__)`` after the class definitions.
    """

    name = "abstract"
    ext = ""
    build_template: str | None = None   # e.g. "go build -o {exe_file} {src_file}"
    run_template = ""                   # e.g. "{exe_file}" / "julia {src_file}"
    docker_image = ""

    INDENT = "\t"
    TYPES: dict[str, str] = {"int": "int", "str": "str", "bool": "bool",
                             "float": "float", "void": ""}
    SHIMS: dict[str, str] = {}          # key -> source, emitted only when used
    NODES: dict[str, type] = {}         # generic node name -> emitting class

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # every backend starts from the default (C-family) emitting classes
        cls.NODES = dict(_default_nodes())

    @classmethod
    def node(cls, node_cls: type) -> type:
        """Class decorator: registers a backend's equivalent for an IR node
        (keyed by its generic name), replacing the default."""
        cls.NODES[node_cls.__name__] = node_cls
        return node_cls

    def __init__(self, level: LanguageLevel):
        self.level = level
        self.used: set[str] = set()

    def type_of(self, ir_type) -> str:
        if T.is_struct(ir_type):
            return ir_type.name
        return self.TYPES.get(ir_type, str(ir_type))

    def quote(self, text: str) -> str:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def prelude(self) -> list[str]:
        lines: list[str] = []
        for key, text in self.SHIMS.items():
            if key in self.used:
                lines.extend(text.splitlines())
                lines.append("")
        return lines

    # -- entry -------------------------------------------------------------
    def translate(self, program, source: str) -> tuple[str, Optional[Phase]]:
        defect = program.defect
        if defect is not None and not isinstance(defect, SemanticDefect):
            return self._passthrough(defect, source), self.phase_for(defect)
        module = lower(program, self.level)
        rebind(module, self.NODES)
        code = module.emit(Context(self))
        phase = self.phase_for(defect) if defect is not None else None
        return code, phase

    # -- passthrough for lexically/syntactically broken programs -----------
    PARSE_MARKER: str | None = None   # spliced before the offending token
    EMPTY_DEFECT = "()"               # stands in for a missing expression

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


# ==========================================================================
# rebinding: swap lowered IR nodes onto a backend's emitting classes
# ==========================================================================

def _default_nodes() -> dict[str, type]:
    """The default emitting classes of this module, by generic node name."""
    return {name: cls for name, cls in globals().items()
            if inspect.isclass(cls) and issubclass(cls, ir.IRNode)}


def rebind(node, table: dict[str, type]) -> None:
    if not isinstance(node, ir.IRNode):
        return
    for field in dataclasses.fields(node):
        value = getattr(node, field.name)
        if isinstance(value, ir.IRNode):
            rebind(value, table)
        elif isinstance(value, list):
            for item in value:
                rebind(item, table)
    target = table.get(type(node).__name__)
    if target is not None:
        node.__class__ = target


# ==========================================================================
# expressions — default (C-family) emitting classes
# ==========================================================================

class IntConst(ir.IntConst):
    def emit(self, ctx: Context) -> Emitted:
        return Emitted(str(self.value))


class FloatConst(ir.FloatConst):
    def emit(self, ctx: Context) -> Emitted:
        return Emitted(self.lexeme)


class StrConst(ir.StrConst):
    def emit(self, ctx: Context) -> Emitted:
        return Emitted(ctx.quote(self.value))


class BoolConst(ir.BoolConst):
    TRUE, FALSE = "true", "false"

    def emit(self, ctx: Context) -> Emitted:
        return Emitted(self.TRUE if self.value else self.FALSE)


class LocalRef(ir.LocalRef):
    def emit(self, ctx: Context) -> Emitted:
        return Emitted(self.name)

    def emit_assign(self, ctx: Context, expr: str) -> list[str]:
        return [f"{self.emit(ctx).text} = {expr}"]


class GlobalRef(ir.GlobalRef, LocalRef):
    pass


class ConstRef(ir.ConstRef, LocalRef):
    pass


class UnresolvedRef(ir.UnresolvedRef, LocalRef):
    """An undeclared name: default spelling is verbatim — statically-
    resolved targets fail natively; laxer targets override."""


class FieldRef(ir.FieldRef):
    def emit(self, ctx: Context) -> Emitted:
        return Emitted(f"{self.obj}.{self.fieldname}")

    def emit_assign(self, ctx: Context, expr: str) -> list[str]:
        return [f"{self.emit(ctx).text} = {expr}"]


class Binary(ir.Binary):
    TEMPLATES = {
        "add": "{left} + {right}", "sub": "{left} - {right}",
        "mul": "{left} * {right}", "div_int": "{left} / {right}",
        "div_float": "{left} / {right}",
        "eq": "{left} == {right}", "lt": "{left} < {right}",
        "gt": "{left} > {right}", "and_": "{left} && {right}",
        "or_": "{left} || {right}", "xor": "{left} ^ {right}",
        "pow": "__pow({left}, {right})",
        "concat": "__concat({left}, {right})",
    }
    # TARGET-language precedence: parenthesize when it would regroup the
    # source tree; operators rendered as calls have no entry (atomic)
    PRECEDENCE = {"or_": 1, "and_": 2, "eq": 3, "lt": 3, "gt": 3,
                  "add": 4, "sub": 4, "xor": 4,
                  "div_int": 5, "div_float": 5, "mul": 5}
    ASSOCIATIVE = ("add", "mul", "and_", "or_")
    SHIM_KEYS: dict[str, tuple[str, ...]] = {}   # op -> shims it needs

    def emit(self, ctx: Context) -> Emitted:
        left = self._operand(ctx, self.left, is_right=False)
        right = self._operand(ctx, self.right, is_right=True)
        ctx.use(*self.SHIM_KEYS.get(self.op, ()))
        return Emitted(self.TEMPLATES[self.op].format(left=left, right=right),
                       op=self.op)

    def _operand(self, ctx: Context, child, is_right: bool) -> str:
        emitted = child.emit(ctx)
        if emitted.unary:
            return f"({emitted.text})"
        if emitted.op is None:
            return emitted.text
        prec = self.PRECEDENCE
        if emitted.op not in prec or self.op not in prec:
            return emitted.text
        child_prec, parent_prec = prec[emitted.op], prec[self.op]
        same_op_chain = (emitted.op == self.op and not is_right
                         and self.op in self.ASSOCIATIVE)
        if child_prec < parent_prec or (child_prec == parent_prec
                                        and not same_op_chain):
            return f"({emitted.text})"
        return emitted.text


class Unary(ir.Unary):
    TEMPLATES = {"neg": "-{operand}", "pos": "+{operand}",
                 "not_": "!{operand}", "fact": "__fact({operand})"}
    SHIM_KEYS: dict[str, tuple[str, ...]] = {}

    def emit(self, ctx: Context) -> Emitted:
        operand = self.operand.emit(ctx)
        text = operand.text
        if operand.op is not None or operand.unary:
            text = f"({text})"
        ctx.use(*self.SHIM_KEYS.get(self.op, ()))
        return Emitted(self.TEMPLATES[self.op].format(operand=text),
                       unary=self.op != "fact")


class Call(ir.Call):
    def emit(self, ctx: Context) -> Emitted:
        args = ", ".join(a.emit(ctx).text for a in self.args)
        return Emitted(f"{self.name}({args})")


class ReadInt(ir.ReadInt):
    TEMPLATE = "__scanf()"
    SHIM_KEYS: tuple[str, ...] = ()

    def emit(self, ctx: Context) -> Emitted:
        ctx.use(*self.SHIM_KEYS)
        return Emitted(self.TEMPLATE)


class Cast(ir.Cast):
    TEMPLATES = {"to_int": "__toInt({operand})",
                 "to_float": "__toFloat({operand})",
                 "to_str": "__str({operand})",
                 "to_bool": "__toBool({operand})",
                 "bool_to_int": "__b2i({operand})"}
    SHIM_KEYS: dict[str, tuple[str, ...]] = {}

    def emit(self, ctx: Context) -> Emitted:
        ctx.use(*self.SHIM_KEYS.get(self.kind, ()))
        return Emitted(self.TEMPLATES[self.kind].format(
            operand=self.operand.emit(ctx).text))


class Ternary(ir.Ternary):
    TEMPLATE = "__tern({cond}, {then}, {other})"
    SHIM_KEYS: tuple[str, ...] = ()

    def emit(self, ctx: Context) -> Emitted:
        ctx.use(*self.SHIM_KEYS)
        return Emitted(self.TEMPLATE.format(cond=self.cond.emit(ctx).text,
                                            then=self.then.emit(ctx).text,
                                            other=self.other.emit(ctx).text))


class CheckType(ir.CheckType):
    """The diagnosed type violation.  Default: emit the operand unchanged —
    a statically-typed target's own compiler rejects it.  Targets laxer
    than the course override with a strict runtime check."""

    def emit(self, ctx: Context) -> Emitted:
        return self.operand.emit(ctx)


# ==========================================================================
# statements — default (C-family) emitting classes
# ==========================================================================

class DeclareLocal(ir.DeclareLocal):
    def emit(self, ctx: Context) -> list[str]:
        init = self.init.emit(ctx).text if self.init is not None else None
        decl = f"{ctx.type_of(self.type)} {self.name}"
        if init is not None:
            decl += f" = {init}"
        return [decl]


class Assign(ir.Assign):
    def emit(self, ctx: Context) -> list[str]:
        # how a target is assigned is the target node's business
        return self.target.emit_assign(ctx, self.expr.emit(ctx).text)


class Print(ir.Print):
    TEMPLATE = "__print({value})"
    SHIM_KEYS: tuple[str, ...] = ()

    def emit(self, ctx: Context) -> list[str]:
        ctx.use(*self.SHIM_KEYS)
        return [self.TEMPLATE.format(value=self.expr.emit(ctx).text)]


class ExprStmt(ir.ExprStmt):
    def emit(self, ctx: Context) -> list[str]:
        return [self.expr.emit(ctx).text]


class If(ir.If):
    def emit(self, ctx: Context) -> list[str]:
        out = [f"if {self.cond.emit(ctx).text} {{",
               *ctx.indent(ctx.stmts(self.then))]
        if self.other is not None:
            out += ["} else {", *ctx.indent(ctx.stmts(self.other))]
        return out + ["}"]


class While(ir.While):
    def emit(self, ctx: Context) -> list[str]:
        return [f"while {self.cond.emit(ctx).text} {{",
                *ctx.indent(ctx.stmts(self.body)), "}"]


class Scope(ir.Scope):
    def emit(self, ctx: Context) -> list[str]:
        return ["{", *ctx.indent(ctx.stmts(self.body)), "}"]


class Return(ir.Return):
    def emit(self, ctx: Context) -> list[str]:
        if self.expr is None:
            return ["return"]
        return [f"return {self.expr.emit(ctx).text}"]


# ==========================================================================
# declarations — default (C-family) emitting classes
# ==========================================================================

class StructDef(ir.StructDef):
    def emit(self, ctx: Context) -> list[str]:
        rows = [f"{ctx.type_of(t)} {n}" for n, t in self.fields]
        return [f"struct {self.name} {{", *ctx.indent(rows), "}", ""]


class GlobalDef(ir.GlobalDef):
    def emit(self, ctx: Context) -> list[str]:
        init = self.init.emit(ctx).text if self.init is not None else None
        decl = f"{ctx.type_of(self.type)} {self.name}"
        if init is not None:
            decl += f" = {init}"
        return [decl]


class ConstDef(ir.ConstDef):
    def emit(self, ctx: Context) -> list[str]:
        return [f"const {self.name} = {self.init.emit(ctx).text}"]


class FuncDef(ir.FuncDef):
    def emit(self, ctx: Context) -> list[str]:
        params = ", ".join(f"{ctx.type_of(t)} {n}" for n, t in self.params)
        ret = ctx.type_of(self.ret)
        head = f"{ret} {self.name}({params})".strip()
        return [f"{head} {{", *ctx.indent(ctx.stmts(self.body)), "}", ""]

    def assigned_globals(self) -> list[str]:
        """Names of globals this function assigns (some targets must
        declare them)."""
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

        walk(self.body)
        return sorted(found)


class Module(ir.Module):
    def emit(self, ctx: Context) -> str:
        decls: list[str] = []
        for group in (self.structs, self.consts, self.globals, self.funcs):
            for decl in group:
                decls.extend(decl.emit(ctx))
        return self.assemble(ctx, decls)

    def assemble(self, ctx: Context, decls: list[str]) -> str:
        out = ctx.backend.prelude() + decls
        while out and out[-1] == "":
            out.pop()
        return "\n".join(out) + "\n"
