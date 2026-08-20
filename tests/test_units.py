"""Focused unit tests for the pieces the corpus exercises only obliquely."""

import pytest

from compiler_testing_lib.transpiler.codegen import get_backend
from compiler_testing_lib.transpiler.codegen.base import rebind
from compiler_testing_lib.transpiler.codegen.passthrough import render_tokens
from compiler_testing_lib.transpiler.diagnostics import ErrorCategory
from compiler_testing_lib.transpiler.ir import lower, nodes as ir
from compiler_testing_lib.transpiler.driver import parse_source
from compiler_testing_lib.transpiler.lexical import Lexer, TokenKind, preprocess
from compiler_testing_lib.transpiler.semantic.analyzer import _trunc_div
from compiler_testing_lib.transpiler.versions import LEVELS, get_level


def test_get_level_rejects_unknown_version():
    with pytest.raises(ValueError, match="Unknown course version"):
        get_level("v7.7")


def test_every_level_is_registered_with_its_own_name():
    for name, level in LEVELS.items():
        assert level.name == name


def test_get_backend_rejects_unknown_target():
    with pytest.raises(ValueError, match="Unknown target"):
        get_backend("cobol")


def test_error_category_phase_tags():
    assert ErrorCategory.LEX_INVALID_TOKEN.phase_tag == "[Lexer]"
    assert ErrorCategory.PARSE_MISSING_TOKEN.phase_tag == "[Parser]"
    assert ErrorCategory.SEM_DIV_ZERO.phase_tag == "[Semantic]"
    assert ErrorCategory.PREPRO_INVALID_DEFINE.phase_tag == "[PrePro]"


def test_trunc_div_truncates_toward_zero_like_c():
    assert _trunc_div(7, 2) == 3
    assert _trunc_div(-7, 2) == -3
    assert _trunc_div(7, -2) == -3
    assert _trunc_div(-7, -2) == 3


def test_lexer_marks_digit_led_words_malformed():
    tokens = Lexer("1x = 3;", get_level("v2.0")).tokenize()
    assert tokens[0].kind is TokenKind.IDEN and tokens[0].malformed


def test_preprocess_substitutes_whole_words_only():
    text, macros, defect = preprocess("#define N 1\nNN = N;\n")
    assert defect is None and macros == {"N": "1"}
    assert "NN = 1" in text and "11" not in text


def test_render_tokens_injects_marker_at_error_index():
    tokens = Lexer("x = (1;", get_level("v2.0")).tokenize()
    text = render_tokens(tokens, error_index=4, marker="}")
    assert "} ;" in text


def test_rebind_swaps_classes_recursively():
    program = parse_source("void main() {\n  printf(1);\n}\n", "v2.3")
    module = lower(program, get_level("v2.3"))
    backend = get_backend("go")(get_level("v2.3"))
    rebind(module, backend.NODES)
    assert type(module).__module__.endswith("codegen.go")
    func = module.funcs[0]
    assert type(func).__module__.endswith("codegen.go")   # Go FuncDef


def test_lowering_normalizes_statement_programs_into_main():
    program = parse_source("x = 1;\nprintf(x);\n", "v2.0")
    module = lower(program, get_level("v2.0"))
    assert [f.name for f in module.funcs] == ["main"]
    assert isinstance(module.funcs[0].body[0], ir.DeclareLocal)


def test_lowering_desugars_for_into_while():
    source = "i = 0;\nfor (i = 0; i < 3; i = i + 1)\n{\n  printf(i);\n}\n"
    program = parse_source(source, "x2.1")
    module = lower(program, get_level("x2.1"))
    kinds = [type(s).__name__ for s in module.funcs[0].body]
    assert "While" in kinds and "For" not in kinds


def test_backend_node_tables_are_isolated():
    go_nodes = get_backend("go").NODES
    julia_nodes = get_backend("julia").NODES
    assert go_nodes["While"] is not julia_nodes["While"]
    # nodes without a backend equivalent fall back to the shared default
    assert go_nodes["IntConst"] is julia_nodes["IntConst"]


def test_julia_quote_escapes_interpolation():
    backend = get_backend("julia")(get_level("v2.2"))
    assert backend.quote('a$b"c') == '"a\\$b\\"c"'
