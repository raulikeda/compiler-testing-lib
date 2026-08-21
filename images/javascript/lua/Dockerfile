FROM compiler-testing-lib-python:latest

WORKDIR /app

# Lua runtime
RUN apt-get update && apt-get install -y lua5.4 && rm -rf /var/lib/apt/lists/*

WORKDIR /src
ENTRYPOINT ["python3", "/app/run_in_container.py"]