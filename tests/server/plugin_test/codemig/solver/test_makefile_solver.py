import logging
import os
import pytest
import unittest
from unittest import mock
from plugin.codemig.codemig_common.codemig_common_utils import ChangeType
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong
from plugin.codemig.main.source_file import SourceFile
from plugin.codemig.solver.makefile_solver import MakefileSolver


MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__)))

SUGGESTION = "此处参数可能与架构相关，请修改为RISCV支持的参数"

class TestMakefileSolver(unittest.TestCase):

    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog  # 将caplog注入为成员变量

    def setUp(self):
        self.test_file1 = SourceFile(MODULE_PATH + "/test_files/makefile_solver/Makefile")
        self.test_file2 = SourceFile(MODULE_PATH + "/test_files/makefile_solver/Makefile_empty")
        self.test_file3 = SourceFile(MODULE_PATH + "/test_files/makefile_solver/Makefile2")
        self.test_file4 = SourceFile(MODULE_PATH + "/test_files/makefile_solver/Makefile4")

    def test_matches_file_with_makefile(self):
        self.assertTrue(MakefileSolver.matches_file("Makefile"))
        self.assertTrue(MakefileSolver.matches_file("some/dir/Makefile"))

    def test_matches_file_without_makefile(self):
        self.assertFalse(MakefileSolver.matches_file("README.md"))
        self.assertFalse(MakefileSolver.matches_file("make_file.txt"))

    def test_append_or_replace(self):
        self.assertEqual(MakefileSolver.append_or_replace(),
                         ChangeType.OTHER.value)

    def test_makefile1(self):
        results = MakefileSolver.solve(self.test_file1)
        self.assertEqual(results,
            ([[
                1, 1, SUGGESTION,
                CodeTooLong.HAS_SOURCE_CODE, 'CFLAGS = -Wall -O2 -g'
            ],
                 [
                     5, 5, SUGGESTION,
                     CodeTooLong.HAS_SOURCE_CODE, 'CXXFLAGS = -Wall -O2 -g'
                 ],
                 [
                     6, 6, SUGGESTION,
                     CodeTooLong.HAS_SOURCE_CODE,
                     'FLAGS = -Wall -O2 -g -march=rv64gc'
                 ],
                 [
                     7, 7, SUGGESTION,
                     CodeTooLong.HAS_SOURCE_CODE,
                     'FLAGS = -Wall -O2 -g -mtune=generic'
                 ],
                 [
                     8, 8, SUGGESTION,
                     CodeTooLong.HAS_SOURCE_CODE, 'FLAGS = -Wall -O2 -g -mabi=lp64d'
                 ],
                 [
                     9, 9, 
                     SUGGESTION,
                     CodeTooLong.HAS_SOURCE_CODE, 'FLAGS = -Wall -O2 -g -march=aaa'
                 ],
                 [
                     10, 10,
                     SUGGESTION,
                     CodeTooLong.HAS_SOURCE_CODE, 'FLAGS = -Wall -O2 -g -mtune=bbb'
                 ],
                 [
                     11, 11,
                     SUGGESTION,
                     CodeTooLong.HAS_SOURCE_CODE, 'FLAGS = -Wall -O2 -g -mabi=ccc'
                 ],
                 [
                     12, 12,
                     SUGGESTION,
                     CodeTooLong.HAS_SOURCE_CODE, 'FLAGS = -Wall -O2 -g'
                 ],
                 [
                     13, 13,
                     SUGGESTION,
                     CodeTooLong.HAS_SOURCE_CODE, 'FLAGS = -Wall -O2 -g -abc'
                 ]], [])
        )

    def test_makefile2(self):
        self.assertEqual(
            MakefileSolver.solve(self.test_file2),
            ([], [])
        )

    def test_makefile3(self):
        self.assertEqual(
            MakefileSolver.solve(self.test_file3),
            ([[2, 2, SUGGESTION, CodeTooLong.HAS_SOURCE_CODE, 'MY = -m64'],
              [3, 3, SUGGESTION, CodeTooLong.HAS_SOURCE_CODE, 'MY2 = -mcpu=abc'],
              [4, 4, SUGGESTION, CodeTooLong.HAS_SOURCE_CODE, 'MY3 = -march=rv64imafdc'],
              [11, 11, SUGGESTION, CodeTooLong.HAS_SOURCE_CODE, 'ABC = -Wall -O2 -g -mabi=ccc']],
             [])
        )

    def test_makefile4(self):
        with self._caplog.at_level(logging.WARNING):
            self.assertEqual(MakefileSolver.solve(self.test_file4), ([], []))
            self.assertIn("WARNING", self._caplog.text)
            self.assertIn("Cannot find the target file", self._caplog.text)

    @mock.patch("builtins.open", side_effect=Exception("Mocked file read error"))
    def test_makefile4_exception(self, mock_open):
        with pytest.raises(Exception, match="Mocked file read error"):
            MakefileSolver.solve(self.test_file4)


if __name__ == "__main__":
    unittest.main()
