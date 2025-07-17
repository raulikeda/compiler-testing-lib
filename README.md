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