FROM compiler-testing-lib-python:latest

WORKDIR /app

# Install Go compiler
RUN apt-get update && apt-get install -y apt-transport-https wget gnupg && rm -rf /var/lib/apt/lists/*

# Install Go compiler
RUN wget -qO- https://dl-ssl.google.com/linux/linux_signing_key.pub \
  | gpg  --dearmor -o /usr/share/keyrings/dart.gpg

RUN echo 'deb [signed-by=/usr/share/keyrings/dart.gpg arch=amd64] https://storage.googleapis.com/download.dartlang.org/linux/debian stable main' \
  | tee /etc/apt/sources.list.d/dart_stable.list

RUN apt-get update && apt-get install -y dart

RUN dart --disable-analytics

# The base image already includes the Python runner and library
WORKDIR /src
ENTRYPOINT ["python3", "/app/run_in_container.py"]