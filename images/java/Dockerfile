FROM compiler-testing-lib-python:latest

WORKDIR /app

# JDK 25: `java main.java` compiles the other source files on demand (JEP 458)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    unzip \
    openjdk-25-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME="/usr/lib/jvm/java-25-openjdk-amd64"
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Scala from upstream (the apt package would pull in a second JDK)
RUN wget -q https://downloads.lightbend.com/scala/2.13.16/scala-2.13.16.tgz && \
    tar -C /opt -xzf scala-2.13.16.tgz && mv /opt/scala-2.13.16 /opt/scala && \
    rm scala-2.13.16.tgz
ENV PATH="/opt/scala/bin:${PATH}"

# Clojure CLI (same reason); prime its deps cache
RUN curl -fsSL -o linux-install.sh https://github.com/clojure/brew-install/releases/latest/download/linux-install.sh && \
    bash linux-install.sh && rm linux-install.sh && \
    clojure -M -e '(println "clojure ok")'

# Install Kotlin 2.2.0
RUN wget https://github.com/JetBrains/kotlin/releases/download/v2.2.0/kotlin-compiler-2.2.0.zip && \
    unzip kotlin-compiler-2.2.0.zip -d /opt && \
    rm kotlin-compiler-2.2.0.zip

ENV KOTLIN_HOME="/opt/kotlinc"
ENV PATH="${KOTLIN_HOME}/bin:${PATH}"

RUN java -version && javac -version && scalac -version && kotlinc -version && clojure -M -e '(println "ok")'

WORKDIR /src
ENTRYPOINT ["python3", "/app/run_in_container.py"]