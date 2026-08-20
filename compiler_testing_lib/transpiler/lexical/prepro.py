"""x2.0 preprocessor: ``#define`` textual substitution.

Mirrors the course's PrePro filter: a ``#define NAME VALUE`` line records a
macro and is removed; every whole-word occurrence of ``NAME`` in the
remaining source is replaced by ``VALUE`` *textually*, before lexing.  This
is why ``N = 3;`` after ``#define N 1`` is a *parse* error in the corpus
(the parser sees ``1 = 3;``), not a semantic one.

A malformed directive yields a :class:`~..diagnostics.LexDefect`-style
PrePro defect (``[PrePro] Invalid define directive``).
"""

from __future__ import annotations

import re
from typing import Optional

from ..diagnostics import Defect, ErrorCategory

_DEFINE_RE = re.compile(r"^\s*#define\s+(\w+)\s+(\S+)\s*$")
_ANY_DIRECTIVE_RE = re.compile(r"^\s*#")


def preprocess(source: str) -> tuple[str, dict[str, str], Optional[Defect]]:
    """Strip ``#define`` lines, substitute macros, report malformed directives.

    Returns ``(new_source, macros, defect)`` where ``defect`` is None unless
    a directive is malformed.  Line count is preserved (directive lines
    become empty lines) so token positions stay meaningful.
    """
    macros: dict[str, str] = {}
    out_lines: list[str] = []
    defect: Optional[Defect] = None
    for lineno, line in enumerate(source.splitlines(), start=1):
        if _ANY_DIRECTIVE_RE.match(line):
            m = _DEFINE_RE.match(line)
            if m:
                macros[m.group(1)] = m.group(2)
            elif defect is None:
                defect = Defect(
                    category=ErrorCategory.PREPRO_INVALID_DEFINE,
                    message="[PrePro] Invalid define directive",
                    line=lineno,
                )
            out_lines.append("")
        else:
            out_lines.append(line)

    text = "\n".join(out_lines)
    for name, value in macros.items():
        text = re.sub(rf"\b{re.escape(name)}\b", value, text)
    return text, macros, defect
