FROM python:3.12-slim

# Base shared image for all language runners
WORKDIR /app

# Common system dependencies: build tools, git, nasm, gcc, curl/ca-certs
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    python3-pip \
    nasm \
    gcc \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Ensure pip is up to date
RUN python3 -m pip install --upgrade pip

# Install local library and handy deps
COPY . /tmp/compiler-testing-lib
RUN pip install -e /tmp/compiler-testing-lib
RUN pip install --no-cache-dir --upgrade requests

# Common runner script
COPY images/python/run_in_container.py ./run_in_container.py

# Quick sanity
RUN python3 -V && pip list | grep compiler-testing-lib

WORKDIR /src
ENTRYPOINT ["python3", "/app/run_in_container.py"]