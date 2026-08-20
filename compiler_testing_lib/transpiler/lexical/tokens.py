"""Token vocabulary, named after the course's own token names.

The diagnostics the corpus expects spell token kinds exactly as below
(``[Parser] Unexpected token CLOSE_PAR``), so the enum member names ARE the
user-visible vocabulary — do not rename them.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class TokenKind(enum.Enum):
    # literals / identifiers
    INT = "INT"
    FLOAT = "FLOAT"
    STR = "STR"            # string literal
    BOOL = "BOOL"          # true / false      (v2.2+)
    IDEN = "IDEN"

    # operators
    PLUS = "PLUS"
    MINUS = "MINUS"
    MULT = "MULT"
    DIV = "DIV"
    POWER = "POWER"        # **                (x1.1)
    XOR = "XOR"            # ^                 (x1.0)
    FACT = "FACT"          # postfix !         (x1.2)
    NOT = "NOT"            # prefix  !         (v2.1+)
    CONCAT = "CONCAT"      # $                 (v2.2+)
    ASSIGN = "ASSIGN"      # =
    EQUAL = "EQUAL"        # ==
    LT = "LT"              # <
    GT = "GT"              # >
    AND = "AND"            # &&
    OR = "OR"              # ||
    QUESTION = "QUESTION"  # ?                 (x2.1)
    COLON = "COLON"        # :                 (x2.1)

    # punctuation
    OPEN_PAR = "OPEN_PAR"
    CLOSE_PAR = "CLOSE_PAR"
    OPEN_BRA = "OPEN_BRA"
    CLOSE_BRA = "CLOSE_BRA"
    EOL = "EOL"            # ;  (the course names the statement terminator EOL)
    NEWLINE = "NEWLINE"    # line end / end-of-input; prints as "EOL" in
                           # diagnostics (course behavior) but, unlike ';',
                           # is skippable between statements
    COMMA = "COMMA"
    DOT = "DOT"            # struct field access (x2.3)

    # keywords
    IF = "IF"
    ELSE = "ELSE"
    WHILE = "WHILE"
    FOR = "FOR"            # (x2.1)
    RETURN = "RETURN"
    PRINT = "PRINT"        # printf
    READ = "READ"          # scanf
    TYPE = "TYPE"          # int / str / bool / float / void (lexeme says which)
    STRUCT = "STRUCT"      # (x2.3)
    CONST = "CONST"        # (x2.0)

    # sentinels
    EOF = "EOF"
    INVALID = "INVALID"                  # [Lexer] Invalid token X
    UNTERMINATED_STR = "UNTERMINATED_STR"  # [Lexer] Unexpected EOF
    INVALID_NUMBER = "INVALID_NUMBER"      # [Lexer] Invalid number format: X

    def __str__(self) -> str:  # so diagnostics read "CLOSE_PAR", not "TokenKind..."
        if self is TokenKind.NEWLINE:
            return "EOL"       # the reference prints line ends as EOL
        return self.value


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    lexeme: str
    line: int = 1
    col: int = 1
    # a digit-led word like ``1x``: scanned as one IDEN-shaped token that the
    # parser must reject ("Unexpected token IDEN"), mirroring the reference
    malformed: bool = False

    def __repr__(self) -> str:
        return f"Token({self.kind}, {self.lexeme!r})"
