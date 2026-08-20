"""Phase 4 — code generation.

One generic :class:`~.emitter.Emitter` walks the source AST; each target
language is a single declarative :class:`~.spec.LanguageSpec` subclass of
mechanical equivalences.  Importing this package registers the built-in
backends.
"""

from .emitter import Emitter
from .registry import available, get_backend
from .spec import LanguageSpec
from . import go        # noqa: F401  (registers GoSpec)
from . import julia     # noqa: F401  (registers JuliaSpec)

__all__ = ["Emitter", "LanguageSpec", "available", "get_backend"]
