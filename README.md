# Compiler Testing Lib

A flexible, multi-language testing framework for compiler and language feature validation. Designed to run language-specific tests defined in YAML files, with support for running tests via Python, Docker, or as a CI/CD step.

## Features
- **Multi-language support:** Organize tests for Python, JavaScript, and more.
- **YAML-based test definitions:** Centralized, versioned test metadata.
- **Pluggable runners:** Run tests using Python, Node.js, or any command-line tool.
- **Docker integration:** Build and run tests in isolated containers, with support for auto-cloning test repos.
- **PyPI package:** Installable as `compiler-testing-lib`.
- **Submodule example repo:** See `compiler-testing-example` for a ready-to-use test suite.

## Directory Structure
```
compiler-testing-lib/           # Main library package
  compiler_testing_lib/
    __init__.py
    runner.py
    languages/                  # Test definitions and source files (per language/version)
      python/
        v1.0/
          test001.py
          test002.py
          test.yaml
  setup.py
  MANIFEST.in
  ...
compiler-testing-example/       # Example repo (as a git submodule)
images/                        # Docker build and run scripts
  python/
    Dockerfile
    run_in_container.py
  run.sh
  mount.sh
  clean.sh
```

## Installation

### As a Python Library
```bash
pip install compiler-testing-lib
```

### For Local Development
```bash
pip install -e .
```

### Install Example Requirements
```bash
pip install -r compiler-testing-example/requirements.txt
```

## Usage

### 1. **Run Tests via Python**
```python
from compiler_testing_lib.runner import TestRunner
runner = TestRunner(language='python', version='v1.0', max_errors=3, timeout=10, file_extension='py')
result = runner.run_tests(command_template='python3 main.py')
print(result)
```

### 2. **Run Tests via Example Scripts**
```bash
python3 compiler-testing-example/test.sh           # Python runner (default)
python3 compiler-testing-example/test.sh js        # Node.js runner
```

### 3. **Run in Docker**
Build the image:
```bash
cd images
./mount.sh
```
Run the container (auto-clones the example repo and runs tests):
```bash
./run.sh
```

## Docker Image Details
- Installs the latest `compiler-testing-lib` from PyPI.
- Accepts `--git_username` and `--git_repository` to auto-clone a test repo.
- Runs all tests and prints results to the terminal.

## Adding/Updating Tests
- Place new test files and update `test.yaml` in the appropriate `languages/<lang>/<version>/` directory inside `compiler_testing_lib/`.
- Rebuild and upload the package to PyPI for distribution.

## Syncing Generated Tests
- Use `./copy.sh <language> <version>` from the repo root to pull tests from `../compiler-tests-generator/output/<language>/<version>/` into `compiler_testing_lib/languages/<language>/<version>/` (e.g., `./copy.sh C v0.0`).
- The script cleans the destination version folder before copying, so ensure you have the desired generator output ready.

## Additional code syntax checking
- The lib also checks syntax based on struct.json file in the `syntax/<version>` directory. The tested code must implement all the expected structure (including static features) designed in the file and can't have additional features. It also does some code quality check, like main clause. Only working for Python now. Pending: pep8 and snake_case check.

## Reference Transpiler (`compiler_testing_lib.transpiler`)

A reference transpiler that translates the course's C-subset test corpus into real target languages (Go and Julia built in, pluggable). Its defining property: **invalid programs are accepted and translated into target code that fails natively at the equivalent point** — a missing `)` stays missing so the target's own parser rejects it, an incompatible assignment fails the target's type check (Go, at build) or a strict runtime check (Julia, a native `TypeError`), and valid programs print identical stdout. It is the oracle used to generate target-language corpora with expected outputs.

### Architecture (standard multi-target compiler pipeline)

```
source ──lexical──▶ tokens ──syntax──▶ AST ──semantic──▶ analyzed AST
                                                              │
                                              ┌────── ir.lowering ──────┐
   (lex/parse defects bypass the IR:          ▼                         │
    token passthrough keeps the flaw)   typed IR (ir.nodes)             │
                                              │                         │
                                        codegen.<target>  ◀── one IREmitter per language
                                              ▼
                                        target source
```

- `transpiler/lexical`, `syntax`, `semantic` — error-tolerant front end. It never rejects input: the first defect is recorded as a `[Lexer]`/`[Parser]`/`[Semantic]` diagnostic (reproducing the reference compilers' exact messages, validated against the whole corpus) and translation continues.
- `transpiler/ir` — a small, typed, target-neutral IR plus the lowering pass. Everything course-specific is resolved here once: name kinds, scoping, `for`-desugaring, `div_int` vs `div_float`, the implicit `main`, and the diagnosed defect materialized as an explicit `CheckType`/`UnresolvedRef` node.
- `transpiler/codegen` — one `IREmitter` subclass per target (`go.py`, `julia.py`) declaring spellings, shims, toolchain recipe, and defect strategy (in which phase each defect fails: parse/build/run). Adding a language touches nothing else.
- `transpiler/harness` — corpus generation and verification under the real toolchains.

### CLI

```bash
# translate one file
python -m compiler_testing_lib.transpiler transpile --target go --version v2.3 test001.c -o test001.go

# generate a full target-language corpus (files + tests.yaml) with validation
python -m compiler_testing_lib.transpiler generate --target julia --versions all

# re-check equivalence without touching the corpus
python -m compiler_testing_lib.transpiler verify --target go --versions v2.3,x2.3
```

Generated `tests.yaml` files keep the course schema and add `error_phase: parse|build|run` (plus an informational `native_error`) for invalid tests. `TestRunner.run_tests` accepts `build_template`/`run_template`/`target_extension` (generalizing the v3.0 asm flow) and `native_errors=True` for grading against transpiler-generated corpora.

## Contributing
1. Fork the repo and create a feature branch.
2. Add or update tests in `compiler_testing_lib/languages/`.
3. Update `test.yaml` as needed.
4. Run tests locally or in Docker.
5. Submit a pull request.

## License
MIT

---

**For more examples, see the `compiler-testing-example` submodule.**