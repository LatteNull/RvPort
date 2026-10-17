import unittest
import os
from plugin.codemig.solver.build_meson_solver import BuildMesonSolver
from plugin.codemig.main.source_file import SourceFile


class MyTestCase(unittest.TestCase):
    """在执行具体的测试方法前，先被调用"""

    def setUp(self):
        self.solver = BuildMesonSolver()
        self.test_dir = os.path.join(os.path.dirname(__file__), 'test_files','test_meson_files')
        pass

    """会在测试代码执行完后执行，相当于做测试后的扫尾工作"""

    def tearDown(self):
        pass

    def test_matches_file(self):
        """测试文件后缀匹配逻辑"""
        # 应该匹配的文件
        self.assertTrue(self.solver.matches_file("meson.build"))
        self.assertTrue(self.solver.matches_file("meson_options.txt"))

        # 不应该匹配的文件
        self.assertFalse(self.solver.matches_file("blank_file.py"))
        self.assertFalse(self.solver.matches_file("README.txt"))

    def test_empty_file(self):
        """测试空文件处理"""
        test_file = SourceFile(os.path.join(self.test_dir, 'blank_file.py'))
        results, _ = self.solver.solve(test_file)
        self.assertEqual(len(results), 0)

    def test_append_or_replace(self):
        """测试append_or_replace函数"""
        value = self.solver.append_or_replace()
        self.assertEqual(value, 2)


    def test_arch_detection(self):
        """测试结果检测"""
        test_file = SourceFile(os.path.join(self.test_dir, 'meson.build'))
        results,_ = self.solver.solve(test_file)

        start_line, end_line, suggestion, _, _ = results[0]
        self.assertEqual(start_line, 66)
        self.assertEqual(end_line, 66)
        self.assertIn("检测到非RISC架构，需要进一步检查", suggestion)

        start_line, end_line, suggestion, _, _ = results[1]
        self.assertEqual(start_line, 67)
        self.assertEqual(end_line, 67)
        self.assertIn("检测到非RISC架构，需要进一步检查", suggestion)

        start_line, end_line, suggestion, _, _ = results[2]
        self.assertEqual(start_line, 76)
        self.assertEqual(end_line, 84)
        self.assertIn("架构分支缺少RISC-V支持！需要添加类似分支：arch_subdir = 'riscv'", suggestion)

if __name__ == '__main__':
    unittest.main()
