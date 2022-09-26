#!/bin/bash

# This builds all the dependencies for runner

cp ../setup_runner.sh .
rsync -av --progress ../runner . --exclude="runner/tools"
rsync -av --progress ../tools . --exclude="cpu-check" --exclude="centipede" --exclude="silifuzz"
sudo docker build --tag sdc_bench .

mkdir -p build
sudo docker run -v $PWD:/app sdc_bench

