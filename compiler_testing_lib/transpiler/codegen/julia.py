"""Julia backend: an IR emitter.

Three facts about the target drive the deltas from the C-family defaults:

* Julia executes a script form by form, so ``assemble`` keeps everything
  inside function bodies and ends with a ``main()`` call — a spliced
  syntax defect then aborts at load, before any output (parse-phase
  fidelity).  ``}`` is never valid Julia, so it serves as the parse
  marker.
* Declarations are typed (``local x::Int64``, typed fields, signatures,
  typed globals) so type defects can fail natively at run time; the IR's
  ``div_int`` spells as ``÷``; ``Scope`` spells as ``let`` (Julia's
  ``begin`` does not scope).
* Where Julia is laxer than the course type system (``convert`` accepts
  ``Bool`` for ``Int64``; assigning an unknown name creates a local;
  ``const`` reassignment only warns), the strict hooks materialize the
  IR's ``CheckType``/``UnresolvedRef``/``ConstDef`` as native failures:
  ``__chk`` raises a TypeError, a probe-read raises an UndefVarError, and
  a const lives in an immutable one-field box whose reassignment raises
  the immutable-struct error.
"""

from __future__ import annotations

from ..diagnostics import Defect, ErrorCategory as C, Phase, SemanticDefect
from ..semantic import types as T
from .base import IREmitter
from .registry import register


@register
class JuliaEmitter(IREmitter):
    name = "julia"
    ext = "jl"
    build_template = None               # run directly, no build step
    run_template = "julia {src_file}"
    docker_image = "compiler-testing-lib-julia"

    INDENT = "    "
    TYPES = {"int": "Int64", "str": "String", "bool": "Bool",
             "float": "Float64", "void": ""}
    ZEROES = {"int": "0", "str": '""', "bool": "false", "float": "0.0"}

    BINOPS = dict(IREmitter.BINOPS, **{
        "div_int": "{left} ÷ {right}",  # C integer division truncates
        "div_float": "{left} / {right}",
        "xor": "xor({left}, {right})",
        "pow": "{left} ^ {right}",
        "concat": "string({left}, {right})",
    })
    PRECEDENCE = dict(IREmitter.PRECEDENCE, **{"pow": 6})
    UNOPS = dict(IREmitter.UNOPS,
                 fact="factorial({operand})")   # DomainError on negatives
    TERNARY = "({cond} ? {then} : {other})"
    CASTS = {"to_int": "__toInt({operand})", "to_float": "__toFloat({operand})",
             "to_str": "string({operand})", "to_bool": "__toBool({operand})",
             "bool_to_int": "Int({operand})"}
    PRINTF = "println({value})"
    READ_INT = "__scanf()"

    FEATURE_SHIMS = {"scanf": ("sh_scanf",), "to_int": ("sh_toInt",),
                     "to_float": ("sh_toFloat",), "to_bool": ("sh_toBool",)}
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

    # -- shapes ------------------------------------------------------------
    def spell_declare(self, node, init):
        if T.is_struct(node.type) and init is None:
            init = f"{node.type.name}()"    # incomplete-init constructor
        decl = f"local {node.name}::{self.type_of(node.type)}"
        if init is not None:
            decl += f" = {init}"
        return [decl]

    def spell_scope(self, body):
        return ["let", *self.indent(body), "end"]   # begin/end would not scope

    def spell_if(self, cond, then, other):
        out = [f"if {cond}", *self.indent(then)]
        if other is not None:
            out += ["else", *self.indent(other)]
        return out + ["end"]

    def spell_while(self, cond, body):
        return [f"while {cond}", *self.indent(body), "end"]

    def spell_func(self, func, body):
        params = ", ".join(f"{n}::{self.type_of(t)}" for n, t in func.params)
        ret = self.type_of(func.ret)
        ret = f"::{ret}" if ret else ""
        assigned = self.assigned_globals(func)
        if assigned:
            body = [f"global {', '.join(assigned)}"] + body
        return [f"function {func.name}({params}){ret}", *self.indent(body),
                "end", ""]

    def spell_struct(self, struct):
        rows = [f"{n}::{self.type_of(t)}" for n, t in struct.fields]
        rows.append(f"{struct.name}() = new()")     # declare-then-assign
        return [f"mutable struct {struct.name}", *self.indent(rows),
                "end", ""]

    def spell_global(self, glob, init):
        if init is None:
            init = self.ZEROES[glob.type]
        return [f"{glob.name}::{self.type_of(glob.type)} = {init}"]

    # x2.0 const: an immutable one-field box — reassignment raises the
    # native "immutable struct ... cannot be changed" error
    def spell_const(self, const):
        return [f"struct __Const_{const.name}", f"{self.INDENT}value", "end",
                f"__const_{const.name} = "
                f"__Const_{const.name}({self.expr(const.init).text})", ""]

    def const_read(self, name):
        return f"__const_{name}.value"

    def spell_assign_const(self, name, expr):
        return [f"__const_{name}.value = {expr}"]

    def assemble(self, module, decls):
        out = self.prelude() + decls
        while out and out[-1] == "":
            out.pop()
        return "\n".join(out + ["", "main()"]) + "\n"

    # -- strict checks where Julia is laxer than the course ----------------
    def spell_check(self, expected, operand):
        self.use("sh_chk")
        return f"__chk({self.type_of(expected)}, {operand})"

    def spell_assign_unresolved(self, name, expr):
        # Julia would silently create a local; probe-read the name first
        # so a native UndefVarError raises at the equivalent point
        return [name, f"{name} = {expr}"]

    # -- defect materialization -------------------------------------------
    PARSE_MARKER = "}"                  # never valid Julia
    EMPTY_DEFECT = "}"

    def prepro_defect_text(self, source):
        # '#'-directives are comments in Julia: re-materialize as a parse
        # error at the directive's position
        return self.PARSE_MARKER

    def defect_program(self, text):
        return ("function main()\n"
                + "\n".join(self.indent(text.splitlines()))
                + "\nend\n\nmain()\n")

    def phase_for(self, defect: Defect) -> Phase:
        if isinstance(defect, SemanticDefect):
            if defect.category is C.SEM_VAR_REDECLARED:
                return Phase.PARSE      # "multiple type declarations" at load
            return Phase.RUN
        return Phase.PARSE              # lex/parse/prepro: rejected at load
