import subprocess
import unittest
import os
import tempfile
from unittest.mock import patch
from plugin.codemig.solver.software_solver import SoftwareSolver, get_file_architecture,\
    is_architecture_supported, analyze_library
from plugin.codemig.main.source_file import SourceFile

class MyTestCase(unittest.TestCase):

    """在执行具体的测试方法前，先被调用"""
    def setUp(self):
        self.solver = SoftwareSolver()
        self.test_dir = os.path.join(os.path.dirname(__file__), 'test_software')
        pass

    """会在测试代码执行完后执行，相当于做测试后的扫尾工作"""
    def tearDown(self):
        pass

    def test_matches_file(self):
        """测试文件类型识别"""
        self.assertTrue(self.solver.matches_file("Test.so"))
        self.assertTrue(self.solver.matches_file("/path/to/SomeClass.dll"))
        self.assertFalse(self.solver.matches_file("script.java"))
        self.assertFalse(self.solver.matches_file("README"))

    def test_append_or_replace(self):
        """测试append_or_replace函数"""
        value = self.solver.append_or_replace()
        self.assertEqual(value, 2)



    @patch('subprocess.run')
    def test_get_file_architecture(self, mock_run):
        """测试文件架构检测"""
        test_cases = [
            ('ELF 64-bit, x86-64', 'x86_64'),
            ('ELF 64-bit, aarch64', 'arm64'),
            ('ELF 64-bit, RISCV64', 'riscv64'),
            ('ELF 64-bit, riscv64', 'riscv64'),
            ('ELF 32-bit, ARM', 'arm'),
            ('ELF 32-bit, Intel 80386', 'x86'),
            ('Mach-O 64-bit, x86_64', 'x86_64'),
            ('Mach-O 64-bit, arm64', 'arm64'),
            ('PE32+ executable', 'x86_64'),
            ('PE32 executable', 'x86'),
            ('Invalid format', 'unknown'),
            ('', 'unknown')  # 模拟命令执行失败
        ]

        for output, expected in test_cases:
            with self.subTest(output=output):
                mock_run.return_value.stdout = output
                result = get_file_architecture('test.so')
                self.assertEqual(result, expected)

    def test_is_architecture_supported(self):
        """测试架构支持判断"""
        test_cases = [
            ('riscv64', True),
            ('RISCV64', True),  # 大小写不敏感
            ('x86_64', False),
            ('arm64', False),
            ('unknown', False)
        ]

        for arch, expected in test_cases:
            with self.subTest(arch=arch):
                result = is_architecture_supported(arch)
                self.assertEqual(result, expected)

    def test_analyze_library(self):
        """测试库文件分析"""
        test_cases = [
            ('riscv64', []),  # 支持架构应返回空列表
            ('x86_64', [['x86_64', None]]),
            ('arm64', [['arm64', None]]),
            ('unknown', [['unknown', None]])  # 错误情况处理
        ]
        for arch, expected in test_cases:
            with self.subTest(arch=arch):
                with patch('plugin.codemig.solver.software_solver.get_file_architecture', return_value=arch):
                    results = []
                    analyze_library('dummy.so', results)
                    self.assertEqual(results, expected)

    @patch('subprocess.run')
    def test_full_scan_process(self, mock_run):
        """测试完整扫描流程"""
        # 配置模拟数据
        mock_run.return_value.stdout = 'ELF 64-bit, x86-64'
        test_file = SourceFile(os.path.join(self.test_dir, 'x86.so'))
        # 执行扫描
        results,found = SoftwareSolver.solve(test_file)
        # 验证结果
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], 'x86_64')
        self.assertIsNone(results[0][1])  # 建议信息为None

    @patch('subprocess.run')
    def test_error_handling(self, mock_run):
        """测试错误处理"""
        mock_run.side_effect = OSError('Mocked error')

        results = []
        analyze_library('invalid.so', results)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], 'error')


if __name__ == '__main__':
    unittest.main()
