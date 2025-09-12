FROM compiler-testing-lib-python:latest

WORKDIR /app

# Install Go compiler
RUN apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*

# Install Go compiler
RUN wget https://golang.org/dl/go1.24.0.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go1.24.0.linux-amd64.tar.gz && \
    rm go1.24.0.linux-amd64.tar.gz

# Set Go environment variables
ENV PATH="/usr/local/go/bin:${PATH}"
ENV GOROOT="/usr/local/go"
ENV GOPATH="/go"
ENV PATH="${GOPATH}/bin:${PATH}"

# The base image already includes the Python runner and library
WORKDIR /src
ENTRYPOINT ["python3", "/app/run_in_container.py"]