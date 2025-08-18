# Rust toolchain + Python runner
FROM python:3.12-slim

# Workdir for runner
WORKDIR /app

# System deps: build tools, git, curl/ca-certs, pkg-config, OpenSSL (common for crates)
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    ca-certificates \
    pkg-config \
    libssl-dev \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install Rust (stable) via rustup with minimal profile
# -y = no prompts; installs to /root/.cargo by default
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y --default-toolchain stable --profile minimal

# Make cargo/rustc available on PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# Optional but handy: add rustfmt and clippy
RUN rustup component add rustfmt clippy

# Ensure pip is up to date
RUN python3 -m pip install --upgrade pip

# Install the local python package and requests
COPY . /tmp/compiler-testing-lib
RUN pip install -e /tmp/compiler-testing-lib
RUN pip install --no-cache-dir --upgrade requests

# Reuse the same runner script
COPY images/python/run_in_container.py ./run_in_container.py

# Verify installation (toolchain + lib)
RUN python3 -V && rustc --version && cargo --version && rustfmt --version
RUN pip list | grep compiler-testing-lib

# Default workdir for cloned repos / mapped source
WORKDIR /src

ENTRYPOINT ["python3", "/app/run_in_container.py"]
