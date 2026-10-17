import sys

import os
import re
from typing import override, List, Tuple

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong, ChangeType
from plugin.codemig.codemig_common.migration_class import MigrationClass
from plugin.codemig.solver.solver import Solver


class BuildScriptSolver(Solver):
    arch_pattern = (
        r"x86_64|amd64|amd64p32|i386|i486|i586|i686|x32|"
        r"arm|arm64|arm64be|armbe|aarch64|aarch64_be|armv8-a|armv9-a|"
        r"ppc|ppc64|ppc64le|powerpc|powerpc64|powerpc64le|"
        r"mips|mips64|mips64le|mips64p32|mips64p32le|mipsle|"
        r"sparc|sparc64|sparcv9|"
        r"s390|s390x|"
        r"loongarch64|loongarch32|loong64|"
        r"wasm|wasm32|wasm64|"
        r"alpha|hppa|ia64|m68k|sh|tilegx|xtensa"
    )

    march_pattern = r"-march=(?!rv)[a-zA-Z0-9_-]+"

    # 改进后的匹配规则
    patterns = [
        # 1.硬编码的架构检测扫描
        (r'case\s*["\']?\$host\b', 'arch_case'),
        (r'case\s*["\']?\$host_cpu\b', 'arch_case'),
        (r'case\s*["\']?\$target\b', 'arch_case'),
        (r'case\s*["\']?\$target_cpu\b', 'arch_case'),

        # 2.特定架构的编译器标志
        (r'(-m(avx|sse|neon|fpu|float-abi|arch=[^ \n]*?(arm|x86)))', 'arch_flag'),

        # 3.字节序（Endianness）硬编码
        # RISC-V 同时支持小端（默认）和大端配置  AC_DEFINE([WORDS_BIGENDIAN], 1)  # 强制定义为大端
        (r'AC_DEFINE\s*\(\s*\[([\w]+_BIGENDIAN|ENDIANNESS)\]\s*,\s*\[?([01])\]?\s*(?:,\s*\[[^\]]*\]\s*)?\)', 'arch_endian'),

        # 4.汇编伪指令
        (rf'\.(set|arch|cpu)\b.*?\b({arch_pattern})\b', 'arch_pseudo_inst'),
        (rf'\.(ifdef|ifndef)\b.*?(__{arch_pattern}__)', 'arch_conditional_asm'),

        # 5. 特定架构的内联汇编检测
        (r'__asm__', 'arch_inline_asm'),

        # 6. 架构特定的环境变量检测
        (rf'\b(CC|CXX|LD|AS)\b.*?\b({arch_pattern})\b', 'arch_env_var'),

        # 7. 配置测试中的架构检测 (AC_TRY_xxx)
        (rf'AC_TRY_(RUN|COMPILE|LINK).*?\b({arch_pattern})\b', 'arch_config_test'),

    ]

    # 迁移建议字典（包含RISC-V支持检查）
    migration_advice = {
        'arch_case': "架构分支缺少RISC-V支持！需要添加类似分支：riscv*) ARCH_FLAGS=\"-mabi=lp64d\" ;;",
        'arch_flag': "特定架构编译器标志，需替换为RISC-V等效标志",
        'arch_endian': "字节序硬编码，RISC-V支持大端(be)和小端(le)配置",
        'arch_pseudo_inst': "汇编伪指令需添加RISC-V支持",
        'arch_conditional_asm': "汇编条件编译需添加RISC-V分支",
        'arch_inline_asm': "检测到架构特定的内联汇编，需替换为RISC-V兼容版本或抽象层",
        'arch_env_var': "检测到架构特定的环境变量，需确保支持riscv*目标",
        'arch_config_test': "配置测试中包含架构特定逻辑，需添加RISC-V分支",
    }

    compiled_patterns = [(re.compile(p[0], re.IGNORECASE), p[1]) for p in patterns]

    # 查找构建脚本
    @staticmethod
    @override
    def matches_file(file_name):
        ends = ['configure.ac', '.m4']
        return any(file_name.endswith(ext) for ext in ends)

    @classmethod
    @override
    def solve(cls, source_file):
        lines = source_file.get_code_lines()
        return BuildScriptSolver.find_pattern(lines, cls.compiled_patterns, cls.migration_advice)

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
            if stripped_line.startswith(('#', 'dnl')) or not stripped_line:
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

            # 处理case块
            if in_arch_case:
                case_lines.append(stripped_line)

                # 检查RISC-V分支
                if re.search(r'risc[_-]?v|rv(?:32|64)', stripped_line, re.IGNORECASE):
                    has_riscv_branch = True

                # 检测case结束
                if stripped_line.startswith('esac') and 'esac' in stripped_line:
                    in_arch_case = False
                    if not has_riscv_branch:
                        advice = migration_advice.get('arch_case')
                        code_too_long, mycode = Solver.extract_code(lines, case_start_line,
                                                                    line_number)
                        results.append(
                            (case_start_line, line_number, advice, code_too_long, mycode))

            # 单行模式匹配
            if not in_arch_case:
                for pattern, pattern_type in compiled_patterns:
                    if pattern_type == 'arch_case':
                        continue

                    match = pattern.search(stripped_line)
                    if match:
                        advice = migration_advice.get(pattern_type, "需要RISC-V兼容性检查")
                        results.append((line_number, line_number,
                                        f"{pattern_type}: {match.group()} - {advice}",
                                        CodeTooLong.HAS_SOURCE_CODE, stripped_line))
                        break  # 每行只匹配一个模式

            # 处理未闭合的case块
        if in_arch_case and not has_riscv_branch:
            advice = migration_advice.get('arch_case')
            end_lineno = len(lines)
            code_too_long, mycode = Solver.extract_code(lines, case_start_line, end_lineno)
            results.append((case_start_line, end_lineno, advice, code_too_long, mycode))

        return results, []

    @staticmethod
    @override
    def append_or_replace():
        return ChangeType.OTHER.value

    @staticmethod
    @override
    def migration_class():
        return MigrationClass.TEXT
