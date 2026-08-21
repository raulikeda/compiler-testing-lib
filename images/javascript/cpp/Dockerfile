FROM compiler-testing-lib-python:latest

WORKDIR /app

# Additional C++ tools
RUN apt-get update && apt-get install -y \
    g++ \
    gdb \
    make \
    cmake \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Set C++ environment variables
ENV CXX="g++"
ENV CC="gcc"
ENV CXXFLAGS="-std=c++20 -Wall -Wextra"
ENV CFLAGS="-Wall -Wextra"

WORKDIR /src
ENTRYPOINT ["python3", "/app/run_in_container.py"]