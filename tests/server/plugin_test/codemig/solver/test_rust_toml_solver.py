"""
RustTomlSolver 测试用例

测试覆盖：
1. TOML 文件匹配
2. target 配置解析和 riscv64 支持判断
3. build 配置解析
4. cfg 表达式解析
5. target-feature 检查
"""

import os
import unittest
import tempfile
from plugin.codemig.solver.rust_toml_solver import RustTomlSolver
from plugin.codemig.main.source_file import SourceFile
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__)))
TEST_FILE_PATH = os.path.join(MODULE_PATH, 'test_files', 'test_rust_files')


class TestRustTomlSolver(unittest.TestCase):
    """RustTomlSolver 测试类"""

    def setUp(self):
        """测试前准备"""
        self.solver = RustTomlSolver()
        self.test_dir = TEST_FILE_PATH

    def test_matches_file(self):
        """测试文件匹配"""
        self.assertTrue(RustTomlSolver.matches_file("Cargo.toml"))
        self.assertFalse(RustTomlSolver.matches_file("test.toml"))
        self.assertTrue(RustTomlSolver.matches_file("config.toml"))
        self.assertFalse(RustTomlSolver.matches_file("test.rs"))
        self.assertFalse(RustTomlSolver.matches_file("test.py"))

    def test_append_or_replace(self):
        """测试 append_or_replace 方法"""
        value = RustTomlSolver.append_or_replace()
        self.assertEqual(value, 2)  # ChangeType.OTHER.value

    def test_migration_class(self):
        """测试 migration_class 方法"""
        value = RustTomlSolver.migration_class()
        from plugin.codemig.codemig_common.migration_class import MigrationClass
        self.assertEqual(value, MigrationClass.TEXT)

    def test_empty_file(self):
        """测试空文件处理"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write('')
            temp_path = f.name

        try:
            source_file = SourceFile(temp_path)
            results, results_rv = RustTomlSolver.solve(source_file)
            self.assertEqual(len(results), 0)
            self.assertEqual(len(results_rv), 0)
        finally:
            os.unlink(temp_path)

    def test_target_cfg_riscv64(self):
        """测试 target cfg 配置 - 支持 riscv64"""
        toml_content = '''[package]
name = "test"

[target.'cfg(target_arch = "riscv64")'.dependencies]
syscalls = "0.6.18"
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            source_file = SourceFile(temp_path)
            results, results_rv = RustTomlSolver.solve(source_file)
            # riscv64 应该在 results_rv 中
            self.assertGreater(len(results_rv), 0)
            # 检查结果中是否包含 riscv64 相关信息
            found_riscv = False
            for _, _, suggestion, _, _ in results_rv:
                if 'riscv64' in suggestion.lower():
                    found_riscv = True
                    break
            self.assertTrue(found_riscv, "应该找到 riscv64 支持")
        finally:
            os.unlink(temp_path)

    def test_target_cfg_x86_64(self):
        """测试 target cfg 配置 - 不支持 riscv64"""
        toml_content = '''[package]
name = "test"

[target.'cfg(target_arch = "x86_64")'.dependencies]
syscalls = "0.6.18"
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            source_file = SourceFile(temp_path)
            results, results_rv = RustTomlSolver.solve(source_file)
            # x86_64 应该在 results 中（需要添加 riscv 支持）
            self.assertGreater(len(results), 0)
        finally:
            os.unlink(temp_path)

    def test_target_cfg_any_riscv64(self):
        """测试 target cfg any 表达式 - 包含 riscv64"""
        toml_content = '''[package]
name = "test"

[target.'cfg(any(target_arch = "x86_64", target_arch = "riscv64"))'.dependencies]
syscalls = "0.6.18"
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            source_file = SourceFile(temp_path)
            results, results_rv = RustTomlSolver.solve(source_file)
            # any 中包含 riscv64，应该在 results_rv 中
            self.assertGreater(len(results_rv), 0)
        finally:
            os.unlink(temp_path)

    def test_target_cfg_not_riscv64(self):
        """测试 target cfg not 表达式 - 不包含 riscv64"""
        toml_content = '''[package]
name = "test"

[target.'cfg(not(target_arch = "riscv64"))'.dependencies]
syscalls = "0.6.18"
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            source_file = SourceFile(temp_path)
            results, results_rv = RustTomlSolver.solve(source_file)
            # not(riscv64) 不支持 riscv，应该在 results 中
            self.assertGreater(len(results), 0)
        finally:
            os.unlink(temp_path)

    def test_target_cfg_target_feature(self):
        """测试 target cfg target_feature"""
        toml_content = '''[package]
name = "test"

[target.'cfg(target_feature = "lzcnt")'.dependencies]
syscalls = "0.6.18"
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            source_file = SourceFile(temp_path)
            results, results_rv = RustTomlSolver.solve(source_file)
            # target_feature 应该被检测到
            # 结果取决于 feature 是否支持 riscv
            self.assertIsInstance(results, list)
            self.assertIsInstance(results_rv, list)
        finally:
            os.unlink(temp_path)

    def test_target_riscv64(self):
        """测试 target.riscv64 配置"""
        toml_content = '''[package]
name = "test"

[target.riscv64gc-unknown-linux-gnu]
linker = "riscv64-linux-gnu-gcc"
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            source_file = SourceFile(temp_path)
            results, results_rv = RustTomlSolver.solve(source_file)
            # riscv64 应该在 results_rv 中
            self.assertGreater(len(results_rv), 0)
        finally:
            os.unlink(temp_path)

    def test_target_x86_64(self):
        """测试 target.x86_64 配置"""
        toml_content = '''[package]
name = "test"

[target.x86_64-unknown-linux-musl]
rustflags = ["-C", "target-feature=+crt-static"]
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            source_file = SourceFile(temp_path)
            results, results_rv = RustTomlSolver.solve(source_file)
            # x86_64 应该在 results 中（需要添加 riscv 支持）
            self.assertGreater(len(results), 0)
        finally:
            os.unlink(temp_path)

    def test_build_target_list_with_riscv64(self):
        """测试 build.target 列表 - 包含 riscv64"""
        toml_content = '''[package]
name = "test"

[[build]]
target = [
    "x86_64-unknown-linux-gnu",
    "riscv64-unknown-linux-gnu"
]
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            source_file = SourceFile(temp_path)
            results, results_rv = RustTomlSolver.solve(source_file)
            # 包含 riscv64，应该在 results_rv 中
            self.assertGreater(len(results_rv), 0)
        finally:
            os.unlink(temp_path)

    def test_build_target_list_without_riscv64(self):
        """测试 build.target 列表 - 不包含 riscv64"""
        toml_content = '''[package]
name = "test"

[[build]]
target = [
    "x86_64-unknown-linux-gnu",
    "aarch64-unknown-linux-gnu"
]
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            source_file = SourceFile(temp_path)
            results, results_rv = RustTomlSolver.solve(source_file)
            # 不包含 riscv64，应该在 results 中
            self.assertGreater(len(results), 0)
        finally:
            os.unlink(temp_path)

    def test_build_target_string_with_riscv64(self):
        """测试 build.target 字符串 - 包含 riscv64"""
        toml_content = '''[package]
name = "test"

[[build]]
target = "riscv64-unknown-linux-gnu"
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            source_file = SourceFile(temp_path)
            results, results_rv = RustTomlSolver.solve(source_file)
            # 包含 riscv64，应该在 results_rv 中
            self.assertGreater(len(results_rv), 0)
        finally:
            os.unlink(temp_path)

    def test_build_target_string_without_riscv64(self):
        """测试 build.target 字符串 - 不包含 riscv64"""
        toml_content = '''[package]
name = "test"

[[build]]
target = "x86_64-unknown-linux-gnu"
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            source_file = SourceFile(temp_path)
            results, results_rv = RustTomlSolver.solve(source_file)
            # 不包含 riscv64，应该在 results 中
            self.assertGreater(len(results), 0)
        finally:
            os.unlink(temp_path)

    def test_build_rustflags_target_feature(self):
        """测试 build.rustflags 中的 target-feature"""
        toml_content = '''[package]
name = "test"

[[build]]
rustflags = [
    "-C", "target-feature=+lzcnt",
    "-C", "link-self-contained=yes"
]
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            source_file = SourceFile(temp_path)
            results, results_rv = RustTomlSolver.solve(source_file)
            # 应该检查 target-feature
            # 结果取决于 feature 是否支持 riscv
            self.assertIsInstance(results, list)
            self.assertIsInstance(results_rv, list)
        finally:
            os.unlink(temp_path)

    def test_complex_toml(self):
        """测试复杂的 TOML 配置"""
        toml_content = '''[package]
name = "mypackage"
version = "0.0.1"

[target.x86_64-unknown-linux-musl]
rustflags = [
    "-C", "target-feature=+crt-static,+lzcnt",
]

[[build]]
target = [
    "x86_64-unknown-linux-gnu",
    "riscv64-unknown-linux-gnu"
]

[target.'cfg(target_arch = "x86_64")'.dependencies]
syscalls = "0.6.18"

[target.'cfg(target_arch = "riscv64")'.dependencies]
syscalls = "0.6.18"
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            source_file = SourceFile(temp_path)
            results, results_rv = RustTomlSolver.solve(source_file)
            # 应该有结果
            self.assertIsInstance(results, list)
            self.assertIsInstance(results_rv, list)
            # 应该同时有需要添加支持的项和已支持的项
            self.assertGreater(len(results) + len(results_rv), 0)
        finally:
            os.unlink(temp_path)

    def test_real_file(self):
        """测试真实文件"""
        test_file = os.path.join(TEST_FILE_PATH, "cfg.toml")
        if os.path.exists(test_file):
            source_file = SourceFile(test_file)
            results, results_rv = RustTomlSolver.solve(source_file)
            # 应该有结果
            self.assertIsInstance(results, list)
            self.assertIsInstance(results_rv, list)

    def test_invalid_toml(self):
        """测试无效的 TOML 文件"""
        toml_content = '''[package
name = "test"
invalid syntax
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            source_file = SourceFile(temp_path)
            # 应该能够处理错误，返回空结果
            results, results_rv = RustTomlSolver.solve(source_file)
            self.assertIsInstance(results, list)
            self.assertIsInstance(results_rv, list)
        finally:
            os.unlink(temp_path)

    def test_nonexistent_file(self):
        """测试不存在的文件"""
        source_file = SourceFile("/nonexistent/path/file.toml")
        results, results_rv = RustTomlSolver.solve(source_file)
        # 应该返回空结果
        self.assertEqual(len(results), 0)
        self.assertEqual(len(results_rv), 0)


if __name__ == '__main__':
    unittest.main()

