# TypeScript runtime + Python runner
FROM python:3.12-slim

# Workdir for runner
WORKDIR /app

# System deps: build tools, git, curl/ca-certs
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    ca-certificates \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (LTS) via NodeSource
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm@latest

# Ensure pip is up to date
RUN python3 -m pip install --upgrade pip

# Install the local python package and requests
COPY . /tmp/compiler-testing-lib
RUN pip install -e /tmp/compiler-testing-lib
RUN pip install --no-cache-dir --upgrade requests

# Install global TypeScript toolchain
RUN npm install -g typescript ts-node

# Reuse the same runner script
COPY images/python/run_in_container.py ./run_in_container.py

# Verify Installation
RUN python3 -V && node --version && npm --version && tsc -v && ts-node -v 
RUN pip list | grep compiler-testing-lib

# Default workdir for cloned repos
WORKDIR /src

ENTRYPOINT ["python3", "/app/run_in_container.py"]
