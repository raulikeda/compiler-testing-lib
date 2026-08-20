"""Diagnostics: the course error taxonomy and defect records.

The course grader classifies every failure of a student compiler into one of
three phases, printed as a bracketed tag: ``[Lexer]``, ``[Parser]`` or
``[Semantic]`` (plus ``[PrePro]`` for the x-track preprocessor).  The
reference transpiler mirrors that taxonomy: the front end never *raises* on
invalid input — it records exactly one :class:`Defect` (course compilers stop
at the first error, and every corpus test seeds exactly one) and the back
ends later translate that defect into a construct that fails natively in the
target language.

``Phase`` describes *when* the translated defect fails under the real target
toolchain (parse/load time, build time, or run time) — the invariant the
verifier checks is phase fidelity, not message fidelity.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:  # pragma: no cover - import cycle guard, typing only
    from .lexical.tokens import Token


class Phase(enum.Enum):
    """When a translated defect fails under the real target toolchain."""

    PARSE = "parse"   # rejected by the target parser (before any output)
    BUILD = "build"   # rejected by the target compiler (go build, ghc, ...)
    RUN = "run"       # fails at execution time (MethodError, DivideError, ...)


class ErrorCategory(enum.Enum):
    """Consolidated course error taxonomy (keys of every backend DEFECT_MAP)."""

    # -- lexical ----------------------------------------------------------
    LEX_INVALID_TOKEN = enum.auto()        # [Lexer] Invalid token @
    LEX_UNTERMINATED_STRING = enum.auto()  # [Lexer] Unexpected EOF
    LEX_INVALID_NUMBER = enum.auto()       # [Lexer] Invalid number format: 5.1.2

    # -- preprocessor (x2.0) ----------------------------------------------
    PREPRO_INVALID_DEFINE = enum.auto()    # [PrePro] Invalid define directive

    # -- syntactic --------------------------------------------------------
    PARSE_UNEXPECTED_TOKEN = enum.auto()   # [Parser] Unexpected token X (expected Y)
    PARSE_MISSING_TOKEN = enum.auto()      # [Parser] Missing CLOSE_PAR / OPEN_BRA / ...
    PARSE_MISSING_RIGHT_EXPR = enum.auto() # [Parser] Missing Right Expression
    PARSE_UNEXPECTED_ELSE = enum.auto()    # [Parser] Unexpected ELSE
    PARSE_UNEXPECTED_IDENTIFIER = enum.auto()  # [Parser] Unexpected Identifier
    PARSE_MISSING_FUNC_TYPE = enum.auto()  # [Parser] Missing function type
    PARSE_NESTED_FUNCTION = enum.auto()    # [Parser] Unexpected token FUNC or OPEN_PAR

    # -- semantic ---------------------------------------------------------
    SEM_INCOMPATIBLE_TYPES = enum.auto()   # [Semantic] Incompatible Types / Type(s)
    SEM_DIV_ZERO = enum.auto()             # [Semantic] Division by zero
    SEM_UNDEFINED_VAR = enum.auto()        # Identifier/Variable not found, Undefined variable
    SEM_VAR_REDECLARED = enum.auto()       # [Semantic] Variable Already Declared
    SEM_CONST_REASSIGN = enum.auto()       # [Semantic] Variable x can not be changed
    SEM_FUNC_NOT_FOUND = enum.auto()       # [Semantic] Function not found
    SEM_UNDEFINED_MAIN = enum.auto()       # Missing/Undefined function main
    SEM_ARG_COUNT = enum.auto()            # [Semantic] Number of args wrong
    SEM_ARG_TYPE = enum.auto()             # [Semantic] Wrong arg type
    SEM_RETURN_TYPE = enum.auto()          # [Semantic] Wrong func return type
    SEM_NEG_FACTORIAL = enum.auto()        # [Semantic] Factorial ... negative numbers
    SEM_STRUCT_ATTR = enum.auto()          # [Semantic] Attribute not found in struct: X
    SEM_STRUCT_ASSIGN = enum.auto()        # [Semantic] Wrong Assignment to/from struct

    @property
    def phase_tag(self) -> str:
        """The course bracket tag this category is reported under."""
        name = self.name
        if name.startswith("LEX_"):
            return "[Lexer]"
        if name.startswith("PREPRO_"):
            return "[PrePro]"
        if name.startswith("PARSE_"):
            return "[Parser]"
        return "[Semantic]"


@dataclass
class Defect:
    """Base record of the single error diagnosed in a source program.

    ``message`` reproduces the exact diagnostic a course reference compiler
    prints (used by the corpus gates); ``category`` is the stable key back
    ends map from; ``line``/``col`` locate the defect in the source.
    """

    category: ErrorCategory
    message: str
    line: int = 0
    col: int = 0

    @property
    def tag(self) -> str:
        return self.category.phase_tag


@dataclass
class LexDefect(Defect):
    """An invalid lexeme: stray character, open string, malformed number."""

    raw: str = ""  # the offending characters, verbatim


@dataclass
class ParseDefect(Defect):
    """A syntax error, with enough context for faithful re-emission.

    ``found``/``expected`` record the tokens involved (so the exact course
    message can be reproduced); ``tail_tokens`` holds the unconsumed token
    stream when recovery gave up — the token-passthrough fallback renders it
    verbatim in the target spelling.
    """

    found: Optional["Token"] = None
    expected: Optional[str] = None
    tail_tokens: list = field(default_factory=list)
    error_index: int = 0   # index into tail_tokens of the offending token


@dataclass
class SemanticDefect(Defect):
    """A semantic violation on a well-formed node of an intact tree.

    ``node`` is the offending AST node (Assign, BinOp, Call, ...);
    ``detail`` carries backend-relevant facts, e.g.
    ``{'lhs_type': 'int', 'rhs_type': 'str'}``.
    """

    node: Any = None
    detail: dict = field(default_factory=dict)
