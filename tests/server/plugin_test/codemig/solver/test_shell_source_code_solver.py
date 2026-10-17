import os
import unittest
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong
from plugin.codemig.main.source_file import SourceFile
from plugin.codemig.solver.shell_source_code_solver import ShellSourceCodeSolver


class MyTestCase(unittest.TestCase):
    """在执行具体的测试方法前，先被调用"""

    def setUp(self):
        self.solver = ShellSourceCodeSolver()
        self.test_dir = os.path.join(os.path.dirname(__file__), 'test_files', 'test_shell_files')
        pass

    """会在测试代码执行完后执行，相当于做测试后的扫尾工作"""

    def tearDown(self):
        pass

    def test_matches_file(self):
        """测试文件后缀匹配逻辑"""
        # 应该匹配的文件
        self.assertTrue(self.solver.matches_file("shell.sh"))
        self.assertTrue(self.solver.matches_file("run_python.sh"))

        # 不应该匹配的文件
        self.assertFalse(self.solver.matches_file("blank_file.py"))
        self.assertFalse(self.solver.matches_file("README.txt"))
        self.assertFalse(self.solver.matches_file("shell.s"))

    def test_empty_file(self):
        """测试空文件处理"""
        test_file = SourceFile(os.path.join(self.test_dir, 'empty_file.sh'))
        results, _ = self.solver.solve(test_file)
        self.assertEqual(len(results), 0)

    def test_append_or_replace(self):
        """测试append_or_replace函数"""
        value = self.solver.append_or_replace()
        self.assertEqual(value, 2)

    def test_arch_detection(self):
        """测试结果检测"""
        test_file = SourceFile(os.path.join(self.test_dir, 'arm_x86.sh'))
        results, _ = self.solver.solve(test_file)

        start_line, end_line, suggestion, code_too_long, code = results[0]
        self.assertEqual(start_line, 31)
        self.assertEqual(end_line, 31)
        self.assertIn("检测到非riscv架构，建议检查", suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code, 'amd64|arm64|arm)')

        # TODO: 修复这部分的单元测试
        """
        start_line, end_line, suggestion = results[1]
        self.assertEqual(start_line, 46)
        self.assertEqual(end_line, 46)
        self.assertIn('检测到非riscv架构，建议检查', suggestion)

        start_line, end_line, suggestion = results[2]
        self.assertEqual(start_line, 47)
        self.assertEqual(end_line, 47)
        self.assertIn('检测到非riscv架构，建议检查', suggestion)

        start_line, end_line, suggestion = results[3]
        self.assertEqual(start_line, 50)
        self.assertEqual(end_line, 50)
        self.assertIn('检测到非riscv架构，建议检查', suggestion)

        start_line, end_line, suggestion = results[4]
        self.assertEqual(start_line, 53)
        self.assertEqual(end_line, 53)
        self.assertIn('检测到非riscv架构，建议检查', suggestion)

        start_line, end_line, suggestion = results[5]
        self.assertEqual(start_line, 54)
        self.assertEqual(end_line, 54)
        self.assertIn('检测到非riscv架构，建议检查', suggestion)

        start_line, end_line, suggestion = results[6]
        self.assertEqual(start_line, 57)
        self.assertEqual(end_line, 57)
        self.assertIn('检测到非riscv架构，建议检查', suggestion)

        start_line, end_line, suggestion = results[7]
        self.assertEqual(start_line, 58)
        self.assertEqual(end_line, 58)
        self.assertIn('检测到非riscv架构，建议检查', suggestion)

        start_line, end_line, suggestion = results[8]
        self.assertEqual(start_line, 63)
        self.assertEqual(end_line, 63)
        self.assertIn('检测到非riscv架构，建议检查', suggestion)

        start_line, end_line, suggestion = results[9]
        self.assertEqual(start_line, 66)
        self.assertEqual(end_line, 66)
        self.assertIn('检测到非riscv架构，建议检查', suggestion)

        start_line, end_line, suggestion = results[10]
        self.assertEqual(start_line, 67)
        self.assertEqual(end_line, 67)
        self.assertIn('检测到非riscv架构，建议检查', suggestion)

        start_line, end_line, suggestion = results[11]
        self.assertEqual(start_line, 70)
        self.assertEqual(end_line, 70)
        self.assertIn('检测到非riscv架构，建议检查', suggestion)

        start_line, end_line, suggestion = results[12]
        self.assertEqual(start_line, 71)
        self.assertEqual(end_line, 71)
        self.assertIn('检测到非riscv架构，建议检查', suggestion)

        start_line, end_line, suggestion = results[13]
        self.assertEqual(start_line, 72)
        self.assertEqual(end_line, 72)
        self.assertIn('检测到非riscv架构，建议检查', suggestion)
        """


if __name__ == '__main__':
    unittest.main()
