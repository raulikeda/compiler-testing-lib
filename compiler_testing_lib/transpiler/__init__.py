"""Reference transpiler: the course C subset → real target languages.

Facade: :func:`transpile` hides the pipeline (preprocessor → lexer →
parser → semantic analyzer → transformer → printer).  Invalid source is
not rejected — it translates to target code that fails natively under the
real target toolchain at the equivalent point, in the phase declared by
the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .diagnostics import Defect, Phase
from .driver import parse_source
from .syntax import ast
from .versions import get_level


@dataclass
class TranspileResult:
    code: str                   # target-language source text
    defect: Optional[Defect]    # the single diagnosed course error, if any
    phase: Optional[Phase]      # declared native-failure phase (None = valid)
    program: ast.Program        # the analyzed source AST


def transpile(source: str, target: str, version: str) -> TranspileResult:
    from .codegen import Emitter, get_backend   # deferred: registers backends

    level = get_level(version)
    spec = get_backend(target)(level)
    program = parse_source(source, version)
    code, phase = Emitter(spec).emit(program, source)
    return TranspileResult(code=code, defect=program.defect,
                           phase=phase, program=program)
