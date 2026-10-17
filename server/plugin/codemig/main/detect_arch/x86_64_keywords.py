import os
import sys

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from plugin.codemig.main.detect_arch.detect_arch_utils import create_0_to_n
from common.public.public import ROOT_PATH

OPCODE_PATH = os.path.join(ROOT_PATH, 'server', 'plugin', 'codemig', 'main', 'detect_arch', 'x86_64.opcode')
def load_x86_64_opcodes():
    x86_64_opcodes = []
    if os.path.exists(OPCODE_PATH):
        with open(OPCODE_PATH, 'r') as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith('#'):
                    opcode_lower = line.lower()
                    if opcode_lower not in x86_64_opcodes:
                        x86_64_opcodes.append(opcode_lower)
    return x86_64_opcodes

X86_64_KEYWORDS = {
    # instructions
    "syscall",
    "pause",
    "rdtsc",
    "rdtscp",
    "cpuid",
    # registers
    "rax",
    "rbx",
    "rcx",
    "rdx",
    "rsi",
    "rdi",
    "rbp",
    "rsp",
    "r8",
    "r9",
    "r10",
    "r11",
    "r12",
    "r13",
    "r14",
    "r15",
    "eax",
    "ebx",
    "ecx",
    "edx",
    "esi",
    "edi",
    "ebp",
    "esp",
    "r8d",
    "r9d",
    "r10d",
    "r11d",
    "r12d",
    "r13d",
    "r14d",
    "r15d",
    "ax",
    "bx",
    "cx",
    "dx",
    "si",
    "di",
    "bp",
    "sp",
    "r8w",
    "r9w",
    "r10w",
    "r11w",
    "r12w",
    "r13w",
    "r14w",
    "r15w",
    "ah",
    "al",
    "bh",
    "bl",
    "ch",
    "cl",
    "dh",
    "dl",
    "sil",
    "bpl",
    "spl",
    "r8b",
    "r9b",
    "r10b",
    "r11b",
    "r12b",
    "r13b",
    "r14b",
    "r15b",
}


def create_x86_registers():
    registers = []
    registers.extend(create_0_to_n("mm", 7))
    registers.extend(create_0_to_n("xmm", 15))
    registers.extend(create_0_to_n("ymm", 15))
    registers.extend(create_0_to_n("zmm", 31))
    registers.extend(X86_64_KEYWORDS)
    return registers


X86_REGISTERS = set(create_x86_registers())
X86_64_OPCODES = set(load_x86_64_opcodes())
