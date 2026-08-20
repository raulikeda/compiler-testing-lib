"""Julia — declarative language spec.

Mechanical equivalences from the course language to Julia, structured
around three facts about the target:

* Julia executes a script form by form, so everything runs inside
  ``function main() ... end`` + ``main()`` — a spliced syntax defect then
  aborts at load, before any output (parse-phase fidelity).  ``}`` is
  never valid Julia, so it serves as the parse marker.
* Every declaration is typed (``local x::Int64``, typed fields,
  signatures, typed globals) so type defects can fail natively at run
  time; ``÷`` keeps integer division C-like, ``let`` blocks reproduce C
  block scoping.
* Where Julia is laxer than the course (``convert`` accepts ``Bool`` for
  ``Int64``; assigning an unknown name just creates a local; ``const``
  reassignment only warns), the spec's check hooks inject a strict
  runtime check — a native TypeError/UndefVarError/immutable-struct error
  at the exact diagnosed point, and only there.
"""

from __future__ import annotations

from ..diagnostics import Defect, ErrorCategory as C, Phase, SemanticDefect
from .registry import register
from .spec import LanguageSpec


@register
class JuliaSpec(LanguageSpec):
    name = "julia"
    ext = "jl"
    build_template = None               # run directly, no build step
    run_template = "julia {src_file}"
    docker_image = "compiler-testing-lib-julia"

    INDENT = "    "
    TYPES = {"int": "Int64", "str": "String", "bool": "Bool",
             "float": "Float64", "void": ""}
    ZEROES = {"int": "0", "str": '""', "bool": "false", "float": "0.0"}

    BINOPS = dict(LanguageSpec.BINOPS, **{
        "/": "{left} ÷ {right}",        # C integer division truncates
        "/float": "{left} / {right}",   # ... unless an operand is float
        "^": "xor({left}, {right})",
        "**": "{left} ^ {right}",
        "$": "string({left}, {right})",
    })
    PRECEDENCE = dict(LanguageSpec.PRECEDENCE, **{"**": 6})

    FACTORIAL = "factorial({operand})"  # DomainError on negatives
    TERNARY = "({cond} ? {then} : {other})"
    CASTS = {"int": "__toInt({operand})", "float": "__toFloat({operand})",
             "str": "string({operand})", "bool": "__toBool({operand})"}
    SCANF = "__scanf()"
    PRINTF = "println({value})"
    PRINT_BOOL_AS_INT = "Int({value})"

    FEATURE_SHIMS = {"scanf": ("scanf",), "cast:int": ("toInt",),
                     "cast:float": ("toFloat",), "cast:bool": ("toBool",)}

    SHIMS = {
        "chk": ('__chk(::Type{T}, value) where {T} = value isa T ? value : '
                'throw(TypeError(:assignment, "variable", T, value))'),
        "scanf": "__scanf() = parse(Int64, readline())",
        "toInt": ("__toInt(value) = value isa AbstractFloat ? "
                  "round(Int64, value) : Int64(value)"),
        "toFloat": ("__toFloat(value) = value isa AbstractString ? "
                    "parse(Float64, value) : Float64(value)"),
        "toBool": "__toBool(value) = value isa Bool ? value : value != 0",
    }

    def quote(self, text):
        escaped = (text.replace("\\", "\\\\").replace('"', '\\"')
                   .replace("$", "\\$"))
        return f'"{escaped}"'

    # -- statement shapes --------------------------------------------------
    def _indent(self, lines):
        return [self.INDENT + line if line else line for line in lines]

    def var_decl(self, name, course_type, init, is_struct):
        jl_type = course_type if is_struct else self.TYPES[course_type]
        if init is None and is_struct:
            init = f"{course_type}()"   # incomplete-init inner constructor
        decl = f"local {name}::{jl_type}"
        if init is not None:
            decl += f" = {init}"
        return [decl]

    def block(self, body, scoped):
        if scoped:                      # C {} shadows; begin/end would not
            return ["let", *self._indent(body), "end"]
        return body

    def if_(self, cond, then, other):
        out = [f"if {cond}", *self._indent(then)]
        if other is not None:
            out += ["else", *self._indent(other)]
        return out + ["end"]

    def while_(self, cond, body):
        return [f"while {cond}", *self._indent(body), "end"]

    def function(self, name, params, ret_course_type, body, assigned_globals):
        sig = ", ".join(f"{n}::{self.TYPES[t]}" for n, t in params)
        ret = self.TYPES[ret_course_type]
        ret = f"::{ret}" if ret else ""
        if assigned_globals:
            body = [f"global {', '.join(assigned_globals)}"] + body
        return [f"function {name}({sig}){ret}", *self._indent(body),
                "end", ""]

    def struct(self, name, fields):
        rows = [f"{n}::{self.TYPES[t]}" for n, t in fields]
        rows.append(f"{name}() = new()")    # allow declare-then-assign
        return [f"mutable struct {name}", *self._indent(rows), "end", ""]

    def global_var(self, name, course_type, init):
        if init is None:
            init = self.ZEROES[course_type]
        return [f"{name}::{self.TYPES[course_type]} = {init}"]

    # x2.0 const: an immutable one-field box — reassignment raises the
    # native "immutable struct ... cannot be changed" error
    def const_topdecl(self, name, init):
        return [f"struct __Const_{name}", f"{self.INDENT}value", "end",
                f"__const_{name} = __Const_{name}({init})", ""]

    def const_decl(self, name, init):
        return []                       # lives in the hoisted box

    def const_read(self, name):
        return f"__const_{name}.value"

    def const_assign(self, name, expr):
        return [f"__const_{name}.value = {expr}"]

    def program(self, decls, main_body):
        out = self.prelude() + decls
        if main_body is not None:
            out += ["function main()", *self._indent(main_body), "end", ""]
        out += ["main()"]
        return "\n".join(out) + "\n"

    # -- defect materialization -------------------------------------------
    PARSE_MARKER = "}"                  # never valid Julia
    EMPTY_DEFECT = "}"

    def prepro_defect_text(self, source):
        # '#'-directives are comments in Julia: re-materialize as a parse
        # error at the directive's position
        return self.PARSE_MARKER

    def defect_program(self, text):
        return ("function main()\n"
                + "\n".join(self._indent(text.splitlines()))
                + "\nend\n\nmain()\n")

    def phase_for(self, defect: Defect) -> Phase:
        if isinstance(defect, SemanticDefect):
            if defect.category is C.SEM_VAR_REDECLARED:
                return Phase.PARSE      # "multiple type declarations" at load
            return Phase.RUN
        return Phase.PARSE              # lex/parse/prepro: rejected at load

    # -- strict checks where Julia is laxer than the course ----------------
    def check_assigned(self, expected_course_type, expr):
        self.use("chk")
        return f"__chk({self.TYPES[expected_course_type]}, {expr})"

    check_operand = check_assigned

    def assign_undeclared(self, name, expr):
        # Julia would silently create a local; probe-read the name first
        # so a native UndefVarError raises at the equivalent point
        return [name, f"{name} = {expr}"]
