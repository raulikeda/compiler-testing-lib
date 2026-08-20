"""Language levels: which features each course version enables.

The course grammar grows stage by stage (v0.0 ... v3.0) with an extra-credit
x-track that grafts one feature onto a base stage.  The whole front end is
version-agnostic code parameterized by a :class:`LanguageLevel` — the same
lexer/parser handles every stage, consulting the level to decide which
tokens, productions and diagnostics exist at that stage (so diagnostics
match what a student compiler for that stage would print).
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class LanguageLevel:
    """Feature switches for one course version."""

    name: str
    expr_mode: bool = False        # v0.0-v1.2/x1.x: source is a bare expression
    bracket_tags: bool = True      # v0.0 prints no [Lexer]/[Parser] prefix
    expected_int_style: bool = False  # v1.0-style "Unexpected token X (expected INT)"
    mul_div: bool = False          # * / and parentheses          (v1.1+)
    comments: bool = False         # // line comments             (v2.0+)
    statements: bool = False       # assignment, printf, ';'      (v2.0+)
    blocks: bool = False           # { } if/else while, bool ops  (v2.1+)
    scanf: bool = False            # scanf()                      (v2.1+)
    types: bool = False            # int/str/bool decls, ", $     (v2.2+)
    functions: bool = False        # decls, return, ',' , void    (v2.3+)
    xor: bool = False              # ^                            (x1.0)
    power: bool = False            # **                           (x1.1)
    factorial: bool = False        # postfix !                    (x1.2)
    prepro: bool = False           # #define, const               (x2.0)
    for_ternary: bool = False      # for loops and ?:             (x2.1)
    floats: bool = False           # float type, casts            (x2.2)
    structs: bool = False          # struct decls, field access   (x2.3)
    bools_as_ints: bool = False    # v3.0/x3.0 (asm) print booleans as 0/1


_V00 = LanguageLevel("v0.0", expr_mode=True, bracket_tags=False,
                     expected_int_style=True)
_V10 = replace(_V00, name="v1.0", bracket_tags=True)
_V11 = replace(_V10, name="v1.1", expected_int_style=False, mul_div=True)
_V12 = replace(_V11, name="v1.2")
_V20 = replace(_V12, name="v2.0", expr_mode=False, comments=True,
               statements=True)
_V21 = replace(_V20, name="v2.1", blocks=True, scanf=True)
_V22 = replace(_V21, name="v2.2", types=True)
_V23 = replace(_V22, name="v2.3", functions=True)
# v3.0 targets assembly but its corpus is a v2.2-level block program;
# functions reappear in the x3.0 extra-credit track.  The asm stages print
# booleans as 0/1 (register values), not true/false.
_V30 = replace(_V22, name="v3.0", bools_as_ints=True)

LEVELS: dict[str, LanguageLevel] = {
    "v0.0": _V00,
    "v1.0": _V10,
    "v1.1": _V11,
    "v1.2": _V12,
    "v2.0": _V20,
    "v2.1": _V21,
    "v2.2": _V22,
    "v2.3": _V23,
    "v3.0": _V30,
    # x-track: one extra feature grafted onto the matching base stage
    "x1.0": replace(_V10, name="x1.0", xor=True),
    "x1.1": replace(_V12, name="x1.1", power=True),
    "x1.2": replace(_V12, name="x1.2", factorial=True),
    "x2.0": replace(_V20, name="x2.0", prepro=True),
    "x2.1": replace(_V21, name="x2.1", for_ternary=True),
    "x2.2": replace(_V22, name="x2.2", floats=True),
    "x2.3": replace(_V23, name="x2.3", structs=True),
    "x3.0": replace(_V23, name="x3.0", bools_as_ints=True),
}


def get_level(version: str) -> LanguageLevel:
    try:
        return LEVELS[version]
    except KeyError:
        raise ValueError(
            f"Unknown course version {version!r}; expected one of "
            f"{', '.join(sorted(LEVELS))}"
        ) from None
