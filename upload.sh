#!/bin/bash
set -e

echo "Cleaning old builds..."
rm -rf dist build *.egg-info

echo "Building package..."
python3 setup.py sdist bdist_wheel

echo "Uploading to PyPI..."
twine upload dist/* 