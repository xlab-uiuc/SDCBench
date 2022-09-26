#!/bin/bash

COMMIT="93b6567ea2e6f2fd9f3c61dcbd2820abb8993ddd"

rm -rf centipede

TOOLS_DIR=`pwd`
CENTIPEDE_BUILD_DIFF_FILE=`pwd`/patch_files/centipede_build.patch

git clone https://github.com/google/centipede.git
cd centipede
git checkout $COMMIT

#patch -u BUILD -i $CENTIPEDE_BUILD_DIFF_FILE

bazel build -c opt :all


