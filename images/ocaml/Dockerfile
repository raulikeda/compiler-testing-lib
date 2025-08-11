# Use the official Python 3.12 slim image
FROM python:3.12-slim

# Set workdir
WORKDIR /app

# Install system dependencies including OCaml compiler dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    python3-pip \
    wget \
    curl \
    unzip \
    libgmp-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install OCaml 5.3
RUN curl -L https://github.com/ocaml/ocaml/archive/5.3.0.tar.gz | tar xz && \
    cd ocaml-5.3.0 && \
    ./configure --prefix=/usr/local && \
    make world && \
    make install && \
    cd .. && \
    rm -rf ocaml-5.3.0

# Install OPAM (OCaml package manager) and initialize
RUN curl -L https://raw.githubusercontent.com/ocaml/opam/master/shell/install.sh | bash -s -- --no-backup && \
    opam init --disable-sandboxing -y && \
    opam switch create 5.3.0 && \
    eval $(opam env)

# Set OCaml environment variables
ENV OPAMROOT="/root/.opam"
ENV PATH="/root/.opam/5.3.0/bin:${PATH}"

# Ensure pip is up to date
RUN python3 -m pip install --upgrade pip

# Copy the entire project and install from local source
COPY . /tmp/compiler-testing-lib
RUN pip install -e /tmp/compiler-testing-lib
RUN pip install --no-cache-dir --upgrade requests

# Copy the run script
COPY images/python/run_in_container.py ./run_in_container.py

# Verify the installation
RUN pip list | grep compiler-testing-lib

# Default workdir for mapped source
WORKDIR /src

ENTRYPOINT ["python3", "/app/run_in_container.py"] 