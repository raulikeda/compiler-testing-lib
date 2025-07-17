#!/bin/bash
set -e

echo "Cleaning old builds..."
rm -rf build/* dist/* *.egg-info

echo "Building package..."
pip install --upgrade build twine
python3 -m build --outdir build

echo "Uploading to PyPI..."
twine upload build/* 