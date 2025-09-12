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

    def run_tests(self, command_template, asm_build_template=None, asm_run_template=None):
        divergences = []
        for idx, test in enumerate(self.tests):
            
            # O code não estava sendo declarado em versões acima de v1.2, então foi movido para fora do if
            test_file = os.path.join(self.base_path, f"{test['name']}.{self.file_extension}")
            with open(test_file, 'r') as f:
                code = f.read()
            
            # command = f"{command_template} {test_file}"
            # if self.version in ['v0.0', 'v1.0', 'v1.1', 'v1.2']:
            #     command = f"{command_template} '{code}'"
            
            # Default command: pass test file path to the compiler for versions > v1.2
            command = f"{command_template} {test_file}"
            if self.version in ['v0.0', 'v1.0', 'v1.1', 'v1.2']:
                # with open(test_file, 'r') as f:
                #     code = f.read()
                command = f"{command_template} '{code}'"
            try:
                input_values = ('\n').join(test['input'])
                # v3.0: compile first (no stdin), then assemble and run the generated ASM with stdin
                if self.version == 'v3.0':
                    compile_result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=self.timeout)
                    stdout = compile_result.stdout.strip()
                    stderr = compile_result.stderr.strip()
                    exit_code = compile_result.returncode
                    
                    expect_success = test.get('exception') is False or test.get('exception') == False
                    expect_fail = test.get('exception') is True or test.get('exception') == True
                    
                    # Only attempt to assemble/run if compilation succeeded and test expects success
                    if exit_code == 0 and expect_success:
                        base, _ = os.path.splitext(test_file)
                        asm_file = f"{base}.asm"
                        if not os.path.exists(asm_file):
                            divergences.append({
                                'index': test.get('index', idx+1),
                                'description': test['description'],
                                'code': code,
                                'input': input_values,
                                'expected': f'ASM file generated at {asm_file}',
                                'actual': 'ASM file not found'
                            })
                            if len(divergences) >= self.max_errors:
                                break
                            # Skip to next test
                            continue
                        # Prepare defaults for building and running ASM if templates not provided
                        exe_file = base  # produce an executable alongside the test file
                        dir_name = os.path.dirname(test_file)
                        base_name = os.path.basename(base)
                        # Build command
                        if asm_build_template:
                            build_cmd = asm_build_template.format(asm_file=asm_file, exe_file=exe_file, base_name=base_name, dir=dir_name)
                        else:
                            # Generic default: use gcc to assemble (assumes GAS syntax)
                            build_cmd = f"gcc -x assembler {asm_file} -o {exe_file}"
                        build_result = subprocess.run(build_cmd, shell=True, capture_output=True, text=True, timeout=self.timeout)
                        if build_result.returncode != 0:
                            divergences.append({
                                'index': test.get('index', idx+1),
                                'description': test['description'],
                                'code': code,
                                'input': input_values,
                                'expected': 'ASM builds successfully',
                                'actual': f'Build failed (exit {build_result.returncode}): {build_result.stderr.strip()}'
                            })
                            if len(divergences) >= self.max_errors:
                                break
                            continue
                        # Run command
                        if asm_run_template:
                            run_cmd = asm_run_template.format(exe_file=exe_file, base_name=base_name, dir=dir_name)
                        else:
                            run_cmd = exe_file
                        run_result = subprocess.run(run_cmd, shell=True, capture_output=True, text=True, timeout=self.timeout, input=input_values)
                        stdout = run_result.stdout.strip()
                        stderr = run_result.stderr.strip()
                        exit_code = run_result.returncode
                else:
                    # Non v3.0 behavior: run the command, passing stdin from test
                    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=self.timeout, input=input_values)
                    stdout = result.stdout.strip()
                    stderr = result.stderr.strip()
                    exit_code = result.returncode
            except subprocess.TimeoutExpired:
                divergences.append({
                    'index': test.get('index', idx+1),
                    'description': test['description'],
                    'code': code,
                    'input': input_values,
                    'expected': 'Complete within timeout',
                    'actual': f'Timeout after {self.timeout} seconds'
                })
                break
            except Exception as e:
                divergences.append({
                    'index': test.get('index', idx+1),
                    'description': test['description'],
                    'code': code,
                    'input': input_values,
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
                        'description': test['description'],
                        'code': code,
                        'input': input_values,
                        'expected': f'Exit 0, output: {test.get("output", "")}',
                        'actual': f'Exit {exit_code}, stderr: {stderr}'
                    })
                elif 'output' in test and ('\n').join(test['output']) != stdout:
                    divergences.append({
                        'index': test.get('index', idx+1),
                        'description': test['description'],
                        'code': code,
                        'input': input_values,
                        'expected': ('\n').join(test['output']),
                        'actual': stdout
                    })
            elif expect_fail:
                if exit_code == 0:
                    divergences.append({
                        'index': test.get('index', idx+1),
                        'description': test['description'],
                        'code': code,
                        'input': input_values,
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
                    'description': test['name'],
                    'code': code,
                    'input': input_values,
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
            message = f"Test {d['index']} - Description: {d['description']}\nTest code:\n```{self.language}\n{d['code']}\n```"
            if d['input'] != '':
                message += f"\nInput:`{d['input']}`"
            message += f"\n\nExpected: {d['expected']}\nResult: {d['actual']}\n"

            issue.append(message)
        return "\n".join(issue)