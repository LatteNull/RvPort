import unittest
import os
import tempfile
from plugin.codemig.main.dir_solver import DirSolver
from plugin.codemig.codemig_common.arch_pattern import ArchPattern


class MyTestCase(unittest.TestCase):
    """在执行具体的测试方法前，先被调用"""
    def setUp(self):
        self.solver = DirSolver()
        self.arch_pattern = ArchPattern()
        self.test_dir = os.path.join(os.path.dirname(__file__), 'test_dir')
        self.sub_dir = os.path.join(self.test_dir, "subdir")
        pass

    """会在测试代码执行完后执行，相当于做测试后的扫尾工作"""
    def tearDown(self):
        pass

    def test_arch_pattern(self):
        """测试架构类型文件识别"""
        # 支持的架构模式（根据arch_pattern.py更新）
        self.assertTrue(self.arch_pattern.is_arch_pattern("Test_amd64.go"))
        self.assertTrue(self.arch_pattern.is_arch_pattern("Test_arm64.go"))
        self.assertTrue(self.arch_pattern.is_arch_pattern("Test_arm.go"))
        self.assertTrue(self.arch_pattern.is_arch_pattern("Test_x86_64.go"))
        self.assertTrue(self.arch_pattern.is_arch_pattern("Test_x86.go"))
        self.assertTrue(self.arch_pattern.is_arch_pattern("Test_aarch64.go"))
        # 不支持的架构（不在arch_pattern中）
        self.assertFalse(self.arch_pattern.is_arch_pattern("Test_riscv64.go"))
        self.assertFalse(self.arch_pattern.is_arch_pattern("Test_mips.go"))

        """测试大小写敏感性（应区分大小写）"""
        # 大写架构名（应不匹配）
        self.assertFalse(self.arch_pattern.is_arch_pattern("file_AMD64.go"))
        # 混合大小写（应不匹配）
        self.assertFalse(self.arch_pattern.is_arch_pattern("file_AmD64.go"))
        # 小写架构名（应匹配）
        self.assertTrue(self.arch_pattern.is_arch_pattern("file_amd64.go"))
        """测试文件后缀边界情况"""
        # 不支持的扩展名
        self.assertFalse(self.arch_pattern.is_arch_pattern("file_amd64.txt"))
        self.assertFalse(self.arch_pattern.is_arch_pattern("file_amd64.c"))
        # 无扩展名
        self.assertFalse(self.arch_pattern.is_arch_pattern("file_amd64"))
        # 多扩展名（如 .go.txt）
        self.assertFalse(self.arch_pattern.is_arch_pattern("file_amd64.go.txt"))
        """测试带路径的文件名"""
        # 相对路径
        self.assertTrue(self.arch_pattern.is_arch_pattern("src/pkg/file_amd64.go"))
        # 绝对路径
        self.assertTrue(self.arch_pattern.is_arch_pattern("/usr/local/src/file_arm64.s"))
        # 路径中包含架构名（但不匹配）
        self.assertFalse(self.arch_pattern.is_arch_pattern("src/amd64/file.go"))
        """测试特殊字符（如 -、_ 等）"""
        # 其他分隔符（应不匹配）
        self.assertFalse(self.arch_pattern.is_arch_pattern("file-amd64.go"))
        # 多个下划线
        self.assertTrue(self.arch_pattern.is_arch_pattern("file__amd64.go"))  # 可能需根据需求调整
        # 数字和特殊字符组合
        self.assertFalse(self.arch_pattern.is_arch_pattern("file_amd64_v2.go"))

    def test_database_table(self):
        """测试database_table函数"""
        Text = self.solver.database_table()
        self.assertEqual(Text.value, 2)

    def test_solve(self):
        """测试solve函数"""
        result = self.solver.solve(self.test_dir)
        self.assertEqual(len(result), 4)
        expected_test_riscv64_path = os.path.join(self.test_dir, "test_riscv64.go")
        expected_arch_riscv64_path = os.path.join(self.test_dir, "arch_riscv64.s")
        expected_test_riscv64_path_sub = os.path.join(self.sub_dir, "test_riscv64.go")
        expected_arch_riscv64_path_sub = os.path.join(self.sub_dir, "arch_riscv64.s")
        self.assertIn(expected_test_riscv64_path, result)
        self.assertIn(expected_arch_riscv64_path, result)
        self.assertIn(expected_test_riscv64_path_sub, result)
        self.assertIn(expected_arch_riscv64_path_sub, result)
        self.assertEqual(result[expected_test_riscv64_path][0], os.path.join(self.test_dir, "test_arm.go"))
        self.assertEqual(result[expected_arch_riscv64_path][0], os.path.join(self.test_dir, "arch_arm64.s"))
        self.assertEqual(result[expected_test_riscv64_path_sub][0], os.path.join(self.sub_dir, "test_arm.go"))
        self.assertEqual(result[expected_arch_riscv64_path_sub][0], os.path.join(self.sub_dir, "arch_arm64.s"))


if __name__ == '__main__':
    unittest.main()
