FROM compiler-testing-lib-python:latest

WORKDIR /app

# System deps for Rust crates
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Rust (stable) via rustup with minimal profile
# -y = no prompts; installs to /root/.cargo by default
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y --default-toolchain stable --profile minimal

# Make cargo/rustc available on PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# Optional but handy: add rustfmt and clippy
RUN rustup component add rustfmt clippy

# Verify installation (toolchain)
RUN python3 -V && rustc --version && cargo --version && rustfmt --version

WORKDIR /src
ENTRYPOINT ["python3", "/app/run_in_container.py"]
