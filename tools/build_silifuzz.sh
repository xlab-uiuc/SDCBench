#!/bin/bash

rm -rf silifuzz

git clone https://github.com/google/silifuzz.git
cd silifuzz
SILIFUZZ_SRC_DIR=`pwd`
sudo ./install_build_dependencies.sh  # Currently, works for the latest Debian and Ubuntu only
#bazel build -c opt @silifuzz//tools:{snap_corpus_tool,fuzz_filter_tool,snap_tool,silifuzz_platform_id}
bazel build -c opt @silifuzz//tools:snap_corpus_tool
bazel build -c opt @silifuzz//tools:fuzz_filter_tool
bazel build -c opt @silifuzz//tools:snap_tool
bazel build -c opt @silifuzz//tools:silifuzz_platform_id
bazel build -c opt @silifuzz//runner:reading_runner_main_nolibc
bazel build -c opt @silifuzz//orchestrator:silifuzz_orchestrator_main
SILIFUZZ_BIN_DIR=`pwd`/bazel-bin/
cd "${SILIFUZZ_BIN_DIR}"

cd "${SILIFUZZ_SRC_DIR}"
bazel build -c opt @silifuzz//proxies:unicorn_x86_64_sancov
bazel build -c opt @centipede//:centipede

cp ../silifuzz.corpus.xz $SILIFUZZ_BIN_DIR

