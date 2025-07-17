#!/bin/bash
set -e

docker run -it \
  -v $(pwd)/languages/python/v1.0:/src \
  compiler-testing-lib-python \
  --language python \
  --version v1.0 \
  --file_extension py \
  --max_errors 3 \
  --timeout 10 \
  --command_template "python3 example/main.py" 