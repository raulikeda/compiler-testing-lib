#!/bin/bash

# receive language and version as arguments
LANGUAGE=$1
VERSION=$2

# clean files in /compiler_testing_lib/languages/${language}/${version} if it exists
if [ -d "./compiler_testing_lib/languages/${LANGUAGE}/${VERSION}" ]; then
  echo "Cleaning /compiler_testing_lib/languages/${LANGUAGE}/${VERSION}..."
  # remove files even if directory is empty
  rm -rf ./compiler_testing_lib/languages/${LANGUAGE}/${VERSION}/*
fi

# copy files from ../compiler-tests-generator/output/{language}/{version} to /compiler_testing_lib/languages/{language}/{version}
SOURCE_DIR="../compiler-tests-generator/output/${LANGUAGE}/${VERSION}"
DEST_DIR="./compiler_testing_lib/languages/${LANGUAGE}/${VERSION}"
echo "Copying files from ${SOURCE_DIR} to ${DEST_DIR}..."
mkdir -p "${DEST_DIR}"
cp -r "${SOURCE_DIR}/." "${DEST_DIR}/"
echo "Files copied successfully."