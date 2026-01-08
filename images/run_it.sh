#!/usr/bin/bash

docker run --rm -it \
  --entrypoint bash \
  -e DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 \
  -e DOTNET_NOLOGO=1 \
  -e DOTNET_CLI_TELEMETRY_OPTOUT=1 \
  compiler-testing-lib-python