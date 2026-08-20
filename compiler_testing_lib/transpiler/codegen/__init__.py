"""Phase 4 — code generation: backends emit the typed IR.

The front end and the lowering pass (:mod:`..ir`) resolve everything
course-specific; a backend is an :class:`~.base.IREmitter` subclass that
spells the IR's small, stable vocabulary and declares its toolchain and
defect strategy.  Importing this package registers the built-in backends.
"""

from .base import IREmitter
from .registry import available, get_backend
from . import go        # noqa: F401  (registers GoEmitter)
from . import julia     # noqa: F401  (registers JuliaEmitter)

__all__ = ["IREmitter", "available", "get_backend"]
