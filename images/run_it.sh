#!/usr/bin/bash

if [[ -z "$1" ]]; then
  echo "Usage: $0 <language>  (ex: haskell, rust, go)"
  exit 1
fi

docker run --rm -it \
  --entrypoint bash \
  "compiler-testing-lib-$1"