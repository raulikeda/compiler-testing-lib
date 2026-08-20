"""Go backend: one emitting class per IR node that differs from C.

Go's surface IS the C-family default for most constructs, so the classes
below cover only the real deltas: declarations (``var`` + a ``_ = x``
blank use, because Go rejects declared-and-not-used variables and the
course language does not), ``for``-spelled loops, function/struct syntax,
and file assembly with imports.

Defects need no special classes at all — the faithful typed translation
is what makes ``go build`` fail natively (wrong initializer types,
unresolved names, constant zero divisors, redeclarations, bad calls), so
``CheckType``/``UnresolvedRef`` keep their transparent defaults and no
parse marker is needed (C-shaped token soup is never valid Go).
"""

from __future__ import annotations

from ..diagnostics import Defect, ErrorCategory as C, Phase
from . import base
from .registry import register


@register
class Go(base.Backend):
    name = "go"
    ext = "go"
    build_template = "go build -o {exe_file} {src_file}"
    run_template = "{exe_file}"
    docker_image = "compiler-testing-lib-go"

    TYPES = {"int": "int", "str": "string", "bool": "bool",
             "float": "float64", "void": ""}
    IMPORTS = {"printf": ("fmt",), "sh_concat": ("fmt",), "sh_str": ("fmt",),
               "sh_scanf": ("bufio", "os", "strconv"), "sh_toInt": ("math",),
               "sh_toFloat": ("strconv",)}

    SHIMS = {
        "sh_scanf": '''\
var __in = bufio.NewReader(os.Stdin)

func __scanf() int {
\tline, _ := __in.ReadString('\\n')
\tfor len(line) > 0 && (line[len(line)-1] == '\\n' || line[len(line)-1] == '\\r') {
\t\tline = line[:len(line)-1]
\t}
\tvalue, _ := strconv.Atoi(line)
\treturn value
}''',
        "sh_concat": '''\
func __concat(parts ...any) string {
\tout := ""
\tfor _, part := range parts {
\t\tout += fmt.Sprint(part)
\t}
\treturn out
}''',
        "sh_pow": '''\
func __pow(base, exp int) int {
\tresult := 1
\tfor i := 0; i < exp; i++ {
\t\tresult *= base
\t}
\treturn result
}''',
        "sh_fact": '''\
func __fact(n int) int {
\tif n < 0 {
\t\tpanic("factorial of negative number")
\t}
\tresult := 1
\tfor i := 2; i <= n; i++ {
\t\tresult *= i
\t}
\treturn result
}''',
        "sh_tern": '''\
func __tern(cond bool, a, b int) int {
\tif cond {
\t\treturn a
\t}
\treturn b
}''',
        "sh_str": '''\
func __str(value any) string {
\treturn fmt.Sprint(value)
}''',
        "sh_b2i": '''\
func __b2i(value bool) int {
\tif value {
\t\treturn 1
\t}
\treturn 0
}''',
        "sh_toInt": '''\
func __toInt(value any) int {
\tswitch v := value.(type) {
\tcase float64:
\t\treturn int(math.Round(v))
\tdefault:
\t\treturn v.(int)
\t}
}''',
        "sh_toFloat": '''\
func __toFloat(value any) float64 {
\tswitch v := value.(type) {
\tcase int:
\t\treturn float64(v)
\tcase string:
\t\tparsed, _ := strconv.ParseFloat(v, 64)
\t\treturn parsed
\tdefault:
\t\treturn v.(float64)
\t}
}''',
        "sh_toBool": '''\
func __toBool(value any) bool {
\tswitch v := value.(type) {
\tcase float64:
\t\treturn v != 0
\tcase int:
\t\treturn v != 0
\tdefault:
\t\treturn v.(bool)
\t}
}''',
    }

    def defect_program(self, text):
        body = "\n".join("\t" + line if line else line
                         for line in text.splitlines())
        return f"package main\n\nfunc main() {{\n{body}\n}}\n"

    def phase_for(self, defect: Defect) -> Phase:
        if defect.category is C.SEM_NEG_FACTORIAL:
            return Phase.RUN            # __fact panics when called
        return Phase.BUILD              # everything else fails `go build`


# -- expression equivalents ------------------------------------------------

@Go.node
class Binary(base.Binary):
    SHIM_KEYS = {"concat": ("sh_concat",), "pow": ("sh_pow",)}
    # templates and precedence: the C-family defaults are Go's own


@Go.node
class Unary(base.Unary):
    SHIM_KEYS = {"fact": ("sh_fact",)}


@Go.node
class Cast(base.Cast):
    SHIM_KEYS = {"to_int": ("sh_toInt",), "to_float": ("sh_toFloat",),
                 "to_str": ("sh_str",), "to_bool": ("sh_toBool",),
                 "bool_to_int": ("sh_b2i",)}


@Go.node
class Ternary(base.Ternary):
    SHIM_KEYS = ("sh_tern",)


@Go.node
class ReadInt(base.ReadInt):
    SHIM_KEYS = ("sh_scanf",)


# -- statement equivalents -------------------------------------------------

@Go.node
class DeclareLocal(base.DeclareLocal):
    def emit(self, ctx):
        decl = f"var {self.name} {ctx.type_of(self.type)}"
        if self.init is not None:
            decl += f" = {self.init.emit(ctx).text}"
        return [decl, f"_ = {self.name}"]   # Go rejects unused locals


@Go.node
class Print(base.Print):
    TEMPLATE = "fmt.Println({value})"       # ints, "true"/"false", strings
    SHIM_KEYS = ("printf",)                 # pulls in the fmt import


@Go.node
class While(base.While):
    def emit(self, ctx):
        return [f"for {self.cond.emit(ctx).text} {{",
                *ctx.indent(ctx.stmts(self.body)), "}"]


# -- declaration equivalents -----------------------------------------------

@Go.node
class GlobalDef(base.GlobalDef):
    def emit(self, ctx):
        decl = f"var {self.name} {ctx.type_of(self.type)}"
        if self.init is not None:
            decl += f" = {self.init.emit(ctx).text}"
        return [decl]                       # globals may be unused in Go


@Go.node
class FuncDef(base.FuncDef):
    def emit(self, ctx):
        params = ", ".join(f"{n} {ctx.type_of(t)}" for n, t in self.params)
        ret = ctx.type_of(self.ret)
        ret = f" {ret}" if ret else ""
        return [f"func {self.name}({params}){ret} {{",
                *ctx.indent(ctx.stmts(self.body)), "}", ""]


@Go.node
class StructDef(base.StructDef):
    def emit(self, ctx):
        rows = [f"{n} {ctx.type_of(t)}" for n, t in self.fields]
        return [f"type {self.name} struct {{", *ctx.indent(rows), "}", ""]


@Go.node
class Module(base.Module):
    def assemble(self, ctx, decls):
        backend = ctx.backend
        imports = sorted({pkg for key, pkgs in backend.IMPORTS.items()
                          if key in backend.used for pkg in pkgs})
        out = ["package main", ""]
        if len(imports) == 1:
            out += [f'import "{imports[0]}"', ""]
        elif imports:
            out += ["import (", *ctx.indent([f'"{p}"' for p in imports]),
                    ")", ""]
        out += backend.prelude()
        out += decls
        while out and out[-1] == "":
            out.pop()
        return "\n".join(out) + "\n"
