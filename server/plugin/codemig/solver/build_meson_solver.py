import os
import re
import sys
from typing import override, List, Tuple

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from plugin.codemig.codemig_common.migration_class import MigrationClass
from plugin.codemig.solver.solver import Solver
from plugin.codemig.codemig_common.codemig_common_utils import ChangeType

ARCH_OTHERS = (
    r"(?<![a-zA-Z0-9])("
    r"x86|x86_64|amd64|amd64p32|i386|i486|i586|i686|x32|"
    r"arm|arm64|arm64be|armbe|aarch64|aarch64_be|armv8-a|armv7|armv8|armv8a"
    r"ppc|ppc64|ppc64le|powerpc|powerpc64|powerpc64le|"
    r"mips|mips64|mips64le|mips64p32|mips64p32le|mipsle|"
    r"sparc|sparc64|sparcv9|"
    r"s390|s390x|"
    r"loongarch64|loong64|"
    r"wasm|wasm32|wasm64|"
    r"alpha|hppa|ia64|m68k|tilegx|xtensa"
    r")(?![a-zA-Z0-9])"
)

ARCH_RISCV = (
    r"(?<![a-zA-Z0-9])("
    r"riscv|risc-v|rvv|riscv64"
    r")(?![a-zA-Z0-9])"
)


class BuildMesonSolver(Solver):
    patterns = [
        (r'host_machine.cpu_family()', 'arch_case'),
        (ARCH_OTHERS, 'arch_detect')
    ]

    migration_advice = {
        'arch_case': "架构分支缺少RISC-V支持！需要添加类似分支：arch_subdir = 'riscv'",
        'arch_detect': "检测到非RISC架构，需要进一步检查"
    }

    compiled_patterns = [
        (re.compile(p[0], re.IGNORECASE), p[1]) for p in patterns
    ]

    # 查找构建脚本
    @staticmethod
    @override
    def matches_file(file_name):
        ends = ['meson.build', 'meson_options.txt']
        return any(file_name.endswith(ext) for ext in ends)

    @classmethod
    @override
    def solve(cls, source_file):
        lines = source_file.get_code_lines()
        return BuildMesonSolver.find_pattern(lines, cls.compiled_patterns,
                                             cls.migration_advice)

    @staticmethod
    def find_pattern(lines: List[str], compiled_patterns, migration_advice) -> List[Tuple]:
        results = []
        in_arch_case = False
        case_start_line = 0
        case_lines = []
        has_riscv_branch = False

        for line_number, line in enumerate(lines, 1):
            stripped_line = line.strip()

            # 跳过注释和空行
            if stripped_line.startswith('#') or not stripped_line:
                continue

            # 处理跨行语句
            next_line = lines[line_number] if line_number < len(lines) else ""

            # 检测case语句
            if not in_arch_case:
                for pattern, pattern_type in compiled_patterns:
                    if pattern_type == 'arch_case' and pattern.search(
                            stripped_line + " " + next_line[:20]):
                        in_arch_case = True
                        case_start_line = line_number
                        case_lines = [stripped_line]
                        has_riscv_branch = False
                        break

            # 处理if判断
            if in_arch_case:
                case_lines.append(stripped_line)

                # 检查RISC-V分支
                # if re.search(r'riscv(?:32|64)?', stripped_line, re.IGNORECASE):
                if re.search(ARCH_RISCV, stripped_line, re.IGNORECASE):
                    has_riscv_branch = True

                if stripped_line.startswith('endif'):
                    in_arch_case = False
                    if not has_riscv_branch:
                        advice = migration_advice.get('arch_case')
                        results.append((case_start_line, line_number, advice))

            if not in_arch_case:
                for pattern, pattern_type in compiled_patterns:
                    if pattern_type == 'arch_case':
                        continue

                    match = pattern.search(stripped_line)
                    if match:
                        advice = migration_advice.get(pattern_type, "需要RISC-V兼容性检查")
                        results.append((line_number, line_number,
                                        f"{pattern_type}: {match.group()} - {advice}"))
                        break  # 每行只匹配一个模式

        if in_arch_case and not has_riscv_branch:
            advice = migration_advice.get('arch_case')
            results.append((case_start_line, len(lines), advice))
        suggestions = []
        for res in results:
            start, end, suggest = res
            code_too_long, code = Solver.extract_code(lines, start, end)
            suggestions.append((start, end, suggest, code_too_long, code))
        return suggestions, []

    @staticmethod
    @override
    def append_or_replace():
        return ChangeType.OTHER.value

    @staticmethod
    @override
    def migration_class():
        return MigrationClass.TEXT
