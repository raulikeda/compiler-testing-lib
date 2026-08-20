"""Visitor (double dispatch) over the source AST.

Consumers of the tree — the semantic analyzer, every backend transformer —
subclass this instead of teaching the nodes about themselves: the nodes
stay pure data (a deliberate contrast with the course's ``node.evaluate()``
style, where behavior lives on the nodes).

Dispatch is by dynamic node class name: ``visit(node)`` calls
``visit_BinOp`` for a :class:`~.ast.BinOp`, falling back to
:meth:`generic_visit`.
"""

from __future__ import annotations

from . import ast


class Visitor:
    def visit(self, node: ast.Node):
        method = getattr(self, f"visit_{type(node).__name__}",
                         self.generic_visit)
        return method(node)

    def generic_visit(self, node: ast.Node):
        raise NotImplementedError(
            f"{type(self).__name__} has no visit_{type(node).__name__}")
