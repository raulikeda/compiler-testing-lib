"""Phase 4 — code generation: pluggable target-language backends.

Importing this package registers the built-in backends.
"""

from .registry import Backend, available, get_backend
from . import go        # noqa: F401  (registers the Go backend)

__all__ = ["Backend", "available", "get_backend"]
