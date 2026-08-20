"""Shared fixtures: the C corpus is the test oracle.

Every corpus test (program + expected diagnostic/stdout) is exposed as a
pytest parameter, so the suite asserts exactly what the course grades.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
import yaml

CORPUS = (Path(__file__).resolve().parent.parent
          / "compiler_testing_lib" / "languages" / "C")

# Corpus entries whose recorded message is impossible for the recorded file
# (copy-paste artifacts); the front end's intended diagnosis is asserted
# instead.  All three still carry the correct [Parser] tag.
KNOWN_ARTIFACTS = {
    ("v2.1", "test017"): "[Parser] Unexpected token EOF",
    ("v2.2", "test017"): "[Parser] Unexpected token EOF",
    ("v2.3", "test034"): "[Parser] Unexpected token EOF (expected OPEN_BRA)",
}


def corpus_cases() -> list:
    cases = []
    for version in sorted(os.listdir(CORPUS)):
        yaml_path = CORPUS / version / "tests.yaml"
        if not yaml_path.exists():
            continue
        tests = yaml.safe_load(yaml_path.read_text())["tests"]
        for test in tests:
            source = (CORPUS / version / f"{test['name']}.c").read_text()
            cases.append(pytest.param(version, test, source,
                                      id=f"{version}-{test['name']}"))
    return cases


CORPUS_CASES = corpus_cases()


def pytest_generate_tests(metafunc):
    if {"version", "test", "source"} <= set(metafunc.fixturenames):
        metafunc.parametrize(("version", "test", "source"), CORPUS_CASES)


def expected_message(version: str, test: dict) -> str | None:
    """The diagnostic the front end must produce (None = clean)."""
    if not test.get("exception"):
        return None
    expected = test["output"][0] if test["output"] else None
    return KNOWN_ARTIFACTS.get((version, test["name"]), expected)


def toolchain_available(name: str) -> bool:
    return shutil.which(name) is not None


requires_go = pytest.mark.skipif(not toolchain_available("go"),
                                 reason="go toolchain not on PATH")
requires_julia = pytest.mark.skipif(not toolchain_available("julia"),
                                    reason="julia toolchain not on PATH")
