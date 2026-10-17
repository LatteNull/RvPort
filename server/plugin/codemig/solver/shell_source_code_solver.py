import os
import re
import sys
from typing import override

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong, ChangeType
from plugin.codemig.codemig_common.migration_class import MigrationClass
from plugin.codemig.solver.solver import Solver

# pylint: disable=too-few-public-methods
class CaseBlockProcessor:
    case_pattern = re.compile(
        r'case\s+"\$'  # case "$
        r'(?:'  # 非捕获组开始
        r'\(uname\s+-m\)'  # (uname -m)
        r'|'  # 或
        r'ARCH'  # ARCH
        r')'  # 非捕获组结束
        r'"'  # "
    )
    riscv_pattern = re.compile(r'riscv(?:64|32)?')

    @classmethod
    def process_lines(cls, lines):
        """
        处理文本行，识别特定case块并进行替换

        :param lines: 原始文本行列表
        :return: 处理后的文本行列表
        """
        processed_lines = []
        i = 0
        total_lines = len(lines)

        while i < total_lines:
            line = lines[i]
            matched = False
            try:
                if cls.case_pattern.search(line):
                    start_line = i
                    end_line = cls._find_case_block_end(lines, i)
                    if not end_line:
                        raise ValueError("文件不完整")
                    block_lines = lines[start_line:end_line + 1]

                    if cls._contains_riscv(block_lines):
                        processed_lines.extend(['\n'] * (end_line - start_line + 1))
                        i = end_line + 1
                        matched = True

                if not matched:
                    processed_lines.append(line)
                    i += 1
            except ValueError as e:
                print(f"处理失败：{e}")
                return processed_lines

        return processed_lines

    @staticmethod
    def _find_case_block_end(lines, start_idx):
        """
        找到case块的结束行(esac所在行)
        """
        indent_level = 0
        for i in range(start_idx, len(lines)):
            line = lines[i]
            if line.strip().startswith('case'):
                indent_level += 1
            elif line.strip() == 'esac':
                indent_level -= 1
                if indent_level == 0:
                    return i
        return False

    @classmethod
    def _contains_riscv(cls, block_lines):
        """
        检查块中是否包含riscv关键字
        """
        for line in block_lines:
            if cls.riscv_pattern.search(line):
                return True
        return False


class ShellSourceCodeSolver(Solver):
    patterns = [
        (r'case\s+"\$((?:\(uname\s+-m\)|ARCH))"', 'arch_case'),
        (r'(?i)(?<![a-z0-9])(x86|x86_64|amd64|amd64p32|arm64|arm64be|aarch64|aarch_64|aarch64_be|'
         r'armbe|arm|loong64|386|ppc|ppc64|ppc64le|s390|s390x|mips|'
         r'mips64|mips64le|mips64p32|mips64p32le|mipsle|sparc|sparc64|wasm)(?![a-z0-9])',
         'arch_detect'),
    ]
    migration_advice = {
        'arch_case': "架构分支缺少RISC-V支持！",
        'arch_detect': '检测到非riscv架构，建议检查',
    }

    compiled_patterns = [(re.compile(p[0], re.IGNORECASE), p[1]) for p in patterns]

    @staticmethod
    @override
    def matches_file(file_name):
        return file_name.endswith(".sh")

    @classmethod
    @override
    def solve(cls, source_file):
        lines = source_file.remove_multiple_comments_lines()
        remove_case_lines = CaseBlockProcessor.process_lines(lines)
        return ShellSourceCodeSolver.find_pattern(remove_case_lines, cls.compiled_patterns,
                                                  cls.migration_advice)

    # 根据匹配规则查找行内容
    @staticmethod
    def find_pattern(lines, compiled_patterns, migration_advice):
        results = []
        for line_number, line in enumerate(lines, 1):
            stripped_line = line.strip()
            for pattern, pattern_type in compiled_patterns:
                if pattern_type == 'arch_case':
                    continue
                match = pattern.search(stripped_line)
                if match:
                    advice = migration_advice.get(pattern_type, "需要RISC-V兼容性检查")
                    results.append(
                        (line_number, line_number,
                         f"{pattern_type}: {match.group()} - {advice}",
                         CodeTooLong.HAS_SOURCE_CODE, stripped_line))
                    break  # 每行只匹配一个模式
        return results, []

    @staticmethod
    @override
    def append_or_replace():
        return ChangeType.OTHER.value

    @staticmethod
    @override
    def migration_class():
        return MigrationClass.TEXT
