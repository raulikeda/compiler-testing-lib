# Use the official Python 3.12 slim image
FROM python:3.12-slim

# Set workdir
WORKDIR /app

# Install system dependencies including Java (required for Kotlin)
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    python3-pip \
    wget \
    curl \
    unzip \
    openjdk-17-jdk \
    && rm -rf /var/lib/apt/lists/*

# Install Kotlin 2.2.0
RUN wget https://github.com/JetBrains/kotlin/releases/download/v2.2.0/kotlin-compiler-2.2.0.zip && \
    unzip kotlin-compiler-2.2.0.zip -d /opt && \
    rm kotlin-compiler-2.2.0.zip

# Set Java and Kotlin environment variables
ENV JAVA_HOME="/usr/lib/jvm/java-17-openjdk-amd64"
ENV KOTLIN_HOME="/opt/kotlinc"
ENV PATH="${KOTLIN_HOME}/bin:${JAVA_HOME}/bin:${PATH}"

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