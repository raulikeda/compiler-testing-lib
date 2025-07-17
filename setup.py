from setuptools import setup, find_packages

setup(
    name='compiler_testing_lib',
    version='0.1.0',
    description='A testing library for running language/compiler tests from YAML metadata.',
    author='Your Name',
    packages=find_packages(),
    install_requires=[
        'pyyaml',
    ],
    python_requires='>=3.7',
) 