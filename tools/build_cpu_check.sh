#!/bin/bash

git clone --recursive  https://github.com/google/cpu-check.git
cd cpu-check
mkdir build
cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DBUILD_STATIC=True -DUSE_CLANG=ON
make -j32

cp cpu_check ../../




