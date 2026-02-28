FROM compiler-testing-lib-python:latest

WORKDIR /app

# Install Go compiler
RUN apt-get update && apt-get install -y libgmp-dev && rm -rf /var/lib/apt/lists/*

# Install Go compiler
RUN curl https://get-ghcup.haskell.org -sSf | \
    BOOTSTRAP_HASKELL_NONINTERACTIVE=1 sh

ENV PATH="/root/.ghcup/bin:/root/.cabal/bin:${PATH}"

# The base image already includes the Python runner and library
WORKDIR /src
ENTRYPOINT ["python3", "/app/run_in_container.py"]