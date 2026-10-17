import os
import sys

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from plugin.codemig.main.detect_arch.detect_arch_utils import create_0_to_n
from common.public.public import ROOT_PATH

OPCODE_PATH = os.path.join(ROOT_PATH, 'server', 'plugin', 'codemig', 'main', 'detect_arch', 'riscv.opcode')

def load_riscv_opcodes():
    riscv_opcodes = []
    if os.path.exists(OPCODE_PATH):
        with open(OPCODE_PATH, 'r') as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith('#'):
                    riscv_opcodes.append(line.lower())
    return riscv_opcodes

REG_EX = {
    "csr", # CSR寄存器
    "zero", #x0
    "ra", #x1
    "gp", #x3
    "tp", #x4
}

REG_SCR_M = {
    "mstatus",
    "mie"
    "mtvec",
    "mscratch",
    "mepc",
    "mcause",
    "mtval",
    "mip",
    "mvendorid",
    "marchid",
    "mimpid",
    "mhartid",
}

REG_SCR_S = {
    "sstatus",
    "sie",
    "stvec",
    "sscratch",
    "sepc",
    "scause",
    "stval",
    "satp",
}

REG_SCR_U = {
    "cycle",
    "time",
    "instret",
    "fflags",
    "frm",
    "fcsr", # FCSR寄存器
}

def create_riscv_registers():
    registers = []
    registers.extend(create_0_to_n("t", 6))
    registers.extend(create_0_to_n("a", 7))
    registers.extend(create_0_to_n("f", 31))
    registers.extend(create_0_to_n("ft", 11))
    registers.extend(create_0_to_n("fs", 11))
    registers.extend(create_0_to_n("fa", 7))
    registers.extend(REG_EX)
    registers.extend(REG_SCR_M)
    registers.extend(REG_SCR_S)
    registers.extend(REG_SCR_U)
    return registers


RISCV_KEYWORDS = set(create_riscv_registers()) | set(load_riscv_opcodes())
