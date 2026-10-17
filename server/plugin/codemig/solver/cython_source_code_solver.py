import os
import re
import sys
from typing import override

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from plugin.codemig.solver.solver import Solver
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong, ChangeType


class CythonSourceCodeSolver(Solver):
    patterns = [
        # ctypes 相关
        # ctypes.CDLL：加载共享库
        # ctypes.cdll.LoadLibrary：加载共享库的方式
        # cffi.FFI.dlopen：cffi库的动态加载方法
        # 匹配从ctypes导入名称中包含"dll"（不区分大小写）的模块 例如 from ctypes import CDLL
        (r'\b(?:ctypes\.CDLL|ctypes\.cdll\.LoadLibrary|cdll\.LoadLibrary|cffi\.FFI\(\)\.dlopen)\s*',
         'ctypes_dynamic_loading'),
        (r'\bfrom\s+ctypes\s+import\s+\w*[dD][lL][lL]\b', 'ctypes_import'),
    ]

    # 每种模式对应的迁移建议
    migration_advice = {
        'ctypes_dynamic_loading':
            (
                "检测到动态加载C库的调用。请确保目标库有RISC-V版本， 使用.so扩展名而非.dll， 并考虑使用跨平台加载方式"),
        'ctypes_import': (
            "检测到ctypes导入。确保ctypes调用的函数在RISC-V上行为一致，并检查结构体对齐和字节序"),
    }

    compiled_patterns = [(re.compile(p[0]), p[1]) for p in patterns]

    # 查找py文件中调用C库的行号
    @staticmethod
    @override
    def matches_file(file_name):
        # python文件和cython文件
        return file_name.endswith(".pyx")

    @classmethod
    @override
    def solve(cls, source_file):
        return CythonSourceCodeSolver.find_pattern(source_file.get_code_lines(),
                                                   cls.compiled_patterns, cls.migration_advice)

    # 根据匹配规则查找行内容
    @staticmethod
    def find_pattern(lines, compiled_patterns, migration_advice):
        results = []
        for line_number, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            for pattern, pattern_type in compiled_patterns:
                match = pattern.search(line)  # 搜索匹配项
                if pattern.search(line):
                    advice = migration_advice.get(pattern_type, "需要进一步检查RISC-V兼容性")
                    results.append((line_number, line_number, f'匹配到{match.group()}代码，{advice}',
                                    CodeTooLong.HAS_SOURCE_CODE, line))
                    break  # 避免同一行多次匹配
        return results, []

    @staticmethod
    @override
    def append_or_replace():
        return ChangeType.OTHER.value
