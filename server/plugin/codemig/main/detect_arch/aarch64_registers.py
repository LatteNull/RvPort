import os
import sys

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from plugin.codemig.main.detect_arch.detect_arch_utils import create_0_to_n
from common.public.public import ROOT_PATH

OPCODE_PATH = os.path.join(ROOT_PATH, 'server', 'plugin', 'codemig', 'main', 'detect_arch', 'aarch64.opcode')
def load_aarch64_opcodes():
    aarch64_opcodes = []
    if os.path.exists(OPCODE_PATH):
        with open(OPCODE_PATH, 'r') as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith('#'):
                    opcode_lower = line.lower()
                    if opcode_lower not in aarch64_opcodes:
                        aarch64_opcodes.append(opcode_lower)
    return aarch64_opcodes

AARCH64_KEYWORDS = {
    # 系统调用
    "svc",
}


def create_aarch64_registers():
    registers = []
    registers.extend(create_0_to_n("x", 30))
    registers.extend(create_0_to_n("w", 30))
    registers.extend(create_0_to_n("b", 31))
    registers.extend(create_0_to_n("h", 31))
    registers.extend(create_0_to_n("s", 31))
    registers.extend(create_0_to_n("d", 31))
    registers.extend(create_0_to_n("q", 31))
    registers.extend(create_0_to_n("v", 31))
    registers.extend(AARCH64_KEYWORDS)
    return registers


AARCH64_REGISTERS = set(create_aarch64_registers())
AARCH64_OPCODES = set(load_aarch64_opcodes())
