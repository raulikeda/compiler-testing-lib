#!/bin/bash
set -e

# Remove all containers (running or stopped) based on the image compiler-testing-lib-python (any tag)
CONTAINERS=$(docker ps -a -q --filter ancestor=compiler-testing-lib-python)
if [ -n "$CONTAINERS" ]; then
  echo "Removing containers: $CONTAINERS"
  docker rm -f $CONTAINERS
else
  echo "No containers found for image compiler-testing-lib-python."
fi 