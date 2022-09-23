#!/bin/bash

# Make sure there is silifuzz directory cloned already
if [[ ! -d silifuzz/ ]]
then
	echo "Silifuzz directory needs to exist first -- run ./build_silifuzz.sh first"
	exit
fi

rm -f silifuzz_tools/snapshot_pb2.py
protoc --python_out=silifuzz_tools/ silifuzz/proto/snapshot.proto
cp silifuzz_tools/silifuzz/proto/snapshot_pb2.py silifuzz_tools/
rm -r silifuzz_tools/silifuzz

