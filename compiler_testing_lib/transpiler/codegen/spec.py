"""Phase 4 — the LanguageSpec: one declarative file per target language.

The translation machinery (walking the AST, indentation, defect handling)
lives ONCE in :mod:`.emitter`.  Everything language-*specific* is a
mechanical equivalence declared here: type spellings, operator templates,
statement shapes, precedence, runtime shims, and how defects materialize.
A new backend subclasses :class:`LanguageSpec`, overrides the deltas, and
registers itself — nothing is reimplemented from zero.

Template placeholders are plain ``str.format`` keys (``{left}``,
``{right}``, ``{operand}``, ``{value}``, ``{cond}``...).  A spec instance
is created per translation and records the shims the program actually
used (``self.use("scanf")``), so preludes stay minimal.
"""

from __future__ import annotations

from ..diagnostics import (Defect, ErrorCategory as C, LexDefect, ParseDefect,
                           Phase, SemanticDefect)
from ..versions import LanguageLevel


class LanguageSpec:
    # -- identity / toolchain ---------------------------------------------
    name = "abstract"
    ext = ""
    build_template: str | None = None   # e.g. "go build -o {exe_file} {src_file}"
    run_template = ""                   # e.g. "{exe_file}" / "julia {src_file}"
    docker_image = ""

    # -- lexical spellings -------------------------------------------------
    INDENT = "\t"
    TYPES: dict[str, str] = {"int": "int", "str": "str", "bool": "bool",
                             "float": "float", "void": ""}
    BOOL_LITS = ("true", "false")

    # -- expression equivalences (mechanical tables) -----------------------
    # C-like defaults; a language overrides only the entries that differ.
    BINOPS: dict[str, str] = {
        "+": "{left} + {right}", "-": "{left} - {right}",
        "*": "{left} * {right}", "/": "{left} / {right}",
        "==": "{left} == {right}", "<": "{left} < {right}",
        ">": "{left} > {right}", "&&": "{left} && {right}",
        "||": "{left} || {right}",
        "^": "{left} ^ {right}",            # xor        (x1.0)
        "**": "__pow({left}, {right})",     # power      (x1.1)
        "$": "__concat({left}, {right})",   # concat     (v2.2)
    }
    UNOPS: dict[str, str] = {"+": "+{operand}", "-": "-{operand}",
                             "!": "!{operand}"}
    # operator precedence of the TARGET language, used to insert parens
    # when the target would regroup the source tree
    PRECEDENCE: dict[str, int] = {"||": 1, "&&": 2, "==": 3, "<": 3, ">": 3,
                                  "+": 4, "-": 4, "^": 4, "*": 5, "/": 5}
    ASSOCIATIVE = ("+", "*", "&&", "||")    # same-op left chains need no parens

    FACTORIAL = "__fact({operand})"         # postfix !  (x1.2)
    TERNARY = "__tern({cond}, {then}, {other})"
    CASTS: dict[str, str] = {"int": "__toInt({operand})",
                             "float": "__toFloat({operand})",
                             "str": "__str({operand})",
                             "bool": "__toBool({operand})"}
    SCANF = "__scanf()"
    PRINTF = "__print({value})"
    PRINT_BOOL_AS_INT = "__b2i({value})"    # v3.0/x3.0 print bools as 0/1
    CALL = "{func}({args})"
    FIELD = "{obj}.{name}"

    # -- runtime shims: key -> source text, emitted only when used ---------
    SHIMS: dict[str, str] = {}
    # template features that require a shim: template-key -> shim keys
    FEATURE_SHIMS: dict[str, tuple[str, ...]] = {}

    def __init__(self, level: LanguageLevel):
        self.level = level
        self.used: set[str] = set()

    def use(self, *features: str) -> None:
        self.used.update(features)

    def feature(self, key: str) -> None:
        """Record that a template feature was used, pulling in its shims."""
        self.used.add(key)
        self.used.update(self.FEATURE_SHIMS.get(key, ()))

    def cast_template(self, course_type: str, operand_node) -> str:
        return self.CASTS[course_type]

    def const_topdecl(self, name: str, init: str) -> list[str]:
        """Lines a ``const`` hoists to the top level (default: none)."""
        return []

    def quote(self, text: str) -> str:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    # -- statement shapes (methods: they produce indented line lists) ------
    def stmt_terminator(self) -> str:
        return ""

    def assign(self, target: str, expr: str, declares: bool) -> list[str]:
        """``declares`` marks the first assignment of an untyped variable."""
        return [f"{target} = {expr}"]

    def var_decl(self, name: str, course_type: str, init: str | None,
                 is_struct: bool) -> list[str]:
        raise NotImplementedError

    def const_decl(self, name: str, init: str) -> list[str]:
        return [f"const {name} = {init}"]

    def const_read(self, name: str) -> str:
        return name

    def const_assign(self, name: str, expr: str) -> list[str]:
        return [f"{name} = {expr}"]

    def block(self, body: list[str], scoped: bool) -> list[str]:
        """A C ``{}`` statement block (``scoped``: it shadows in the course)."""
        raise NotImplementedError

    def if_(self, cond: str, then: list[str],
            other: list[str] | None) -> list[str]:
        raise NotImplementedError

    def while_(self, cond: str, body: list[str]) -> list[str]:
        raise NotImplementedError

    def for_(self, init: list[str], cond: str, step: list[str],
             body: list[str]) -> list[str]:
        """Default: desugar the C for into init + while(cond){body; step}."""
        return init + self.while_(cond, body + step)

    def return_(self, expr: str) -> list[str]:
        return [f"return {expr}"]

    def expr_stmt(self, expr: str) -> list[str]:
        return [expr]

    # -- declaration shapes ------------------------------------------------
    def function(self, name: str, params: list[tuple[str, str]],
                 ret_course_type: str, body: list[str],
                 assigned_globals: list[str]) -> list[str]:
        raise NotImplementedError

    def struct(self, name: str, fields: list[tuple[str, str]]) -> list[str]:
        raise NotImplementedError

    def global_var(self, name: str, course_type: str,
                   init: str | None) -> list[str]:
        raise NotImplementedError

    def program(self, decls: list[str], main_body: list[str] | None) -> str:
        """Assemble the whole file: prelude + declarations + entry point."""
        raise NotImplementedError

    def prelude(self) -> list[str]:
        lines: list[str] = []
        for key, text in self.SHIMS.items():
            if key in self.used:
                lines.extend(text.splitlines())
                lines.append("")
        return lines

    # -- defect materialization -------------------------------------------
    PARSE_MARKER: str | None = None   # spliced before the offending token
    EMPTY_DEFECT = "()"               # stands in for a missing expression

    def spell_token(self, tok) -> str | None:
        """Override a token's spelling in passthrough (None = keep lexeme)."""
        return None

    def lex_defect_text(self, source: str) -> str:
        return source.rstrip("\n")    # the invalid characters speak for themselves

    def prepro_defect_text(self, source: str) -> str:
        return source.rstrip("\n")

    def defect_program(self, text: str) -> str:
        """Wrap passthrough text so it fails in the right phase."""
        raise NotImplementedError

    def phase_for(self, defect: Defect) -> Phase:
        """When the translated defect fails under the real toolchain."""
        raise NotImplementedError

    # -- semantic-defect hooks (default: the native translation already
    #    fails; a language overrides where it is laxer than the course) ----
    def check_assigned(self, expected_course_type: str, expr: str) -> str:
        return expr

    def check_operand(self, expected_course_type: str, expr: str) -> str:
        return expr

    def assign_undeclared(self, name: str, expr: str) -> list[str]:
        return self.assign(name, expr, declares=False)
