"""Corpus generation: translate the C corpus into a target-language corpus.

For every ``languages/C/<version>/testNNN.c`` this driver writes
``languages/<target>/<version>/testNNN.<ext>`` plus a ``tests.yaml``, and
validates each translation under the real toolchain:

* valid tests must build, run with the corpus stdin, and print the corpus
  stdout exactly;
* invalid tests must fail in the phase the backend declared (``parse``
  defects additionally with empty stdout).

The generated ``tests.yaml`` keeps the course schema (``output`` still
holds the course tag the student compiler must print, so the existing
runner keeps working) and adds two fields per invalid test:
``error_phase`` (parse|build|run) and ``native_error`` (the first line of
the real toolchain's diagnostic, informational).
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import yaml

from .. import transpile
from ..diagnostics import Phase
from .toolchain import Toolchain

CORPUS_ROOT = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "..", "languages")


@dataclass
class TestOutcome:
    name: str
    ok: bool
    detail: str = ""
    phase: str | None = None
    native_error: str = ""
    partial_output: list = field(default_factory=list)


@dataclass
class VersionReport:
    version: str
    outcomes: list = field(default_factory=list)

    @property
    def failures(self) -> list:
        return [o for o in self.outcomes if not o.ok]


def _first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def _validate(result, test, toolchain) -> TestOutcome:
    name = test["name"]
    run = toolchain.run_source(result.code, "\n".join(test["input"]))
    phase = result.phase.value if result.phase else None
    native = _first_line(run.build_stderr or run.stderr)
    if phase is None:
        expected_out = "\n".join(test["output"])
        if not run.build_ok:
            return TestOutcome(name, False,
                               f"valid test failed to build: {native}")
        if run.exit_code != 0:
            return TestOutcome(name, False,
                               f"valid test exited {run.exit_code}: {native}")
        if run.stdout.strip() != expected_out.strip():
            return TestOutcome(
                name, False, f"stdout mismatch: expected "
                f"{expected_out!r}, got {run.stdout.strip()!r}")
        return TestOutcome(name, True)
    if phase == Phase.BUILD.value:
        if run.build_ok:
            return TestOutcome(name, False,
                               "expected the build to fail, but it succeeded",
                               phase=phase)
        return TestOutcome(name, True, phase=phase, native_error=native)
    # parse/run phases: no separate build step, the program must fail
    if run.build_ok and run.exit_code == 0:
        return TestOutcome(name, False,
                           f"expected a {phase}-phase failure, exited 0",
                           phase=phase)
    if phase == Phase.PARSE.value and run.stdout.strip():
        return TestOutcome(name, False,
                           f"parse-phase defect printed {run.stdout!r} "
                           "before failing", phase=phase)
    partial = run.stdout.splitlines() if run.stdout.strip() else []
    return TestOutcome(name, True, phase=phase, native_error=native,
                       partial_output=partial)


def generate_version(target: str, version: str, out_root: str | None = None,
                     toolchain_mode: str = "local", jobs: int = 8,
                     validate: bool = True) -> VersionReport:
    from ..codegen import get_backend

    backend_cls = get_backend(target)
    src_dir = os.path.normpath(os.path.join(CORPUS_ROOT, "C", version))
    out_dir = os.path.normpath(os.path.join(out_root or CORPUS_ROOT,
                                            target, version))
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(src_dir, "tests.yaml")) as handle:
        tests = yaml.safe_load(handle)["tests"]

    report = VersionReport(version=version)
    entries: list[dict] = []

    def process(test):
        with open(os.path.join(src_dir, f"{test['name']}.c")) as handle:
            source = handle.read()
        result = transpile(source, target, version)
        ext = backend_cls.ext
        with open(os.path.join(out_dir, f"{test['name']}.{ext}"), "w") as out:
            out.write(result.code)
        if validate:
            toolchain = Toolchain(backend_cls, mode=toolchain_mode)
            outcome = _validate(result, test, toolchain)
        else:
            outcome = TestOutcome(test["name"], True,
                                  phase=result.phase.value
                                  if result.phase else None)
        entry = {"index": test["index"], "name": test["name"],
                 "description": test["description"], "input": test["input"],
                 "output": test["output"], "exception": test["exception"]}
        if outcome.phase is not None:
            entry["error_phase"] = outcome.phase
            if outcome.native_error:
                entry["native_error"] = outcome.native_error
        if outcome.partial_output:
            entry["partial_output"] = outcome.partial_output
        return outcome, entry

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for outcome, entry in pool.map(process, tests):
            report.outcomes.append(outcome)
            entries.append(entry)

    entries.sort(key=lambda e: e["index"])
    with open(os.path.join(out_dir, "tests.yaml"), "w") as handle:
        yaml.safe_dump({"tests": entries}, handle, sort_keys=False,
                       allow_unicode=True)
    return report


def render_report(target: str, reports: list[VersionReport]) -> str:
    lines = [f"# Corpus generation report — target: {target}", ""]
    for report in reports:
        total = len(report.outcomes)
        ok = total - len(report.failures)
        lines.append(f"## {report.version}: {ok}/{total} equivalent")
        for failure in report.failures:
            lines.append(f"- **{failure.name}**: {failure.detail}")
        lines.append("")
    return "\n".join(lines)
