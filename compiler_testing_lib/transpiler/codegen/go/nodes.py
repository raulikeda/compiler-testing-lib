"""Go target AST (Composite).

A deliberately small model of Go — just the shapes the course language
needs — plus the shared ``Raw`` escape hatch for defect splices.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..target import TargetNode


# -- expressions ----------------------------------------------------------

@dataclass
class GoLit(TargetNode):
    text: str = ""                  # 42, 1.6, "abc", true


@dataclass
class GoName(TargetNode):
    name: str = ""


@dataclass
class GoBin(TargetNode):
    op: str = ""                    # + - * / == < > && || ^
    left: TargetNode = None
    right: TargetNode = None


@dataclass
class GoUn(TargetNode):
    op: str = ""                    # + - !
    operand: TargetNode = None


@dataclass
class GoCall(TargetNode):
    func: str = ""                  # fmt.Println, __scanf, fac, int, float64
    args: list = field(default_factory=list)


@dataclass
class GoField(TargetNode):
    obj: TargetNode = None
    name: str = ""


# -- statements -----------------------------------------------------------

@dataclass
class GoBlock(TargetNode):
    stmts: list = field(default_factory=list)


@dataclass
class GoVarDecl(TargetNode):
    name: str = ""
    go_type: str = ""
    init: Optional[TargetNode] = None
    blank_use: bool = True          # emit "_ = name" (kills declared-and-not-used)


@dataclass
class GoAssign(TargetNode):
    target: TargetNode = None
    expr: TargetNode = None
    declare: bool = False           # ":=" first assignment of an untyped var
    blank_use: bool = False


@dataclass
class GoConstDecl(TargetNode):
    name: str = ""
    init: TargetNode = None


@dataclass
class GoExprStmt(TargetNode):
    expr: TargetNode = None


@dataclass
class GoIf(TargetNode):
    cond: TargetNode = None
    then: GoBlock = None
    other: Optional[GoBlock] = None


@dataclass
class GoFor(TargetNode):
    """Covers both C while (cond only) and x2.1 for (init/post as text)."""
    init: Optional[TargetNode] = None
    cond: Optional[TargetNode] = None
    post: Optional[TargetNode] = None
    body: GoBlock = None


@dataclass
class GoReturn(TargetNode):
    expr: Optional[TargetNode] = None


# -- declarations ---------------------------------------------------------

@dataclass
class GoFunc(TargetNode):
    name: str = ""
    params: list = field(default_factory=list)   # [(name, go_type)]
    ret: str = ""                                # "" for void
    body: GoBlock = None


@dataclass
class GoStruct(TargetNode):
    name: str = ""
    fields: list = field(default_factory=list)   # [(name, go_type)]


@dataclass
class GoFile(TargetNode):
    imports: list = field(default_factory=list)
    prelude: list = field(default_factory=list)  # Raw helper blocks
    decls: list = field(default_factory=list)
