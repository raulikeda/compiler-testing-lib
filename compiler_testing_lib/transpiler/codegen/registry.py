"""Phase 4 — backend registry (Factory).

A backend IS its :class:`~.spec.LanguageSpec` subclass: the declarative
equivalence tables plus the toolchain recipe (``build_template``,
``run_template``, ``ext``, ``docker_image``) are class attributes.  Adding
a language means one new spec module decorated with :func:`register` —
nothing else in the pipeline changes.
"""

from __future__ import annotations

_REGISTRY: dict[str, type] = {}


def register(spec_cls: type) -> type:
    """Class decorator: puts a LanguageSpec subclass in the registry."""
    _REGISTRY[spec_cls.name] = spec_cls
    return spec_cls


def get_backend(name: str) -> type:
    try:
        return _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "none loaded"
        raise ValueError(f"Unknown target {name!r} (known: {known})") from None


def available() -> list[str]:
    return sorted(_REGISTRY)
