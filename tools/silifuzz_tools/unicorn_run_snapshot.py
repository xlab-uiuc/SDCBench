#!/usr/bin/python

from __future__ import print_function
from unicorn import *
from unicorn.x86_const import *
from capstone import *
import struct
import argparse

import snapshot_pb2

from google.protobuf.json_format import MessageToDict

parser = argparse.ArgumentParser(description='Emulate silifuzz protobuf')
parser.add_argument('--snapshot_protobuf', type=str, help='Protobuf file', default='test.pb')
args = parser.parse_args()

snapshot = snapshot_pb2.Snapshot()
with open(args.snapshot_protobuf, 'rb') as f:
    snapshot.ParseFromString(f.read())
    json_obj = MessageToDict(snapshot)
    #print(json_obj)

class FPRegisters:
    def __init__(self, fpregs_bytes):
        self.fcw, self.fsw, self.ftw, self.reserved0, self.fop, self.rip, self.rdp, self.mxcsr, self.mxcsr_mask, self.st, self.xmm, self.padding = struct.unpack('<HHBBHQQLL128s256s96s', fpregs_bytes)

        sts = []
        for i in range(0, int(len(self.st) / 8), 2):
            a, b = struct.unpack('<QQ', self.st[i*8:(i+2)*8])
            c = (a << 64) | b
            sts.append(c)
        self.st = sts
        
        xmm = []
        for i in range(0, int(len(self.xmm) / 8), 2):
            a, b = struct.unpack('<QQ', self.xmm[i*8:(i+2)*8])
            c = (a << 64) | b
            xmm.append(c)
        self.xmm = xmm


class GRegisters:
    def __init__(self, gregs_bytes):
        self.r15, self.r14, self.r13, self.r12, self.rbp, self.rbx, self.r11, self.r10, \
        self.r9, self.r8, self.rax, self.rcx, self.rdx, self.rsi, self.rdi, self.orig_rax, self.rip, \
        self.cs, self.eflags, self.rsp, self.ss, self.fs_base, self.gs_base, self.ds, self.es, \
        self.fs, self.gs = struct.unpack('8Q8Q2Q6QQ2Q', gregs_bytes)

class Registers:
    def __init__(self, snapshot):
        fpregs_bytes = snapshot.registers.fpregs
        gregs_bytes = snapshot.registers.gregs

        self.fpregs = FPRegisters(fpregs_bytes)
        self.gregs = GRegisters(gregs_bytes)


regs = Registers(snapshot)

# code to be emulated
X86_CODE32 = b"\x41\x4a" # INC ecx; DEC edx

# memory address where emulation starts
ADDRESS = 0x1000000

CODE_ADDR = 1 << 31
CODE_SIZE = 0x1000

MEM_ADDR = 0x1000
MEM_SIZE = (1 << 30) - MEM_ADDR

STACK_ADDR = 0x1000000

MAX_INST_EXEC = 100

print("Emulate i386 code")
try:
    # Initialize emulator in X86-32bit mode
    cs = Cs(CS_ARCH_X86, CS_MODE_64)
    mu = Uc(UC_ARCH_X86, UC_MODE_64)

    for m in snapshot.memory_mappings:
        mu.mem_map(m.start_address, m.num_bytes, m.permissions)
    
    for m in snapshot.memory_bytes:
        print(f'Writing to {m.start_address:016X}...')
        mu.mem_write(m.start_address, m.byte_values)

        if regs.gregs.rip == m.start_address:
            instructions = m.byte_values
            for i, c in enumerate(m.byte_values):
                if c == ord(b'\xCC'):
                    instructions = m.byte_values[:i]
                    break

            print('Instructions:')
            insts = instructions[:]
            for i in cs.disasm(insts, regs.gregs.rip):
                print("0x%x:\t%s\t%s" %(i.address, i.mnemonic, i.op_str))
                if i.mnemonic == 'call' and i.op_str == 'qword ptr [rip]':
                    instructions = insts[:i.address - regs.gregs.rip]
                    break


    # map 2MB memory for this emulation
    #mu.mem_map(CODE_ADDR, CODE_SIZE)

    # write machine code to be emulated to memory
    #mu.mem_write(CODE_ADDRESS, X86_CODE32)

    
    mu.reg_write(UC_X86_REG_R8, regs.gregs.r8)
    mu.reg_write(UC_X86_REG_R9, regs.gregs.r9)
    mu.reg_write(UC_X86_REG_R10, regs.gregs.r10)
    mu.reg_write(UC_X86_REG_R11, regs.gregs.r11)
    mu.reg_write(UC_X86_REG_R12, regs.gregs.r12)
    mu.reg_write(UC_X86_REG_R13, regs.gregs.r13)
    mu.reg_write(UC_X86_REG_R14, regs.gregs.r14)
    mu.reg_write(UC_X86_REG_R15, regs.gregs.r15)
    
    mu.reg_write(UC_X86_REG_RDI, regs.gregs.rdi)
    mu.reg_write(UC_X86_REG_RSI, regs.gregs.rsi)
    mu.reg_write(UC_X86_REG_RBP, regs.gregs.rbp)
    mu.reg_write(UC_X86_REG_RBX, regs.gregs.rbx)
    mu.reg_write(UC_X86_REG_RDX, regs.gregs.rdx)
    mu.reg_write(UC_X86_REG_RAX, regs.gregs.rax)
    mu.reg_write(UC_X86_REG_RCX, regs.gregs.rcx)
    mu.reg_write(UC_X86_REG_RSP, regs.gregs.rsp)
    mu.reg_write(UC_X86_REG_RIP, regs.gregs.rip)
    mu.reg_write(UC_X86_REG_RFLAGS, regs.gregs.eflags)

    mu.reg_write(UC_X86_REG_CS, regs.gregs.cs)
    #mu.reg_write(UC_X86_REG_GS, regs.gregs.gs)
    #mu.reg_write(UC_X86_REG_FS, regs.gregs.fs)
    mu.reg_write(UC_X86_REG_SS, regs.gregs.ss)
    mu.reg_write(UC_X86_REG_DS, regs.gregs.ds)
    mu.reg_write(UC_X86_REG_ES, regs.gregs.es)
    
    mu.reg_write(UC_X86_REG_FS_BASE, regs.gregs.fs_base)
    mu.reg_write(UC_X86_REG_GS_BASE, regs.gregs.gs_base)
    
    mu.reg_write(UC_X86_REG_FPCW, regs.fpregs.fcw)
    mu.reg_write(UC_X86_REG_FPSW, regs.fpregs.fsw)
    mu.reg_write(UC_X86_REG_FPTAG, regs.fpregs.ftw)
    mu.reg_write(UC_X86_REG_FOP, regs.fpregs.fop)
    mu.reg_write(UC_X86_REG_FIP, regs.fpregs.rip)
    mu.reg_write(UC_X86_REG_FDP, regs.fpregs.rdp)
    mu.reg_write(UC_X86_REG_MXCSR, regs.fpregs.mxcsr)
    #mu.reg_write(UC_X86_REG_MXCSR_MASK, regs.fpregs.mxcsr_mask)

    mu.reg_write(UC_X86_REG_ST0, regs.fpregs.st[0])
    mu.reg_write(UC_X86_REG_ST1, regs.fpregs.st[1])
    mu.reg_write(UC_X86_REG_ST2, regs.fpregs.st[2])
    mu.reg_write(UC_X86_REG_ST3, regs.fpregs.st[3])
    mu.reg_write(UC_X86_REG_ST4, regs.fpregs.st[4])
    mu.reg_write(UC_X86_REG_ST5, regs.fpregs.st[5])
    mu.reg_write(UC_X86_REG_ST6, regs.fpregs.st[6])
    mu.reg_write(UC_X86_REG_ST7, regs.fpregs.st[7])
    
    mu.reg_write(UC_X86_REG_XMM0, regs.fpregs.xmm[0])
    mu.reg_write(UC_X86_REG_XMM1, regs.fpregs.xmm[1])
    mu.reg_write(UC_X86_REG_XMM2, regs.fpregs.xmm[2])
    mu.reg_write(UC_X86_REG_XMM3, regs.fpregs.xmm[3])
    mu.reg_write(UC_X86_REG_XMM4, regs.fpregs.xmm[4])
    mu.reg_write(UC_X86_REG_XMM5, regs.fpregs.xmm[5])
    mu.reg_write(UC_X86_REG_XMM6, regs.fpregs.xmm[6])
    mu.reg_write(UC_X86_REG_XMM7, regs.fpregs.xmm[7])
    mu.reg_write(UC_X86_REG_XMM8, regs.fpregs.xmm[8])
    mu.reg_write(UC_X86_REG_XMM9, regs.fpregs.xmm[9])
    mu.reg_write(UC_X86_REG_XMM10, regs.fpregs.xmm[10])
    mu.reg_write(UC_X86_REG_XMM11, regs.fpregs.xmm[11])
    mu.reg_write(UC_X86_REG_XMM12, regs.fpregs.xmm[12])
    mu.reg_write(UC_X86_REG_XMM13, regs.fpregs.xmm[13])
    mu.reg_write(UC_X86_REG_XMM14, regs.fpregs.xmm[14])
    mu.reg_write(UC_X86_REG_XMM15, regs.fpregs.xmm[15])

    def dump_state():
        R8 = mu.reg_read(UC_X86_REG_R8)
        R9 = mu.reg_read(UC_X86_REG_R9)
        R10 = mu.reg_read(UC_X86_REG_R10)
        R11 = mu.reg_read(UC_X86_REG_R11)
        R12 = mu.reg_read(UC_X86_REG_R12)
        R13 = mu.reg_read(UC_X86_REG_R13)
        R14 = mu.reg_read(UC_X86_REG_R14)
        R15 = mu.reg_read(UC_X86_REG_R15)
        
        RDI = mu.reg_read(UC_X86_REG_RDI)
        RSI = mu.reg_read(UC_X86_REG_RSI)
        RBP = mu.reg_read(UC_X86_REG_RBP)
        RBX = mu.reg_read(UC_X86_REG_RBX)
        RDX = mu.reg_read(UC_X86_REG_RDX)
        RAX = mu.reg_read(UC_X86_REG_RAX)
        RCX = mu.reg_read(UC_X86_REG_RCX)
        RSP = mu.reg_read(UC_X86_REG_RSP)
        RIP = mu.reg_read(UC_X86_REG_RIP)
        RFLAGS = mu.reg_read(UC_X86_REG_RFLAGS)

        CS = mu.reg_read(UC_X86_REG_CS)
        #GS = mu.reg_read(UC_X86_REG_GS)
        #FS = mu.reg_read(UC_X86_REG_FS)
        SS = mu.reg_read(UC_X86_REG_SS)
        DS = mu.reg_read(UC_X86_REG_DS)
        ES = mu.reg_read(UC_X86_REG_ES)
        
        FS_BASE = mu.reg_read(UC_X86_REG_FS_BASE)
        GS_BASE = mu.reg_read(UC_X86_REG_GS_BASE)
        
        FPCW = mu.reg_read(UC_X86_REG_FPCW)
        FPSW = mu.reg_read(UC_X86_REG_FPSW)
        FPTAG = mu.reg_read(UC_X86_REG_FPTAG)
        FOP = mu.reg_read(UC_X86_REG_FOP)
        FIP = mu.reg_read(UC_X86_REG_FIP)
        FDP = mu.reg_read(UC_X86_REG_FDP)
        MXCSR = mu.reg_read(UC_X86_REG_MXCSR)
        #MXCSR_MASK = mu.reg_read(UC_X86_REG_MXCSR_MASK)

        ST0 = mu.reg_read(UC_X86_REG_ST0)
        ST1 = mu.reg_read(UC_X86_REG_ST1)
        ST2 = mu.reg_read(UC_X86_REG_ST2)
        ST3 = mu.reg_read(UC_X86_REG_ST3)
        ST4 = mu.reg_read(UC_X86_REG_ST4)
        ST5 = mu.reg_read(UC_X86_REG_ST5)
        ST6 = mu.reg_read(UC_X86_REG_ST6)
        ST7 = mu.reg_read(UC_X86_REG_ST7)
        
        XMM0 = mu.reg_read(UC_X86_REG_XMM0)
        XMM1 = mu.reg_read(UC_X86_REG_XMM1)
        XMM2 = mu.reg_read(UC_X86_REG_XMM2)
        XMM3 = mu.reg_read(UC_X86_REG_XMM3)
        XMM4 = mu.reg_read(UC_X86_REG_XMM4)
        XMM5 = mu.reg_read(UC_X86_REG_XMM5)
        XMM6 = mu.reg_read(UC_X86_REG_XMM6)
        XMM7 = mu.reg_read(UC_X86_REG_XMM7)
        XMM8 = mu.reg_read(UC_X86_REG_XMM8)
        XMM9 = mu.reg_read(UC_X86_REG_XMM9)
        XMM10 = mu.reg_read(UC_X86_REG_XMM10)
        XMM11 = mu.reg_read(UC_X86_REG_XMM11)
        XMM12 = mu.reg_read(UC_X86_REG_XMM12)
        XMM13 = mu.reg_read(UC_X86_REG_XMM13)
        XMM14 = mu.reg_read(UC_X86_REG_XMM14)
        XMM15 = mu.reg_read(UC_X86_REG_XMM15)
        
        print(">>> R8  = 0x%x" % R8)
        print(">>> R9  = 0x%x" % R9)
        print(">>> R10 = 0x%x" % R10)
        print(">>> R11 = 0x%x" % R11)
        print(">>> R12 = 0x%x" % R12)
        print(">>> R13 = 0x%x" % R13)
        print(">>> R14 = 0x%x" % R14)
        print(">>> R15 = 0x%x" % R15)

        print(">>> RDI = 0x%x" % RDI)
        print(">>> RSI = 0x%x" % RSI)
        print(">>> RBP = 0x%x" % RBP)
        print(">>> RBX = 0x%x" % RBX)
        print(">>> RDX = 0x%x" % RDX)
        print(">>> RAX = 0x%x" % RAX)
        print(">>> RCX = 0x%x" % RCX)
        print(">>> RSP = 0x%x" % RSP)
        print(">>> RIP = 0x%x" % RIP)
        print(">>> RFLAGS = 0x%x" % RFLAGS)

    def hook_code64(uc, address, size, user_data):
        print('')
        print(">>> Tracing instruction at 0x%x, instruction size = 0x%x" %(address, size))
        rip = uc.reg_read(UC_X86_REG_RIP)
        print(">>> RIP is 0x%x" % rip)
        insts = uc.mem_read(address, size)
        for i in cs.disasm(insts, address):
            print(f'{i.address:016X}: \t{i.mnemonic}\t{i.op_str}')
        dump_state()
        print('')


    #mu.mem_map(CODE_ADDR, CODE_SIZE)
    #mu.mem_write(CODE_ADDRESS, X86_CODE32)
    mu.hook_add(UC_HOOK_CODE, hook_code64)
    
    print(f'Starting execution on {regs.gregs.rip:016X} with len {len(instructions)}')
    dump_state()
    # emulate code in infinite time & unlimited instructions
    mu.emu_start(regs.gregs.rip, regs.gregs.rip + len(instructions))

    # now print out some registers
    print("Emulation done. Below is the CPU context")

    r_ecx = mu.reg_read(UC_X86_REG_ECX)
    r_edx = mu.reg_read(UC_X86_REG_EDX)
    print(">>> ECX = 0x%x" %r_ecx)
    print(">>> EDX = 0x%x" %r_edx)

except UcError as e:
    print("ERROR: %s" % e)

