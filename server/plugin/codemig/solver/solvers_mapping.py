from enum import Enum

# pylint: disable=too-few-public-methods
class SolverType(Enum):
    MAKEFILE = (0, "Makefile")
    INTRINSICS = (1, "内联函数")
    BUILTIN = (2, "内置函数")
    MACROS = (3, "宏定义")
    INLINE_ASM = (4, "内联汇编")
    ASM_FILE = (5, "汇编文件")
    JAVA_SOURCE_CODE = (6, "Java源代码")
    PYTHON_SOURCE_CODE = (7, "Python源代码")
    GO_SOURCE_CODE = (8, "Go源代码")
    SHELL_SOURCE_CODE = (9, "Shell源代码")
    BUILD_SCRIPT = (10, "构建脚本")
    GO_RELEASER_TML = (11, "GO配置文件")
    RUST_SOURCE_CODE = (12, "Rust源代码")
    RUST_TOML_CODE = (13, "Rust配置文件")

    def __new__(cls, value, description):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.description = description
        return obj


SOLVERS_MAPPING = {
    'MakefileSolver': SolverType.MAKEFILE,
    'IntrinsicsSolver': SolverType.INTRINSICS,
    'BuiltinSolver': SolverType.BUILTIN,
    'MacrosSolver': SolverType.MACROS,
    'InlineAsmSolver': SolverType.INLINE_ASM,
    'AsmFileSolver': SolverType.ASM_FILE,
    'JavaSourceCodeSolver': SolverType.JAVA_SOURCE_CODE,
    'PythonSourceCodeSolver': SolverType.PYTHON_SOURCE_CODE,
    'CythonSourceCodeSolver': SolverType.PYTHON_SOURCE_CODE,
    'GoSourceCodeSolver': SolverType.GO_SOURCE_CODE,
    'ShellSourceCodeSolver': SolverType.SHELL_SOURCE_CODE,
    'BuildScriptSolver': SolverType.BUILD_SCRIPT,
    'GoReleaserYmlSolver': SolverType.GO_RELEASER_TML,
    'CMakeSolver': SolverType.BUILD_SCRIPT,
    'BuildMesonSolver': SolverType.BUILD_SCRIPT,
    'RustSourceCodeSolver': SolverType.RUST_SOURCE_CODE,
    'RustTomlSolver': SolverType.RUST_TOML_CODE
}


def solver_to_str(solver_name):
    return SOLVERS_MAPPING[solver_name].value
