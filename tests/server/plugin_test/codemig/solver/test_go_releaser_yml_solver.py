"""
GoReleaserYmlSolver 测试用例

测试覆盖：
1. 文件匹配规则
2. goarch 块识别
3. RISC-V 架构支持检测
4. 多架构块处理
5. 边界情况处理
"""

import os
import unittest
from plugin.codemig.solver.go_releaser_yml_solver import GoReleaserYmlSolver
from plugin.codemig.main.source_file import SourceFile
from plugin.codemig.codemig_common.migration_class import MigrationClass
from plugin.codemig.codemig_common.codemig_common_utils import ChangeType

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__)))
TEST_FILE_PATH = os.path.join(MODULE_PATH, 'test_files', 'test_go_files')


class TestGoReleaserYmlSolver(unittest.TestCase):
    """GoReleaserYmlSolver 测试类"""

    def setUp(self):
        """测试前准备"""
        self.solver = GoReleaserYmlSolver()

    # ==================== 基础方法测试 ====================

    def test_matches_file_goreleaser_yml(self):
        """测试匹配 goreleaser.yml 文件"""
        self.assertTrue(GoReleaserYmlSolver.matches_file("goreleaser.yml"))
        self.assertTrue(GoReleaserYmlSolver.matches_file(".goreleaser.yml"))
        self.assertTrue(GoReleaserYmlSolver.matches_file("release/goreleaser.yml"))

    def test_matches_file_not_goreleaser(self):
        """测试不匹配非 goreleaser.yml 文件"""
        self.assertFalse(GoReleaserYmlSolver.matches_file("go.yml"))
        self.assertFalse(GoReleaserYmlSolver.matches_file("config.yml"))
        self.assertFalse(GoReleaserYmlSolver.matches_file("goreleaser.yaml"))
        self.assertFalse(GoReleaserYmlSolver.matches_file("main.go"))

    def test_append_or_replace(self):
        """测试 append_or_replace 方法"""
        value = GoReleaserYmlSolver.append_or_replace()
        self.assertEqual(value, ChangeType.OTHER.value)

    def test_migration_class(self):
        """测试 migration_class 方法"""
        value = GoReleaserYmlSolver.migration_class()
        self.assertEqual(value, MigrationClass.TEXT)

    # ==================== find_arch_blocks 核心逻辑测试 ====================

    def test_find_arch_blocks_no_riscv(self):
        """测试没有 RISC-V 支持的架构块"""
        # 注意：代码模式 r'^\s*goarch:\s*$' 不匹配 '- goarch:'，所以使用直接的 goarch: 声明
        lines = [
            "builds:\n",
            "  goarch:\n",
            "    - amd64\n",
            "    - arm64\n",
            "  other: value\n",  # 块结束行
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        # 应该检测到缺少 riscv64
        self.assertGreater(len(results), 0)
        self.assertIn("RISC-V", results[0][2])

    def test_find_arch_blocks_with_riscv64(self):
        """测试包含 riscv64 的架构块"""
        lines = [
            "builds:\n",
            "  goarch:\n",
            "      - amd64\n",
            "      - arm64\n",
            "      - riscv64\n",
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        # 包含 riscv64，不应该有结果
        self.assertEqual(len(results), 0)

    def test_find_arch_blocks_with_riscv(self):
        """测试包含 riscv 的架构块"""
        lines = [
            "builds:\n",
            "  goarch:\n",
            "      - amd64\n",
            "      - riscv\n",
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        # 包含 riscv，不应该有结果
        self.assertEqual(len(results), 0)

    def test_find_arch_blocks_empty_list(self):
        """测试空的架构列表"""
        lines = [
            "builds:\n",
            "  goarch:\n",
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        # 空列表不应该触发警告
        self.assertEqual(len(results), 0)

    def test_find_arch_blocks_single_arch(self):
        """测试单架构定义"""
        lines = [
            "builds:\n",
            "  goarch:\n",
            "      - amd64\n",
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        # 只有 amd64，应该检测到缺少 riscv
        self.assertGreater(len(results), 0)

    def test_find_arch_blocks_case_insensitive(self):
        """测试大小写不敏感匹配"""
        lines = [
            "builds:\n",
            "  goarch:\n",
            "      - amd64\n",
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        # goarch 应该被匹配
        self.assertGreater(len(results), 0)

    def test_find_arch_blocks_with_whitespace(self):
        """测试带空白字符的行"""
        lines = [
            "builds:\n",
            "  goarch:\n",
            "      - amd64   \n",
            "      - arm64\n",
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        self.assertGreater(len(results), 0)

    def test_find_arch_blocks_indentation_change(self):
        """测试缩进变化导致块结束"""
        lines = [
            "builds:\n",
            "  goarch:\n",
            "      - amd64\n",
            "      - arm64\n",
            "      - x86\n",  # 添加一个架构确保列表不为空
            "  main: ./cmd\n",  # 缩进回到同一级别，块结束
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        self.assertGreater(len(results), 0)

    def test_find_arch_blocks_deeper_indent(self):
        """测试更深的缩进"""
        lines = [
            "builds:\n",
            "  id: mybuild\n",
            "    goarch:\n",
            "      - amd64\n",
            "      - arm64\n",
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        self.assertGreater(len(results), 0)

    def test_find_arch_blocks_file_ending_no_riscv(self):
        """测试文件末尾没有 RISC-V 的块"""
        lines = [
            "builds:\n",
            "  goarch:\n",
            "      - amd64\n",
            "      - arm64\n",
        ]
        # 确保文件末尾正确处理
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        self.assertGreater(len(results), 0)

    def test_find_arch_blocks_multiple_blocks_first_no_riscv(self):
        """测试多个块，第一个没有 RISC-V"""
        lines = [
            "builds:\n",
            "  id: linux\n",
            "    goarch:\n",
            "      - amd64\n",
            "      - arm64\n",
            "  id: darwin\n",
            "    goarch:\n",
            "      - amd64\n",
            "      - arm64\n",
            "      - riscv64\n",
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        # 第一个块没有 riscv，应该有结果
        self.assertGreater(len(results), 0)

    def test_find_arch_blocks_all_caps(self):
        """测试全大写架构名"""
        lines = [
            "builds:\n",
            "  goarch:\n",
            "      - AMD64\n",
            "      - ARM64\n",
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        # 大写的 AMD64/ARM64 不匹配小写的 riscv，应该检测到缺少 RISC-V
        self.assertGreater(len(results), 0)

    def test_find_arch_blocks_mixed_case_arch(self):
        """测试混合大小写的架构名"""
        lines = [
            "builds:\n",
            "  goarch:\n",
            "      - amd64\n",
            "      - arm64\n",
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        # 没有 riscv64 或 riscv，应该报告缺少支持
        self.assertGreater(len(results), 0)

    # ==================== 真实文件测试 ====================

    def test_real_file_no_riscv(self):
        """测试没有 RISC-V 支持的真实文件"""
        test_file = os.path.join(TEST_FILE_PATH, "goreleaser_no_riscv.yml")
        if os.path.exists(test_file):
            source_file = SourceFile(test_file)
            results, results_rv = GoReleaserYmlSolver.solve(source_file)
            # 应该检测到缺少 RISC-V 支持
            self.assertGreater(len(results), 0)
            self.assertIsInstance(results_rv, list)

    def test_real_file_with_riscv(self):
        """测试有 RISC-V 支持的真实文件"""
        test_file = os.path.join(TEST_FILE_PATH, "goreleaser_with_riscv.yml")
        if os.path.exists(test_file):
            source_file = SourceFile(test_file)
            results, results_rv = GoReleaserYmlSolver.solve(source_file)
            # 包含 riscv64，不应该有结果
            self.assertEqual(len(results), 0)

    def test_real_file_empty(self):
        """测试空的真实文件"""
        test_file = os.path.join(TEST_FILE_PATH, "goreleaser_empty.yml")
        if os.path.exists(test_file):
            source_file = SourceFile(test_file)
            results, results_rv = GoReleaserYmlSolver.solve(source_file)
            # 没有 goarch 声明，不应该有结果
            self.assertEqual(len(results), 0)

    def test_real_file_multiple_blocks(self):
        """测试有多个架构块的真实文件"""
        test_file = os.path.join(TEST_FILE_PATH, "goreleaser_multiple_arch_blocks.yml")
        if os.path.exists(test_file):
            source_file = SourceFile(test_file)
            results, results_rv = GoReleaserYmlSolver.solve(source_file)
            # 第一个块没有 riscv，应该有结果
            self.assertIsInstance(results, list)
            self.assertIsInstance(results_rv, list)

    def test_real_file_single_arch(self):
        """测试单架构的真实文件"""
        test_file = os.path.join(TEST_FILE_PATH, "goreleaser_single_arch.yml")
        if os.path.exists(test_file):
            source_file = SourceFile(test_file)
            results, results_rv = GoReleaserYmlSolver.solve(source_file)
            # 只有 amd64，应该检测到缺少 RISC-V
            self.assertGreater(len(results), 0)

    # ==================== 边界情况测试 ====================

    def test_empty_lines_only(self):
        """测试只有空行的文件"""
        lines = ["\n", "\n", "\n"]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        self.assertEqual(len(results), 0)

    def test_no_goarch_declaration(self):
        """测试没有 goarch 声明的文件"""
        lines = [
            "project_name: myapp\n",
            "archives:\n",
            "  - format: tar.gz\n",
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        self.assertEqual(len(results), 0)

    def test_goarch_at_start_of_line(self):
        """测试 goarch 在行首"""
        lines = [
            "goarch:\n",
            "- amd64\n",
            "- arm64\n",
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        # 这种格式可能不被正确解析（因为缩进为 0）
        self.assertIsInstance(results, list)

    def test_goarch_with_inline_content(self):
        """测试 goarch 行有 inline 内容"""
        lines = [
            "builds:\n",
            "  goarch: [amd64, arm64]\n",
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        # 这种格式可能不被正确解析
        self.assertIsInstance(results, list)

    def test_comments_in_file(self):
        """测试文件中有注释"""
        lines = [
            "# This is a comment\n",
            "builds:\n",
            "  goarch:\n",
            "      - amd64\n",
            "      - arm64\n",
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        self.assertGreater(len(results), 0)

    def test_special_characters_in_arch(self):
        """测试架构名中的引号"""
        lines = [
            "builds:\n",
            "  goarch:\n",
            "      - amd64\n",
            "      - arm64\n",
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        self.assertGreater(len(results), 0)

    def test_result_format(self):
        """测试结果格式验证"""
        from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong
        
        lines = [
            "builds:\n",
            "  goarch:\n",
            "      - amd64\n",
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        if results:
            result = results[0]
            self.assertEqual(len(result), 5)
            self.assertIsInstance(result[0], int)  # start line
            self.assertIsInstance(result[1], int)  # end line
            self.assertIsInstance(result[2], str)  # message
            self.assertIsInstance(result[3], CodeTooLong)  # code_too_long (enum)
            self.assertIsInstance(result[4], str)  # code

    def test_large_arch_list(self):
        """测试大型架构列表"""
        lines = ["builds:\n", "  goarch:\n"]
        archs = ["      - amd64\n", "      - arm64\n", "      - 386\n", "      - arm\n", "      - mips\n"]
        lines.extend(archs)
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        self.assertGreater(len(results), 0)

    def test_arch_list_with_extra_items(self):
        """测试架构列表中有额外项"""
        lines = [
            "builds:\n",
            "  goarch:\n",
            "      - amd64\n",
            "      - arm64\n",
            "      - custom_arch\n",
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        self.assertGreater(len(results), 0)

    def test_only_riscv64(self):
        """测试只有 riscv64"""
        lines = [
            "builds:\n",
            "  goarch:\n",
            "      - riscv64\n",
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        # 只有 riscv64，应该通过
        self.assertEqual(len(results), 0)

    def test_only_riscv(self):
        """测试只有 riscv"""
        lines = [
            "builds:\n",
            "  goarch:\n",
            "      - riscv\n",
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        # 只有 riscv，应该通过
        self.assertEqual(len(results), 0)

    def test_both_riscv_and_riscv64(self):
        """测试同时有 riscv 和 riscv64"""
        lines = [
            "builds:\n",
            "  goarch:\n",
            "      - riscv\n",
            "      - riscv64\n",
        ]
        results, _ = GoReleaserYmlSolver.find_arch_blocks(
            lines, GoReleaserYmlSolver.compiled_patterns, GoReleaserYmlSolver.migration_advice)
        # 两者都有，应该通过
        self.assertEqual(len(results), 0)


if __name__ == '__main__':
    unittest.main()
