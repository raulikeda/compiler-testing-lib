"""Julia backend: one emitting class per IR node that differs from C.

Three facts about the target drive the classes below:

* Julia executes a script form by form, so ``Module`` keeps everything
  inside function bodies and ends with a ``main()`` call — a spliced
  syntax defect then aborts at load, before any output (parse-phase
  fidelity).  ``}`` is never valid Julia, so it serves as the parse
  marker.
* Declarations are typed (``local x::Int64``, typed fields, signatures,
  typed globals) so type defects can fail natively at run time;
  ``div_int`` spells as ``÷``; ``Scope`` spells as ``let`` (Julia's
  ``begin`` does not scope); ``end``-blocks replace braces.
* Where Julia is laxer than the course type system (``convert`` accepts
  ``Bool`` for ``Int64``; assigning an unknown name creates a local;
  ``const`` reassignment only warns), the equivalent classes materialize
  the IR's defect nodes as native failures: ``CheckType`` raises a
  TypeError via ``__chk``, ``UnresolvedRef`` probe-reads for an
  UndefVarError, and ``ConstDef`` lives in an immutable one-field box
  whose reassignment raises the immutable-struct error.
"""

from __future__ import annotations

from ..diagnostics import Defect, ErrorCategory as C, Phase, SemanticDefect
from ..semantic import types as T
from . import base
from .registry import register


@register
class Julia(base.Backend):
    name = "julia"
    ext = "jl"
    build_template = None               # run directly, no build step
    run_template = "julia {src_file}"
    docker_image = "compiler-testing-lib-julia"

    INDENT = "    "
    TYPES = {"int": "Int64", "str": "String", "bool": "Bool",
             "float": "Float64", "void": ""}

    SHIMS = {
        "sh_chk": ('__chk(::Type{T}, value) where {T} = value isa T ? value '
                   ': throw(TypeError(:assignment, "variable", T, value))'),
        "sh_scanf": "__scanf() = parse(Int64, readline())",
        "sh_toInt": ("__toInt(value) = value isa AbstractFloat ? "
                     "round(Int64, value) : Int64(value)"),
        "sh_toFloat": ("__toFloat(value) = value isa AbstractString ? "
                       "parse(Float64, value) : Float64(value)"),
        "sh_toBool": "__toBool(value) = value isa Bool ? value : value != 0",
    }

    def quote(self, text):
        escaped = (text.replace("\\", "\\\\").replace('"', '\\"')
                   .replace("$", "\\$"))
        return f'"{escaped}"'

    PARSE_MARKER = "}"                  # never valid Julia
    EMPTY_DEFECT = "}"

    def prepro_defect_text(self, source):
        # '#'-directives are comments in Julia: re-materialize as a parse
        # error at the directive's position
        return self.PARSE_MARKER

    def defect_program(self, text):
        body = "\n".join(self.INDENT + line if line else line
                         for line in text.splitlines())
        return f"function main()\n{body}\nend\n\nmain()\n"

    def phase_for(self, defect: Defect) -> Phase:
        if isinstance(defect, SemanticDefect):
            if defect.category is C.SEM_VAR_REDECLARED:
                return Phase.PARSE      # "multiple type declarations" at load
            return Phase.RUN
        return Phase.PARSE              # lex/parse/prepro: rejected at load


# -- expression equivalents ------------------------------------------------

@Julia.node
class Binary(base.Binary):
    TEMPLATES = dict(base.Binary.TEMPLATES, **{
        "div_int": "{left} ÷ {right}",  # C integer division truncates
        "div_float": "{left} / {right}",
        "xor": "xor({left}, {right})",
        "pow": "{left} ^ {right}",
        "concat": "string({left}, {right})",
    })
    PRECEDENCE = dict(base.Binary.PRECEDENCE, pow=6)


@Julia.node
class Unary(base.Unary):
    TEMPLATES = dict(base.Unary.TEMPLATES,
                     fact="factorial({operand})")   # DomainError on negatives


@Julia.node
class Cast(base.Cast):
    TEMPLATES = {"to_int": "__toInt({operand})",
                 "to_float": "__toFloat({operand})",
                 "to_str": "string({operand})",
                 "to_bool": "__toBool({operand})",
                 "bool_to_int": "Int({operand})"}
    SHIM_KEYS = {"to_int": ("sh_toInt",), "to_float": ("sh_toFloat",),
                 "to_bool": ("sh_toBool",)}


@Julia.node
class Ternary(base.Ternary):
    TEMPLATE = "({cond} ? {then} : {other})"


@Julia.node
class ReadInt(base.ReadInt):
    SHIM_KEYS = ("sh_scanf",)


@Julia.node
class CheckType(base.CheckType):
    def emit(self, ctx):
        # strict check: Julia's convert would accept e.g. Bool for Int64,
        # so raise a native TypeError at the diagnosed point
        ctx.use("sh_chk")
        return base.Emitted(f"__chk({ctx.type_of(self.expected)}, "
                            f"{self.operand.emit(ctx).text})")


@Julia.node
class ConstRef(base.ConstRef):
    def emit(self, ctx):
        return base.Emitted(f"__const_{self.name}.value")

    def emit_assign(self, ctx, expr):
        # a field of an immutable struct: raises the native
        # "immutable struct ... cannot be changed" error
        return [f"__const_{self.name}.value = {expr}"]


@Julia.node
class UnresolvedRef(base.UnresolvedRef):
    def emit_assign(self, ctx, expr):
        # Julia would silently create a local; probe-read the name first
        # so a native UndefVarError raises at the equivalent point
        return [self.name, f"{self.name} = {expr}"]


# -- statement equivalents -------------------------------------------------

@Julia.node
class DeclareLocal(base.DeclareLocal):
    def emit(self, ctx):
        init = self.init.emit(ctx).text if self.init is not None else None
        if T.is_struct(self.type) and init is None:
            init = f"{self.type.name}()"    # incomplete-init constructor
        decl = f"local {self.name}::{ctx.type_of(self.type)}"
        if init is not None:
            decl += f" = {init}"
        return [decl]


@Julia.node
class Print(base.Print):
    TEMPLATE = "println({value})"


@Julia.node
class If(base.If):
    def emit(self, ctx):
        out = [f"if {self.cond.emit(ctx).text}",
               *ctx.indent(ctx.stmts(self.then))]
        if self.other is not None:
            out += ["else", *ctx.indent(ctx.stmts(self.other))]
        return out + ["end"]


@Julia.node
class While(base.While):
    def emit(self, ctx):
        return [f"while {self.cond.emit(ctx).text}",
                *ctx.indent(ctx.stmts(self.body)), "end"]


@Julia.node
class Scope(base.Scope):
    def emit(self, ctx):
        # let, not begin: only let reproduces C block scoping
        return ["let", *ctx.indent(ctx.stmts(self.body)), "end"]


# -- declaration equivalents -----------------------------------------------

@Julia.node
class GlobalDef(base.GlobalDef):
    ZEROES = {"int": "0", "str": '""', "bool": "false", "float": "0.0"}

    def emit(self, ctx):
        init = self.init.emit(ctx).text if self.init is not None \
            else self.ZEROES[self.type]
        return [f"{self.name}::{ctx.type_of(self.type)} = {init}"]


@Julia.node
class ConstDef(base.ConstDef):
    def emit(self, ctx):
        # an immutable one-field box (see ConstRef)
        return [f"struct __Const_{self.name}", f"{ctx.backend.INDENT}value",
                "end",
                f"__const_{self.name} = "
                f"__Const_{self.name}({self.init.emit(ctx).text})", ""]


@Julia.node
class FuncDef(base.FuncDef):
    def emit(self, ctx):
        params = ", ".join(f"{n}::{ctx.type_of(t)}" for n, t in self.params)
        ret = ctx.type_of(self.ret)
        ret = f"::{ret}" if ret else ""
        body = ctx.stmts(self.body)
        assigned = self.assigned_globals()
        if assigned:
            body = [f"global {', '.join(assigned)}"] + body
        return [f"function {self.name}({params}){ret}", *ctx.indent(body),
                "end", ""]


@Julia.node
class StructDef(base.StructDef):
    def emit(self, ctx):
        rows = [f"{n}::{ctx.type_of(t)}" for n, t in self.fields]
        rows.append(f"{self.name}() = new()")   # declare-then-assign
        return [f"mutable struct {self.name}", *ctx.indent(rows), "end", ""]


@Julia.node
class Module(base.Module):
    def assemble(self, ctx, decls):
        out = ctx.backend.prelude() + decls
        while out and out[-1] == "":
            out.pop()
        return "\n".join(out + ["", "main()"]) + "\n"
