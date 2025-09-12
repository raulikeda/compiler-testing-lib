#!/bin/bash
set -e

# Build base image first (python)
if [ -f "python/Dockerfile" ]; then
  echo "Building base image compiler-testing-lib-python:latest..."
  docker build --no-cache -t compiler-testing-lib-python:latest -f "python/Dockerfile" ..
  docker image prune -f
fi

# Build the remaining images using the base
for dir in */ ; do
    name="${dir%/}"
    if [ "$name" = "python" ]; then
        continue
    fi
    if [ -f "${name}/Dockerfile" ]; then
        image_name="compiler-testing-lib-${name}:latest"
        echo "Building $image_name from ${name}/Dockerfile..."
        docker build --no-cache -t $image_name -f "${name}/Dockerfile" ..
        docker image prune -f
    fi
done 