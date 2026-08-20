"""Command-line interface.

    python -m compiler_testing_lib.transpiler transpile --target go [--version v2.3] input.c [-o out.go]
    python -m compiler_testing_lib.transpiler generate  --target julia --versions v2.3,x2.3 [--out DIR] [--jobs 8] [--no-validate]
    python -m compiler_testing_lib.transpiler verify    --target go --versions all
"""

from __future__ import annotations

import argparse
import os
import sys

from . import transpile
from .codegen import available
from .harness.generate import CORPUS_ROOT, generate_version, render_report
from .versions import LEVELS


def _resolve_versions(spec: str) -> list[str]:
    if spec == "all":
        corpus_dir = os.path.normpath(os.path.join(CORPUS_ROOT, "C"))
        return sorted(v for v in os.listdir(corpus_dir) if v in LEVELS)
    return spec.split(",")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="compiler_testing_lib.transpiler")
    sub = parser.add_subparsers(dest="command", required=True)

    p_transpile = sub.add_parser("transpile",
                                 help="translate one source file")
    p_transpile.add_argument("input")
    p_transpile.add_argument("--target", required=True, choices=available())
    p_transpile.add_argument("--version", default="v2.3",
                             choices=sorted(LEVELS))
    p_transpile.add_argument("-o", "--output")

    for name in ("generate", "verify"):
        p = sub.add_parser(name)
        p.add_argument("--target", required=True, choices=available())
        p.add_argument("--versions", default="all")
        p.add_argument("--out", default=None,
                       help="output corpus root (default: the package's "
                            "languages/ directory)")
        p.add_argument("--jobs", type=int, default=8)
        p.add_argument("--toolchain", default="local",
                       choices=("local", "docker"))
        if name == "generate":
            p.add_argument("--no-validate", action="store_true",
                           help="write translations without running them")
        p.add_argument("--report", default=None,
                       help="write the markdown report to this file")

    args = parser.parse_args(argv)

    if args.command == "transpile":
        with open(args.input) as handle:
            source = handle.read()
        result = transpile(source, args.target, args.version)
        if args.output:
            with open(args.output, "w") as handle:
                handle.write(result.code)
        else:
            sys.stdout.write(result.code)
        if result.defect is not None:
            print(f"# diagnosed: {result.defect.message} "
                  f"(fails at {result.phase.value})", file=sys.stderr)
        return 0

    # generate writes (and validates) the target corpus; verify does the
    # same work into a scratch directory, only reporting equivalence
    reports = []
    validate = not getattr(args, "no_validate", False)
    if args.command == "verify" and args.out is None:
        import tempfile
        args.out = tempfile.mkdtemp(prefix="ctl-verify-")
        validate = True
    for version in _resolve_versions(args.versions):
        report = generate_version(args.target, version, out_root=args.out,
                                  toolchain_mode=args.toolchain,
                                  jobs=args.jobs, validate=validate)
        reports.append(report)
        failures = len(report.failures)
        status = "ok" if failures == 0 else f"{failures} DIVERGENCES"
        print(f"{args.target} {version}: "
              f"{len(report.outcomes) - failures}/{len(report.outcomes)} "
              f"{status}")
    text = render_report(args.target, reports)
    if args.report:
        with open(args.report, "w") as handle:
            handle.write(text)
    total_failures = sum(len(r.failures) for r in reports)
    if total_failures:
        print(text)
    return 1 if total_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
