FROM compiler-testing-lib-python:latest

WORKDIR /app

# Install Ruby
RUN apt-get update && apt-get install -y \
    ruby-full \
    && rm -rf /var/lib/apt/lists/*

# Set Ruby environment variables
ENV PATH="/usr/local/bin:${PATH}"

WORKDIR /src
ENTRYPOINT ["python3", "/app/run_in_container.py"]