"""Go — declarative language spec.

Mechanical equivalences from the course language to Go.  Almost every
defect needs no special handling: the faithful typed translation is what
makes ``go build`` fail natively (wrong initializer types, undeclared
names, constant zero divisors, redeclarations, bad calls), and C-shaped
token soup is never valid Go, so no parse marker is required.

The one systematic concession: ``_ = x`` after every local declaration,
because Go rejects declared-and-not-used variables and the course
language does not.
"""

from __future__ import annotations

from ..diagnostics import Defect, ErrorCategory as C, Phase
from .registry import register
from .spec import LanguageSpec


@register
class GoSpec(LanguageSpec):
    name = "go"
    ext = "go"
    build_template = "go build -o {exe_file} {src_file}"
    run_template = "{exe_file}"
    docker_image = "compiler-testing-lib-go"

    TYPES = {"int": "int", "str": "string", "bool": "bool",
             "float": "float64", "void": ""}

    BINOPS = dict(LanguageSpec.BINOPS)      # C-like defaults suit Go:
    #   + - * / == < > && || ^(xor) are spelled identically;
    #   $ and ** fall back to the __concat/__pow shims of the base table.

    PRINTF = "fmt.Println({value})"         # ints, "true"/"false", strings
    FEATURE_SHIMS = {
        "$": ("concat",), "**": ("pow",), "scanf": ("scanf",),
        "fact": ("fact",), "ternary": ("tern",), "b2i": ("b2i",),
        "cast:int": ("toInt",), "cast:float": ("toFloat",),
        "cast:str": ("str",), "cast:bool": ("toBool",),
    }

    IMPORTS = {"printf": ("fmt",), "concat": ("fmt",), "str": ("fmt",),
               "scanf": ("bufio", "os", "strconv"), "toInt": ("math",),
               "toFloat": ("strconv",)}

    SHIMS = {
        "scanf": '''\
var __in = bufio.NewReader(os.Stdin)

func __scanf() int {
\tline, _ := __in.ReadString('\\n')
\tfor len(line) > 0 && (line[len(line)-1] == '\\n' || line[len(line)-1] == '\\r') {
\t\tline = line[:len(line)-1]
\t}
\tvalue, _ := strconv.Atoi(line)
\treturn value
}''',
        "concat": '''\
func __concat(parts ...any) string {
\tout := ""
\tfor _, part := range parts {
\t\tout += fmt.Sprint(part)
\t}
\treturn out
}''',
        "pow": '''\
func __pow(base, exp int) int {
\tresult := 1
\tfor i := 0; i < exp; i++ {
\t\tresult *= base
\t}
\treturn result
}''',
        "fact": '''\
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
        "tern": '''\
func __tern(cond bool, a, b int) int {
\tif cond {
\t\treturn a
\t}
\treturn b
}''',
        "str": '''\
func __str(value any) string {
\treturn fmt.Sprint(value)
}''',
        "b2i": '''\
func __b2i(value bool) int {
\tif value {
\t\treturn 1
\t}
\treturn 0
}''',
        "toInt": '''\
func __toInt(value any) int {
\tswitch v := value.(type) {
\tcase float64:
\t\treturn int(math.Round(v))
\tdefault:
\t\treturn v.(int)
\t}
}''',
        "toFloat": '''\
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
        "toBool": '''\
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

    # -- statement shapes --------------------------------------------------
    def _indent(self, lines: list[str]) -> list[str]:
        return [self.INDENT + line if line else line for line in lines]

    def assign(self, target, expr, declares):
        if declares:
            return [f"{target} := {expr}", f"_ = {target}"]
        return [f"{target} = {expr}"]

    def var_decl(self, name, course_type, init, is_struct):
        go_type = course_type if is_struct else self.TYPES[course_type]
        decl = f"var {name} {go_type}"
        if init is not None:
            decl += f" = {init}"
        return [decl, f"_ = {name}"]

    def block(self, body, scoped):
        return ["{", *self._indent(body), "}"]

    def if_(self, cond, then, other):
        out = [f"if {cond} {{", *self._indent(then)]
        if other is not None:
            out += ["} else {", *self._indent(other)]
        return out + ["}"]

    def while_(self, cond, body):
        return [f"for {cond} {{", *self._indent(body), "}"]

    def for_(self, init, cond, step, body):
        header = f"for {init[0] if init else ''}; {cond}; " \
                 f"{step[0] if step else ''} {{"
        return [header, *self._indent(body), "}"]

    def function(self, name, params, ret_course_type, body, assigned_globals):
        sig = ", ".join(f"{n} {self.TYPES[t]}" for n, t in params)
        ret = self.TYPES[ret_course_type]
        ret = f" {ret}" if ret else ""
        return [f"func {name}({sig}){ret} {{", *self._indent(body), "}", ""]

    def struct(self, name, fields):
        rows = [f"{n} {self.TYPES[t]}" for n, t in fields]
        return [f"type {name} struct {{", *self._indent(rows), "}", ""]

    def global_var(self, name, course_type, init):
        decl = f"var {name} {self.TYPES[course_type]}"
        if init is not None:
            decl += f" = {init}"
        return [decl]

    def program(self, decls, main_body):
        imports = sorted({pkg for key, pkgs in self.IMPORTS.items()
                          if key in self.used for pkg in pkgs})
        out = ["package main", ""]
        if len(imports) == 1:
            out += [f'import "{imports[0]}"', ""]
        elif imports:
            out += ["import (", *self._indent([f'"{p}"' for p in imports]),
                    ")", ""]
        prelude = self.prelude()
        if prelude:
            out += prelude
        out += decls
        if main_body is not None:
            out += [f"func main() {{", *self._indent(main_body), "}"]
        while out and out[-1] == "":
            out.pop()
        return "\n".join(out) + "\n"

    # -- defect materialization -------------------------------------------
    def defect_program(self, text):
        return ("package main\n\nfunc main() {\n"
                + "\n".join(self._indent(text.splitlines()))
                + "\n}\n")

    def phase_for(self, defect: Defect) -> Phase:
        if defect.category is C.SEM_NEG_FACTORIAL:
            return Phase.RUN            # __fact panics when called
        return Phase.BUILD              # everything else fails `go build`
