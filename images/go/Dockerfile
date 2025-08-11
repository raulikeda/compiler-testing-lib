# Use the official Python 3.12 slim image
FROM python:3.12-slim

# Set workdir
WORKDIR /app

# Install system dependencies including Go compiler
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    python3-pip \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install Go compiler
RUN wget https://golang.org/dl/go1.24.0.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go1.24.0.linux-amd64.tar.gz && \
    rm go1.24.0.linux-amd64.tar.gz

# Set Go environment variables
ENV PATH="/usr/local/go/bin:${PATH}"
ENV GOROOT="/usr/local/go"
ENV GOPATH="/go"
ENV PATH="${GOPATH}/bin:${PATH}"

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