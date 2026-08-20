"""Phase 4 — common ground for target-language ASTs.

Every backend models its language as its own Composite hierarchy rooted in
:class:`TargetNode`.  Two node shapes are shared:

* :class:`Raw` — the escape hatch.  An invalid source program cannot become
  a well-formed target tree, so defect translation splices literal text
  (token-faithful spelling of the defective region) into otherwise
  well-formed surroundings.  Printers render it verbatim.
* :class:`Seq` — a flat sequence of nodes, the generic "many statements"
  container.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TargetNode:
    pass


@dataclass
class Raw(TargetNode):
    """Literal target text, rendered verbatim (defect splices, preludes)."""
    text: str = ""


@dataclass
class Seq(TargetNode):
    items: list = field(default_factory=list)
