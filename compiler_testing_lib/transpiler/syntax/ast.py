"""Phase 2 — the abstract syntax tree (Composite pattern).

One node hierarchy for every course version; a stage that lacks a feature
simply never produces the corresponding node.  Nodes are plain dataclasses:
consumers traverse them with Visitors (see ``codegen.visitor``), the nodes
themselves know nothing about types, targets or rendering.

``Program.defect`` carries the single diagnosed error, if any (course
compilers stop at the first error, and every corpus test seeds exactly
one).  A :class:`SemanticDefect` wraps a *well-formed* node inside an
otherwise intact tree; lexical/parse defects may leave ``tail_tokens`` for
the token-passthrough fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from ..diagnostics import Defect


@dataclass
class Node:
    """Base of the Composite; ``line``/``col`` locate the construct."""
    line: int = 0
    col: int = 0


# -- expressions ----------------------------------------------------------

@dataclass
class IntLit(Node):
    value: int = 0


@dataclass
class FloatLit(Node):
    value: float = 0.0
    lexeme: str = ""          # keep the exact spelling (1.6, 2.0, ...)


@dataclass
class StrLit(Node):
    value: str = ""


@dataclass
class BoolLit(Node):
    value: bool = False


@dataclass
class Ident(Node):
    name: str = ""


@dataclass
class FieldAccess(Node):      # student1.age            (x2.3)
    obj: Optional[Node] = None
    fieldname: str = ""


@dataclass
class BinOp(Node):
    """op is the source spelling: + - * / == < > && || $ ^ **"""
    op: str = ""
    left: Optional[Node] = None
    right: Optional[Node] = None


@dataclass
class UnOp(Node):             # prefix + - !
    op: str = ""
    operand: Optional[Node] = None


@dataclass
class PostOp(Node):           # postfix ! (factorial)   (x1.2)
    op: str = "!"
    operand: Optional[Node] = None


@dataclass
class Ternary(Node):          # cond ? a : b            (x2.1)
    cond: Optional[Node] = None
    then: Optional[Node] = None
    other: Optional[Node] = None


@dataclass
class Cast(Node):             # (int) expr              (x2.2)
    target_type: str = ""
    operand: Optional[Node] = None


@dataclass
class Scanf(Node):            # scanf() -> int
    pass


@dataclass
class Call(Node):             # fac(n)                  (v2.3)
    name: str = ""
    args: list = field(default_factory=list)


# -- statements -----------------------------------------------------------

@dataclass
class NoOp(Node):
    """Null Object: the empty statement (bare ``;``)."""


@dataclass
class Block(Node):
    stmts: list = field(default_factory=list)


@dataclass
class VarDecl(Node):          # int x = 3;  /  const x = 1;  /  struct S s;
    var_type: str = ""        # int str bool float | struct name | "" (const)
    name: str = ""
    init: Optional[Node] = None
    is_const: bool = False
    is_struct: bool = False


@dataclass
class Assign(Node):
    target: Union[Ident, FieldAccess, None] = None
    expr: Optional[Node] = None


@dataclass
class Printf(Node):
    expr: Optional[Node] = None


@dataclass
class If(Node):
    cond: Optional[Node] = None
    then: Optional[Block] = None
    other: Optional[Node] = None   # Block or None


@dataclass
class While(Node):
    cond: Optional[Node] = None
    body: Optional[Block] = None


@dataclass
class For(Node):              # for (init; cond; step) body   (x2.1)
    init: Optional[Node] = None
    cond: Optional[Node] = None
    step: Optional[Node] = None
    body: Optional[Node] = None


@dataclass
class Return(Node):
    expr: Optional[Node] = None


@dataclass
class ExprStmt(Node):         # x2.0 fallback: expression used as a statement
    expr: Optional[Node] = None


# -- declarations ---------------------------------------------------------

@dataclass
class Param(Node):
    par_type: str = ""
    name: str = ""


@dataclass
class FuncDecl(Node):
    ret_type: str = ""        # int str bool float void
    name: str = ""
    params: list = field(default_factory=list)   # [Param]
    body: Optional[Block] = None


@dataclass
class StructField(Node):
    field_type: str = ""
    name: str = ""


@dataclass
class StructDecl(Node):       # struct Student { ... };  (x2.3)
    name: str = ""
    fields: list = field(default_factory=list)   # [StructField]


@dataclass
class Program(Node):
    """Root. For program mode ``items`` holds declarations/statements; for
    expression mode (v0.0-v1.2/x1.x) it holds the single expression."""
    items: list = field(default_factory=list)
    expr_mode: bool = False
    defect: Optional[Defect] = None
