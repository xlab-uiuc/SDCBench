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
import json
from capstone import *

# /home/henry/Desktop/sdc/SDCBench/runner/tools/silifuzz/runner/reading_runner_main_nolibc 3b0c70f01523e40acb7379d01caa0c9921c1c60b5b5134862f85a89276806f90.corpus.xz | head -c100


parser = argparse.ArgumentParser(description='Extracts single snapshot from silifuzz corpus')
parser.add_argument('--silifuzz_bin_dir', type=str, help='Silifuzz binary directory (to run Centipede fuzzer and unicorn binaries)', default='tools/silifuzz')
parser.add_argument('--silifuzz_tools_dir', type=str, help='Silifuzz tools dir', default='tools/silifuzz_tools')
parser.add_argument('--corpus', type=str, help='Snapshot id', default='', required=True)
parser.add_argument('--snapshot', type=str, help='Snapshot id', default='', required=True)
parser.add_argument('--protobuf_output', type=str, help='Protobuf generated name', default='extracted_snapshot.pb')
parser.add_argument('--corpus_output', type=str, help='Corpus file generated name', default='extracted_snapshot.corpus')
args = parser.parse_args()

def panic(s):
    logging.critical(f'PANIC: {s}')
    sys.exit(1)

silifuzz_bin_dir = Path(args.silifuzz_bin_dir)
fuzz_filter_tool = silifuzz_bin_dir / 'tools' / 'fuzz_filter_tool'
snap_tool = silifuzz_bin_dir / 'tools' / 'snap_tool'
snap_corpus_tool = silifuzz_bin_dir / 'tools' / 'snap_corpus_tool'
reading_runner_main_nolibc = silifuzz_bin_dir / 'runner' / 'reading_runner_main_nolibc'
silifuzz_orchestrator_main = silifuzz_bin_dir / 'orchestrator' / 'silifuzz_orchestrator_main'
silifuzz_tools_dir = Path(args.silifuzz_tools_dir)
unicorn_run_snapshot = silifuzz_tools_dir / 'unicorn_run_snapshot.py'
if not silifuzz_bin_dir.exists():
    panic(f'silifuzz_bin_dir does not exist: {silifuzz_bin_dir}')
if not fuzz_filter_tool.exists():
    panic(f'fuzz_filter_tool does not exist: {fuzz_filter_tool}')
if not snap_tool.exists():
    panic(f'snap_tool does not exist: {snap_tool}')
if not silifuzz_tools_dir.exists():
    panic(f'silifuzz_tools_dir does not exist: {silifuzz_tools_dir}')
if not unicorn_run_snapshot.exists():
    panic(f'silifuzz_tools_dir does not exist: {unicorn_run_snapshot}')

if '.xz' in args.corpus:
    corpus_no_xz = args.corpus[:-3]
    if not Path(corpus_no_xz).exists():
        subprocess.run(f'xz -d -k -f {args.corpus}', shell=True, stderr=subprocess.PIPE, text=True)
    args.corpus = corpus_no_xz

args.corpus = Path(args.corpus).resolve()
args.protobuf_output = Path(args.protobuf_output).resolve()

print(f'Working on {args.corpus}...')

snap_exists = False

o = subprocess.run(f'{snap_corpus_tool} list_snaps {args.corpus}', shell=True, capture_output=True, text=True, cwd=silifuzz_bin_dir)
for l in o.stderr.split('\n'):
    l = l.rstrip()
    ll = l.split(' ')
    snap_id = ll[-1]
    #print(snap_id)
    if snap_id == args.snapshot:
        snap_exists = True
        break

if not snap_exists:
    print(f'[{args.snapshot}] does not exist')
    sys.exit(-1)
snapshot_bytes = bytes.fromhex(args.snapshot)
o = subprocess.run(f'{fuzz_filter_tool} /dev/stdin {args.protobuf_output}', shell=True, capture_output=True, input=snapshot_bytes, cwd=silifuzz_bin_dir)

print_protobuf_out = subprocess.run(f'{snap_tool} print {args.protobuf_output}', shell=True, capture_output=True, text=True, cwd=silifuzz_bin_dir)
protobuf_details = print_protobuf_out.stdout
print(protobuf_details)

o = subprocess.run(f'{snap_tool} generate_corpus {args.protobuf_output}', shell=True, capture_output=True, cwd=silifuzz_bin_dir)
with open(args.corpus_output, 'wb+') as f:
    f.write(o.stdout)

o = subprocess.run(f'{reading_runner_main_nolibc} {args.corpus_output}', shell=True, capture_output=True, text=True)
output = o.stdout
running_info = o.stderr
if len(output) == 0:
    print('No errors!')
else:
    data = output[output.find(' ') + 1:]
    print(data)

    cpu_id_str = 'cpu_id:'
    cpu_id_start = data.find(cpu_id_str) + len(cpu_id_str)
    cpu_id_end = data.find(' ', cpu_id_start)
    faulty_cpu = data[cpu_id_start:cpu_id_end]

    o = subprocess.run(f'{silifuzz_orchestrator_main.resolve()} --duration=1s --runner={reading_runner_main_nolibc.resolve()} {args.corpus_output}.xz', shell=True, capture_output=True, text=True)
    orchestrator_data = o.stderr
    #print(orchestrator_data)

    # Generate protobuf again...
    #o = subprocess.run(f'{fuzz_filter_tool} /dev/stdin {args.protobuf_output}', shell=True, capture_output=True, input=snapshot_bytes, cwd=silifuzz_bin_dir)

    emulator_results_f = open('emulator_results.txt', 'w+')

    o = subprocess.run(f'python unicorn_run_snapshot.py --snapshot_protobuf {args.protobuf_output}', shell=True, capture_output=True, text=True, cwd=silifuzz_tools_dir)
    for l in o.stdout.split('\n'):
        print(l)
        emulator_results_f.write(l + '\n')

    print(running_info)

    print(f'\nFaulty core: {faulty_cpu}')

    rip = 0
    for l in protobuf_details.split('\n'):
        if 'rip' in l:
            rip_hex = l.split(' ')[6]
            rip = int(rip_hex, 16)
            break

    cs = Cs(CS_ARCH_X86, CS_MODE_64)
    instruction_count = 0
    for i in cs.disasm(snapshot_bytes, rip):
        print("0x%x:\t%s\t%s" % (i.address, i.mnemonic, i.op_str))
        instruction_count += 1
        emulator_results_f.write("0x%x:\t%s\t%s\n" % (i.address, i.mnemonic, i.op_str))

    print('\n')
    print(f'Please start debug by running "{silifuzz_orchestrator_main.resolve()} --duration=30s --runner={reading_runner_main_nolibc.resolve()} {args.corpus_output}.xz"')
    print(f'Please debug by running "gdb -x gdb.txt {reading_runner_main_nolibc}"')
    with open('gdb.txt', 'w+') as f:
        f.write(f'set disassemble-next-line on\n')
        f.write(f'set disassembly-flavor intel\n')
        f.write(f'b RestoreUContextNoSyscalls\n')
        f.write(f'r --cpu={faulty_cpu} {args.corpus_output}\n')
        f.write(f'b *0x{rip:016X}\n')
        f.write(f'c\n')
        def run_next_and_print_state():
            f.write(f'ni\n')
            f.write(f'i r\n')
        for i in range(instruction_count):
            run_next_and_print_state()
