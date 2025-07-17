from setuptools import setup, find_packages
import os

# Ensure the build directory exists
os.makedirs('build', exist_ok=True)

setup(
    name='compiler-testing-lib',
    version='0.1.5',
    description='A testing library for running language/compiler tests from YAML metadata.',
    author='Your Name',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'pyyaml',
    ],
    python_requires='>=3.7',
) 