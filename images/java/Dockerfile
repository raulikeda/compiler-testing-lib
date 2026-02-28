FROM compiler-testing-lib-python:latest

WORKDIR /app

# Install Java and tools for Kotlin
RUN apt-get update && apt-get install -y \
    openjdk-21-jdk \
    && rm -rf /var/lib/apt/lists/*

# Set Java and Kotlin environment variables
ENV JAVA_HOME="/usr/lib/jvm/java-17-openjdk-amd64"
ENV PATH="${JAVA_HOME}/bin:${PATH}"

WORKDIR /src
ENTRYPOINT ["python3", "/app/run_in_container.py"]