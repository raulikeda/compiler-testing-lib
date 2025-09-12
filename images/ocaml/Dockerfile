FROM compiler-testing-lib-python:latest

WORKDIR /app

# Install system dependencies including OCaml compiler dependencies
RUN apt-get update && apt-get install -y \
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

WORKDIR /src
ENTRYPOINT ["python3", "/app/run_in_container.py"]