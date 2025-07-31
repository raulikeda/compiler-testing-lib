import sys
import argparse
import subprocess
import os
import requests
import json
from compiler_testing_lib.runner import TestRunner

parser = argparse.ArgumentParser(description='Run compiler-testing-lib in container')
parser.add_argument('--git_username', required=True)
parser.add_argument('--git_repository', required=True)
parser.add_argument('--language', default='C')
parser.add_argument('--version', required=True)
parser.add_argument('--file_extension', default='c')
parser.add_argument('--max_errors', type=int, default=3)
parser.add_argument('--timeout', type=int, default=10)
parser.add_argument('--command_template', required=True)
parser.add_argument('--token', required=False)
parser.add_argument('--release', required=False)
parser.add_argument('--callback_url', required=False)
parser.add_argument('--api_secret', required=False)
args = parser.parse_args()

def send_callback(callback_url, api_secret, version_name, release_name, git_username, repository_name, test_status, issue_text=None):
    """Send test results to the callback URL"""
    try:
        payload = {
            "version_name": version_name,
            "release_name": release_name,
            "git_username": git_username,
            "repository_name": repository_name,
            "test_status": test_status,
            "issue_text": issue_text
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-API-Secret": api_secret,  # Actual secret from .env
            "Authorization": f"Bearer {api_secret}"
        }
        
        response = requests.post(callback_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        print(f"Callback sent successfully: {result.get('message', 'Success')}")
        if result.get('issue_url'):
            print(f"Issue created: {result['issue_url']}")
        
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to send callback: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"Failed to parse callback response: {e}")
        return False

if args.token:
    installation_token = args.token
    repo_url = f"https://x-access-token:{installation_token}@github.com/{args.git_username}/{args.git_repository}.git"
else:
    repo_url = f"https://github.com/{args.git_username}/{args.git_repository}.git"

repo_dir = f"/src/{args.git_repository}"

print(f"Cloning {repo_url} into {repo_dir}...")
subprocess.run(["git", "clone", repo_url, repo_dir], check=True)

# Change working directory to the cloned repo
os.chdir(repo_dir)

# Checkout specific release/tag if token is provided and release is specified
if args.release:
    print(f"Checking out release: {args.release}")
    subprocess.run(["git", "checkout", args.release], check=True)

runner = TestRunner(
    language=args.language,
    version=args.version,
    max_errors=args.max_errors,
    timeout=args.timeout,
    file_extension=args.file_extension
)

try:
    result = runner.run_tests(command_template=args.command_template)
except Exception as e:
    result = f"Runner Exception: {str(e)}"
    print(f"\033[91mRunner failed with exception: {e}\033[0m")

# Determine test status and prepare callback data
if result == "":
    test_status = "PASS"
    issue_text = None
    print("\033[92mAll tests passed!\033[0m")
else:
    # Check if it's an error (timeout, exception) or just test failures
    if "Timeout after" in result or "Exception:" in result or "Runner Exception:" in result:
        test_status = "ERROR"
    else:
        test_status = "FAILED"
    
    issue_text = result
    print("\n\033[91mTest Divergences:\033[0m\n")
    print(result)

# Send callback with test results
if args.callback_url:
    print(f"Sending results to {args.callback_url}...")
    send_callback(
        callback_url=args.callback_url,
        api_secret=args.api_secret,
        version_name=args.version,
        release_name=args.release,
        git_username=args.git_username,
        repository_name=args.git_repository,
        test_status=test_status,
        issue_text=issue_text
    ) 