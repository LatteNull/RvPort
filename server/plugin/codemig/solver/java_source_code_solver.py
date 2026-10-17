import os
import re
import sys
from typing import override

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from plugin.codemig.codemig_common.migration_class import MigrationClass
from plugin.codemig.solver.solver import Solver
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong, ChangeType


class JavaSourceCodeSolver(Solver):
    # 匹配规则
    # 扩展匹配规则
    patterns = [
        # JNI标准调用
        # System.load 和 System.loadLibrary：加载本地库的标准方式
        # Runtime.getRuntime().loadLibrary：通过运行时加载本地库
        # java.lang.Runtime.getRuntime()
        (r'\b(?:System\s*\.\s*(?:load|loadLibrary)|Native\s*\.\s*loadLibrary)\s*\([^)]*\)',
         'jni_standard_load'),
        (r'\bRuntime\s*\.\s*getRuntime\s*\(\s*\)\s*\.\s*(?:load|loadLibrary)\s*\([^)]*\)',
         'runtime_load'),
        (r'\b(\w+)\s*=\s*(?:java\s*\.\s*lang\s*\.\s*)?\bRuntime\s*\.\s*getRuntime\s*\(\s*\)\s*;', 'runtime_getruntime_variable_class'),
        (r'(\w+)\.(?:load\b|loadLibrary)\s*\(', 'runtime_getruntime_variable'),
    ]

    # 迁移建议字典
    migration_advice = {
        'jni_standard_load': (
            "检测到JNI标准库加载调用。确保本地库有RISC-V版本(.so文件),检查库文件名是否遵循RISC-V命名约定,"
            "考虑使用System.mapLibraryName()获取平台相关库名"
        ),
        'runtime_load':
            ("检测到通过Runtime加载本地库。确保JVM是RISC-V兼容版本,验证库搜索路径包含RISC-V库目录"),
        'runtime_getruntime_variable':
            ("检测到通过Runtime加载本地库。确保JVM是RISC-V兼容版本,验证库搜索路径包含RISC-V库目录"),
    }

    compiled_patterns = [(re.compile(p[0], re.IGNORECASE), p[1]) for p in patterns]

    # 查找Java文件中调用C库（JNI/JNA）的行号
    @staticmethod
    @override
    def matches_file(file_name):
        return file_name.endswith(".java")

    @classmethod
    @override
    def solve(cls, source_file):
        lines = source_file.get_code_lines()
        return JavaSourceCodeSolver.find_pattern(lines, cls.compiled_patterns, cls.migration_advice)

    # 根据匹配规则查找行内容
    @staticmethod
    def find_pattern(lines, compiled_patterns, migration_advice):
        results = []
        tmpclass = []  # 在循环外初始化，用于跨行跟踪 Runtime 变量
        in_multiline_comment = False
        content = ""
        for line_number, line in enumerate(lines, 1):
            line = line.strip()
            if '/*' in line and not in_multiline_comment:
                in_multiline_comment = True
                # 提取 /* 前面的内容（去掉 /*）
                content = line.split('/*', 1)[0]
                # 如果这一行还包含 */，说明是单行 /* ... */ 注释
                if '*/' in line.split('/*', 1)[1]:
                    in_multiline_comment = False
                    content = content + " " + line.split('*/', 1)[1].strip()
                line = content
            elif in_multiline_comment and '*/' in line:
                in_multiline_comment = False
                line = line.split('*/', 1)[1].strip()

            # 同一行中存在 */  xxxx   /* 情况， 未处理
            if in_multiline_comment:
                # 多行注释中的行，直接跳过
                continue
          
            if "//" in line:
                line = line.split('//', 1)[0].strip()

            for pattern, pattern_type in compiled_patterns:
                match = pattern.search(line)  # 搜索匹配项
                if match:
                    if pattern_type == 'runtime_getruntime_variable_class':
                        # 记录 Runtime.getRuntime() 的变量名，用于后续行匹配
                        tmpclass.append(match.group(1))
                        continue
                    if pattern_type == 'runtime_getruntime_variable':
                        # 检查变量名是否在之前定义的 Runtime 变量列表中
                        if match.group(1) not in tmpclass:
                            continue

                    advice = migration_advice.get(pattern_type, "需要进一步检查RISC-V兼容性")
                    results.append((line_number, line_number,
                                    f'匹配到{match.group()}代码，{advice}',
                                    CodeTooLong.HAS_SOURCE_CODE, line))
                    break  # 避免同一行多次匹配
        return results, []

    @staticmethod
    @override
    def append_or_replace():
        return ChangeType.OTHER.value

    @staticmethod
    @override
    def migration_class():
        return MigrationClass.TEXT
