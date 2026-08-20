"""Phase 4 — backend registry (Factory).

A backend is a bundle: target AST + Transformer + Printer + toolchain
recipe.  Adding a language means one new ``codegen/<lang>/`` package and
one :func:`register` call — nothing else in the pipeline changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Backend:
    name: str                       # registry key: "go", "julia"
    ext: str                        # file extension: "go", "jl"
    transformer_cls: type
    printer_cls: type
    build_template: Optional[str]   # e.g. "go build -o {exe_file} {src_file}"; None = no build step
    run_template: str               # e.g. "{exe_file}" or "julia {src_file}"
    docker_image: str               # images/<name> used by the harness


_REGISTRY: dict[str, Backend] = {}


def register(backend: Backend) -> Backend:
    _REGISTRY[backend.name] = backend
    return backend


def get_backend(name: str) -> Backend:
    try:
        return _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "none loaded"
        raise ValueError(f"Unknown target {name!r} (known: {known})") from None


def available() -> list[str]:
    return sorted(_REGISTRY)
