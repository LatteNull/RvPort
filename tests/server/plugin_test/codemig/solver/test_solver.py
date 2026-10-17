import unittest
from plugin.codemig.codemig_common.codemig_common_utils import NUMBER_LINES_TOO_LONG
from plugin.codemig.solver.makefile_solver import MakefileSolver
from plugin.codemig.solver.intrinsics_solver import IntrinsicsSolver
from plugin.codemig.solver.builtin_solver import BuiltinSolver
from plugin.codemig.solver.macros_solver import MacrosSolver
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong
from plugin.codemig.solver.solver import Solver
import os

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__)))


class TestSolver(unittest.TestCase):

    def setUp(self):
        self.file = MODULE_PATH + "/test_files/builtin_solver/builtin.c"

    def test_solver_type(self):
        self.assertEqual(MakefileSolver.get_solver_type(), 0)
        self.assertEqual(IntrinsicsSolver.get_solver_type(), 1)
        self.assertEqual(BuiltinSolver.get_solver_type(), 2)
        self.assertEqual(MacrosSolver.get_solver_type(), 3)

    def test_extract_code(self):
        lines = [str(i) for i in range(NUMBER_LINES_TOO_LONG + 10)]
        code_too_long, code = Solver.extract_code(lines, 1,
                                                  NUMBER_LINES_TOO_LONG)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        expected = '\n'.join([str(i) for i in range(NUMBER_LINES_TOO_LONG)])
        self.assertEqual(code, expected)

    def test_extract_code_too_long(self):
        lines = [str(i) for i in range(NUMBER_LINES_TOO_LONG + 10)]
        code_too_long, code = Solver.extract_code(lines, 1,
                                                  NUMBER_LINES_TOO_LONG + 1)
        self.assertEqual(code_too_long, CodeTooLong.CODE_TOO_LONG)
        self.assertEqual(code, None)


if __name__ == "__main__":
    unittest.main()
