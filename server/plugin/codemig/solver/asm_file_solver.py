import sys
import os
from typing import override

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from plugin.codemig.solver.asm_arch import AsmArch
from plugin.codemig.solver.solver import Solver
from plugin.codemig.codemig_common.arch_pattern import ArchPattern
from plugin.codemig.codemig_common.codemig_common_utils import NUMBER_LINES_TOO_LONG, CodeTooLong, \
    ChangeType


class AsmFileSolver(Solver):

    @staticmethod
    @override
    def matches_file(file_name):
        return (file_name.endswith(".s") or file_name.endswith(".S") or file_name.endswith(
            ".asm")) and not ArchPattern.is_arch_pattern(file_name)

    @staticmethod
    def extract_code(code, start_lineno, end_lineno):
        number_lines = end_lineno - start_lineno + 1
        code_too_long = number_lines > NUMBER_LINES_TOO_LONG
        if code_too_long:
            return CodeTooLong.CODE_TOO_LONG, None
        return CodeTooLong.HAS_SOURCE_CODE, code

    @classmethod
    @override
    def solve(cls, source_file):
        code = source_file.get_code().strip()
        if not code:
            return [], []

        arch = AsmArch.detect_asm_arch(code)
        if arch != AsmArch.RISCV:
            lineno = len(source_file.get_code_lines())
            code_too_long, my_code = AsmFileSolver.extract_code(code, 1, lineno + 1)
            return [[1, lineno, f"此处汇编与架构相关，请转换为适用于 RISC-V 架构的实现。",
                     code_too_long, my_code]], []
        return [], []

    @staticmethod
    @override
    def append_or_replace():
        return ChangeType.OTHER.value
