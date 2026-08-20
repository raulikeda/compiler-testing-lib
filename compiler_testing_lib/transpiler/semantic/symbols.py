"""Phase 3 — symbol tables as a scope chain.

A :class:`Scope` resolves names locally and delegates misses to its parent
(Chain of Responsibility), which is exactly how block shadowing works in
the course language: an inner ``{}`` re-declaring ``x_2`` hides the outer
one until the block ends.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Symbol:
    name: str
    type: object = None            # types.INT / StructType / ...
    kind: str = "var"              # var | const | func | struct
    params: list = field(default_factory=list)   # for kind == "func"
    ret_type: object = None                      # for kind == "func"


class Scope:
    def __init__(self, parent: Optional["Scope"] = None):
        self.parent = parent
        self._table: dict[str, Symbol] = {}

    def declare(self, sym: Symbol) -> bool:
        """Declare in THIS scope; False if the name already lives here."""
        if sym.name in self._table:
            return False
        self._table[sym.name] = sym
        return True

    def resolve(self, name: str) -> Optional[Symbol]:
        scope: Optional[Scope] = self
        while scope is not None:
            if name in scope._table:
                return scope._table[name]
            scope = scope.parent
        return None

    def child(self) -> "Scope":
        return Scope(parent=self)
