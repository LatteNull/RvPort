from plugin.codemig.codemig_common.codemig_common_utils import ChangeType
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong
from plugin.codemig.codemig_common.codemig_common_utils import NUMBER_LINES_TOO_LONG
from plugin.codemig.solver.asm_arch import AsmArch
from plugin.codemig.main.source_file import SourceFile
from plugin.codemig.solver.inline_asm_solver import *

import os
import unittest

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), ))
TEST_FILE_PATH = os.path.join(MODULE_PATH, 'test_files', 'inline_asm_solver')


def get_three_items(data):
    res, _ = data
    return [sub_array[:3] for sub_array in res]


class TestIncodeAsmSolver(unittest.TestCase):
    test_x86 = SourceFile(os.path.join(TEST_FILE_PATH, "inline_asm_x86_64.c"))
    test_arm = SourceFile(os.path.join(TEST_FILE_PATH, "inline_asm_aarch64.c"))
    test_riscv = SourceFile(os.path.join(TEST_FILE_PATH, "inline_asm_riscv.c"))
    test_unknown = SourceFile(os.path.join(TEST_FILE_PATH, "inline_asm_unknown.c"))
    test_in_string = SourceFile(os.path.join(TEST_FILE_PATH, "inline_asm_in_string.c"))
    test_x86_2 = SourceFile(os.path.join(TEST_FILE_PATH, "inline_asm_x86_64_2.c"))
    test_wrong = SourceFile(os.path.join(TEST_FILE_PATH, "inline_asm_wrong.c"))
    test_perf = SourceFile(os.path.join(TEST_FILE_PATH, "inline_asm_perf.c"))

    def test_get_line_offsets(self):
        self.assertEqual(get_line_offsets(self.test_in_string.get_code()), [0, 19, 20, 33, 57, 81, 106, 107, 153, 154, 191, 205])

    def test_get_line_number(self):
        self.assertEqual(get_line_number(0, 1, [0, 19, 20, 33, 57, 81, 106, 107, 153, 154, 191, 205]), (1, 1))
        self.assertEqual(get_line_number(25, 25, [0, 19, 20, 33, 57, 81, 106, 107, 153, 154, 191, 205]), (3, 3))
        self.assertEqual(get_line_number(25, 155, [0, 19, 20, 33, 57, 81, 106, 107, 153, 154, 191, 205]), (3, 10))
        self.assertEqual(get_line_number(25, 259, [0, 19, 20, 33, 57, 81, 106, 107, 153, 154, 191, 205]), (3, 12))
        self.assertEqual(get_line_number(259, 288, [0, 19, 20, 33, 57, 81, 106, 107, 153, 154, 191, 205]), (12, 12))

    def test_find_end_pos(self):
        code = self.test_in_string.get_code()
        self.assertEqual(find_end_pos(111, code), 150)
        self.assertEqual(find_end_pos(250, code), None)

    def test_matches_file(self):
        self.assertTrue(InlineAsmSolver.matches_file("test.h"))
        self.assertTrue(InlineAsmSolver.matches_file("test.c"))
        self.assertTrue(InlineAsmSolver.matches_file("test.cc"))
        self.assertTrue(InlineAsmSolver.matches_file("test.cpp"))

    def test_find_asm_for_file(self):
        self.assertEqual(InlineAsmSolver.find_asm_for_file(self.test_in_string.remove_c_comments()),
                         [(8, 8, 'asm("some text with a quote: \\" inside")')])
        self.assertEqual(InlineAsmSolver.find_asm_for_file(self.test_x86.remove_c_comments()),
                         [(7, 19, 'asm volatile (\n'
                                  '        "movl %[count], %%ecx\\n\\t"   \n'
                                  '        "xorl %%eax, %%eax\\n\\t"      \n'
                                  '        "xorl %%ebx, %%ebx\\n\\t"      \n'
                                  '        "loop_start:\\n\\t"\n'
                                  '        "addl %%ebx, %%eax\\n\\t"      \n'
                                  '        "incl %%ebx\\n\\t"             \n'
                                  '        "loop loop_start\\n\\t"        \n'
                                  '        "movl %%eax, %[result]\\n\\t"  \n'
                                  '        : [result] "=r" ()        \n'
                                  '        : [count] "r" ()            \n'
                                  '        : "eax", "ebx", "ecx"        \n'
                                  '    )')])

    def test_find_asm_for_file_wrong(self):
        self.assertEqual(InlineAsmSolver.find_asm_for_file(self.test_wrong.remove_c_comments()), [])

    def test_find_asm_for_file_perf(self):
        self.assertEqual(InlineAsmSolver.find_asm_for_file(self.test_perf.remove_c_comments()),
                         [(2, 2, 'asm volatile ("sync" : : : "memory")'),
                          (5, 5, 'asm volatile("bcr 15,0" ::: "memory")'),
                          (9, 9, 'asm volatile("synco" ::: "memory")'),
                          (11, 11, 'asm volatile("" ::: "memory")'),
                          (15, 15, 'asm volatile("" ::: "memory")'),
                          (18, 18, 'asm volatile("":::"memory")'),
                          (21, 21, 'asm volatile("mb" ::: "memory")'),
                          (24, 24, 'asm volatile ("mf" ::: "memory")'),
                          (40, 40, 'asm volatile("dmb ld" ::: "memory")'),
                          (53, 53, 'asm volatile("lock; addl $0,0(%%esp)" ::: "memory")'),
                          (61, 61, 'asm volatile("lfence":::"memory")')])

    def test_create_suggestion_for_arch(self):
        self.assertEqual(InlineAsmSolver.create_suggestion_for_arch(AsmArch.UNKNOWN),
                         '此处汇编与架构相关，请转换为适用于 RISC-V 架构的实现。')

    def test_create_suggestion(self):
        actual, _ = InlineAsmSolver.create_suggestion([(8, 8, 'asm("some text with a quote: \\" inside");')])
        expected = [[
            8, 8, '此处汇编与架构相关，请转换为适用于 RISC-V 架构的实现。',
            CodeTooLong.HAS_SOURCE_CODE,
            'asm("some text with a quote: \\" inside");'
        ]]
        self.assertEqual(actual, expected)

        actual2, _ = InlineAsmSolver.create_suggestion([
            (7, 19, 'asm volatile (\n'
                    '        "movl %[count], %%ecx\\n\\t"   \n'
                    '        "xorl %%eax, %%eax\\n\\t"      \n'
                    '        "xorl %%ebx, %%ebx\\n\\t"      \n'
                    '        "loop_start:\\n\\t"\n'
                    '        "addl %%ebx, %%eax\\n\\t"      \n'
                    '        "incl %%ebx\\n\\t"             \n'
                    '        "loop loop_start\\n\\t"        \n'
                    '        "movl %%eax, %[result]\\n\\t"  \n'
                    '        : [result] "=r" (sum)        \n'
                    '        : [count] "r" (i)            \n'
                    '        : "eax", "ebx", "ecx"        \n'
                    '    );')
        ])
        expected2 = [[
            7, 19, '此处汇编与架构相关，请转换为适用于 RISC-V 架构的实现。',
            CodeTooLong.HAS_SOURCE_CODE, 'asm volatile (\n'
                                         '        "movl %[count], %%ecx\\n\\t"   \n'
                                         '        "xorl %%eax, %%eax\\n\\t"      \n'
                                         '        "xorl %%ebx, %%ebx\\n\\t"      \n'
                                         '        "loop_start:\\n\\t"\n'
                                         '        "addl %%ebx, %%eax\\n\\t"      \n'
                                         '        "incl %%ebx\\n\\t"             \n'
                                         '        "loop loop_start\\n\\t"        \n'
                                         '        "movl %%eax, %[result]\\n\\t"  \n'
                                         '        : [result] "=r" (sum)        \n'
                                         '        : [count] "r" (i)            \n'
                                         '        : "eax", "ebx", "ecx"        \n'
                                         '    );'
        ]]
        self.assertEqual(actual2, expected2)

    def test_solve(self):
        actual1 = get_three_items(InlineAsmSolver.solve(self.test_x86))
        self.assertEqual(actual1, [[7, 19, '此处汇编与架构相关，请转换为适用于 RISC-V 架构的实现。']])
        actual2 = get_three_items(InlineAsmSolver.solve(self.test_arm))
        self.assertEqual(actual2, [[7, 20, '此处汇编与架构相关，请转换为适用于 RISC-V 架构的实现。']])
        actual3 = get_three_items(InlineAsmSolver.solve(self.test_riscv))
        self.assertEqual(actual3, [])
        actual4 = get_three_items(InlineAsmSolver.solve(self.test_unknown))
        self.assertEqual(actual4, [[8, 13, '此处汇编与架构相关，请转换为适用于 RISC-V 架构的实现。']])
        actual5 = get_three_items(InlineAsmSolver.solve(self.test_in_string))
        self.assertEqual(actual5, [[8, 8, '此处汇编与架构相关，请转换为适用于 RISC-V 架构的实现。']])
        actual6 = get_three_items(InlineAsmSolver.solve(self.test_x86_2))
        self.assertEqual(actual6, [[7, 19, '此处汇编与架构相关，请转换为适用于 RISC-V 架构的实现。']])

    def test_append_or_replace(self):
        self.assertEqual(InlineAsmSolver.append_or_replace(), ChangeType.OTHER.value)

    def test_extract_code(self):
        asm_stmt = "deadbeaf"
        code_too_long, code = InlineAsmSolver.extract_code(asm_stmt, 1, NUMBER_LINES_TOO_LONG)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code, "deadbeaf")

    def test_extract_code_too_long(self):
        asm_stmt = "deadbeaf"
        code_too_long, code = InlineAsmSolver.extract_code(asm_stmt, 1, NUMBER_LINES_TOO_LONG + 1)
        self.assertEqual(code_too_long, CodeTooLong.CODE_TOO_LONG)
        self.assertEqual(code, None)

    def test_remove_variable_basic(self):
        """测试基本的变量移除功能"""
        # 测试带名称标签和约束条件
        asm1 = 'asm ("mov %0, %1" : [result] "=r" (sum) : [count] "r" (i));'
        result1 = InlineAsmSolver.remove_variable(asm1)
        self.assertEqual(result1, 'asm ("mov %0, %1" : [result] "=r" () : [count] "r" ());')
        
        # 测试只有约束条件
        asm2 = 'asm ("add %0, %1" : "=r" (sum) : "r" (i));'
        result2 = InlineAsmSolver.remove_variable(asm2)
        self.assertEqual(result2, 'asm ("add %0, %1" : "=r" () : "r" ());')

    def test_remove_variable_multiple(self):
        """测试多个输入输出的情况"""
        asm = 'asm ("mov %0, %1" : "=r" (a), "=r" (b) : "r" (x), "r" (y));'
        result = InlineAsmSolver.remove_variable(asm)
        self.assertEqual(result, 'asm ("mov %0, %1" : "=r" (), "=r" () : "r" (), "r" ());')

    def test_remove_variable_with_clobbered(self):
        """测试包含 clobbered 列表的情况"""
        asm = 'asm ("mov %0, %1" : "=r" (sum) : "r" (i) : "memory");'
        result = InlineAsmSolver.remove_variable(asm)
        # clobbered 列表应该保持不变
        self.assertEqual(result, 'asm ("mov %0, %1" : "=r" () : "r" () : "memory");')

    def test_remove_variable_name_label_only(self):
        """测试只有名称标签，无约束条件的情况"""
        asm = 'asm ("mov %[out], %[in]" : [out] (sum) : [in] (i));'
        result = InlineAsmSolver.remove_variable(asm)
        self.assertEqual(result, 'asm ("mov %[out], %[in]" : [out] () : [in] ());')

    def test_remove_variable_no_output_input(self):
        """测试没有输入输出列表的情况"""
        asm = 'asm ("nop");'
        result = InlineAsmSolver.remove_variable(asm)
        self.assertEqual(result, 'asm ("nop");')

    def test_remove_variable_only_output(self):
        """测试只有输出列表的情况"""
        asm = 'asm ("mov %0, 1" : "=r" (result));'
        result = InlineAsmSolver.remove_variable(asm)
        self.assertEqual(result, 'asm ("mov %0, 1" : "=r" ());')

    def test_remove_variable_only_input(self):
        """测试只有输入列表的情况"""
        asm = 'asm ("mov r0, %0" : : "r" (value));'
        result = InlineAsmSolver.remove_variable(asm)
        self.assertEqual(result, 'asm ("mov r0, %0" : : "r" ());')

    def test_remove_variable_string_with_colon(self):
        """测试字符串中包含冒号的情况"""
        asm = 'asm ("mov %0, \\"test:value\\"" : "=r" (result));'
        result = InlineAsmSolver.remove_variable(asm)
        # 字符串中的冒号不应该被识别为列表分隔符
        self.assertEqual(result, 'asm ("mov %0, \\"test:value\\"" : "=r" ());')

    def test_remove_variable_complex_variable_names(self):
        """测试复杂变量名（包含运算符）的情况"""
        asm = 'asm ("add %0, %1" : "=r" (arr[i]) : "r" (ptr->value));'
        result = InlineAsmSolver.remove_variable(asm)
        self.assertEqual(result, 'asm ("add %0, %1" : "=r" () : "r" ());')

    def test_remove_variable_multiline(self):
        """测试多行内联汇编的情况"""
        asm = ('asm volatile (\n'
               '        "movl %[count], %%ecx\\n\\t"\n'
               '        : [result] "=r" (sum)\n'
               '        : [count] "r" (i)\n'
               '        : "eax", "ebx", "ecx"\n'
               '    );')
        result = InlineAsmSolver.remove_variable(asm)
        expected = ('asm volatile (\n'
                    '        "movl %[count], %%ecx\\n\\t"\n'
                    '        : [result] "=r" ()\n'
                    '        : [count] "r" ()\n'
                    '        : "eax", "ebx", "ecx"\n'
                    '    );')
        self.assertEqual(result, expected)

    def test_remove_variable_empty_parentheses(self):
        """测试已经是空括号的情况（应该保持不变）"""
        asm = 'asm ("nop" : "=r" () : "r" ());'
        result = InlineAsmSolver.remove_variable(asm)
        self.assertEqual(result, 'asm ("nop" : "=r" () : "r" ());')

    def test_remove_variable_escaped_quotes(self):
        """测试转义引号的情况"""
        asm = 'asm ("mov %0, \\"value\\"" : "=r" (result));'
        result = InlineAsmSolver.remove_variable(asm)
        self.assertEqual(result, 'asm ("mov %0, \\"value\\"" : "=r" ());')

    def test_remove_variable_mixed_formats(self):
        """测试混合格式（有些带名称标签，有些不带）"""
        asm = 'asm ("mov %0, %1" : [out1] "=r" (a), "=r" (b) : [in1] "r" (x), "r" (y));'
        result = InlineAsmSolver.remove_variable(asm)
        self.assertEqual(result, 'asm ("mov %0, %1" : [out1] "=r" (), "=r" () : [in1] "r" (), "r" ());')


if __name__ == "__main__":
    unittest.main()
