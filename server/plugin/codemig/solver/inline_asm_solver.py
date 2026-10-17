import os
import re
import sys
from typing import override

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from plugin.codemig.solver.asm_arch import AsmArch
from plugin.codemig.solver.solver import Solver
from plugin.codemig.codemig_common.codemig_common_utils import NUMBER_LINES_TOO_LONG, CodeTooLong, \
    matches_c_file, ChangeType


def get_line_offsets(code):
    index = 0
    line_offsets = []
    offset = 0
    for line in code.splitlines(keepends=True):
        line_offsets.append(offset)
        offset += len(line)
        index += 1
    return line_offsets


def get_line_number(start_pos, end_pos, line_offsets):
    start_lineno = None
    for i, start in enumerate(line_offsets):
        if start_lineno is None and start_pos < start:
            start_lineno = i
        if end_pos < start:
            return start_lineno, i

    end_lineno = len(line_offsets)
    if start_lineno is None:
        return end_lineno, end_lineno
    return start_lineno, end_lineno


# 提取完整 asm 表达式：查找括号配对直到 ';'
def find_end_pos(start_pos, code):
    i = start_pos
    n = len(code)
    paren_count = 0
    in_string = False
    escaped = False
    while i < n:
        c = code[i]
        if in_string:
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == '"':
                in_string = False
        else:
            if c == '"':
                in_string = True
            elif c == '(':
                paren_count += 1
            elif c == ')':
                if paren_count == 1:
                    return i
                paren_count -= 1
        i += 1
    return None  # 匹配失败


class InlineAsmSolver(Solver):
    asm_start_pattern = re.compile(
        r'''
        (?:
            \b__asm__|\b__asm|\basm|\basm!|\bglobal_asm!|\bnaked_asm!       # __asm__ 或 __asm 或 asm
        )
        (?:\s+\w+)*                       # 0 个或多个修饰词（如 volatile/goto）
        \s*\(                             # 后跟左括号
        ''', re.VERBOSE | re.MULTILINE)

    @staticmethod
    @override
    def matches_file(file_name):
        return matches_c_file(file_name)

    @classmethod
    def find_asm_for_file(cls, code):
        lineno_and_asm_stmt = []
        for match in cls.asm_start_pattern.finditer(code):
            start_pos = match.start()
            end_pos = find_end_pos(start_pos, code)
            if end_pos is not None:
                asm_stmt = code[start_pos:end_pos + 1]
                asm_stmt = cls.remove_variable(asm_stmt)
                start_lineno, end_lineno = get_line_number(start_pos, end_pos,
                                                           get_line_offsets(code))
                lineno_and_asm_stmt.append((start_lineno, end_lineno, asm_stmt))
        return lineno_and_asm_stmt

    @staticmethod
    def create_suggestion_for_arch(arch):
        arch_str = arch.value
        return f"此处汇编与架构相关，请转换为适用于 RISC-V 架构的实现。"

    @staticmethod
    def extract_code(asm_stmt, start_lineno, end_lineno):
        number_lines = end_lineno - start_lineno + 1
        code_too_long = number_lines > NUMBER_LINES_TOO_LONG
        if code_too_long:
            return CodeTooLong.CODE_TOO_LONG, None
        return CodeTooLong.HAS_SOURCE_CODE, asm_stmt

    @staticmethod
    def create_suggestion(lineno_and_asm_stmt):
        suggestions = []
        for start_lineno, end_lineno, asm_stmt in lineno_and_asm_stmt:
            arch = AsmArch.detect_asm_arch(asm_stmt)
            if arch != AsmArch.RISCV:
                code_too_long, code = InlineAsmSolver.extract_code(asm_stmt, start_lineno,
                                                                   end_lineno)
                suggestions.append([
                    start_lineno, end_lineno,
                    InlineAsmSolver.create_suggestion_for_arch(arch),
                    code_too_long, code
                ])
        return suggestions, []

    @classmethod
    @override
    def solve(cls, source_file):
        code = source_file.remove_c_comments()
        lineno_and_asm_stmt = cls.find_asm_for_file(code)
        return InlineAsmSolver.create_suggestion(lineno_and_asm_stmt)

    @staticmethod
    @override
    def append_or_replace():
        return ChangeType.OTHER.value

    @classmethod
    def remove_variable(cls, asm_stmt):
        """
        从 asm_stmt 中移除汇编语言的 input 和 output 中的变量名，保留约束条件。
        先识别出输入输出列表的范围，然后在这些范围内移除变量名。
        例如：
        - [result] "=r" (sum) -> [result] "=r" ()
        - [count] "r" (i) -> [count] "r" ()
        - "=m" (sum) -> "=m" ()
        - "r" (i) -> "r" ()
        - [name] (variable) -> [name] ()  # 无约束条件的情况
        Args:
            asm_stmt: 内联汇编语句字符串
        Returns:
            移除变量名后的汇编语句
        """
        # 内联汇编的格式：
        # asm (...) (
        #     "汇编代码"
        #     : [output_name] "constraint" (variable)  // 输出列表
        #     : [input_name] "constraint" (variable)    // 输入列表
        #     : "clobbered registers"                   // 被修改的寄存器列表
        # );

        if asm_stmt is None or len(asm_stmt) == 0 or ":" not in asm_stmt:
            return asm_stmt

        # 第一步 找到所有冒号的位置（冒号用于分隔不同的列表）
        colon_positions = []
        in_string = False
        escape_next = False
        
        for i, char in enumerate(asm_stmt):
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if char == ':' and not in_string:
                colon_positions.append(i)

        if len(colon_positions) == 0:
            # 没有冒号，说明没有输入输出列表，直接返回
            return asm_stmt

        # 确定需要处理的区域
        # 第一个冒号之后是输出列表
        # 第二个冒号之后是输入列表
        # 第三个冒号之后是 clobbered 列表（不需要处理）
        # 从后往前处理，避免索引位置变化的问题
        result = asm_stmt
        processed_ranges = []
        
        # 处理输出列表和输入列表（前两个冒号之后的内容）
        for i in range(min(2, len(colon_positions))):
            colon_pos = colon_positions[i]
            # 找到这个列表的结束位置（下一个冒号或字符串结尾）
            if i + 1 < len(colon_positions):
                list_end = colon_positions[i + 1]
            else:
                list_end = len(asm_stmt)
            
            # 提取这个列表的内容（包含冒号）
            list_content = result[colon_pos:list_end]
            
            # 在这个列表内容中移除变量名
            # 匹配模式：
            # 1. [name] "constraint" (variable) - 带名称标签和约束条件
            # 2. "constraint" (variable) - 只有约束条件
            # 3. [name] (variable) - 只有名称标签（无约束条件，较少见）
            
            # 匹配带名称标签和约束条件: [name] "constraint" (variable)
            pattern1 = re.compile(
                r'(\[[^\]]+\]\s*"[^"]*"\s*)\([^)]+\)',
                re.MULTILINE | re.DOTALL
            )
            
            # 匹配只有约束条件: "constraint" (variable)
            pattern2 = re.compile(
                r'("[^"]*"\s*)\([^)]+\)',
                re.MULTILINE | re.DOTALL
            )
            
            # 匹配只有名称标签: [name] (variable)
            pattern3 = re.compile(
                r'(\[[^\]]+\]\s*)\([^)]+\)',
                re.MULTILINE | re.DOTALL
            )
            
            # 按顺序处理，避免重复匹配
            processed_content = pattern1.sub(r'\1()', list_content)
            processed_content = pattern2.sub(r'\1()', processed_content)
            processed_content = pattern3.sub(r'\1()', processed_content)
            
            # 记录需要替换的范围
            processed_ranges.append((colon_pos, list_end, processed_content))
        
        # 从后往前替换，避免索引位置变化
        for colon_pos, list_end, processed_content in reversed(processed_ranges):
            result = result[:colon_pos] + processed_content + result[list_end:]

        return result
