"""The intermediate representation: small, typed, target-neutral.

Lowering (:mod:`.lowering`) resolves every course-language question —
scoping, name kinds, operator meaning, implicit ``main``, desugaring —
into this vocabulary; backends only spell it.  Design rules:

* Every expression node carries ``type`` (a :mod:`..semantic.types` value:
  ``"int"``, ``"str"``, ..., or :class:`~..semantic.types.StructType`).
* Operators are a closed enum of *resolved* operations — ``div_int`` and
  ``div_float`` are distinct; ``concat`` is explicit; there is no ``for``.
* Name references are pre-resolved into kinds (:class:`LocalRef`,
  :class:`GlobalRef`, :class:`ConstRef`, :class:`FieldRef`) —
  :class:`UnresolvedRef` is itself meaningful: the course program used an
  undeclared name, and the translation must fail natively there.
* A diagnosed type violation appears as an explicit :class:`CheckType`
  wrapper at the equivalent point; a backend whose own type system already
  rejects the code emits it transparently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Binary.op values
BINARY_OPS = ("add", "sub", "mul", "div_int", "div_float", "xor", "pow",
              "concat", "eq", "lt", "gt", "and_", "or_")
# Unary.op values
UNARY_OPS = ("neg", "pos", "not_", "fact")
# Cast.kind values
CAST_KINDS = ("to_int", "to_float", "to_str", "to_bool", "bool_to_int")


@dataclass
class IRNode:
    pass


# -- references (usable as expressions and assignment targets) ------------

@dataclass
class Ref(IRNode):
    name: str = ""
    type: object = "int"


@dataclass
class LocalRef(Ref):
    pass


@dataclass
class GlobalRef(Ref):
    pass


@dataclass
class ConstRef(Ref):
    pass


@dataclass
class UnresolvedRef(Ref):
    """A name the course program never declared — must fail natively."""


@dataclass
class FieldRef(IRNode):
    obj: str = ""
    fieldname: str = ""
    type: object = "int"


# -- expressions ----------------------------------------------------------

@dataclass
class IntConst(IRNode):
    value: int = 0
    type: object = "int"


@dataclass
class FloatConst(IRNode):
    lexeme: str = "0.0"      # keep the exact source spelling
    type: object = "float"


@dataclass
class StrConst(IRNode):
    value: str = ""
    type: object = "str"


@dataclass
class BoolConst(IRNode):
    value: bool = False
    type: object = "bool"


@dataclass
class Binary(IRNode):
    op: str = "add"          # one of BINARY_OPS
    left: IRNode = None
    right: IRNode = None
    type: object = "int"


@dataclass
class Unary(IRNode):
    op: str = "neg"          # one of UNARY_OPS
    operand: IRNode = None
    type: object = "int"


@dataclass
class Call(IRNode):
    name: str = ""
    args: list = field(default_factory=list)
    type: object = "int"


@dataclass
class ReadInt(IRNode):       # scanf(): one integer from stdin
    type: object = "int"


@dataclass
class Cast(IRNode):
    kind: str = "to_int"     # one of CAST_KINDS
    operand: IRNode = None
    type: object = "int"


@dataclass
class Ternary(IRNode):
    cond: IRNode = None
    then: IRNode = None
    other: IRNode = None
    type: object = "int"


@dataclass
class CheckType(IRNode):
    """The diagnosed type violation: ``operand`` does not have
    ``expected`` under the course rules.  Statically-typed backends emit
    the operand unchanged (their compiler rejects it); dynamic backends
    emit a strict runtime check that raises natively."""
    expected: object = "int"
    operand: IRNode = None
    type: object = "int"


# -- statements -----------------------------------------------------------

@dataclass
class DeclareLocal(IRNode):
    name: str = ""
    type: object = "int"
    init: Optional[IRNode] = None


@dataclass
class Assign(IRNode):
    target: IRNode = None    # a Ref subclass or FieldRef
    expr: IRNode = None


@dataclass
class Print(IRNode):         # newline-terminated course printf
    expr: IRNode = None


@dataclass
class ExprStmt(IRNode):
    expr: IRNode = None


@dataclass
class If(IRNode):
    cond: IRNode = None
    then: list = field(default_factory=list)
    other: Optional[list] = None


@dataclass
class While(IRNode):
    cond: IRNode = None
    body: list = field(default_factory=list)


@dataclass
class Scope(IRNode):
    """An explicit lexical scope (a typed-stage C ``{}`` block)."""
    body: list = field(default_factory=list)


@dataclass
class Return(IRNode):
    expr: Optional[IRNode] = None


# -- declarations ---------------------------------------------------------

@dataclass
class StructDef(IRNode):
    name: str = ""
    fields: list = field(default_factory=list)   # [(name, type)]


@dataclass
class GlobalDef(IRNode):
    name: str = ""
    type: object = "int"
    init: Optional[IRNode] = None


@dataclass
class ConstDef(IRNode):      # x2.0 const: immutable named value
    name: str = ""
    init: IRNode = None


@dataclass
class FuncDef(IRNode):
    name: str = ""
    params: list = field(default_factory=list)   # [(name, type)]
    ret: object = "void"
    body: list = field(default_factory=list)


@dataclass
class Module(IRNode):
    """A whole lowered program.  The entry point, when the source has one,
    is the ``main`` FuncDef (lowering wraps statement/expression programs
    into one); its absence is itself meaningful — the translation must
    fail natively for lack of an entry point."""
    structs: list = field(default_factory=list)
    consts: list = field(default_factory=list)
    globals: list = field(default_factory=list)
    funcs: list = field(default_factory=list)
