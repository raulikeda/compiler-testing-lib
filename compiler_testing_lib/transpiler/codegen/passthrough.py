"""Token-passthrough rendering for defective programs.

A program that failed lexing/parsing has no usable tree; instead its token
stream is re-spelled in the target, preserving line structure and — most
importantly — the defect itself (a missing ``)`` stays missing).

Where the literal transposition alone might be *legal* in the target
language, a backend passes a ``marker`` (an always-invalid glyph in that
target, e.g. ``@``) which is spliced immediately before the token where
the course compiler diagnosed the error — so the target parser fails at
the equivalent position.
"""

from __future__ import annotations

from typing import Callable, Optional

from ..lexical.tokens import Token, TokenKind as K


def render_tokens(tokens: list[Token],
                  error_index: Optional[int] = None,
                  marker: Optional[str] = None,
                  spell: Optional[Callable[[Token], str]] = None) -> str:
    """Re-spell a token stream as target text.

    ``spell`` lets a backend override individual token spellings; by
    default the original lexeme is kept (string literals are re-quoted).
    """
    parts: list[str] = []
    line: list[str] = []

    def flush():
        parts.append(" ".join(line))
        line.clear()

    for index, tok in enumerate(tokens):
        if marker is not None and index == error_index:
            line.append(marker)
        if tok.kind is K.EOF:
            break
        if tok.kind is K.NEWLINE:
            flush()
            continue
        spelled = spell(tok) if spell is not None else None
        if spelled is None:
            if tok.kind is K.STR:
                spelled = f'"{tok.lexeme}"'
            elif tok.kind is K.UNTERMINATED_STR:
                spelled = f'"{tok.lexeme}'
            else:
                spelled = tok.lexeme
        line.append(spelled)
    flush()
    return "\n".join(parts)
