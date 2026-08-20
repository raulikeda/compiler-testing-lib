"""Phase 4 — code generation: per-node emitting classes over the typed IR.

:mod:`.base` gives every IR node a default (C-family) emitting class; a
backend module defines its :class:`~.base.Backend` plus equivalent
classes — same generic names — for exactly the nodes whose spelling
differs.  The lowered tree is rebound onto the backend's classes and
emits itself polymorphically.  Importing this package registers the
built-in backends.
"""

from .base import Backend, Context, Emitted, rebind
from .registry import available, get_backend
from . import go        # noqa: F401  (registers Go)
from . import julia     # noqa: F401  (registers Julia)

__all__ = ["Backend", "Context", "Emitted", "available", "get_backend",
           "rebind"]
