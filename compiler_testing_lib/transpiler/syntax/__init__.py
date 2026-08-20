"""Phase 2 — syntax analysis (AST Composite + recursive-descent parser)."""

from . import ast
from .parser import Parser, ParseError

__all__ = ["ast", "Parser", "ParseError"]
