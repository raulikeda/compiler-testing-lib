"""Code generation over the whole corpus, plus golden spot checks.

The full behavioral guarantee (translated programs run identically /
fail natively under go and julia) is asserted by the toolchain-marked
tests; here every corpus program is translated to BOTH targets and the
structural invariants are checked without external tools.
"""

import pytest

from compiler_testing_lib.transpiler import transpile
from compiler_testing_lib.transpiler.diagnostics import Phase

from conftest import CORPUS


@pytest.fixture(params=["go", "julia"])
def target(request):
    return request.param


def test_corpus_translates(version, test, source, target):
    result = transpile(source, target, version)
    assert result.code.strip(), "translation must never be empty"
    if test.get("exception"):
        assert result.phase in (Phase.PARSE, Phase.BUILD, Phase.RUN)
        if target == "go":
            # go's compiler front-loads all course phases except the
            # negative-factorial runtime panic
            assert result.phase in (Phase.BUILD, Phase.RUN)
    else:
        assert result.phase is None
        assert result.defect is None


def _code(name: str, target: str, version: str = "v2.3") -> str:
    source = (CORPUS / version / f"{name}.c").read_text()
    return transpile(source, target, version).code


def test_go_golden_snippets():
    code = _code("test001", "go")
    assert "func fac(x int) int {" in code
    assert "var A int = 2" in code
    assert "fmt.Println" in code
    assert "__scanf()" in code
    assert "__concat(" in code           # the $ operator
    assert "_ = x_1" in code             # unused-local concession


def test_julia_golden_snippets():
    code = _code("test001", "julia")
    assert "function fac(x::Int64)::Int64" in code
    assert "A::Int64 = 2" in code        # typed global
    assert "global A" in code            # main assigns the global
    assert "println(" in code
    assert "string(" in code             # the $ operator
    assert code.rstrip().endswith("main()")


def test_julia_integer_division_spelled_with_division_sign():
    code = _code("test001", "julia", version="v3.0")
    assert "÷" in code
    assert "let" in code                 # C {} blocks scope via let


def test_julia_defect_gets_strict_check():
    # int y = true;  — legal for Julia's convert, so a __chk must appear
    source = (CORPUS / "v2.3" / "test056.c").read_text()
    result = transpile(source, "julia", "v2.3")
    assert "__chk(Int64, true)" in result.code
    assert result.phase is Phase.RUN


def test_go_defect_stays_native():
    # the same defect needs no injection in Go
    source = (CORPUS / "v2.3" / "test056.c").read_text()
    result = transpile(source, "go", "v2.3")
    assert "__chk" not in result.code
    assert "var y int = true" in result.code
    assert result.phase is Phase.BUILD


def test_parse_defect_token_passthrough_keeps_flaw():
    # y = (1;   →  the missing ')' must stay missing
    source = (CORPUS / "v2.0" / "test020.c").read_text()
    go_code = transpile(source, "go", "v2.0").code
    assert "( 1" in go_code and "( 1 )" not in go_code
    julia = transpile(source, "julia", "v2.0")
    assert julia.phase is Phase.PARSE
    assert "}" in julia.code             # the julia parse marker


def test_xtrack_features():
    struct_code = _code("test001", "julia", version="x2.3")
    assert "mutable struct Student" in struct_code
    assert "Student() = new()" in struct_code
    const_code = _code("test001", "julia", version="x2.0")
    assert "__const_x.value" in const_code
    ternary_code = _code("test001", "go", version="x2.1")
    assert "__tern(" in ternary_code
    cast_code = _code("test001", "go", version="x2.2")
    assert "__toInt(" in cast_code and "__toFloat(" in cast_code


def test_unknown_target_is_rejected():
    with pytest.raises(ValueError, match="Unknown target"):
        transpile("1+1", "cobol", "v1.0")


def test_unknown_version_is_rejected():
    with pytest.raises(ValueError, match="Unknown course version"):
        transpile("1+1", "go", "v9.9")
