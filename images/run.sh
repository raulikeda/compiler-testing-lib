#!/bin/bash
set -e

docker run --rm -it \
  compiler-testing-lib-python \
  --git_username raulikeda \
  --git_repository compiler-2005-1 \
  --language C \
  --version v1.0 \
  --file_extension c \
  --max_errors 5 \
  --timeout 10 \
  --command_template "python3 main.py" 