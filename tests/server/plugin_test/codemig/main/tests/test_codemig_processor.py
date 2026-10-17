import unittest
import os
from plugin.codemig.main.codemig_processor import CodemigProcessor
from plugin.codemig.solver.makefile_solver import MakefileSolver
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..", "solver"))
SUGGESTION = "此处参数可能与架构相关，请修改为RISCV支持的参数"

class TestCodemigProcessor(unittest.TestCase):

    def setUp(self):
        self.test_file1 = MODULE_PATH + "/test_files/makefile_solver/Makefile"
        self.test_file2 = MODULE_PATH + "/test_files/makefile_solver/test/Makefile"

    def test_process_file(self):
        res = CodemigProcessor.process_file(self.test_file1)[MakefileSolver]
        change, found = res
        self.assertEqual(
            change,
            [[
                1, 1,
                SUGGESTION,
                CodeTooLong.HAS_SOURCE_CODE, 'CFLAGS = -Wall -O2 -g'
            ],
             [
                 5, 5,
                 SUGGESTION,
                 CodeTooLong.HAS_SOURCE_CODE, 'CXXFLAGS = -Wall -O2 -g'
             ],
             [
                 6, 6,
                 SUGGESTION,
                 CodeTooLong.HAS_SOURCE_CODE,
                 'FLAGS = -Wall -O2 -g -march=rv64gc'
             ],
             [
                 7, 7,
                 SUGGESTION,
                 CodeTooLong.HAS_SOURCE_CODE,
                 'FLAGS = -Wall -O2 -g -mtune=generic'
             ],
             [
                 8, 8,
                 SUGGESTION,
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
             ]],
        )

    def test_process_file2(self):
        self.assertEqual(
            CodemigProcessor.process_file(self.test_file2)[MakefileSolver],
            ([],[])
        )


if __name__ == "__main__":
    unittest.main()
