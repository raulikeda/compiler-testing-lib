# Use the official Python 3.12 slim image
FROM python:3.12-slim

# Set workdir
WORKDIR /app

# Install system dependencies (if any)
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Ensure pip is up to date
RUN python3 -m pip install --upgrade pip

# Always install the latest version of the testing library from PyPI
RUN pip install --no-cache-dir --upgrade compiler-testing-lib requests

# Copy the run script
COPY images/python/run_in_container.py ./run_in_container.py

# Verify the installation
RUN pip list | grep compiler-testing-lib

# Default workdir for mapped source
WORKDIR /src

ENTRYPOINT ["python3", "/app/run_in_container.py"] 