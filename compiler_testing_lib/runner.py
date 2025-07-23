import os
import yaml
import subprocess

class TestRunner:
    def __init__(self, language='C', version=None, max_errors=5, timeout=10, file_extension='c'):
        if version is None:
            raise ValueError("version must be specified")
        self.language = language
        self.version = version
        # Get the directory where this file (runner.py) is located
        self._root_dir = os.path.dirname(os.path.abspath(__file__))
        self.base_path = os.path.join(self._root_dir, 'languages', self.language, self.version)
        self.test_yaml_path = os.path.join(self.base_path, 'tests.yaml')
        self.tests = self.load_tests()
        self.max_errors = max_errors
        self.timeout = timeout
        self.file_extension = file_extension

    def load_tests(self):
        with open(self.test_yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        return data['tests']

    def run_tests(self, command_template):
        divergences = []
        for idx, test in enumerate(self.tests):
            test_file = os.path.join(self.base_path, f"{test['name']}.{self.file_extension}")
            command = f"{command_template} {test_file}"
            try:
                input_values = ('\n').join(test['input'])
                result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=self.timeout, input=input_values)
                stdout = result.stdout.strip()
                stderr = result.stderr.strip()
                exit_code = result.returncode
            except subprocess.TimeoutExpired:
                divergences.append({
                    'index': test.get('index', idx+1),
                    'name': test['name'],
                    'expected': 'Complete within timeout',
                    'actual': f'Timeout after {self.timeout} seconds'
                })
                break
            except Exception as e:
                divergences.append({
                    'index': test.get('index', idx+1),
                    'name': test['name'],
                    'expected': 'No generic exception during subprocess',
                    'actual': f'Exception: {str(e)}'
                })
                break
            expect_success = test.get('exception') is False or test.get('exception') == False
            expect_fail = test.get('exception') is True or test.get('exception') == True
            if expect_success:
                if exit_code != 0:
                    divergences.append({
                        'index': test.get('index', idx+1),
                        'name': test['name'],
                        'expected': f'Exit 0, output: {test.get("output", "")}',
                        'actual': f'Exit {exit_code}, stderr: {stderr}'
                    })
                elif 'output' in test and ('\n').join(test['output']) != stdout:
                    divergences.append({
                        'index': test.get('index', idx+1),
                        'name': test['name'],
                        'expected': ('\n').join(test['output']),
                        'actual': stdout
                    })
            elif expect_fail:
                if exit_code == 0:
                    divergences.append({
                        'index': test.get('index', idx+1),
                        'name': test['name'],
                        'expected': f'Exception',
                        'actual': f'Exit 0, output: {stdout}'
                    })
                # elif test.get('exception') and test.get('exception') not in [None, 'None'] and test.get('exception') not in stderr:
                #     divergences.append({
                #         'index': test.get('index', idx+1),
                #         'name': test['name'],
                #         'expected': f'Exception: {test.get("exception")}',
                #         'actual': f'Exception: {stderr}'
                #     })
            else:
                divergences.append({
                    'index': test.get('index', idx+1),
                    'name': test['name'],
                    'expected': f"Valid 'result' field (true/false)",
                    'actual': test.get('result')
                })
            if len(divergences) >= self.max_errors:
                break
        if not divergences:
            return ""
        # Format as GitHub issue markdown
        issue = []
        #issue = ["## Test Divergences Found\n"]
        #issue.append("| Test # | Name    | Expected | Actual |")
        #issue.append("|--------|---------|----------|--------|")
        for d in divergences:
            issue.append(f"Test {d['index']} | Description: {d['name']}\nExpected: {d['expected']}\nResult: {d['actual']}\n")
        return "\n".join(issue) 