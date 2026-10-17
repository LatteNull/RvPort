import os
import unittest
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong
from plugin.codemig.main.source_file import SourceFile
from plugin.codemig.solver.build_script_solver import BuildScriptSolver


class MyTestCase(unittest.TestCase):
    """在执行具体的测试方法前，先被调用"""

    def setUp(self):
        self.solver = BuildScriptSolver()
        self.test_dir = os.path.join(os.path.dirname(__file__), 'test_files', 'test_build_script_files')
        pass

    """会在测试代码执行完后执行，相当于做测试后的扫尾工作"""

    def tearDown(self):
        pass

    def test_matches_file(self):
        """测试文件后缀匹配逻辑"""
        # 应该匹配的文件
        self.assertTrue(self.solver.matches_file("configure.ac"))
        self.assertTrue(self.solver.matches_file("macro.m4"))

        # 不应该匹配的文件
        self.assertFalse(self.solver.matches_file("main.c"))
        self.assertFalse(self.solver.matches_file("invalid.txt"))
        self.assertFalse(self.solver.matches_file("README.md"))
        self.assertFalse(self.solver.matches_file("config.in"))
        self.assertFalse(self.solver.matches_file("path/configure"))
        self.assertFalse(self.solver.matches_file("admin/test.sub"))
        self.assertFalse(self.solver.matches_file("Makefile"))

    def test_empty_file(self):
        """测试空文件处理"""
        test_file = SourceFile(os.path.join(self.test_dir, 'empty.m4'))
        results,_ = self.solver.solve(test_file)
        self.assertEqual(len(results), 0)

    def test_append_or_replace(self):
        """测试append_or_replace函数"""
        value = self.solver.append_or_replace()
        self.assertEqual(value, 2)

    def test_arch_detection(self):
        """测试结果检测"""
        test_file = SourceFile(os.path.join(self.test_dir, 'configure.ac'))
        results,_ = self.solver.solve(test_file)

        start_line, end_line, suggestion, code_too_long, code = results[0]
        self.assertEqual(start_line, 4)
        self.assertEqual(end_line, 11)
        self.assertIn(self.solver.migration_advice.get('arch_case'), suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(
            code,
            'case $host_cpu in\n  x86_64)\n    ARCH_CFLAGS="-march=x86-64"\n    ;;\n  arm*)\n    ARCH_CFLAGS="-march=armv8-a"\n    ;;\nesac'
        )

        start_line, end_line, suggestion, code_too_long, code = results[1]
        self.assertEqual(start_line, 27)
        self.assertEqual(end_line, 32)
        self.assertIn(self.solver.migration_advice.get('arch_case'), suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(
            code,
            'AC_CANONICAL_TARGET\ncase $target_cpu in\n  aarch64)\n    CFLAGS="$CFLAGS -march=armv8-a"\n    ;;\nesac'
        )

        start_line, end_line, suggestion, code_too_long, code = results[2]
        self.assertEqual(start_line, 34)
        self.assertEqual(end_line, 34)
        self.assertIn(self.solver.migration_advice.get('arch_flag'), suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code, 'CFLAGS+="-mavx2 -mfpu=neon"')

        start_line, end_line, suggestion, code_too_long, code = results[3]
        self.assertEqual(start_line, 35)
        self.assertEqual(end_line, 35)
        self.assertIn(self.solver.migration_advice.get('arch_flag'), suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code, 'CFLAGS+="-mfpu=neon"')

        start_line, end_line, suggestion, code_too_long, code = results[4]
        self.assertEqual(start_line, 36)
        self.assertEqual(end_line, 36)
        self.assertIn(self.solver.migration_advice.get('arch_flag'), suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code, 'CFLAGS+="-march=arm"')

        start_line, end_line, suggestion, code_too_long, code = results[5]
        self.assertEqual(start_line, 39)
        self.assertEqual(end_line, 39)
        self.assertIn(self.solver.migration_advice.get('arch_flag'), suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code, 'CFLAGS="-mavx2 -msse4.2 -march=skylake"')

        start_line, end_line, suggestion, code_too_long, code = results[6]
        self.assertEqual(start_line, 40)
        self.assertEqual(end_line, 40)
        self.assertIn(self.solver.migration_advice.get('arch_endian'),
                      suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code, 'AC_DEFINE([WORDS_BIGENDIAN], 1)')

        start_line, end_line, suggestion, code_too_long, code = results[7]
        self.assertEqual(start_line, 41)
        self.assertEqual(end_line, 41)
        self.assertIn(self.solver.migration_advice.get('arch_endian'),
                      suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code, 'AC_DEFINE([WORDS_BIGENDIAN], 0)')

        start_line, end_line, suggestion, code_too_long, code = results[8]
        self.assertEqual(start_line, 42)
        self.assertEqual(end_line, 42)
        self.assertIn(self.solver.migration_advice.get('arch_endian'),
                      suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code, 'AC_DEFINE([WORDS_BIGENDIAN], [1], [Target is big-endian])')

        start_line, end_line, suggestion, code_too_long, code = results[9]
        self.assertEqual(start_line, 46)
        self.assertEqual(end_line, 46)
        self.assertIn(self.solver.migration_advice.get('arch_pseudo_inst'),
                      suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code, '.set arch, armv8-a')

        start_line, end_line, suggestion, code_too_long, code = results[10]
        self.assertEqual(start_line, 48)
        self.assertEqual(end_line, 48)
        self.assertIn(self.solver.migration_advice.get('arch_inline_asm'),
                      suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code, '__asm__("mov %eax, %ebx");')

        start_line, end_line, suggestion, code_too_long, code = results[11]
        self.assertEqual(start_line, 50)
        self.assertEqual(end_line, 50)
        self.assertIn(self.solver.migration_advice.get('arch_env_var'),
                      suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code, 'CC="aarch64-linux-gnu-gcc"')

        start_line, end_line, suggestion, code_too_long, code = results[12]
        self.assertEqual(start_line, 52)
        self.assertEqual(end_line, 52)
        self.assertIn(self.solver.migration_advice.get('arch_config_test'),
                      suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code, 'AC_TRY_RUN([arm])')


if __name__ == '__main__':
    unittest.main()
