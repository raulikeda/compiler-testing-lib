FROM compiler-testing-lib-python:latest

WORKDIR /app

# Install Java and tools for Kotlin
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    openjdk-21-jdk \
    clojure \
    scala \
    && rm -rf /var/lib/apt/lists/*

# Install Kotlin 2.2.0
RUN wget https://github.com/JetBrains/kotlin/releases/download/v2.2.0/kotlin-compiler-2.2.0.zip && \
    unzip kotlin-compiler-2.2.0.zip -d /opt && \
    rm kotlin-compiler-2.2.0.zip

# Set Java and Kotlin environment variables
ENV JAVA_HOME="/usr/lib/jvm/java-21-openjdk-amd64"
# ENV PATH="${JAVA_HOME}/bin:${PATH}"

ENV KOTLIN_HOME="/opt/kotlinc"
ENV PATH="${KOTLIN_HOME}/bin:${JAVA_HOME}/bin:${PATH}"

WORKDIR /src
ENTRYPOINT ["python3", "/app/run_in_container.py"]