"""Phase 4 — the Printer: target AST → source text.

A Visitor over the backend's target nodes; owns indentation and layout so
transformers never concatenate strings.  ``Raw`` and ``Seq`` are handled
here once for every backend.
"""

from __future__ import annotations

from .target import Raw, Seq, TargetNode


class Printer:
    INDENT = "\t"

    def __init__(self):
        self._depth = 0

    # -- dispatch ----------------------------------------------------------
    def print(self, root: TargetNode) -> str:
        return "\n".join(self.lines(root)) + "\n"

    def lines(self, node: TargetNode) -> list[str]:
        method = getattr(self, f"lines_{type(node).__name__}",
                         self.generic_lines)
        return method(node)

    def generic_lines(self, node: TargetNode) -> list[str]:
        raise NotImplementedError(
            f"{type(self).__name__} has no lines_{type(node).__name__}")

    # -- shared nodes ------------------------------------------------------
    def lines_Raw(self, node: Raw) -> list[str]:
        return node.text.splitlines() or [""]

    def lines_Seq(self, node: Seq) -> list[str]:
        out: list[str] = []
        for item in node.items:
            out.extend(self.lines(item))
        return out

    # -- helpers -----------------------------------------------------------
    def indented(self, lines: list[str]) -> list[str]:
        return [self.INDENT + line if line else line for line in lines]
