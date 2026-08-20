"""Go backend: an IR emitter.

Go's surface is the C-family default, so this backend is mostly tables:
type spellings, the shims behind ``concat``/``pow``/casts, imports, and
file assembly.  Defects need no special handling — the faithful typed
translation is what makes ``go build`` fail natively (wrong initializer
types, unresolved names, constant zero divisors, redeclarations, bad
calls), so ``spell_check`` stays transparent and no parse marker is
needed (C-shaped token soup is never valid Go).  The one systematic
concession: ``_ = x`` after every local declaration, because Go rejects
declared-and-not-used variables and the course language does not.
"""

from __future__ import annotations

from ..diagnostics import Defect, ErrorCategory as C, Phase
from .base import IREmitter
from .registry import register


@register
class GoEmitter(IREmitter):
    name = "go"
    ext = "go"
    build_template = "go build -o {exe_file} {src_file}"
    run_template = "{exe_file}"
    docker_image = "compiler-testing-lib-go"

    TYPES = {"int": "int", "str": "string", "bool": "bool",
             "float": "float64", "void": ""}
    PRINTF = "fmt.Println({value})"     # ints, "true"/"false", strings
    READ_INT = "__scanf()"

    FEATURE_SHIMS = {
        "concat": ("sh_concat",), "pow": ("sh_pow",), "fact": ("sh_fact",),
        "ternary": ("sh_tern",), "scanf": ("sh_scanf",),
        "to_int": ("sh_toInt",), "to_float": ("sh_toFloat",),
        "to_str": ("sh_str",), "to_bool": ("sh_toBool",),
        "bool_to_int": ("sh_b2i",),
    }
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

    # -- shapes ------------------------------------------------------------
    def spell_declare(self, node, init):
        decl = f"var {node.name} {self.type_of(node.type)}"
        if init is not None:
            decl += f" = {init}"
        return [decl, f"_ = {node.name}"]   # Go rejects unused locals

    def spell_while(self, cond, body):
        return [f"for {cond} {{", *self.indent(body), "}"]

    def spell_func(self, func, body):
        params = ", ".join(f"{n} {self.type_of(t)}" for n, t in func.params)
        ret = self.type_of(func.ret)
        ret = f" {ret}" if ret else ""
        return [f"func {func.name}({params}){ret} {{", *self.indent(body),
                "}", ""]

    def spell_struct(self, struct):
        rows = [f"{n} {self.type_of(t)}" for n, t in struct.fields]
        return [f"type {struct.name} struct {{", *self.indent(rows), "}", ""]

    def spell_global(self, glob, init):
        decl = f"var {glob.name} {self.type_of(glob.type)}"
        if init is not None:
            decl += f" = {init}"
        return [decl]                        # globals may be unused in Go

    def assemble(self, module, decls):
        imports = sorted({pkg for key, pkgs in self.IMPORTS.items()
                          if key in self.used for pkg in pkgs})
        out = ["package main", ""]
        if len(imports) == 1:
            out += [f'import "{imports[0]}"', ""]
        elif imports:
            out += ["import (", *self.indent([f'"{p}"' for p in imports]),
                    ")", ""]
        out += self.prelude()
        out += decls
        while out and out[-1] == "":
            out.pop()
        return "\n".join(out) + "\n"

    # -- defect materialization -------------------------------------------
    def defect_program(self, text):
        return ("package main\n\nfunc main() {\n"
                + "\n".join(self.indent(text.splitlines()))
                + "\n}\n")

    def phase_for(self, defect: Defect) -> Phase:
        if defect.category is C.SEM_NEG_FACTORIAL:
            return Phase.RUN            # __fact panics when called
        return Phase.BUILD              # everything else fails `go build`
