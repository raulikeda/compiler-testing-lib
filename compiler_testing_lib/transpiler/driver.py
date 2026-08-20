"""Compilation driver: orchestrates the front-end phases.

preprocessor (x2.0) → lexer → parser → semantic analyzer, stopping at the
first phase that diagnoses a defect — exactly like the course reference
compilers.  The result is always a :class:`~.syntax.ast.Program`; an
invalid source yields a Program whose ``defect`` field carries the single
diagnosed error instead of raising.
"""

from __future__ import annotations

from .diagnostics import ErrorCategory as C, LexDefect
from .lexical import Lexer, TokenKind as K, preprocess
from .syntax import ast
from .syntax.parser import Parser
from .versions import get_level

_SENTINEL_MESSAGES = {
    K.INVALID: (C.LEX_INVALID_TOKEN, "Invalid token {raw}"),
    K.UNTERMINATED_STR: (C.LEX_UNTERMINATED_STRING, "Unexpected EOF"),
    K.INVALID_NUMBER: (C.LEX_INVALID_NUMBER, "Invalid number format: {raw}"),
}


def parse_source(source: str, version: str) -> ast.Program:
    """Run the front end (through syntax analysis) for one source file."""
    level = get_level(version)

    if level.prepro:
        source, _macros, prepro_defect = preprocess(source)
        if prepro_defect is not None:
            return ast.Program(defect=prepro_defect,
                               expr_mode=level.expr_mode)

    tokens = Lexer(source, level).tokenize()

    # The course lexer aborts at the first invalid lexeme, before parsing.
    for tok in tokens:
        if tok.kind in _SENTINEL_MESSAGES:
            category, template = _SENTINEL_MESSAGES[tok.kind]
            tag = f"{category.phase_tag} " if level.bracket_tags else ""
            return ast.Program(
                defect=LexDefect(
                    category=category,
                    message=tag + template.format(raw=tok.lexeme),
                    line=tok.line, col=tok.col, raw=tok.lexeme),
                expr_mode=level.expr_mode)

    return Parser(tokens, level).parse()
