#!/bin/bash

# This packages runner into docker image

cd runner
docker build --tag runner .
docker save runner > ../runner.tar

