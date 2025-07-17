# Use the official Python 3.12 slim image
FROM python:3.12-slim

# Set workdir
WORKDIR /app

# Install system dependencies (if any)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements for faster build
COPY setup.py ./
COPY compiler_testing_lib/ ./compiler_testing_lib/

# Install the testing library
RUN pip install .

# Copy the run script
COPY images/python/run_in_container.py ./run_in_container.py

# Default workdir for mapped source
WORKDIR /src

ENTRYPOINT ["python3", "/app/run_in_container.py"] 