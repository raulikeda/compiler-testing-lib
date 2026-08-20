"""Go backend: course AST → Go AST → .go source."""

from ..registry import Backend, register
from .transformer import GoTransformer
from .printer import GoPrinter

BACKEND = register(Backend(
    name="go",
    ext="go",
    transformer_cls=GoTransformer,
    printer_cls=GoPrinter,
    build_template="go build -o {exe_file} {src_file}",
    run_template="{exe_file}",
    docker_image="compiler-testing-lib-go",
))
