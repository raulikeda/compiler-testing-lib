FROM compiler-testing-lib-python:latest

WORKDIR /app

# System deps: xz for extracting Zig
RUN apt-get update && apt-get install -y \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Zig (prebuilt)
# Change ZIG_VERSION if you need a different release.
ENV ZIG_VERSION=0.14.1
RUN curl -fsSL https://ziglang.org/download/${ZIG_VERSION}/zig-x86_64-linux-${ZIG_VERSION}.tar.xz -o /tmp/zig.tar.xz \
    && mkdir -p /opt/zig \
    && tar -xJf /tmp/zig.tar.xz -C /opt/zig --strip-components=1 \
    && rm /tmp/zig.tar.xz \
    && ln -s /opt/zig/zig /usr/local/bin/zig

# Verify installation (toolchain)
RUN python3 -V && zig version

WORKDIR /src
ENTRYPOINT ["python3", "/app/run_in_container.py"]
