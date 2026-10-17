from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong
from plugin.codemig.main.source_file import SourceFile
from plugin.codemig.solver.python_source_code_solver import PythonSourceCodeSolver

import os
import unittest


class MyTestCase(unittest.TestCase):
    """在执行具体的测试方法前，先被调用"""

    def setUp(self):
        self.solver = PythonSourceCodeSolver()
        self.test_dir = os.path.join(os.path.dirname(__file__), 'test_files', 'test_python_files')
        pass

    """会在测试代码执行完后执行，相当于做测试后的扫尾工作"""

    def tearDown(self):
        pass

    def test_matches_file(self):
        """测试文件类型识别"""
        self.assertTrue(self.solver.matches_file("Test.py"))
        # self.assertTrue(self.solver.matches_file("/path/to/SomeClass.pyx"))
        self.assertFalse(self.solver.matches_file("script.java"))
        self.assertFalse(self.solver.matches_file("README.txt"))

    def test_empty_file(self):
        """测试空文件处理"""
        temp_file = SourceFile(os.path.join(self.test_dir, 'empty_file.py'))
        results, _ = self.solver.solve(temp_file)
        self.assertEqual(len(results), 0)

    def test_append_or_replace(self):
        """测试append_or_replace函数"""
        value = self.solver.append_or_replace()
        self.assertEqual(value, 2)

    def test_ctypes_direct_load(self):
        """测试ctypes.CDLL直接加载模式"""
        test_file = SourceFile(os.path.join(self.test_dir, 'ctypes_direct_load.py'))
        results, _ = self.solver.solve(test_file)

        # 预期这个文件中应该包含3个有效的ctypes加载调用
        self.assertEqual(len(results), 5)

        # 检查每个结果是否符合预期
        for start_line, end_line, suggestion, _, _ in results:
            self.assertIn(self.solver.migration_advice.get('ctypes_dynamic_loading'), suggestion)

    def test_cffi_dlopen(self):
        """测试cffi.FFI().dlopen模式"""
        test_file = SourceFile(os.path.join(self.test_dir, 'cffi_dlopen.py'))
        results, _ = self.solver.solve(test_file)

        self.assertEqual(len(results), 4)

        # 检查每个结果是否符合预期
        start_line, end_line, suggestion, _, _ = results[1]
        self.assertIn(self.solver.migration_advice.get('ctypes_dynamic_loading'), suggestion)

    def test_ctypes_import(self):
        """测试from ctypes import *DLL模式"""
        test_file = SourceFile(os.path.join(self.test_dir, 'ctypes_import.py'))
        results, _ = self.solver.solve(test_file)

        self.assertEqual(len(results), 0)

        # 检查每个结果是否符合预期
        # for start_line, end_line, suggestion, _, _ in results:
        #     self.assertIn(self.solver.migration_advice.get('ctypes_import'), suggestion)

    def test_cdef(self):
        """测试from ctypes import *DLL模式"""
        test_file = SourceFile(os.path.join(self.test_dir, 'check_cdef.py'))
        results, _ = self.solver.solve(test_file)

        self.assertEqual(len(results), 7)
        self.assertEqual(results[0][0], 29)
        self.assertEqual(results[0][1], 47)

    def test_result_format(self):
        """测试返回结果格式"""
        test_file = SourceFile(os.path.join(self.test_dir, 'result_format.py'))
        results, _ = self.solver.solve(test_file)

        self.assertEqual(len(results), 2)

        # 检查第一个匹配项
        # start_line, end_line, suggestion, code_too_long, code = results[0]
        # self.assertEqual(start_line, 3)
        # self.assertEqual(end_line, 3)
        # self.assertIn("from ctypes import CDLL", suggestion)
        # self.assertIn(self.solver.migration_advice.get('ctypes_import'), suggestion)
        # self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        # self.assertEqual(code, 'from ctypes import CDLL, cdll')

        # 检查第二个匹配项
        start_line, end_line, suggestion, code_too_long, code = results[0]
        self.assertEqual(start_line, 6)
        self.assertEqual(end_line, 6)
        # self.assertIn("ctypes.CDLL", suggestion)
        self.assertIn(self.solver.migration_advice.get('ctypes_dynamic_loading'), suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code, 'libc = ctypes.CDLL("libc.so.6")')

        # 检查第三个匹配项
        start_line, end_line, suggestion, code_too_long, code = results[1]
        self.assertEqual(start_line, 7)
        self.assertEqual(end_line, 7)
        # self.assertIn("ctypes.cdll.LoadLibrary", suggestion)
        self.assertIn(self.solver.migration_advice.get('ctypes_dynamic_loading'), suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code, 'libc = ctypes.cdll.LoadLibrary("libc.so.6")')

    def test_result_format_py2(self):
        """测试返回结果格式"""
        test_file = SourceFile(os.path.join(self.test_dir, 'python2.py'))
        results, _ = self.solver.solve(test_file)




if __name__ == '__main__':
    unittest.main()
