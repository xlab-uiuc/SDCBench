#!/bin/bash

# This builds all the dependencies for runner

RUNNER_TOOLS_DIR="runner/tools"

cd tools

./build_cpu_check.sh
./build_silifuzz.sh

cd ..

rm -rf $RUNNER_TOOLS_DIR/*

cp tools/cpu-check/build/cpu_check $RUNNER_TOOLS_DIR
cp tools/dcdiag $RUNNER_TOOLS_DIR
cp -rL tools/silifuzz/bazel-bin $RUNNER_TOOLS_DIR/silifuzz

