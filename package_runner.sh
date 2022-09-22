#!/bin/bash

# This packages runner into docker image

cd runner
docker build -t .
docker save > runner.tar

