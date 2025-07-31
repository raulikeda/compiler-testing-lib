#!/bin/bash
set -e

docker run --rm -it \
  compiler-testing-lib-python \
  --git_username raulikeda \
  --git_repository compiler-testing-example \
  --language python \
  --version v0.0 \
  --file_extension py \
  --max_errors 3 \
  --timeout 10 \
  --command_template "python3 main_v0.0.py" 