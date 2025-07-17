# Compiler Testing Lib

A Python library to run language/compiler tests defined in YAML files, supporting multiple languages and versions.

## Directory Structure

```
languages/
  python/
    v1.0/
      test001.py
      test002.py
      test.yaml
```

## test.yaml Example

```yaml
tests:
  - index: 1
    name: test001
    description: Check if 7 is a prime number using Python.
    input: [7]
    result: true
    output: |
      The input value 7 is a prime number.
      Function returned True as expected.
    exception: None

  - index: 2
    name: test002
    description: Check if 10 is a prime number using Python.
    input: [10]
    result: false
    output: |
      The input value 10 is not a prime number.
      Function returned False as expected.
    exception: None
```

## Usage

Install the library:

```bash
pip install .
```

Run the tests in Python:

```python
from compiler_testing_lib.runner import TestRunner

runner = TestRunner('python', 'v1.0')
results = runner.run_python_tests()
for result in results:
    print(result)
```