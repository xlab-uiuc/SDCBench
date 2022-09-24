import os
import struct
import subprocess
import argparse
import sys
import logging
import os
from pathlib import Path
import shutil
import hashlib


parser = argparse.ArgumentParser(description='Generates silifuzz corpus')
parser.add_argument('--silifuzz_bin_dir', type=str, help='Silifuzz binary directory (to run Centipede fuzzer and unicorn binaries', default='tools/silifuzz')
parser.add_argument('--silifuzz_tools_dir', type=str, help='Silifuzz tools directory (to parse centipede fuzzer output using a script)', default='tools/silifuzz_tools')
parser.add_argument('--num_runs', type=int, help='Number of runs', default=100000)
parser.add_argument('--j', type=int, help='Number of cores', default=os.cpu_count())
parser.add_argument('--work_dir', type=str, help='Work dir', default='tools/silifuzz_work_dir')
parser.add_argument('--corpus_output', type=str, help='Corpus file generated name', default='tools/silifuzz.corpus')
parser.add_argument('--corpus_save_dir', type=str, help='Corpus file generated name', default='../saved_corpus')
args = parser.parse_args()

def panic(s):
    logging.critical(f'PANIC: {s}')
    sys.exit(1)

silifuzz_bin_dir = Path(args.silifuzz_bin_dir)
centipede_bin = silifuzz_bin_dir / 'external/centipede/centipede'
unicorn_bin = silifuzz_bin_dir / 'proxies/unicorn_x86_64_sancov'
if not silifuzz_bin_dir.exists():
    panic(f'silifuzz_bin_dir does not exist: {silifuzz_bin_dir}')
if not centipede_bin.exists():
    panic(f'centipede_bin does not exist: {centipede_bin}')
if not unicorn_bin.exists():
    panic(f'unicorn_bin does not exist: {unicorn_bin}')

silifuzz_tools_dir = Path(args.silifuzz_tools_dir)
if not silifuzz_tools_dir.exists():
    panic(f'silifuzz_tools_dir does not exist: {silifuzz_tools_dir}')

transform_centipede_fuzz_results_to_silifuzz_corpus = silifuzz_tools_dir / 'transform_centipede_fuzz_results_to_silifuzz_corpus.py' 
if not transform_centipede_fuzz_results_to_silifuzz_corpus.exists():
    panic(f'transform_centipede_fuzz_results_to_silifuzz_corpus does not exist: {transform_centipede_fuzz_results_to_silifuzz_corpus}')

work_dir = Path(args.work_dir)
if work_dir.exists():
    shutil.rmtree(work_dir)
work_dir.mkdir(exist_ok=True)

corpus_output = Path(args.corpus_output)
corpus_save_dir = Path(args.corpus_save_dir)
corpus_save_dir.mkdir(exist_ok=True)

def get_hash_file(filename):
    h = hashlib.sha256()
    b = bytearray(128*1024)
    mv = memoryview(b)
    with open(filename, 'rb', buffering=0) as f:
        while n := f.readinto(mv):
            h.update(mv[:n])
    return h.hexdigest()

try:
    subprocess.check_output(f'{centipede_bin} --binary={unicorn_bin} --workdir={work_dir} --num_runs={args.num_runs} --j={args.j}', shell=True, stderr=subprocess.STDOUT)
    subprocess.check_output(f'python {transform_centipede_fuzz_results_to_silifuzz_corpus} --fuzzing_results="{work_dir}/corpus.*" --bin_dir="{silifuzz_bin_dir}" --corpus_output="{corpus_output}"', shell=True, stderr=subprocess.STDOUT)
    corpus_hash = get_hash_file(corpus_output)
    corpus_save_file = corpus_save_dir / f'{corpus_hash}.corpus.xz'
    shutil.copy(corpus_output, corpus_save_file)
except Exception as e:
    panic(str(e))

