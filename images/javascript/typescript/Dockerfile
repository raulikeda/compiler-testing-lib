FROM compiler-testing-lib-python:latest

WORKDIR /app

# Install Node.js (LTS) via NodeSource
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm@latest

# Install global TypeScript toolchain
RUN npm install -g typescript ts-node

# Verify Installation
RUN python3 -V && node --version && npm --version && tsc -v && ts-node -v 

WORKDIR /src
ENTRYPOINT ["python3", "/app/run_in_container.py"]
