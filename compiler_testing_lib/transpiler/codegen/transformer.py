"""Phase 4 — the Transformer: source AST → target AST (tree to tree).

Template Method: :meth:`Transformer.transform` fixes the program-assembly
order for every backend —

1. a *defective* program short-circuits to defect translation
   (:meth:`transform_defect`), producing target code that fails natively at
   the equivalent point and phase;
2. a *valid* program is transformed node by node (Visitor double dispatch)
   into the backend's own target AST, wrapped by :meth:`build_program`.

Concrete backends (``codegen/go``, ``codegen/julia``) override the hooks;
they never override :meth:`transform` itself.
"""

from __future__ import annotations

from ..diagnostics import Defect, LexDefect, ParseDefect, Phase, SemanticDefect
from ..syntax import ast
from ..syntax.visitor import Visitor
from ..versions import LanguageLevel
from .target import TargetNode


class Transformer(Visitor):
    def __init__(self, level: LanguageLevel):
        self.level = level
        self.used_features: set[str] = set()   # drives prelude selection

    # -- Template Method ---------------------------------------------------
    def transform(self, program: ast.Program, source: str) -> TargetNode:
        defect = program.defect
        if isinstance(defect, (LexDefect, ParseDefect)) or (
                defect is not None
                and not isinstance(defect, SemanticDefect)):
            # lexical / preprocessor / syntactic: the tree is unusable;
            # re-emit the program token- (or character-) faithfully with
            # the native flaw preserved at the equivalent position
            return self.transform_defect(defect, program, source)
        # valid program, or a semantic defect wrapped in an intact tree:
        # full structural translation (the defective node itself translates
        # to a construct that fails natively in the target)
        return self.build_program(program)

    # -- hooks -------------------------------------------------------------
    def build_program(self, program: ast.Program) -> TargetNode:
        raise NotImplementedError

    def transform_defect(self, defect: Defect, program: ast.Program,
                         source: str) -> TargetNode:
        raise NotImplementedError

    def declared_phase(self, program: ast.Program) -> Phase | None:
        """The phase at which this program's translation fails under the
        real toolchain (None for valid programs)."""
        raise NotImplementedError
