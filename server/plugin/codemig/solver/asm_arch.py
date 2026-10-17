from enum import Enum
import os
import sys
import re

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from plugin.codemig.main.detect_arch.riscv_registers import RISCV_KEYWORDS
from plugin.codemig.main.detect_arch.aarch64_registers import AARCH64_OPCODES
from plugin.codemig.main.detect_arch.x86_64_keywords import X86_64_OPCODES

# - riscv
# https://msyksphinz-self.github.io/riscv-isadoc/
# https://riscv.github.io/riscv-isa-manual/snapshot/unprivileged/
# https://riscv.github.io/riscv-isa-manual/snapshot/privileged/
# https://sourceware.org/git/?spm=5176.28103460.0.0.72ab6308kyBUfu&p=binutils-gdb.git;a=blob;f=opcodes/riscv-opc.c

# - arm
# https://developer.arm.com/documentation/ddi0487/latest/   
# Arm Architecture Reference Manual for A-profile architecture
# https://sourceware.org/git/?p=binutils-gdb.git;a=tree;f=opcodes  aarch64-tbl.h aarch64-tbl-2.h  

# - amd
# https://www.felixcloutier.com/x86/
# https://sourceware.org/git/?p=binutils-gdb.git;a=tree;f=opcodes  i386-opc.tbl

def create_unique_riscvs():
    """
    从 RISCV_KEYWORDS 中排除 AARCH64_OPCODES 和 X86_64_OPCODES，
    返回只属于 RISC-V 的关键字集合
    """    
    # 排除 ARM 和 x86 的指令，只保留 RISC-V 独有的关键字
    unique_riscvs = RISCV_KEYWORDS - AARCH64_OPCODES - X86_64_OPCODES
    return unique_riscvs

class AsmArch(Enum):
    RISCV = "RISC-V"
    X86_64 = "x86_64"
    AARCH64 = "aarch64"
    UNKNOWN = "unknown_arch"

    @staticmethod
    def remove_asm_comments(content):
        """
        移除汇编代码中的注释，支持多种注释格式：
        - # 单行注释（Unix/AT&T 风格）
        - // 单行注释（C++ 风格，某些汇编器支持）
        - ; 单行注释（某些汇编器使用）
        """
        if content is None or len(content) == 0:
            return ''
        # 移除 # 单行注释
        content = re.sub(r'#.*?$', '', content, flags=re.MULTILINE)
        # 移除 // 单行注释
        content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
        # 移除 ; 单行注释（某些汇编器使用，如 NASM）
        # 简单处理：移除 ; 后面到行尾的内容
        content = re.sub(r';.*?$', '', content, flags=re.MULTILINE)
        return content

    @staticmethod
    def detect_asm_arch(asm_stmt):
        # 先移除注释，避免注释中的文本影响架构检测
        asm_stmt = AsmArch.remove_asm_comments(asm_stmt)
        for match in re.findall(r'\$?[a-zA-Z][a-zA-Z0-9]*\b', asm_stmt):
            reg = match.lower()
            if reg in create_unique_riscvs():
                return AsmArch.RISCV
        for match in re.findall(r'\$?[a-zA-Z]+(?:\.[a-zA-Z]+){0,3}\b', asm_stmt):
            opcode = match.lower()
            if opcode in create_unique_riscvs():
                return AsmArch.RISCV
        return AsmArch.UNKNOWN
