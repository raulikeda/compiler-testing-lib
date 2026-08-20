"""Corpus generation harness and (toolchain-gated) end-to-end runs."""

import yaml
import pytest

from compiler_testing_lib.transpiler import transpile
from compiler_testing_lib.transpiler.codegen import get_backend
from compiler_testing_lib.transpiler.harness.generate import (
    generate_version, render_report)
from compiler_testing_lib.transpiler.harness.toolchain import Toolchain
from compiler_testing_lib.transpiler.versions import get_level

from conftest import CORPUS, requires_go, requires_julia


def test_generate_writes_corpus_and_yaml(tmp_path):
    report = generate_version("go", "v1.2", out_root=str(tmp_path),
                              validate=False)
    out_dir = tmp_path / "go" / "v1.2"
    assert (out_dir / "test001.go").exists()
    entries = yaml.safe_load((out_dir / "tests.yaml").read_text())["tests"]
    assert len(entries) == len(report.outcomes) == 24
    invalid = [e for e in entries if e["exception"]]
    assert invalid and all("error_phase" in e for e in invalid)
    # the course-facing fields are preserved verbatim
    assert entries[0]["output"] and entries[0]["exception"] is False


def test_render_report_lists_divergences(tmp_path):
    report = generate_version("julia", "x1.1", out_root=str(tmp_path),
                              validate=False)
    text = render_report("julia", [report])
    assert "# Corpus generation report" in text
    assert "x1.1: 4/4 equivalent" in text


@requires_go
@pytest.mark.toolchain
def test_go_end_to_end_valid_program():
    source = (CORPUS / "v2.3" / "test001.c").read_text()
    result = transpile(source, "go", "v2.3")
    run = Toolchain(get_backend("go")(get_level("v2.3"))).run_source(
        result.code, stdin="3")
    assert run.build_ok and run.exit_code == 0
    expected = yaml.safe_load(
        (CORPUS / "v2.3" / "tests.yaml").read_text())["tests"][0]["output"]
    assert run.stdout.strip() == "\n".join(expected)


@requires_go
@pytest.mark.toolchain
def test_go_end_to_end_defect_fails_build():
    source = (CORPUS / "v2.3" / "test056.c").read_text()   # int y = true;
    result = transpile(source, "go", "v2.3")
    run = Toolchain(get_backend("go")(get_level("v2.3"))).run_source(
        result.code)
    assert not run.build_ok
    assert "cannot use true" in run.build_stderr


@requires_julia
@pytest.mark.toolchain
def test_julia_end_to_end_parse_defect_prints_nothing():
    source = (CORPUS / "v2.0" / "test002.c").read_text()   # f = 1+;
    result = transpile(source, "julia", "v2.0")
    run = Toolchain(get_backend("julia")(get_level("v2.0"))).run_source(
        result.code)
    assert run.exit_code != 0
    assert run.stdout.strip() == ""
