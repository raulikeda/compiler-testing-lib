#!/usr/bin/env python3
import os
from compiler_testing_lib.runner import TestRunner

# Assume we want to run the tests for python/v1.0
runner = TestRunner(language='python', version='v1.0', max_errors=3, timeout=10, file_extension='py')
result = runner.run_tests(command_template='python3 example/main.py')

if result == "":
    print("\033[92mAll tests passed!\033[0m")  # Green text
else:
    print("\n\033[91mTest Divergences:\033[0m\n")  # Red text
    print(result)

# Optionally, demonstrate running main.py with a test file
def run_main_with_codefile(codefile):
    os.system(f"python3 example/main.py {codefile}")

# Example usage (uncomment to run):
# run_main_with_codefile('languages/python/v1.0/test001.py') 