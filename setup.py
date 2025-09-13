from setuptools import setup, find_packages
import os

# Ensure the build directory exists
os.makedirs('build', exist_ok=True)

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name='compiler-testing-lib',
    version='0.1.12',
    description='A testing library for running language/compiler tests from YAML metadata.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='Your Name',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'pyyaml',
    ],
    python_requires='>=3.7',
) 