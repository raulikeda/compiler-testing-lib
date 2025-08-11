#!/bin/bash
set -e

for dir in */ ; do
    if [ -f "$dir/Dockerfile" ]; then
        image_name="compiler-testing-lib-$dir:latest"
        echo "Building $image_name from $dir/Dockerfile..."
        docker build --no-cache -t $image_name -f "$dir/Dockerfile" ..
    fi
done 

docker image prune -f