#!/bin/bash

#COMMIT="74ae11176898634de558b8ffe52087727bdf15c8"

rm -rf silifuzz

SILIFUZZ_ORCHESTRATOR_BUILD_PATCH=`pwd`/patch_files/silifuzz_orchestrator_build.patch
SILIFUZZ_PROXIES_BUILD_PATCH=`pwd`/patch_files/silifuzz_proxies_build.patch
SILIFUZZ_PROXIES_BUILD_STATIC_DEFS_PATCH=`pwd`/patch_files/silifuzz_proxies_build_static_defs.patch

CENTIPEDE_DIR=`pwd`/centipede

if [[ ! -d centipede ]]; then
	echo "Centipede repo must be cloned first"
	exit -1
fi

git clone https://github.com/google/silifuzz.git
cd silifuzz
#git checkout $COMMIT
SILIFUZZ_SRC_DIR=`pwd`

#patch -u orchestrator/BUILD -i $SILIFUZZ_ORCHESTRATOR_BUILD_PATCH
#patch -u proxies/BUILD -i $SILIFUZZ_PROXIES_BUILD_PATCH
#cp $CENTIPEDE_DIR/testing/build_defs.bzl proxies/build_static_defs.bzl
#patch -u proxies/build_static_defs.bzl -i $SILIFUZZ_PROXIES_BUILD_STATIC_DEFS_PATCH

./install_build_dependencies.sh  # Currently, works for the latest Debian and Ubuntu only
#bazel build -c opt @silifuzz//tools:{snap_corpus_tool,fuzz_filter_tool,snap_tool,silifuzz_platform_id}
bazel build -c opt @silifuzz//tools:snap_corpus_tool
bazel build -c opt @silifuzz//tools:fuzz_filter_tool
bazel build -c opt @silifuzz//tools:snap_tool
bazel build -c opt @silifuzz//tools:silifuzz_platform_id
bazel build -c opt @silifuzz//tools:simple_fix_tool
bazel build -c opt @silifuzz//proxies:unicorn_x86_64_sancov
bazel build -c opt @silifuzz//runner:reading_runner_main_nolibc
bazel build -c opt @silifuzz//orchestrator:silifuzz_orchestrator_main

SILIFUZZ_BIN_DIR=`pwd`/bazel-bin/
cd "${SILIFUZZ_BIN_DIR}"

cd "${SILIFUZZ_SRC_DIR}"
bazel build -c opt @silifuzz//proxies:unicorn_x86_64_sancov
bazel build -c opt @centipede//:centipede

cp ../silifuzz.corpus.xz $SILIFUZZ_BIN_DIR

