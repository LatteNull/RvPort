import os
import unittest

from plugin.codemig.codemig_common.codemig_common_utils import ChangeType
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong
from plugin.codemig.main.source_file import SourceFile
from plugin.codemig.solver.builtin_solver import BuiltinSolver

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__)))
TEST_FILE_PATH = os.path.join(MODULE_PATH, 'test_files', 'builtin_solver')


class TestBuiltinSolver(unittest.TestCase):
    test_file1 = SourceFile(os.path.join(TEST_FILE_PATH, "builtin.c"))
    test_file2 = SourceFile(os.path.join(TEST_FILE_PATH, "empty.c"))
    test_file3 = SourceFile(os.path.join(TEST_FILE_PATH, "builtin2.c"))

    def test_matches_file(self):
        self.assertTrue(BuiltinSolver.matches_file("abc.h"))
        self.assertTrue(BuiltinSolver.matches_file("some/dir/aaa.c"))
        self.assertTrue(BuiltinSolver.matches_file("abc.cc"))
        self.assertTrue(BuiltinSolver.matches_file("abc.cpp"))

    def test_matches_file(self):
        self.assertFalse(BuiltinSolver.matches_file("README.md"))
        self.assertFalse(BuiltinSolver.matches_file("make_file.f"))

    def test_append_or_replace(self):
        self.assertEqual(BuiltinSolver.append_or_replace(), ChangeType.APPEND.value)

    def test_builtin(self):
        self.assertEqual(
            BuiltinSolver.solve(self.test_file1),
            ([[
                4, 4,
                '// Line 4, built-in __builtin_copysignq(offset: 19) is not supported.\n',
                CodeTooLong.HAS_SOURCE_CODE,
                '  double result1 = __builtin_copysignq(1.0, -2.0);  '
            ],
                 [
                     6, 6,
                     '// Line 6, built-in __builtin_copysignq(offset: 19) is not supported.\n',
                     CodeTooLong.HAS_SOURCE_CODE,
                     '  double result3 = __builtin_copysignq(1.0, -2.0);'
                 ],
                 [
                     7, 7,
                     '// Line 7, built-in __builtin_cpu_init(offset: 2) and __builtin_copysignq(offset: 41) are not supported.\n',
                     CodeTooLong.HAS_SOURCE_CODE,
                     '  __builtin_cpu_init(); double result5 = __builtin_copysignq(1.0, -2.0);'
                 ]], []),
        )

    def test_builtin2(self):
        self.assertEqual(BuiltinSolver.solve(self.test_file2), ([], []))

    def test_builtin3(self):
        self.assertEqual(
            BuiltinSolver.solve(self.test_file3),
            ([[
                4, 4,
                '// Line 4, built-in __builtin_aarch64_get_fpcr(offset: 19) is not supported.\n',
                CodeTooLong.HAS_SOURCE_CODE,
                '  double result1 = __builtin_aarch64_get_fpcr(1.0, -2.0);'
            ]], [])
        )

    def test_x86(self):
        miss, found = BuiltinSolver.solve(SourceFile(os.path.join(TEST_FILE_PATH, "all_x86.c")))
        self.assertTrue(len(miss), 961)

    def test_arm(self):
        miss, found = BuiltinSolver.solve(SourceFile(os.path.join(TEST_FILE_PATH, "all_arm.c")))
        self.assertTrue(len(miss), 8)


if __name__ == "__main__":
    unittest.main()
