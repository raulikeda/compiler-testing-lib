# Use the official Python 3.12 slim image
FROM python:3.12-slim

# Set workdir
WORKDIR /app

# Install system dependencies including .NET 9
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    python3-pip \
    wget \
    curl \
    apt-transport-https \
    && rm -rf /var/lib/apt/lists/*

# Install .NET 9
RUN wget https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb -O packages-microsoft-prod.deb && \
    dpkg -i packages-microsoft-prod.deb && \
    rm packages-microsoft-prod.deb && \
    apt-get update && \
    apt-get install -y dotnet-sdk-9.0 && \
    rm -rf /var/lib/apt/lists/*

# Set .NET environment variables
ENV DOTNET_ROOT="/usr/share/dotnet"
ENV PATH="${DOTNET_ROOT}:${PATH}"
ENV DOTNET_CLI_TELEMETRY_OPTOUT="1"

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