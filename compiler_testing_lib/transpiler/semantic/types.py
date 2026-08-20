"""Phase 3 — the course type system.

Types are lightweight values: the four scalars are interned strings and a
struct type carries its name and field table.  ``spelled`` gives the
uppercase spelling the reference uses in diagnostics (``FLOAT and STR``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

INT = "int"
STR = "str"
BOOL = "bool"
FLOAT = "float"
VOID = "void"

SCALARS = {INT, STR, BOOL, FLOAT, VOID}


@dataclass(frozen=True)
class StructType:
    name: str
    fields: tuple = field(default_factory=tuple)   # ((name, scalar type), ...)

    def field_type(self, fieldname: str):
        for fname, ftype in self.fields:
            if fname == fieldname:
                return ftype
        return None


def is_struct(t) -> bool:
    return isinstance(t, StructType)


def is_numeric(t) -> bool:
    return t == INT or t == FLOAT


def spelled(t) -> str:
    """Uppercase spelling used in reference diagnostics."""
    return t.name.upper() if is_struct(t) else str(t).upper()
