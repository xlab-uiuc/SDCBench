#!/bin/bash

# This packages runner into docker image and cleans up the directory
RUNNER_TOOLS_DIR="runner/tools"

rm -f $RUNNER_TOOLS_DIR/silifuzz.corpus
rm -f $RUNNER_TOOLS_DIR/silifuzz.corpus.xz
rm -rf $RUNNER_TOOLS_DIR/tmp
rm -rf $RUNNER_TOOLS_DIR/silifuzz_work_dir

cd runner
docker build --tag runner .
docker save runner > ../runner.tar

