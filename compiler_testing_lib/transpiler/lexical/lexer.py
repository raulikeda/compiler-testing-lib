"""Phase 1 — lexical analysis.

An error-tolerant scanner: it never raises on bad input.  Invalid lexemes
become sentinel tokens (``INVALID``, ``UNTERMINATED_STR``,
``INVALID_NUMBER``) carrying the offending characters, and the driver turns
the first sentinel into a :class:`~..diagnostics.LexDefect`.  Which
characters are meaningful at all depends on the course version, so the
scanner is parameterized by a :class:`~..versions.LanguageLevel`.
"""

from __future__ import annotations

from ..versions import LanguageLevel
from .tokens import Token, TokenKind as K


def _keyword_table(level: LanguageLevel) -> dict[str, K]:
    kw: dict[str, K] = {}
    if level.statements:
        kw["printf"] = K.PRINT
    if level.scanf:
        kw["scanf"] = K.READ
    if level.blocks:
        kw["if"] = K.IF
        kw["else"] = K.ELSE
        kw["while"] = K.WHILE
    if level.for_ternary:
        kw["for"] = K.FOR
    if level.types:
        kw["int"] = K.TYPE
        kw["str"] = K.TYPE
        kw["bool"] = K.TYPE
        kw["true"] = K.BOOL
        kw["false"] = K.BOOL
    if level.floats:
        kw["float"] = K.TYPE
    if level.functions:
        kw["void"] = K.TYPE
        kw["return"] = K.RETURN
    if level.structs:
        kw["struct"] = K.STRUCT
    if level.prepro:
        kw["const"] = K.CONST
    return kw


class Lexer:
    """Scan the whole source into a token list (always EOF-terminated)."""

    def __init__(self, source: str, level: LanguageLevel):
        self.src = source
        self.level = level
        self.pos = 0
        self.line = 1
        self.col = 1
        self.keywords = _keyword_table(level)

    # -- character helpers -------------------------------------------------
    def _peek(self, ahead: int = 0) -> str:
        i = self.pos + ahead
        return self.src[i] if i < len(self.src) else ""

    def _advance(self) -> str:
        ch = self.src[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def _token(self, kind: K, lexeme: str, line: int, col: int) -> Token:
        return Token(kind, lexeme, line, col)

    # -- scanning ----------------------------------------------------------
    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while self.pos < len(self.src):
            ch = self._peek()
            if ch in " \t\r\n":
                self._advance()
                continue
            if ch == "/" and self._peek(1) == "/" and self.level.comments:
                while self.pos < len(self.src) and self._peek() != "\n":
                    self._advance()
                continue
            tokens.append(self._next_token())
        tokens.append(self._token(K.EOF, "", self.line, self.col))
        return tokens

    def _next_token(self) -> Token:
        line, col = self.line, self.col
        ch = self._peek()

        if ch.isdigit():
            return self._number(line, col)
        if ch.isalpha() or ch == "_":
            return self._word(line, col)
        if ch == '"' and self.level.types:
            return self._string(line, col)

        level = self.level
        two = ch + self._peek(1)

        # two-character operators first
        if two == "**" and level.power:
            self._advance(); self._advance()
            return self._token(K.POWER, "**", line, col)
        if two == "==" and level.blocks:
            self._advance(); self._advance()
            return self._token(K.EQUAL, "==", line, col)
        if two == "&&" and level.blocks:
            self._advance(); self._advance()
            return self._token(K.AND, "&&", line, col)
        if two == "||" and level.blocks:
            self._advance(); self._advance()
            return self._token(K.OR, "||", line, col)

        single: dict[str, K | None] = {
            "+": K.PLUS,
            "-": K.MINUS,
            "*": K.MULT if level.mul_div else None,
            "/": K.DIV if level.mul_div else None,
            "^": K.XOR if level.xor else None,
            "!": K.FACT if level.factorial else (K.NOT if level.blocks else None),
            "$": K.CONCAT if level.types else None,
            "=": K.ASSIGN if level.statements else None,
            "<": K.LT if level.blocks else None,
            ">": K.GT if level.blocks else None,
            "(": K.OPEN_PAR,
            ")": K.CLOSE_PAR,
            "{": K.OPEN_BRA if level.blocks else None,
            "}": K.CLOSE_BRA if level.blocks else None,
            ";": K.EOL if level.statements else None,
            ",": K.COMMA if level.functions else None,
            ".": K.DOT if level.structs else None,
            "?": K.QUESTION if level.for_ternary else None,
            ":": K.COLON if level.for_ternary else None,
        }
        kind = single.get(ch)
        self._advance()
        if kind is None:
            return self._token(K.INVALID, ch, line, col)
        return self._token(kind, ch, line, col)

    def _number(self, line: int, col: int) -> Token:
        start = self.pos
        while self._peek().isdigit():
            self._advance()
        if self.level.floats and self._peek() == ".":
            self._advance()
            while self._peek().isdigit():
                self._advance()
            # a second '.' makes the whole lexeme a malformed number (5.1.2)
            if self._peek() == ".":
                self._advance()
                while self._peek().isdigit() or self._peek() == ".":
                    self._advance()
                return self._token(K.INVALID_NUMBER, self.src[start:self.pos],
                                   line, col)
            return self._token(K.FLOAT, self.src[start:self.pos], line, col)
        return self._token(K.INT, self.src[start:self.pos], line, col)

    def _word(self, line: int, col: int) -> Token:
        start = self.pos
        while self._peek().isalnum() or self._peek() == "_":
            self._advance()
        lexeme = self.src[start:self.pos]
        kind = self.keywords.get(lexeme, K.IDEN)
        return self._token(kind, lexeme, line, col)

    def _string(self, line: int, col: int) -> Token:
        start = self.pos
        self._advance()  # opening quote
        while self.pos < len(self.src) and self._peek() not in '"\n':
            self._advance()
        if self._peek() == '"':
            self._advance()
            return self._token(K.STR, self.src[start + 1:self.pos - 1],
                               line, col)
        # never closed: the course lexer reports "[Lexer] Unexpected EOF"
        return self._token(K.UNTERMINATED_STR, self.src[start:self.pos],
                           line, col)
