import os
import re
import sys
from typing import override

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from plugin.codemig.codemig_common.migration_class import MigrationClass
from plugin.codemig.solver.solver import Solver
from plugin.codemig.codemig_common.codemig_common_utils import ChangeType


class GoReleaserYmlSolver(Solver):
    # 匹配规则
    patterns = [(r'^\s*goarch:\s*$', 'goarch_declaration')]

    # 迁移建议字典
    migration_advice = {'goarch_declaration': '架构列表缺少RISC-V支持'}

    compiled_patterns = [
        (re.compile(p[0], re.IGNORECASE), p[1]) for p in patterns
    ]

    @staticmethod
    @override
    def matches_file(file_name):
        return file_name.endswith("goreleaser.yml")

    @classmethod
    @override
    def solve(cls, source_file):
        lines = source_file.get_code_lines()
        return GoReleaserYmlSolver.find_arch_blocks(lines, cls.compiled_patterns,
                                                    cls.migration_advice)

    # 查找所有goarch块并检查架构
    @staticmethod
    def find_arch_blocks(lines, compiled_patterns, migration_advice):
        results = []
        in_arch_block = False
        arch_block_start = 0
        arch_list = []
        current_indent = 0

        for line_number, line in enumerate(lines, 1):
            stripped_line = line.strip()

            # 检查是否进入goarch块
            if not in_arch_block:
                for pattern, _ in compiled_patterns:
                    if pattern.search(line):  # 使用原始行而不是stripped_line
                        in_arch_block = True
                        arch_block_start = line_number
                        current_indent = len(line) - len(line.lstrip())
                        break
                continue

            # 处理goarch块内容
            if in_arch_block:
                # 计算当前行的缩进
                line_indent = len(line) - len(line.lstrip())

                # 检查是否还在同一个缩进级别
                if line_indent <= current_indent and stripped_line:
                    # 块结束
                    in_arch_block = False

                    # 检查架构列表是否包含riscv64
                    if arch_list and not {'riscv64', 'riscv'}.intersection(arch_list):
                        advice = migration_advice.get('goarch_declaration',
                                                      "需要进一步检查RISC-V兼容性")
                        code_too_long, mycode = Solver.extract_code(
                            lines, arch_block_start, line_number - 1)
                        results.append((
                            arch_block_start, line_number - 1,
                            f'发现架构定义块(行{arch_block_start}-{line_number - 1})，{advice}',
                            code_too_long, mycode))

                    arch_list = []
                    continue

                # 检查是否是列表项（正确的缩进级别）
                if line_indent > current_indent and stripped_line.startswith('- '):
                    arch = stripped_line[2:].strip()
                    arch_list.append(arch)

        # 处理文件末尾的块
        if arch_list and not {'riscv64', 'riscv'}.intersection(arch_list):
            advice = migration_advice.get('goarch_declaration', "需要进一步检查RISC-V兼容性")
            end_lineno = len(lines)
            code_too_long, mycode = Solver.extract_code(lines, arch_block_start, end_lineno)
            results.append(
                (arch_block_start, end_lineno,
                 f'发现架构定义块(行{arch_block_start}-{len(lines)})，{advice}',
                 code_too_long, mycode))

        return results, []

    @staticmethod
    @override
    def append_or_replace():
        return ChangeType.OTHER.value

    @staticmethod
    @override
    def migration_class():
        return MigrationClass.TEXT
