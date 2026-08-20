"""Phase 3 — semantic analysis (scope chain, type system, analyzer)."""

from .analyzer import SemanticAnalyzer
from .symbols import Scope, Symbol
from . import types

__all__ = ["SemanticAnalyzer", "Scope", "Symbol", "types"]
