import os
from collections import defaultdict
import sys

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from plugin.codemig.solver.solver import Solver
from plugin.codemig.solver.makefile_solver import MakefileSolver
from plugin.codemig.solver.intrinsics_solver import IntrinsicsSolver
from plugin.codemig.solver.builtin_solver import BuiltinSolver
from plugin.codemig.solver.macros_solver import MacrosSolver
from plugin.codemig.solver.inline_asm_solver import InlineAsmSolver
from plugin.codemig.solver.asm_file_solver import AsmFileSolver
from plugin.codemig.solver.java_source_code_solver import JavaSourceCodeSolver
from plugin.codemig.solver.python_source_code_solver import PythonSourceCodeSolver
from plugin.codemig.solver.cython_source_code_solver import CythonSourceCodeSolver
from plugin.codemig.solver.software_solver import SoftwareSolver
from plugin.codemig.main.source_file import SourceFile
from plugin.codemig.solver.go_source_code_solver import GoSourceCodeSolver
from plugin.codemig.solver.build_script_solver import BuildScriptSolver
from plugin.codemig.solver.build_meson_solver import BuildMesonSolver
from plugin.codemig.solver.shell_source_code_solver import ShellSourceCodeSolver
from plugin.codemig.solver.go_releaser_yml_solver import GoReleaserYmlSolver
from plugin.codemig.solver.cmake_solver import CMakeSolver
from plugin.codemig.solver.rust_source_code_solver import RustSourceCodeSolver
from plugin.codemig.solver.rust_toml_solver import RustTomlSolver
from plugin.codemig.main.C_sencond_processor import post_process_file


class CodemigProcessor:
    my_solvers = [
        MakefileSolver,
        IntrinsicsSolver,
        BuiltinSolver,
        MacrosSolver,
        InlineAsmSolver,
        AsmFileSolver,
        JavaSourceCodeSolver,
        PythonSourceCodeSolver,
        CythonSourceCodeSolver,
        GoSourceCodeSolver,
        SoftwareSolver,
        BuildScriptSolver,
        BuildMesonSolver,
        CMakeSolver,
        ShellSourceCodeSolver,
        GoReleaserYmlSolver,
        RustSourceCodeSolver,
        RustTomlSolver
    ]

    @classmethod
    def create_my_solvers(cls):
        return defaultdict(lambda: ([], []), {solver: ([], []) for solver in cls.my_solvers})

    @classmethod
    def process_file(cls, file_path):
        file_solvers_result = cls.create_my_solvers()
        file_name = os.path.basename(file_path)
        source_file = SourceFile(file_path)
        for solver, result_list in file_solvers_result.items():
            change_list, found_list = result_list
            if solver.matches_file(file_name):
                result, found = solver.solve(source_file)
                change_list.extend(result)
                found_list.extend(found)
        post_process_file(source_file, file_solvers_result)

        # 特殊处理,当A的行包含b的起止行,则只报外层问题即可
        return file_solvers_result
