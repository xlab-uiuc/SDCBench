import os
import struct
import subprocess
import argparse
import sys
import logging
import os
from pathlib import Path
import shutil

parser = argparse.ArgumentParser(description='Generates silifuzz corpus')
parser.add_argument('--silifuzz_bin_dir', type=str, help='Silifuzz binary directory (to run Centipede fuzzer and unicorn binaries', default='tools/silifuzz')
parser.add_argument('--silifuzz_tools_dir', type=str, help='Silifuzz tools directory (to parse centipede fuzzer output using a script)', default='tools/silifuzz_tools')
parser.add_argument('--num_runs', type=int, help='Number of runs', default=100000)
parser.add_argument('--j', type=int, help='Number of cores', default=os.cpu_count() - 1)
parser.add_argument('--work_dir', type=str, help='Work dir', default='tools/silifuzz_work_dir')
parser.add_argument('--corpus_output', type=str, help='Corpus file generated name', default='tools/silifuzz.corpus')
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

try:
    subprocess.check_output(f'{centipede_bin} --binary={unicorn_bin} --workdir={work_dir} --num_runs={args.num_runs} --j={args.j}', shell=True, stderr=subprocess.STDOUT)
    subprocess.check_output(f'python {transform_centipede_fuzz_results_to_silifuzz_corpus} --fuzzing_results="{work_dir}/corpus.*" --bin_dir="{silifuzz_bin_dir}" --corpus_output="{args.corpus_output}"', shell=True, stderr=subprocess.STDOUT)
except Exception as e:
    panic(str(e))

