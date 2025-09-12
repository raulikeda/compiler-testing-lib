FROM compiler-testing-lib-python:latest

WORKDIR /app

# Essentials for Swift on Debian-based images (close to Swift's Jammy list)
RUN apt-get update && apt-get install -y \
    clang \
    libicu-dev \
    libcurl4-openssl-dev \
    libxml2-dev \
    libsqlite3-dev \
    pkg-config \
    zlib1g-dev \
  && rm -rf /var/lib/apt/lists/*

# Install Swift 6.1.2 (Ubuntu 22.04 tarball layout)
ENV SWIFT_VERSION=6.1.2
RUN set -eux; \
  PLATFORM_PATH="ubuntu2204"; \
  FILE_BASENAME="swift-${SWIFT_VERSION}-RELEASE-ubuntu22.04"; \
  URL="https://download.swift.org/swift-${SWIFT_VERSION}-release/${PLATFORM_PATH}/swift-${SWIFT_VERSION}-RELEASE/${FILE_BASENAME}.tar.gz"; \
  echo "Fetching ${URL}"; \
  curl -fsSL "${URL}" -o /tmp/swift.tar.gz; \
  tar -xzf /tmp/swift.tar.gz -C /opt; \
  rm /tmp/swift.tar.gz; \
  test -x "/opt/${FILE_BASENAME}/usr/bin/swift"

# Put Swift on PATH (alternatively: create symlinks in /usr/local/bin)
ENV PATH="/opt/swift-${SWIFT_VERSION}-RELEASE-ubuntu22.04/usr/bin:${PATH}"

# Verify installation (toolchain + lib)
RUN python3 -V && swift --version && swiftc --version
WORKDIR /src
ENTRYPOINT ["python3", "/app/run_in_container.py"]
