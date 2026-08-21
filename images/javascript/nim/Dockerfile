FROM compiler-testing-lib-python:latest

WORKDIR /app

# Install Nim
# RUN apt-get update && apt-get install -y \
#     nim \
#     && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://nim-lang.org/choosenim/init.sh -o init.sh && sh init.sh -y && rm init.sh
# Set Nim environment variables
ENV PATH="/root/.nimble/bin:$PATH"

WORKDIR /src
ENTRYPOINT ["python3", "/app/run_in_container.py"]