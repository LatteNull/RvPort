import sys

import os
import re
from typing import override

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.public.public import ROOT_PATH

from plugin.codemig.solver.solver import Solver
from plugin.codemig.solver.solver import create_automaton
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong, matches_c_file, \
    ChangeType

REPLACEMENT = "建议使用riscv的intrinsics进行替换、优化文件中{arch}的intrinsic函数"

ARCH_X86 = "__x86_64__"
ARCH_ARM = "__aarch64__"
ARCH_UNKNOWN = "unknown_arch"


# INTRINSICS = {
#     "x86intrin.h": ARCH_X86,
#     "mmintrin.h": ARCH_X86,
#     "mm3dnow.h": ARCH_X86,
#     "xmmintrin.h": ARCH_X86,
#     "emmintrin.h": ARCH_X86,
#     "pmmintrin.h": ARCH_X86,
#     "tmmintrin.h": ARCH_X86,
#     "popcntintrin.h": ARCH_X86,
#     "ammintrin.h": ARCH_X86,
#     "smmintrin.h": ARCH_X86,
#     "nmmintrin.h": ARCH_X86,
#     "wmmintrin.h": ARCH_X86,
#     "immintrin.h": ARCH_X86,
#     "arm_neon.h": ARCH_ARM,
#     "intrin.h": ARCH_ARM,
# }


def load_head_from_file(file_path: str) -> list:
    head = []
    with open(file_path, 'r') as file:
        head = [line.strip() for line in file if line.strip()]
    return head


CONF_PATH = os.path.join(ROOT_PATH, 'server', 'plugin', 'codemig', 'solver')
X86_HEAD_SET = {head: ARCH_X86 for head in
                load_head_from_file(os.path.join(CONF_PATH, 'x86.intrinsics'))}
ARM_HEAD_SET = {head: ARCH_ARM for head in
                load_head_from_file(os.path.join(CONF_PATH, 'aarch64.intrinsics'))}
# INTRINSICS.update(X86_HEAD_SET)
INTRINSICS = {}
INTRINSICS.update(ARM_HEAD_SET)
INTRINSICS.update(X86_HEAD_SET)


class IntrinsicsSolver(Solver):
    automaton = create_automaton(INTRINSICS)

    @staticmethod
    def solve_intrinsics(lines, line_number_and_matches):
        suggestions = []
        for line_number, matches in line_number_and_matches:
            arch = INTRINSICS.get(matches[0], ARCH_UNKNOWN)
            suggestion = REPLACEMENT.format(arch=arch, file_name=matches[0])
            suggestions.append([line_number, line_number, suggestion, CodeTooLong.HAS_SOURCE_CODE,
                                lines[line_number - 1]])
        return suggestions, []

    @staticmethod
    @override
    def matches_file(file_name):
        return matches_c_file(file_name)

    @classmethod
    def find_matches(cls, lines):
        line_number_and_matches = []
        for line_number, line in enumerate(lines, start=1):
            matches = []
            for _, (_, match) in cls.automaton.iter(line):
                # matches = [match for _, (_, match) in cls.automaton.iter(line)]
                # 使用正则表达式进行整字匹配 (通过 \b 表示单词边界)
                pattern = rf'\b{re.escape(match)}\b'
                if re.search(pattern, line):
                    matches.append(match)
            if matches:
                line_number_and_matches.append((line_number, matches))
        return line_number_and_matches

    @classmethod
    @override
    def solve(cls, source_file):
        lines = source_file.remove_c_comments_lines()
        line_number_and_matches = cls.find_matches(lines)
        return IntrinsicsSolver.solve_intrinsics(lines, line_number_and_matches)

    @staticmethod
    @override
    def append_or_replace():
        return ChangeType.REPLACE.value
