"""Run transpiled programs under the real target toolchain.

Used by corpus generation and verification: builds (when the backend has a
build step) and runs a translated test, reporting exit status and captured
output.  Toolchains are found on PATH by default; ``docker`` mode runs the
backend's course image instead.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass


@dataclass
class RunResult:
    build_ok: bool
    build_stderr: str
    ran: bool
    exit_code: int
    stdout: str
    stderr: str


class Toolchain:
    def __init__(self, backend, mode: str = "local", timeout: int = 30):
        self.backend = backend
        self.mode = mode
        self.timeout = timeout

    def run_source(self, code: str, stdin: str = "") -> RunResult:
        with tempfile.TemporaryDirectory(prefix="ctl-transpile-") as workdir:
            src_file = os.path.join(workdir, f"prog.{self.backend.ext}")
            with open(src_file, "w") as handle:
                handle.write(code)
            return self.run_file(src_file, stdin, workdir)

    def run_file(self, src_file: str, stdin: str,
                 workdir: str | None = None) -> RunResult:
        workdir = workdir or os.path.dirname(src_file)
        base, _ = os.path.splitext(src_file)
        exe_file = base
        fmt = dict(src_file=src_file, exe_file=exe_file,
                   base_name=os.path.basename(base), dir=workdir)

        if self.backend.build_template is not None:
            build_cmd = self._wrap(self.backend.build_template.format(**fmt))
            build = subprocess.run(build_cmd, shell=True, capture_output=True,
                                   text=True, timeout=self.timeout,
                                   cwd=workdir)
            if build.returncode != 0:
                return RunResult(build_ok=False,
                                 build_stderr=build.stderr.strip(),
                                 ran=False, exit_code=build.returncode,
                                 stdout="", stderr="")

        run_cmd = self._wrap(self.backend.run_template.format(**fmt))
        try:
            run = subprocess.run(run_cmd, shell=True, capture_output=True,
                                 text=True, timeout=self.timeout,
                                 input=stdin, cwd=workdir)
        except subprocess.TimeoutExpired:
            return RunResult(build_ok=True, build_stderr="", ran=False,
                             exit_code=-1, stdout="", stderr="timeout")
        return RunResult(build_ok=True, build_stderr="", ran=True,
                         exit_code=run.returncode, stdout=run.stdout,
                         stderr=run.stderr)

    def _wrap(self, command: str) -> str:
        if self.mode == "docker":
            image = self.backend.docker_image
            return (f"docker run --rm -i -v {os.getcwd()}:{os.getcwd()} "
                    f"-w {os.getcwd()} {image} sh -c {command!r}")
        return command
