FROM compiler-testing-lib-python:latest

WORKDIR /app

# Install Julia (1.10 LTS: typed globals need >= 1.8)
RUN apt-get update && apt-get install -y wget expect && rm -rf /var/lib/apt/lists/*

RUN wget -q https://julialang-s3.julialang.org/bin/linux/x64/1.10/julia-1.10.9-linux-x86_64.tar.gz && \
    tar -C /usr/local -xzf julia-1.10.9-linux-x86_64.tar.gz && \
    mv /usr/local/julia-1.10.9 /usr/local/julia && \
    rm julia-1.10.9-linux-x86_64.tar.gz

ENV PATH="/usr/local/julia/bin:${PATH}"

# Warm up the compilation cache so graded runs start fast
RUN julia -e "println(1 + 1)"

# The base image already includes the Python runner and library
WORKDIR /src
ENTRYPOINT ["python3", "/app/run_in_container.py"]
