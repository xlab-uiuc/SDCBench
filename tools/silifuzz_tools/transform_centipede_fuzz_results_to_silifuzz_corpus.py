import os
import struct
import subprocess
import argparse
from glob import glob
import sys
import logging
import os
import pathlib
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
import shutil

parser = argparse.ArgumentParser(description='Transform centipede fuzz results to a silifuzz corpus')
parser.add_argument('--fuzzing_results', type=str, help='Fuzzing result files regex (Default: corpus*)', default='corpus.*')
parser.add_argument('--temp_dir', type=str, help='Temp dir', default='tools/tmp')
parser.add_argument('--bin_dir', type=str, help='Bin dir containing silifuzz build outputs', default='../bazel-bin')
parser.add_argument('--corpus_output', type=str, help='Path to output corpus', default='tools/tmp/generated.corpus')
args = parser.parse_args()

fuzzing_results = args.fuzzing_results
corpus_output = args.corpus_output

files = glob(fuzzing_results)
PACK_BEGIN_MAGIC = '-Centipede-'.encode()
PACK_END_MAGIC = '-edepitneC-'.encode()
HASH_LEN = 40

bin_dir = pathlib.Path(args.bin_dir).resolve()

temp_dir = pathlib.Path(args.temp_dir)
if temp_dir.exists():
    shutil.rmtree(temp_dir)
temp_dir.mkdir(exist_ok=True)

fuzz_filter_tool = bin_dir / 'tools' / 'fuzz_filter_tool'
snap_tool = bin_dir / 'tools' / 'snap_tool'

def panic(s):
    logging.critical(f'PANIC: {s}')
    sys.exit(1)

def process_input_data(data, hash_value):
    # Write to temp dir the snapshot
    out_path = temp_dir / f'{hash_value.decode()}.pb'
    out_path = out_path.resolve()
    if out_path.exists():
        return True
    try:
        # Use the fuzz_filter_tool to generate a snapshot
        # Need to change directory since there is a dependency from fuzz_filter_tool to reading_runner_main_nolibc
        subprocess.check_output(f'{fuzz_filter_tool} /dev/stdin {out_path}', shell=True, input=data, stderr=subprocess.STDOUT, cwd=bin_dir)
        
        # Set id of snapshot
        subprocess.check_output(f'{snap_tool} set_id {out_path} {data.hex()}', shell=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        # If snapshot failed to generate, delete file if exists
        out_path.unlink(missing_ok=True)
        return True

    return True



if __name__ == "__main__":
    # Go through each fuzz corpus
    print(f'Transforming fuzz results {files}...')
    if len(files) == 0:
        panic(f'{fuzzing_results} does not contain any results')
    for file in files:
        print(f'Transforming {file}...')
        with open(file, 'rb') as f:
            data = f.read()

        # Run a pool to parse transform fuzz result to snapshot
        with ProcessPoolExecutor() as e:
            # Hold results from each transformation
            results = []
        
            # Now parse every fuzz result from the file
            # Each entry in the file contains this format:
            # - PACK_BEGIN_MAGIC (12 bytes)
            # - hash(data)       (40 bytes)
            # - data size        (8 bytes)
            # - data             (? bytes)
            # - PACK_END_MAGIC   (12 bytes)
            index = 0
            while index < len(data):
                begin = data[index:index+len(PACK_BEGIN_MAGIC)]
                if begin != PACK_BEGIN_MAGIC:
                    print(f'{begin} != {PACK_BEGIN_MAGIC}')
                    break
                index += len(PACK_BEGIN_MAGIC)

                hash_value = data[index:index+HASH_LEN]
                logging.info(f'Hash value {hash_value}')
                index += HASH_LEN

                data_len = struct.unpack('q', data[index:index+8])[0]
                index += 8
                
                input_data = data[index:index+data_len]
                r = e.submit(process_input_data, input_data, hash_value)
                results.append(r)
                index += data_len

                end = data[index:index+len(PACK_END_MAGIC)]
                if end != PACK_END_MAGIC:
                    # Sometimes the end is missing, past the end of file
                    if index > len(data):
                        print(f'Warning: end bytes [{end}] != {PACK_END_MAGIC} for {file}. Terminating loop early...')
                        break
                    else:
                        print(f'{end} != {PACK_END_MAGIC}')
                        break

                index += len(PACK_END_MAGIC)
                
            # Make sure every transformation is finished
            for r in results:
                r.result()

        print(f'Finished transforming {file}...')

    # Gather all the snapshots
    files = [str(f) for f in temp_dir.iterdir() if '.pb' in str(f)]
    if len(files) == 0:
        panic(f'Trying to generate corpus, but there are no snapshots created in {temp_dir}')
    file_names = ' '.join(files)

    # Generate corpus from snapshots
    o = subprocess.check_output([snap_tool, 'generate_corpus', *files], stderr=subprocess.PIPE)
    #o = subprocess.check_output(f'{snap_tool} generate_corpus {file_names}', shell=True, stderr=subprocess.PIPE)
    with open(corpus_output, 'wb') as f:
        f.write(o)

    # Write a compressed corpus for orchestrator to use
    with open(f'{corpus_output}.xz', 'wb') as f:
        o = subprocess.run(f'xz -c {corpus_output}', shell=True, stdout=f, stderr=subprocess.PIPE)

