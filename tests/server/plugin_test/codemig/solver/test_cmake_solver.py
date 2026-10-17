import os
import pytest

from plugin.codemig.codemig_common.codemig_common_utils import ChangeType
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong
from plugin.codemig.main.source_file import SourceFile
from plugin.codemig.solver.cmake_solver import *

from plugin.codemig.solver.cmake_solver import CMakeSolver

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__)))
TEST_FILE_PATH = os.path.join(MODULE_PATH, 'test_files', 'cmake_solver')

ARC_TEST_CASES = [
    ("if (CMAKE_SYSTEM_PROCESSOR match x86)", True, "CMAKE_SYSTEM_PROCESSOR and x86"),
    ("if ARCH_ARM ", True, "only arm"),
    ("if x86 ", True, "only x86"),
    ("if x86_64 ", True, "only x86_64"),
    ("if ARCH_AARM ", False, "arm within some word"),
    ("if (CMAKE_SYSTEM_PROCESSOR match x86 AND CMAKE_HOST_SYSTEM_PROCESSOR )", True, "CMAKE_SYSTEM_PROCESSOR and CMAKE_HOST_SYSTEM_PROCESSOR"),
]

# 参数化测试用例
@pytest.mark.parametrize("input_str, expected, description", ARC_TEST_CASES)
def test_contains_architecture_condition(input_str, expected, description):
    """测试if语句括号封闭性"""
    result = contains_architecture_others(input_str)
    assert result == expected, f"{description}"

# 测试数据数组
BRACKET_TEST_CASES = [
    # (输入字符串, 期望结果, 测试描述)
    ("print(() )", (2, 2), "基本测试：括号在字符串外部应被正确计数"),
    ('print("( )")', (1, 1), "忽略字符串中的括号"),
    ('func("(") + (1 + 2)', (2, 2), "正确处理混合场景"),
    (r'print(\"(\")")', (2, 1), "正确忽略字符串中转义字符的括号"),
    ('', (0, 0), "空字符串应返回 (0, 0)"),
    ('if (ARC=x86 || ARC="(34" || (AEC==1 and adc==2))', (2, 2), "复杂条件表达式"),
    ('This is a line without parentheses', (0, 0), "无括号的字符串"),
    ('("outer(inner)")', (1, 1), "正确忽略字符串中嵌套括号"),
    ('(outer_func("inner_func(3)")) + (1 + (2))', (4, 4), "同时处理括号和嵌套"),
    (r'func_name(a=\"(\(test))\")', (2, 3), "混合场景中正确处理嵌套括号和转义符"),
    (r'This is a string with no parentheses but with \"escaped quotes\"', (0, 0), "处理无括号的字符串及转义符"),
    ('if(CMAKE_SYSTEM_PROCESSOR MATCHES "x86_64")', (1, 1), "CMake if语句测试"),
    ('if(CMAKE_SYSTEM_PROCESSOR MATCHES "x86_64" AND (CMAKE_BUILD_TYPE STREQUAL "Release"))', (2, 2), "嵌套CMake if语句"),
    ('target_compile_options(my_target PRIVATE "-DOPTION=value()")', (1, 1), "CMake字符串内的括号不计数"),
    ('if("some string with (parentheses)" STREQUAL "test")', (1, 1), "CMake字符串包含括号"),
    ('if((${VAR} STREQUAL "test") AND (NOT DISABLED))', (3, 3), "CMake复杂嵌套括号"),
]

# 参数化测试用例
@pytest.mark.parametrize("input_str, expected, description", BRACKET_TEST_CASES)
def test_count_brackets_outside_strings(input_str, expected, description):
    """测试if语句括号封闭性"""
    result = count_brackets_outside_strings(input_str)
    assert result == expected, f"{description}"

COMMENT_TEST_CASES = [
    ('fixxdgg','fixxdgg',"无注释" ),
    ('fixxdgg  #xge','fixxdgg',"有注释" ),
    ('fixxdgg  #xge #gege','fixxdgg',"双#注释" ),
    ("fixxdgg  '#xge' #gege","fixxdgg  '#xge'","双#注释" ),
]
# 参数化测试用例
@pytest.mark.parametrize("input_str, expected, description", COMMENT_TEST_CASES)
def test_remove_comments(input_str, expected, description):
    """测试if语句括号封闭性"""
    result = remove_comments(input_str)
    assert result == expected, f"{description}"
SUGGESTION='架构分支缺少RISC-V支持！需要添加类似分支;'
Except_one_if=[[1,3,SUGGESTION, CodeTooLong.HAS_SOURCE_CODE, 'if (CMAKE_SYSTEM_PROCESSOR MATCH A)\n  print(\'1\')\nendif()']]
Except_if_else=[[1,5,SUGGESTION, CodeTooLong.HAS_SOURCE_CODE, 'if (CMAKE_SYSTEM_PROCESSOR MATCH A)\n  print(\'1\')\nelse()\nprint(2)\nendif()']]
Except_multi_brackets=[[1,7, SUGGESTION,CodeTooLong.HAS_SOURCE_CODE, 'if (A AND C OR ( a+b) and\n    CMAKE_SYSTEM_PROCESSOR MATCH A)\n  print(\'1\')\nelseif (ACRH or (c))\n  (riscv)\n  print(2)\nendif()']]
Except_multi_level=[[18,19,SUGGESTION,CodeTooLong.HAS_SOURCE_CODE, '  if(x86):\n  endif()']]

IF_BLOCK_TEST_CASES = [
    # ('one_if.cmake', Except_one_if, '一个if块'),
    # ('if_else.cmake', Except_if_else, '一个if else块'),
    # ('if_elif.cmake', [], '一个if elif块'),
    # ('if_multiline.cmake', [], '条件语句跨行'),
    # ('multi_brackets.cmake', Except_multi_brackets, '多括号条件判断'),
    ('multi_level.cmake', Except_multi_level, '多层级if判断'),
]

@pytest.mark.parametrize("input_file, expected, description", IF_BLOCK_TEST_CASES)
def test_solver(input_file, expected, description):
    """测试if语句括号封闭性"""

    suggestion,exists = CMakeSolver.solve(SourceFile(os.path.join(TEST_FILE_PATH, input_file)))
    assert suggestion == expected, f"{description}"
