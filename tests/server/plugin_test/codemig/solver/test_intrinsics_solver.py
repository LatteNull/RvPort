import unittest
import os
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong
from plugin.codemig.solver.intrinsics_solver import IntrinsicsSolver
from plugin.codemig.main.source_file import SourceFile
from plugin.codemig.codemig_common.codemig_common_utils import ChangeType

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__)))


class TestIntrinsicsSolver(unittest.TestCase):

    def setUp(self):
        self.test_file1 = SourceFile(
            MODULE_PATH + "/test_files/intrinsics_solver/intrinsics-1.h")
        self.test_file2 = SourceFile(
            MODULE_PATH + "/test_files/intrinsics_solver/intrinsics-2.h")
        self.test_file3 = SourceFile(
            MODULE_PATH + "/test_files/intrinsics_solver/intrinsics-4.h")
        self.test_file4 = SourceFile(
            MODULE_PATH + "/test_files/intrinsics_solver/intrinsics-5.h")

    def test_matches_file_true(self):
        self.assertTrue(IntrinsicsSolver.matches_file("abc.h"))
        self.assertTrue(IntrinsicsSolver.matches_file("some/dir/aaa.h"))
        self.assertTrue(IntrinsicsSolver.matches_file("make_file.c"))
        self.assertTrue(IntrinsicsSolver.matches_file("abc.cc"))
        self.assertTrue(IntrinsicsSolver.matches_file("abc.cpp"))

    def test_matches_file_false(self):
        self.assertFalse(IntrinsicsSolver.matches_file("README.md"))

    def test_append_or_replace(self):
        self.assertEqual(IntrinsicsSolver.append_or_replace(),
                         ChangeType.REPLACE.value)

    def test_intrinsics1(self):
        self.assertEqual(
            IntrinsicsSolver.solve(self.test_file1),
            ([[
                3, 3,
                "建议使用riscv的intrinsics进行替换、优化文件中__x86_64__的intrinsic函数",
                CodeTooLong.HAS_SOURCE_CODE, '#include <emmintrin.h>'
            ]],[])
        )

    def test_intrinsics2(self):
        self.assertEqual(
            IntrinsicsSolver.solve(self.test_file2),
            ([[
                1, 1,
                "建议使用riscv的intrinsics进行替换、优化文件中__x86_64__的intrinsic函数",
                CodeTooLong.HAS_SOURCE_CODE, '#include <emmintrin.h>'
            ],
             [
                 2, 2,
                 "建议使用riscv的intrinsics进行替换、优化文件中__x86_64__的intrinsic函数",
                 CodeTooLong.HAS_SOURCE_CODE, '#include <emmintrin.h>'
             ],
             [
                 4, 4,
                 "建议使用riscv的intrinsics进行替换、优化文件中__x86_64__的intrinsic函数",
                 CodeTooLong.HAS_SOURCE_CODE, '#include <emmintrin.h>'
             ],
             [
                 6, 6,
                 "建议使用riscv的intrinsics进行替换、优化文件中__x86_64__的intrinsic函数",
                 CodeTooLong.HAS_SOURCE_CODE, '#include <emmintrin.h>'
             ],
             [
                 8, 8,
                 "建议使用riscv的intrinsics进行替换、优化文件中__x86_64__的intrinsic函数",
                 CodeTooLong.HAS_SOURCE_CODE, '#include "emmintrin.h"'
             ]],[])
        )

    def test_intrinsics3(self):
        self.assertEqual(
            IntrinsicsSolver.solve(self.test_file3),
            ([],[])
        )

    def test_intrinsics4(self):
        self.assertEqual(
            IntrinsicsSolver.solve(self.test_file4),
            ([[
                1, 1,
                '建议使用riscv的intrinsics进行替换、优化文件中__aarch64__的intrinsic函数',
                CodeTooLong.HAS_SOURCE_CODE, '#include "arm_neon.h"'
            ]],[])
        )


if __name__ == "__main__":
    unittest.main()
