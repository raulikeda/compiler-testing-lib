import sys
import argparse
from compiler_testing_lib.runner import TestRunner

parser = argparse.ArgumentParser(description='Run compiler-testing-lib in container')
parser.add_argument('--language', default='python')
parser.add_argument('--version', required=True)
parser.add_argument('--file_extension', default='py')
parser.add_argument('--max_errors', type=int, default=3)
parser.add_argument('--timeout', type=int, default=10)
parser.add_argument('--command_template', required=True)
args = parser.parse_args()

runner = TestRunner(
    language=args.language,
    version=args.version,
    max_errors=args.max_errors,
    timeout=args.timeout,
    file_extension=args.file_extension
)

result = runner.run_tests(command_template=args.command_template)

if result == "":
    print("\033[92mAll tests passed!\033[0m")
else:
    print("\n\033[91mTest Divergences:\033[0m\n")
    print(result)

# Hold the container live for inspection
try:
    print("\nContainer will stay alive. Press Ctrl+C to exit.")
    while True:
        pass
except KeyboardInterrupt:
    print("Exiting container.") 