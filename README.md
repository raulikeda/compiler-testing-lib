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

## Multi-file submissions

The whole student repository is cloned into the container, and the runner
executes the repository's `command_template` once per test with the test file
(or, for v0.0–v1.2, the source text) appended as the last argument. Splitting
the compiler into several files is supported per language as follows:

- **Python** (`python3 main.py`): `codecheck` follows every project-local
  import from the entry file — flat modules (`from lexer import Lexer`),
  sub-packages with or without `__init__.py` (`from src.parser import Parser`,
  `from src import lexer`, `import src.tokens`) and relative imports inside
  packages (`from .lexer import Lexer`). Cycles are fine.
- **Go** (`go run .`; the legacy `go run main.go` template is rewritten to it
  at runtime by `runner.normalize_command_template`): every `*.go` at the
  repository root is built as one package. The image runs with
  `GO111MODULE=auto`, so a `go.mod` is optional for that layout and
  **required** for sub-packages (`import "<module>/lexer"`; run
  `go mod init <name>`) — the runner says so instead of failing the build.
- **Java** (`java main.java`, JDK 25): the launcher compiles the other source
  files on demand (JEP 458). Each class must live in a file named after it, in
  a directory matching its package (`Parser.java`, `lexer/Lexer.java` with
  `package lexer;`); only `main.java` is exempt from that rule.

### DS (syntax diagram) link

For versions ≥ v1.0 the README must link the diagram served by compiler-tester.
Both forms are accepted, parameters in any order:

```
https://compiler-tester.insper-comp.com.br/ds?version=v2.1
https://compiler-tester.insper-comp.com.br/ds?version=v2.1&language=go
```

The `language` parameter is optional (the server has a per-semester default); a
link naming a *different* language than the one being tested is rejected.

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