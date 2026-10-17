"""
CythonSourceCodeSolver 测试用例

测试覆盖：
1. 文件匹配规则（.pyx文件）
2. ctypes动态加载检测
3. ctypes导入检测
4. 注释和空行处理
5. 多种ctypes使用场景
6. 边界情况处理
"""

import os
import tempfile
import unittest
from plugin.codemig.solver.cython_source_code_solver import CythonSourceCodeSolver
from plugin.codemig.main.source_file import SourceFile
from plugin.codemig.codemig_common.migration_class import MigrationClass
from plugin.codemig.codemig_common.codemig_common_utils import ChangeType, CodeTooLong

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__)))
TEST_FILE_PATH = os.path.join(tempfile.gettempdir(), 'test_cython_files')


class TestCythonSourceCodeSolver(unittest.TestCase):
    """CythonSourceCodeSolver 测试类"""

    def setUp(self):
        """测试前准备"""
        self.solver = CythonSourceCodeSolver()

    # ==================== 基础方法测试 ====================

    def test_matches_file_pyx(self):
        """测试匹配.pyx文件"""
        self.assertTrue(CythonSourceCodeSolver.matches_file("example.pyx"))
        self.assertTrue(CythonSourceCodeSolver.matches_file("lib.pyx"))
        self.assertTrue(CythonSourceCodeSolver.matches_file("src/module.pyx"))

    def test_matches_file_not_pyx(self):
        """测试不匹配非.pyx文件"""
        self.assertFalse(CythonSourceCodeSolver.matches_file("test.py"))
        self.assertFalse(CythonSourceCodeSolver.matches_file("test.c"))
        self.assertFalse(CythonSourceCodeSolver.matches_file("test.h"))
        self.assertFalse(CythonSourceCodeSolver.matches_file("test.cpp"))
        self.assertFalse(CythonSourceCodeSolver.matches_file("test.rs"))

    def test_append_or_replace(self):
        """测试 append_or_replace 方法"""
        value = CythonSourceCodeSolver.append_or_replace()
        self.assertEqual(value, ChangeType.OTHER.value)

    def test_migration_class(self):
        """测试 migration_class 方法"""
        value = CythonSourceCodeSolver.migration_class()
        self.assertEqual(value, MigrationClass.TEXT)

    # ==================== find_pattern 核心逻辑测试 ====================

    def test_find_pattern_ctypes_cdll(self):
        """测试ctypes.CDLL检测"""
        lines = [
            "import ctypes\n",
            "lib = ctypes.CDLL('libexample.so')\n",
        ]
        results, _ = CythonSourceCodeSolver.find_pattern(
            lines, CythonSourceCodeSolver.compiled_patterns, CythonSourceCodeSolver.migration_advice)
        self.assertGreater(len(results), 0)
        self.assertIn("ctypes.CDLL", results[0][2])
        self.assertIn("RISC-V", results[0][2])

    def test_find_pattern_ctypes_cdll_loadlibrary(self):
        """测试ctypes.cdll.LoadLibrary检测"""
        lines = [
            "import ctypes\n",
            "lib = ctypes.cdll.LoadLibrary('libexample.so')\n",
        ]
        results, _ = CythonSourceCodeSolver.find_pattern(
            lines, CythonSourceCodeSolver.compiled_patterns, CythonSourceCodeSolver.migration_advice)
        self.assertGreater(len(results), 0)
        self.assertIn("cdll.LoadLibrary", results[0][2])

    def test_find_pattern_cdll_loadlibrary_without_ctypes(self):
        """测试cdll.LoadLibrary（不带ctypes前缀）检测"""
        lines = [
            "from ctypes import cdll\n",
            "lib = cdll.LoadLibrary('libexample.so')\n",
        ]
        results, _ = CythonSourceCodeSolver.find_pattern(
            lines, CythonSourceCodeSolver.compiled_patterns, CythonSourceCodeSolver.migration_advice)
        # 第一行会匹配ctypes_import，第二行会匹配ctypes_dynamic_loading
        self.assertGreater(len(results), 0)
        # 至少有一个结果提到ctypes
        self.assertTrue(any("ctypes" in r[2] for r in results))

    def test_find_pattern_cffi_dlopen(self):
        """测试cffi.FFI().dlopen检测"""
        lines = [
            "import cffi\n",
            "lib = cffi.FFI().dlopen('libexample.so')\n",
        ]
        results, _ = CythonSourceCodeSolver.find_pattern(
            lines, CythonSourceCodeSolver.compiled_patterns, CythonSourceCodeSolver.migration_advice)
        self.assertGreater(len(results), 0)
        self.assertIn("dlopen", results[0][2])

    def test_find_pattern_ctypes_import_dll(self):
        """测试from ctypes import CDLL检测"""
        lines = [
            "from ctypes import CDLL\n",
            "lib = CDLL('libexample.so')\n",
        ]
        results, _ = CythonSourceCodeSolver.find_pattern(
            lines, CythonSourceCodeSolver.compiled_patterns, CythonSourceCodeSolver.migration_advice)
        self.assertGreater(len(results), 0)
        self.assertIn("ctypes", results[0][2])

    def test_find_pattern_ctypes_import_windll(self):
        """测试from ctypes import WinDLL检测"""
        lines = [
            "from ctypes import WinDLL\n",
            "lib = WinDLL('user32.dll')\n",
        ]
        results, _ = CythonSourceCodeSolver.find_pattern(
            lines, CythonSourceCodeSolver.compiled_patterns, CythonSourceCodeSolver.migration_advice)
        self.assertGreater(len(results), 0)
        self.assertIn("ctypes", results[0][2])

    def test_find_pattern_ctypes_import_oledll(self):
        """测试from ctypes import OleDLL检测"""
        lines = [
            "from ctypes import OleDLL\n",
            "lib = OleDLL('ole32.dll')\n",
        ]
        results, _ = CythonSourceCodeSolver.find_pattern(
            lines, CythonSourceCodeSolver.compiled_patterns, CythonSourceCodeSolver.migration_advice)
        self.assertGreater(len(results), 0)
        self.assertIn("ctypes", results[0][2])

    def test_find_pattern_no_match(self):
        """测试没有匹配的情况"""
        lines = [
            "def add(a, b):\n",
            "    return a + b\n",
        ]
        results, _ = CythonSourceCodeSolver.find_pattern(
            lines, CythonSourceCodeSolver.compiled_patterns, CythonSourceCodeSolver.migration_advice)
        self.assertEqual(len(results), 0)

    def test_find_pattern_empty_lines(self):
        """测试空行处理"""
        lines = [
            "\n",
            "\n",
            "\n",
        ]
        results, _ = CythonSourceCodeSolver.find_pattern(
            lines, CythonSourceCodeSolver.compiled_patterns, CythonSourceCodeSolver.migration_advice)
        self.assertEqual(len(results), 0)

    def test_find_pattern_comments(self):
        """测试注释行处理"""
        lines = [
            "# import ctypes\n",
            "# lib = ctypes.CDLL('libexample.so')\n",
            "# from ctypes import CDLL\n",
        ]
        results, _ = CythonSourceCodeSolver.find_pattern(
            lines, CythonSourceCodeSolver.compiled_patterns, CythonSourceCodeSolver.migration_advice)
        self.assertEqual(len(results), 0)

    def test_find_pattern_mixed_content(self):
        """测试混合内容"""
        lines = [
            "# This is a comment\n",
            "def func():\n",
            "    pass\n",
            "\n",
            "import ctypes\n",
            "lib = ctypes.CDLL('lib.so')\n",
            "\n",
            "# Another comment\n",
            "result = lib.some_func()\n",
        ]
        results, _ = CythonSourceCodeSolver.find_pattern(
            lines, CythonSourceCodeSolver.compiled_patterns, CythonSourceCodeSolver.migration_advice)
        self.assertGreater(len(results), 0)
        # 应该只匹配到ctypes.CDLL那一行
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], 6)  # 第6行

    def test_find_pattern_multiple_matches(self):
        """测试多个匹配项"""
        lines = [
            "import ctypes\n",
            "lib1 = ctypes.CDLL('lib1.so')\n",
            "lib2 = ctypes.cdll.LoadLibrary('lib2.so')\n",
        ]
        results, _ = CythonSourceCodeSolver.find_pattern(
            lines, CythonSourceCodeSolver.compiled_patterns, CythonSourceCodeSolver.migration_advice)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0][0], 2)  # 第2行
        self.assertEqual(results[1][0], 3)  # 第3行

    def test_find_pattern_result_format(self):
        """测试结果格式验证"""
        lines = [
            "lib = ctypes.CDLL('lib.so')\n",
        ]
        results, _ = CythonSourceCodeSolver.find_pattern(
            lines, CythonSourceCodeSolver.compiled_patterns, CythonSourceCodeSolver.migration_advice)
        if results:
            result = results[0]
            self.assertEqual(len(result), 5)
            self.assertIsInstance(result[0], int)  # start line
            self.assertIsInstance(result[1], int)  # end line
            self.assertIsInstance(result[2], str)  # message
            self.assertIsInstance(result[3], CodeTooLong)  # code_too_long
            self.assertIsInstance(result[4], str)  # code

    def test_find_pattern_case_insensitive_dll(self):
        """测试大小写不敏感的dll匹配"""
        # CDLL, Cdll, cDll, cdll都应该匹配
        test_cases = [
            "from ctypes import CDLL\n",
            "from ctypes import Cdll\n",
            "from ctypes import cDll\n",
            "from ctypes import cdll\n",
        ]
        for line in test_cases:
            lines = [line]
            results, _ = CythonSourceCodeSolver.find_pattern(
                lines, CythonSourceCodeSolver.compiled_patterns, CythonSourceCodeSolver.migration_advice)
            self.assertGreater(len(results), 0, f"Failed to match: {line}")

    def test_find_pattern_whitespace_handling(self):
        """测试空白字符处理"""
        lines = [
            "  lib = ctypes.CDLL('lib.so')  \n",
            "\tlib2 = ctypes.cdll.LoadLibrary('lib2.so')\t\n",
        ]
        results, _ = CythonSourceCodeSolver.find_pattern(
            lines, CythonSourceCodeSolver.compiled_patterns, CythonSourceCodeSolver.migration_advice)
        self.assertGreater(len(results), 0)

    def test_find_pattern_inline_comment(self):
        """测试行内注释"""
        lines = [
            "lib = ctypes.CDLL('lib.so')  # Load the library\n",
        ]
        results, _ = CythonSourceCodeSolver.find_pattern(
            lines, CythonSourceCodeSolver.compiled_patterns, CythonSourceCodeSolver.migration_advice)
        self.assertGreater(len(results), 0)
        # 应该匹配到ctypes.CDLL
        self.assertIn("ctypes.CDLL", results[0][2])

    # ==================== solve方法测试（集成测试）====================

    def test_solve_with_pyx_file(self):
        """测试使用.pyx文件的solve方法"""
        # 创建一个临时的.pyx测试文件
        test_content = """# Cython file with ctypes usage
import ctypes

def load_library():
    lib = ctypes.CDLL('libexample.so')
    return lib

def another_function():
    from ctypes import cdll
    lib2 = cdll.LoadLibrary('lib2.so')
    return lib2
"""
        # 写入临时文件
        test_file = os.path.join(TEST_FILE_PATH, "test_ctypes.pyx")
        os.makedirs(TEST_FILE_PATH, exist_ok=True)
        try:
            with open(test_file, 'w') as f:
                f.write(test_content)
            
            source_file = SourceFile(test_file)
            results, _ = CythonSourceCodeSolver.solve(source_file)
            
            # 应该检测到两个ctypes使用
            self.assertGreater(len(results), 0)
            
        finally:
            # 清理临时文件
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_solve_empty_pyx_file(self):
        """测试空的.pyx文件"""
        test_content = ""
        test_file = os.path.join(TEST_FILE_PATH, "test_empty.pyx")
        os.makedirs(TEST_FILE_PATH, exist_ok=True)
        try:
            with open(test_file, 'w') as f:
                f.write(test_content)
            
            source_file = SourceFile(test_file)
            results, _ = CythonSourceCodeSolver.solve(source_file)
            
            # 空文件不应该有结果
            self.assertEqual(len(results), 0)
            
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_solve_pyx_without_ctypes(self):
        """测试没有ctypes使用的.pyx文件"""
        test_content = """# Pure Cython file without ctypes
def add(int a, int b):
    return a + b

def multiply(int a, int b):
    return a * b
"""
        test_file = os.path.join(TEST_FILE_PATH, "test_pure_cython.pyx")
        os.makedirs(TEST_FILE_PATH, exist_ok=True)
        try:
            with open(test_file, 'w') as f:
                f.write(test_content)
            
            source_file = SourceFile(test_file)
            results, _ = CythonSourceCodeSolver.solve(source_file)
            
            # 没有ctypes使用，不应该有结果
            self.assertEqual(len(results), 0)
            
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    # ==================== 边界情况测试 ====================

    def test_find_pattern_string_containing_dll_keyword(self):
        """测试字符串中包含'dll'关键字但不实际使用ctypes"""
        lines = [
            "filename = 'mydll.txt'\n",
            "comment = 'This is not a dll reference'\n",
        ]
        results, _ = CythonSourceCodeSolver.find_pattern(
            lines, CythonSourceCodeSolver.compiled_patterns, CythonSourceCodeSolver.migration_advice)
        # 这些不应该匹配
        self.assertEqual(len(results), 0)

    def test_find_pattern_variable_named_dll(self):
        """测试变量名为dll但不使用ctypes"""
        lines = [
            "dll = 'some_string'\n",
            "my_dll_loader = None\n",
        ]
        results, _ = CythonSourceCodeSolver.find_pattern(
            lines, CythonSourceCodeSolver.compiled_patterns, CythonSourceCodeSolver.migration_advice)
        # 这些不应该匹配
        self.assertEqual(len(results), 0)

    def test_find_pattern_partial_match_avoidance(self):
        """测试避免部分匹配"""
        lines = [
            "# notdll should not match\n",
            "not_ctypes = True\n",
        ]
        results, _ = CythonSourceCodeSolver.find_pattern(
            lines, CythonSourceCodeSolver.compiled_patterns, CythonSourceCodeSolver.migration_advice)
        self.assertEqual(len(results), 0)

    def test_find_pattern_complex_expression(self):
        """测试复杂表达式"""
        lines = [
            "lib = getattr(ctypes, 'CDLL')('lib.so')\n",
            "loader = lambda: ctypes.cdll.LoadLibrary('lib.so')\n",
        ]
        results, _ = CythonSourceCodeSolver.find_pattern(
            lines, CythonSourceCodeSolver.compiled_patterns, CythonSourceCodeSolver.migration_advice)
        # 这些应该匹配
        self.assertGreater(len(results), 0)


if __name__ == '__main__':
    unittest.main()
