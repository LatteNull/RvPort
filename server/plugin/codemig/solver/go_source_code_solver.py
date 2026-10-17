import sys
import os
import re
from typing import override

from tree_sitter import Language, Parser
import tree_sitter_go as tsg

GO_LANGUAGE = Language(tsg.language())

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from plugin.codemig.codemig_common.arch_pattern import ArchPattern
from plugin.codemig.solver.solver import Solver
from plugin.codemig.codemig_common.migration_class import MigrationClass
from plugin.codemig.solver.intrinsics_solver import IntrinsicsSolver
from plugin.codemig.solver.builtin_solver import BuiltinSolver
from plugin.codemig.solver.macros_solver import MacrosSolver
from plugin.codemig.solver.inline_asm_solver import InlineAsmSolver
from plugin.codemig.main.source_file import SourceFile
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong, ChangeType


class GoSourceCodeSolver(Solver):
    # 源码匹配规则
    source_patterns = [
        # Build Tags 是用于条件编译的特殊注释，允许你根据不同的构建环境，通常出现在 .go 文件的开头
        # 新格式（Go 1.17+）：//go:build ...   旧格式（兼容性）：// +build ...
        # 增加负向先行断言  确保 riscv64 不在匹配范围内
        (r'(//\s*go:build\s+(?=.*(?:x86_64|x86|amd64|arm|arm64|aarch64)\b)(?!.*riscv64\b).*$)|'
         r'(//\s*\+build\s+(?=.*(?:x86_64|x86|amd64|arm|arm64|aarch64)\b)(?!.*riscv64\b).*$)',
         'build_tags'),
    ]

    # 每种模式对应的迁移建议
    migration_advice = {
        'build_tags': (
            "检测到静态条件编译中特殊注释部分，请判断编译内容中是否支持rv架构，如不支持，请判断在这部分内容中，"
            "是否需要增加新的.go文件，来支持rv架构。"),
        'runtime': (
            "检测到动态条件编译部分，请判断动态条件编译部分中，是否包含rv架构的内容，若不包含，"
            "请判断该部分代码是否需要添加rv架构内容。"),
        'var_runtime': (
            "检测到动态架构检测被赋值给变量，请检查该变量的处理逻辑中，是否包含rv架构的内容，若不包含，"
            "请判断该部分代码是否需要添加rv架构内容。"),
        'C': (
            "检测到C语言依赖部分，请判断C语言依赖部分是否支持rv架构，若不支持，请为目标平台构建C语言库，"
            "或者寻找纯Go的替代方案。"),
    }

    # 源码扫描器
    compiled_patterns = [(re.compile(p[0]), p[1]) for p in source_patterns]

    @staticmethod
    @override
    def matches_file(file_name):
        return file_name.endswith(".go") and not ArchPattern.is_arch_pattern(file_name)

    @classmethod
    @override
    def solve(cls, source_file):
        results = []
        results_rv = []
        result1, result_rv1 = GoSourceCodeSolver.analyze_code(source_file.get_code(),  cls.compiled_patterns,
                                               cls.migration_advice)
        result2, result_rv2 = GoSourceCodeSolver.find_pattern(source_file.get_code_lines(), cls.compiled_patterns,
                                               cls.migration_advice)

        results.extend(result1)
        results.extend(result2)
        results_rv.extend(result_rv1)
        results_rv.extend(result_rv2)
        return results, results_rv

    # 根据匹配规则查找行内容
    @staticmethod
    def find_pattern(lines, compiled_patterns, migration_advice):
        results = []
        # found = []
        # 多行匹配 C语言依赖部分
        content = ""  # 存储纯注释内容（去掉 //, /*, */）
        comment_start_line = None
        in_multiline_comment = False
        for line_number, line in enumerate(lines, 1):
            line = line.strip()

            # 处理多行注释开始
            if '/*' in line and not in_multiline_comment:
                in_multiline_comment = True
                comment_start_line = line_number
                # 提取 /* 后面的内容（去掉 /*）
                comment_content = line.split('/*', 1)[1]
                # 如果这一行还包含 */，说明是单行 /* ... */ 注释
                if '*/' in comment_content:
                    in_multiline_comment = False
                    # 去掉 */ 并取前面的内容
                    comment_content = comment_content.split('*/', 1)[0].strip()
                    if comment_content:
                        content = comment_content
                else:
                    # 纯 /* 开头，暂存内容
                    content = comment_content.strip()

            # 处理多行注释内容
            elif in_multiline_comment:
                if '*/' in line:
                    in_multiline_comment = False
                    # 去掉 */ 并取前面的内容
                    comment_content = line.split('*/', 1)[0].strip()
                    if comment_content:
                        content += "\n" + comment_content
                else:
                    # 完全在注释中的行，直接存储（去掉缩进）
                    content += "\n" + line

            # 处理单行注释（非多行注释内的）
            elif not in_multiline_comment and line.startswith('//'):
                if not content:  # 新的单行注释块开始
                    comment_start_line = line_number
                    # 去掉 // 并保留后面的内容
                comment_content = line.split('//', 1)[1].strip()
                if content:
                    content += "\n" + comment_content
                else:
                    content = comment_content

            # 处理 import "C"
            else:
                if 'import "C"' in line and content:
                    # 关联注释块与 import "C"
                    source_file = SourceFile("")
                    source_file.code = content
                    solvers = [
                        IntrinsicsSolver.solve,
                        BuiltinSolver.solve,
                        MacrosSolver.solve,
                        InlineAsmSolver.solve
                    ]

                    for solver in solvers:
                        solver_results, _ = solver(source_file)
                        if solver_results:
                            for result in solver_results:
                                result[0] = result[0] + comment_start_line - 1
                                result[1] = result[1] + comment_start_line - 1
                            results.extend(solver_results)
                content = ""

            for pattern, pattern_type in compiled_patterns:
                match = pattern.search(line)  # 搜索匹配项
                if pattern.search(line) and pattern_type == 'build_tags':
                    advice = migration_advice.get(pattern_type, "需要进一步检查RISC-V兼容性")
                    results.append((line_number, line_number, f'匹配到{match.group()}代码，{advice}',
                                    CodeTooLong.HAS_SOURCE_CODE, line))
                    break  # 避免同一行多次匹配
        return results, []

    @staticmethod
    def analyze_code(content, compiled_patterns, migration_advice):
        parser = Parser(GO_LANGUAGE)
        tree = parser.parse(bytes(content, 'utf-8'))
        compare_patterns = [
            (r'runtime\s*\.\s*GOARCH\s*==\s*["\']([^"\']+)["\']', 'equal'),
            (r'runtime\s*\.\s*GOARCH\s*!=\s*["\']([^"\']+)["\']', 'not_equal')
        ]
        compiled_compare_patterns = [(re.compile(p[0]), p[1]) for p in compare_patterns]
        goarch_pattern = r'\bruntime\s*\.\s*GOARCH\s*'
        goarch_pattern_compiled = re.compile(goarch_pattern)

        handle_if_binary_list = []
        # 返回值 是否支持riscv64架构  true: 支持; false: 不支持，需要提示
        def handle_if_statement(node) -> bool:
            # if 没有 riscv64, 最后有 else, 提示
            # if 没有 riscv64, 最后没有 else, 提示
            # if 有 riscv64，不提示； 与提示同时存在，不提示
            # 判断中没有 GOARCH, 不提示； 与提示同时存在，提示
            ret_list = [0, 0, 0] # 0: 不支持riscv64提示; 1: 支持riscv64不提示, 2: 没有GOARCH不提示
            value_list = [0, 0, 0]
            for child in node.children:
                if child.type == "block":
                    # 处理同级的if
                    continue
                elif child.type == "if_statement":
                    value_list =  handle_if_statement(child)
                elif child.type == "binary_expression":
                    info = (node.start_point.row, node.start_point.column, node.end_point.row, node.end_point.column)
                    if info in handle_if_binary_list:
                        continue
                    handle_if_binary_list.append(info)
                    tmp_content = node.text.decode()
                    for pattern, pattern_type in compiled_compare_patterns:
                        match = pattern.findall(tmp_content)
                        if pattern_type == "equal":
                            if len(match) > 0:
                                if "riscv64" not in match:
                                    ret_list[0] += 1
                                else:
                                    ret_list[1] += 1
                            else:
                                ret_list[2] += 1
                        elif pattern_type == "not_equal":
                            if len(match) > 0:
                                if "riscv64" in match:
                                    ret_list[0] += 1
                                else:
                                    ret_list[1] += 1
                            else:
                                ret_list[2] += 1
            ret_list = [a + b for a, b in zip(ret_list, value_list)]
            return ret_list

        def handle_expression_switch_statement(node) -> bool:
            """
            处理 switch 语句，检查是否包含 riscv64
            支持两种形式：
            1. switch runtime.GOARCH { case "386", "amd64", ... : ... }
            2. switch { case ... && runtime.GOARCH == "amd64": ... }
            """
            tmp_content = node.text.decode()
            match = goarch_pattern_compiled.search(tmp_content)
            if match is None:
                return True

            bstart = False
            switch_content = ""
            case_content_list = []
            for child in node.children:
                if child.type == "switch":
                    bstart = True
                    continue
                elif child.type == "{":
                    bstart = False
                    continue
                elif child.type == "expression_case":
                    for tmp_child in child.children:
                        if tmp_child.type == "expression_list":
                            case_content_list.append(tmp_child.text.decode())

                if bstart:
                    switch_content += " " + child.text.decode()

            if len(switch_content) == 0:
                bsupport = True
                for pattern, pattern_type in compiled_compare_patterns:
                    matchs = pattern.findall(tmp_content)
                    for match in matchs:
                        if pattern_type == "equal":
                            # 如果包含riscv64，不匹配（返回True）；如果不包含riscv64，匹配（返回False）
                            if "riscv64" in match:
                                return True  # 包含riscv64，不匹配
                            else:
                                bsupport = False  # 不包含riscv64，匹配
                        elif pattern_type == "not_equal":
                            # 如果包含riscv64（即 != "riscv64"），匹配（返回False）；如果不包含riscv64，不匹配（返回True）
                            if "riscv64" in match:
                                return False  # 明确排除riscv64，需要匹配
                            else:
                                bsupport = True  # 没有排除riscv64，不匹配

                if not bsupport:
                    return False 

            else:
                match = goarch_pattern_compiled.search(switch_content)
                if match is None:
                    return True
                bsupport = False
                for line in case_content_list:
                    if "riscv64" in line:
                        bsupport = True
                        break
                return bsupport


        def handle_assignment_statement(node) -> bool:
            tmp_content = node.text.decode()
            # 检查比较操作：runtime.GOARCH == "xxx" 或 runtime.GOARCH != "xxx"
            matched = False
            bsupport = True
            for pattern, pattern_type in compiled_compare_patterns:
                matchs = pattern.findall(tmp_content)
                for match in matchs:
                    matched = True
                    if pattern_type == "equal":
                        # 如果包含riscv64，不匹配（返回True）；如果不包含riscv64，匹配（返回False）
                        if "riscv64" in match:
                            return True  # 包含riscv64，不匹配
                        else:
                            bsupport = False  # 不包含riscv64，匹配
                    elif pattern_type == "not_equal":
                        # 如果包含riscv64（即 != "riscv64"），匹配（返回False）；如果不包含riscv64，不匹配（返回True）
                        if "riscv64" in match:
                            return False  # 明确排除riscv64，需要匹配
                        else:
                            bsupport = True  # 没有排除riscv64，不匹配

            if not bsupport:
                return False 

            if not matched:
                # 检查直接赋值：variable = runtime.GOARCH
                direct_assignment_pattern = re.compile(r'(\w+)\s*=\s*runtime\s*\.\s*GOARCH\b')
                direct_match = direct_assignment_pattern.search(tmp_content)
                if direct_match:
                    # 直接赋值应该被匹配（因为后续可能使用该变量进行架构判断）
                    return False
            return True

        def handle_const_spec(node) -> bool:
            tmp_content = node.text.decode()
            for pattern, pattern_type in compiled_compare_patterns:
                match = pattern.findall(tmp_content)
                if len(match) > 0:
                    if pattern_type == "equal" and "riscv64" not in match:
                        return False
                    elif pattern_type == "not_equal" and "riscv64" in match:
                        return False
            return True

        def handle_var_declaration(node):
            tmp_content = node.text.decode()
            pattern = re.compile(r'(\w+)\s*=\s*runtime\s*\.\s*GOARCH')
            match = pattern.search(tmp_content)
            if match:
                return False
            return True
        
        def handle_short_var_declaration(node):
            pattern = re.compile( r'(\w+)\s*:?=\s*runtime\s*\.\s*GOARCH')
            tmp_content = node.text.decode()
            match = pattern.search(tmp_content)
            if match:
                return False
            return True


        results = []
        def walk(node, depth=0):
            """
            1. runtime.GOARCH 的变量赋值情况
            2. runtime.GOARCH 的 if 判断情况
            3. runtime.GOARCH 的 switch 判断情况
            """
            briscv = True
            base_pattern = re.compile(r'runtime\s*\.\s*GOARCH\s*')

            pass_list = ["comment"]
            if node.type in pass_list:
                return

            # code 中， 没有runtime.GOARCH 不处理;
            match = base_pattern.search(node.text.decode())
            if not match:
                return

            if node.type == "if_statement":
                ret_list = handle_if_statement(node)
                if ret_list[0] > 0 and ret_list[1] == 0:
                    briscv = False
                else:
                    briscv = True
            elif node.type == "assignment_statement":
                briscv = handle_assignment_statement(node)
            elif node.type == "const_declaration":
                briscv = handle_const_spec(node)
            elif node.type == "expression_switch_statement":
                briscv = handle_expression_switch_statement(node)
            elif node.type == "var_declaration":
                briscv = handle_var_declaration(node)
            elif node.type == "short_var_declaration":
                briscv = handle_short_var_declaration(node)
            else:
                pass

            if not briscv:
                # 对于var_declaration和short_var_declaration，使用var_runtime建议
                if node.type == "var_declaration" or node.type == "short_var_declaration":
                    advice = migration_advice.get('var_runtime', "需要进一步检查RISC-V兼容性")
                else:
                    advice = migration_advice.get('runtime', "需要进一步检查RISC-V兼容性")
                info = (node.start_point.row + 1, node.end_point.row + 1, f'匹配到runtime.GOARCH相关代码，{advice}',
                                    CodeTooLong.HAS_SOURCE_CODE, node.text.decode())
                results.append(info)
                return

            for child in node.children:
                walk(child, depth + 1)

        walk(tree.root_node)
        return results, []

    @staticmethod
    @override
    def append_or_replace():
        return ChangeType.OTHER.value

    @staticmethod
    @override
    def migration_class():
        return MigrationClass.TEXT
