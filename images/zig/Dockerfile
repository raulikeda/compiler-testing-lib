# Zig toolchain + Python runner
FROM python:3.12-slim

# Workdir for runner
WORKDIR /app

# System deps: build tools, git, curl/ca-certs, xz for extracting Zig
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    ca-certificates \
    xz-utils \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install Zig (prebuilt)
# Change ZIG_VERSION if you need a different release.
ENV ZIG_VERSION=0.14.1
RUN curl -fsSL https://ziglang.org/download/${ZIG_VERSION}/zig-x86_64-linux-${ZIG_VERSION}.tar.xz -o /tmp/zig.tar.xz \
    && mkdir -p /opt/zig \
    && tar -xJf /tmp/zig.tar.xz -C /opt/zig --strip-components=1 \
    && rm /tmp/zig.tar.xz \
    && ln -s /opt/zig/zig /usr/local/bin/zig

# Ensure pip is up to datecompiler-testing-lib/compiler-testing-example
RUN python3 -m pip install --upgrade pip

# Install the local python package and requests
COPY . /tmp/compiler-testing-lib
RUN pip install -e /tmp/compiler-testing-lib
RUN pip install --no-cache-dir --upgrade requests

# Reuse the same runner script
COPY images/python/run_in_container.py ./run_in_container.py

# Verify installation (toolchain + lib)
RUN python3 -V && zig version
RUN pip list | grep compiler-testing-lib

# Default workdir for cloned repos / mapped source
WORKDIR /src

ENTRYPOINT ["python3", "/app/run_in_container.py"]
