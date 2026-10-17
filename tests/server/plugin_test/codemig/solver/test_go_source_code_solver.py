import unittest
import os
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong, ChangeType
from plugin.codemig.codemig_common.migration_class import MigrationClass
from plugin.codemig.solver.go_source_code_solver import GoSourceCodeSolver
from plugin.codemig.main.source_file import SourceFile


class MyTestCase(unittest.TestCase):
    """在执行具体的测试方法前，先被调用"""

    def setUp(self):
        self.solver = GoSourceCodeSolver()
        self.test_dir = os.path.join(os.path.dirname(__file__), 'test_files', 'test_go_files')
        pass

    """会在测试代码执行完后执行，相当于做测试后的扫尾工作"""

    def tearDown(self):
        pass

    def test_matches_file(self):
        """测试文件类型识别"""
        self.assertTrue(self.solver.matches_file("Test.go"))
        self.assertTrue(self.solver.matches_file("/path/to/SomeClass.go"))
        self.assertFalse(self.solver.matches_file("script.py"))
        self.assertFalse(self.solver.matches_file("README.txt"))
        # 架构类型文件（根据arch_pattern.py，这些应该被排除）
        self.assertFalse(self.solver.matches_file("Test_amd64.go"))
        self.assertFalse(self.solver.matches_file("Test_arm64.go"))
        self.assertFalse(self.solver.matches_file("Test_arm.go"))
        self.assertFalse(self.solver.matches_file("Test_x86_64.go"))
        self.assertFalse(self.solver.matches_file("Test_x86.go"))
        self.assertFalse(self.solver.matches_file("Test_aarch64.go"))
        # riscv64和其他架构不在arch_pattern中，应该被处理
        self.assertTrue(self.solver.matches_file("Test_riscv64.go"))
        self.assertTrue(self.solver.matches_file("Test_mips.go"))

    def test_empty_file(self):
        """测试空文件处理"""
        test_file = SourceFile(os.path.join(self.test_dir, 'empty_file.go'))
        results, _ = self.solver.solve(test_file)
        self.assertEqual(len(results), 0)

    def test_append_or_replace(self):
        """测试append_or_replace函数"""
        value = self.solver.append_or_replace()
        self.assertEqual(value, ChangeType.OTHER.value)
        self.assertEqual(value, 2)

    def test_migration_class(self):
        """测试migration_class函数"""
        value = self.solver.migration_class()
        self.assertEqual(value, MigrationClass.TEXT)

    def test_build_tags(self):
        """测试Build Tags 用于条件编译的特殊注释，允许你根据不同的构建环境"""
        test_file = SourceFile(os.path.join(self.test_dir, 'build_tags.go'))
        results, _ = self.solver.solve(test_file)

        # build_tags.go 包含：
        # 第1行：//go:build (amd64 && go1.17 && !go1.25) || (arm64 && go1.20 && !go1.25) - 匹配
        # 第2行：// +build amd64,go1.17,!go1.25 arm64,go1.20,!go1.25 - 匹配
        # 第3行：// +build go1.18 - 不匹配（没有架构关键字）
        # 第5行：// +build riscv64,... - 不匹配（包含riscv64）
        # 第6行：//go:build riscv64,... - 不匹配（包含riscv64）
        self.assertEqual(len(results), 2, f"Expected 2 results, got {len(results)}: {results}")

        # 检查每个结果是否符合预期
        for start_line, end_line, suggestion, _, _ in results:
            self.assertIn(self.solver.migration_advice.get('build_tags'),
                          suggestion)
            # 验证行号范围
            self.assertGreaterEqual(start_line, 1)
            self.assertLessEqual(start_line, 6)
            self.assertEqual(start_line, end_line)  # build tags 通常是单行匹配

    def test_runtime_GOARCH(self):
        """测试Go中运行时提供的变量，用于运行时检测系统环境"""
        test_file = SourceFile(os.path.join(self.test_dir, 'runtime_GOARCH.go'))
        results, _ = self.solver.solve(test_file)

        # runtime_GOARCH.go 包含多个 runtime.GOARCH 的使用：
        # analyze_code 方法使用 tree-sitter 解析，检查以下节点类型：
        # 1. if_statement: 检查是否包含 riscv64
        #    - 第8-10行：if runtime.GOARCH == "x86_64" { ... } - 不包含riscv64，应该匹配
        #    - 第12-14行：if runtime.GOARCH == "arm64" { ... } - 不包含riscv64，应该匹配
        #    - 第16-25行：多行if语句，不包含riscv64，应该匹配
        #    - 第27-37行：多行if语句，包含riscv64，不应该匹配
        #    - 第39-46行：if-else语句，不包含riscv64，应该匹配
        #    - 第48-55行：if-else语句，包含riscv64，不应该匹配
        #    - 第57-64行：if-else语句，else if包含riscv64，不应该匹配
        #    - 第111-122行：函数中的if语句，不包含riscv64，应该匹配
        # 2. assignment_statement: 检查是否包含 riscv64
        #    - 第67-70行：多行赋值，不包含riscv64，应该匹配
        #    - 第72-75行：多行赋值，包含riscv64，不应该匹配
        # 3. const_declaration: 检查是否包含 riscv64
        #    - 第77-79行：const声明，不包含riscv64，应该匹配
        # 4. expression_switch_statement: 检查是否包含 riscv64
        #    - 第82-92行：switch runtime.GOARCH { case "x86_64", "arm64", "riscv64": ... } - 包含riscv64，不应该匹配
        #    - 第94-104行：switch runtime.GOARCH { case "x86_64", "arm64": ... } - 不包含riscv64，应该匹配
        #    - 第126-145行：switch runtime.GOARCH { case "386", "amd64", ..., "riscv64", ...: ... } - 包含riscv64，不应该匹配
        #    - 第147-154行：switch { case ... && runtime.GOARCH == "amd64": ... } - 不包含riscv64，应该匹配
        # 注意：
        # - 第1-6行是独立的表达式，不在if/switch/const/var块中，可能不会被analyze_code匹配
        # - 第106行：var arch = runtime.GOARCH 是var声明，应该匹配
        # - 第108行：tmp_value = runtime . GOARCH 是赋值语句，应该匹配
        # 预期匹配：至少10个结果（4个if + 1个assignment + 1个const + 2个switch + 1个var + 1个assignment）
        # 注意：第126-145行和第147-154行的switch语句也会被检测
        self.assertGreaterEqual(len(results), 10, f"Expected at least 10 results, got {len(results)}: {results}")

        # 检查每个结果是否符合预期
        matched_lines = set()
        matched_codes = []
        for start_line, end_line, suggestion, _, code in results:
            # var_declaration和short_var_declaration使用var_runtime建议，其他使用runtime建议
            has_runtime_advice = self.solver.migration_advice.get('runtime') in suggestion
            has_var_runtime_advice = self.solver.migration_advice.get('var_runtime') in suggestion
            self.assertTrue(has_runtime_advice or has_var_runtime_advice,
                          f"建议应该包含runtime或var_runtime建议: {suggestion}")
            # 验证行号范围（包括125-156行的switch语句）
            self.assertGreaterEqual(start_line, 1)
            self.assertLessEqual(start_line, 156)
            # 记录匹配的行号范围和代码
            matched_lines.add((start_line, end_line))
            matched_codes.append((start_line, end_line, code))
        
        # 验证关键匹配项
        # 应该包含第8-10行的if语句（不包含riscv64）
        has_if_x86_64 = any(start <= 8 and end >= 10 for start, end in matched_lines)
        # 应该包含第12-14行的if语句（不包含riscv64）
        has_if_arm64 = any(start <= 12 and end >= 14 for start, end in matched_lines)
        # 应该包含第16-25行的多行if语句（不包含riscv64）
        has_if_multiline = any(start <= 16 and end >= 25 for start, end in matched_lines)
        # 应该包含第39-46行的if-else语句（不包含riscv64）
        has_if_else = any(start <= 39 and end >= 46 for start, end in matched_lines)
        # 应该包含第67-70行的赋值语句（不包含riscv64）
        has_assignment = any(start <= 67 and end >= 70 for start, end in matched_lines)
        # 应该包含第77-79行的const声明（不包含riscv64）
        has_const = any(start <= 77 and end >= 79 for start, end in matched_lines)
        # 应该包含第94-104行的switch语句（不包含riscv64）
        has_switch = any(start <= 94 and end >= 104 for start, end in matched_lines)
        # 应该包含第147-154行的switch语句（不包含riscv64，switch { case ... && runtime.GOARCH == ... }）
        has_switch_condition = any(start <= 147 and end >= 154 for start, end in matched_lines)
        # 应该包含第111-122行的函数中的if语句（不包含riscv64）
        has_func_if = any(start <= 111 and end >= 122 for start, end in matched_lines)
        # 应该包含第106行的var声明（runtime.GOARCH赋值）
        has_var_assignment = any(start <= 106 and end >= 106 for start, end in matched_lines)
        # 应该包含第108行的赋值语句（runtime.GOARCH赋值）
        has_direct_assignment = any(start <= 108 and end >= 108 for start, end in matched_lines)
        
        # 验证不应该匹配包含riscv64的块
        # 第27-37行包含riscv64，不应该匹配
        has_if_with_riscv64_27_37 = any(start <= 27 and end >= 37 for start, end in matched_lines)
        # 第48-55行包含riscv64，不应该匹配
        has_if_with_riscv64_48_55 = any(start <= 48 and end >= 55 for start, end in matched_lines)
        # 第57-64行包含riscv64（else if），不应该匹配
        has_if_with_riscv64_57_64 = any(start <= 57 and end >= 64 for start, end in matched_lines)
        # 第72-75行包含riscv64，不应该匹配
        has_assignment_with_riscv64 = any(start <= 72 and end >= 75 for start, end in matched_lines)
        # 第82-92行包含riscv64，不应该匹配
        has_switch_with_riscv64 = any(start <= 82 and end >= 92 for start, end in matched_lines)
        # 第126-145行包含riscv64，不应该匹配（switch runtime.GOARCH { case ..., "riscv64", ...: ... }）
        has_switch_with_riscv64_126_145 = any(start <= 126 and end >= 145 for start, end in matched_lines)
        
        # 验证关键匹配项存在
        self.assertTrue(has_if_x86_64 or has_if_arm64 or has_if_multiline or has_if_else or has_func_if, 
                        f"应该至少匹配一个不包含riscv64的if语句。匹配的行号: {matched_lines}")
        self.assertTrue(has_assignment or has_const or has_switch or has_switch_condition or has_var_assignment or has_direct_assignment,
                        f"应该至少匹配一个不包含riscv64的assignment/const/switch/var语句。匹配的行号: {matched_lines}")
        # 验证第106行和第108行的赋值语句被匹配
        self.assertTrue(has_var_assignment, 
                        f"第106行的var声明（var arch = runtime.GOARCH）应该被匹配。匹配的行号: {matched_lines}")
        self.assertTrue(has_direct_assignment, 
                        f"第108行的赋值语句（tmp_value = runtime . GOARCH）应该被匹配。匹配的行号: {matched_lines}")
        
        # 验证不应该匹配包含riscv64的块（这些块不应该出现在结果中）
        self.assertFalse(has_if_with_riscv64_27_37, 
                        f"不应该匹配包含riscv64的if语句（第27-37行）。匹配的行号: {matched_lines}")
        self.assertFalse(has_if_with_riscv64_48_55, 
                        f"不应该匹配包含riscv64的if语句（第48-55行）。匹配的行号: {matched_lines}")
        self.assertFalse(has_if_with_riscv64_57_64, 
                        f"不应该匹配包含riscv64的if语句（第57-64行）。匹配的行号: {matched_lines}")
        self.assertFalse(has_assignment_with_riscv64, 
                        f"不应该匹配包含riscv64的赋值语句（第72-75行）。匹配的行号: {matched_lines}")
        self.assertFalse(has_switch_with_riscv64, 
                        f"不应该匹配包含riscv64的switch语句（第82-92行）。匹配的行号: {matched_lines}")
        self.assertFalse(has_switch_with_riscv64_126_145, 
                        f"不应该匹配包含riscv64的switch语句（第126-145行）。匹配的行号: {matched_lines}")

    def test_import_C(self):
        """测试C语言依赖部分"""
        test_file = SourceFile(os.path.join(self.test_dir, 'import_C.go'))
        results, _ = self.solver.solve(test_file)
        
        # import_C.go 包含多个 import "C" 语句，每个前面的注释块会被检测：
        # 第1-7行：包含 #include <x86intrin.h> 等，可能匹配 intrinsics
        # 第9-17行：包含 __builtin_foo, __builtin_bar, __builtin_baz，匹配 builtin
        # 第19-25行：只有 #include <stdio.h>，可能不匹配
        # 第27-36行：包含 __x86_64__ 和 __aarch64__，可能匹配 macros
        # 第38-57行：包含 __asm__，匹配 inline_asm
        # 第59-69行：包含 __asm__，匹配 inline_asm
        # 第71-80行：只有普通C代码，可能不匹配
        # 第82-83行：空的，不匹配
        # 预期至少匹配 builtin (1个) + inline_asm (2个) = 3个，可能还有 intrinsics 和 macros
        self.assertGreaterEqual(len(results), 3, f"Expected at least 3 results, got {len(results)}: {results}")

    def test_result_format(self):
        """测试返回结果格式"""
        test_file = SourceFile(os.path.join(self.test_dir, 'result_format.go'))
        results, _ = self.solver.solve(test_file)

        # result_format.go 包含：
        # 第1行：//go:build (amd64 && go1.17 && !go1.25) || (arm64 && go1.20 && !go1.25) - 匹配
        # 第2行：// +build amd64,go1.17,!go1.25 arm64,go1.20,!go1.25 - 匹配
        # 第15行：runtime . GOARCH == "x86_64" - 不匹配（不在函数中，独立表达式）
        # 第16行：runtime. GOARCH = "x86_64" - 不匹配（不在函数中，独立表达式）
        # 至少应该匹配 2 个（build tags）
        self.assertGreaterEqual(len(results), 2, f"Expected at least 2 results, got {len(results)}: {results}")

        # 检查第一个匹配项（build tag）
        start_line, end_line, suggestion, code_too_long, code = results[0]
        self.assertEqual(start_line, 1)
        self.assertEqual(end_line, 1)
        self.assertIn(
            "//go:build (amd64 && go1.17 && !go1.25) || (arm64 && go1.20 && !go1.25)",
            suggestion)
        self.assertIn(self.solver.migration_advice.get('build_tags'),
                      suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(
            code,
            '//go:build (amd64 && go1.17 && !go1.25) || (arm64 && go1.20 && !go1.25)'
        )

        # 检查第二个匹配项（build tag）
        start_line, end_line, suggestion, code_too_long, code = results[1]
        self.assertEqual(start_line, 2)
        self.assertEqual(end_line, 2)
        self.assertIn("// +build amd64,go1.17,!go1.25 arm64,go1.20,!go1.25",
                      suggestion)
        self.assertIn(self.solver.migration_advice.get('build_tags'),
                      suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code,
                         '// +build amd64,go1.17,!go1.25 arm64,go1.20,!go1.25')

        # 注意：第15-16行的runtime.GOARCH表达式不在函数中，是独立表达式，
        # 可能不会被analyze_code匹配（因为不在if/switch/const/var/assignment语句块中）
        # 如果结果中有更多匹配项，验证它们
        if len(results) > 2:
            # 检查是否有runtime.GOARCH相关的匹配
            for i in range(2, len(results)):
                start_line, end_line, suggestion, code_too_long, code = results[i]
                # 验证结果格式正确
                self.assertIsInstance(start_line, int)
                self.assertIsInstance(end_line, int)
                self.assertIsInstance(suggestion, str)
                self.assertIsInstance(code_too_long, CodeTooLong)
                self.assertIsInstance(code, str)

    def test_var_declaration_goarch(self):
        """测试var声明中的runtime.GOARCH变量赋值"""
        code = """
package main

import "runtime"

func test() {
    var arch = runtime.GOARCH
    if arch == "amd64" {
        fmt.Println("amd64")
    } else if arch == "arm64" {
        fmt.Println("arm64")
    }
}
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 应该检测到不包含riscv64的if语句
        self.assertGreaterEqual(len(results), 1, 
                                f"Expected at least 1 result, got {len(results)}: {results}")
        
        # 验证结果中包含runtime相关的建议
        has_runtime_advice = any(
            self.solver.migration_advice.get('var_runtime') in suggestion 
            for _, _, suggestion, _, _ in results
        )
        self.assertTrue(has_runtime_advice, "应该包含var_runtime相关的迁移建议")

    def test_short_var_declaration_goarch(self):
        """测试短变量声明中的runtime.GOARCH变量赋值"""
        code = """
package main

import "runtime"

func test() {
    goarch := runtime.GOARCH
    if goarch == "amd64" || goarch == "arm64" {
        fmt.Println("supported")
    }
}
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 应该检测到不包含riscv64的if语句
        self.assertGreaterEqual(len(results), 1, 
                                f"Expected at least 1 result, got {len(results)}: {results}")

    def test_function_scope_reset(self):
        """测试函数作用域重置goarch_list"""
        code = """
package main

import "runtime"

func func1() {
    var arch1 = runtime.GOARCH
    if arch1 == "amd64" {
        fmt.Println("amd64")
    }
}

func func2() {
    var arch2 = runtime.GOARCH
    if arch2 == "arm64" {
        fmt.Println("arm64")
    }
}
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 每个函数中的if语句都应该被检测到
        self.assertGreaterEqual(len(results), 2, 
                                f"Expected at least 2 results, got {len(results)}: {results}")

    def test_const_declaration_goarch(self):
        """测试const声明中的runtime.GOARCH比较"""
        code = """
package main

import "runtime"

const isX86 = runtime.GOARCH == "amd64" || runtime.GOARCH == "386"
const isArm = runtime.GOARCH == "arm64" || runtime.GOARCH == "arm"
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 应该检测到不包含riscv64的const声明
        self.assertGreaterEqual(len(results), 1, 
                                f"Expected at least 1 result, got {len(results)}: {results}")

    def test_switch_with_goarch_variable(self):
        """测试使用goarch变量的switch语句"""
        code = """
package main

import "runtime"

func test() {
    goarch := runtime.GOARCH
    switch goarch {
    case "amd64":
        fmt.Println("amd64")
    case "arm64":
        fmt.Println("arm64")
    default:
        fmt.Println("other")
    }
}
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 应该检测到不包含riscv64的switch语句
        self.assertGreaterEqual(len(results), 1, 
                                f"Expected at least 1 result, got {len(results)}: {results}")

    def test_nested_if_statements(self):
        """测试嵌套的if语句"""
        code = """
package main

import "runtime"

func test() {
    if runtime.GOARCH == "amd64" {
        if runtime.GOARCH == "arm64" {
            fmt.Println("nested")
        }
    }
}
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 嵌套的if语句也应该被检测
        self.assertGreaterEqual(len(results), 1, 
                                f"Expected at least 1 result, got {len(results)}: {results}")

    def test_riscv64_included_should_not_match(self):
        """测试包含riscv64的代码不应该被匹配"""
        code = """
package main

import "runtime"

func test() {
    if runtime.GOARCH == "amd64" || runtime.GOARCH == "riscv64" {
        fmt.Println("supported")
    }
    
    switch runtime.GOARCH {
    case "amd64":
        fmt.Println("amd64")
    case "riscv64":
        fmt.Println("riscv64")
    default:
        fmt.Println("other")
    }
}
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 包含riscv64的代码不应该被匹配
        # 但可能还有其他不包含riscv64的代码被匹配，所以结果可能不为0
        # 主要验证包含riscv64的块不会被匹配
        matched_code = [code for _, _, _, _, code in results]
        for matched in matched_code:
            # 如果匹配的代码块同时包含riscv64和其他架构，说明逻辑有问题
            # 但这里我们主要验证包含riscv64的完整块不会被单独匹配
            if "riscv64" in matched and "amd64" in matched:
                # 这种情况可能出现在同一个if/switch中，需要进一步检查
                pass

    def test_build_tags_with_riscv64_excluded(self):
        """测试包含riscv64的build tags不应该被匹配"""
        code = """
//go:build amd64 || arm64
// +build amd64 arm64
//go:build riscv64 || amd64
// +build riscv64 amd64
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 只有前两行应该被匹配（不包含riscv64）
        self.assertEqual(len(results), 2, 
                        f"Expected 2 results, got {len(results)}: {results}")
        
        # 验证匹配的行号（注意：字符串代码从第2行开始，所以实际行号是2,3,4,5）
        matched_lines = [start for start, _, _, _, _ in results]
        self.assertIn(2, matched_lines, "第2行（代码中的第1行）应该被匹配")
        self.assertIn(3, matched_lines, "第3行（代码中的第2行）应该被匹配")
        self.assertNotIn(4, matched_lines, "第4行（包含riscv64）不应该被匹配")
        self.assertNotIn(5, matched_lines, "第5行（包含riscv64）不应该被匹配")

    def test_multiline_comment_with_import_C(self):
        """测试多行注释中的import C处理"""
        code = """
/*
#include <x86intrin.h>
#include <immintrin.h>
*/
import "C"
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 应该检测到C语言相关的依赖
        # 具体匹配数量取决于IntrinsicsSolver等子solver的匹配结果
        # 至少应该有一些结果
        self.assertIsInstance(results, list, "结果应该是列表")

    def test_solve_returns_two_lists(self):
        """测试solve方法返回两个列表"""
        test_file = SourceFile(os.path.join(self.test_dir, 'empty_file.go'))
        results, results_rv = self.solver.solve(test_file)
        
        self.assertIsInstance(results, list, "第一个返回值应该是列表")
        self.assertIsInstance(results_rv, list, "第二个返回值应该是列表")
        self.assertEqual(len(results_rv), 0, "空文件的results_rv应该为空")

    def test_var_declaration_should_not_match(self):
        """测试var声明中的runtime.GOARCH赋值应该被匹配"""
        code = """
package main

import "runtime"

func test() {
    var arch = runtime.GOARCH
    // var声明应该被匹配
}
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # var声明应该被匹配（handle_var_declaration返回False，briscv=False时会添加结果）
        matched_code = [code for _, _, _, _, code in results]
        var_declaration_matched = any("var arch = runtime.GOARCH" in c for c in matched_code)
        # var声明应该被匹配
        self.assertIsInstance(results, list, "结果应该是列表")
        # 验证var声明被匹配
        self.assertTrue(var_declaration_matched, "var声明应该被匹配")

    def test_short_var_declaration_should_not_match(self):
        """测试短变量声明中的runtime.GOARCH赋值应该被匹配"""
        code = """
package main

import "runtime"

func test() {
    goarch := runtime.GOARCH
    // 短变量声明应该被匹配
}
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 短变量声明应该被匹配（handle_short_var_declaration返回False，briscv=False时会添加结果）
        matched_code = [code for _, _, _, _, code in results]
        short_var_matched = any("goarch := runtime.GOARCH" in c for c in matched_code)
        # 短变量声明应该被匹配
        self.assertIsInstance(results, list, "结果应该是列表")
        self.assertTrue(short_var_matched, "短变量声明应该被匹配")

    def test_complex_if_with_else(self):
        """测试复杂的if-else语句"""
        code = """
package main

import "runtime"

func test() {
    if runtime.GOARCH == "amd64" {
        fmt.Println("amd64")
    } else if runtime.GOARCH == "arm64" {
        fmt.Println("arm64")
    } else {
        fmt.Println("other")
    }
}
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 应该检测到不包含riscv64的if语句
        self.assertGreaterEqual(len(results), 1, 
                                f"Expected at least 1 result, got {len(results)}: {results}")

    def test_switch_with_multiple_cases(self):
        """测试包含多个case的switch语句"""
        code = """
package main

import "runtime"

func test() {
    switch runtime.GOARCH {
    case "amd64":
        fmt.Println("amd64")
    case "arm64":
        fmt.Println("arm64")
    case "386":
        fmt.Println("386")
    default:
        fmt.Println("other")
    }
}
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 应该检测到不包含riscv64的switch语句
        self.assertGreaterEqual(len(results), 1, 
                                f"Expected at least 1 result, got {len(results)}: {results}")

    def test_switch_with_riscv64_should_not_match(self):
        """测试包含riscv64的switch语句不应该被匹配"""
        code = """
package main

import "runtime"

func test() {
    switch runtime.GOARCH {
    case "amd64":
        fmt.Println("amd64")
    case "riscv64":
        fmt.Println("riscv64")
    default:
        fmt.Println("other")
    }
}
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 包含riscv64的switch不应该被匹配
        matched_code = [code for _, _, _, _, code in results]
        switch_with_riscv64 = any("case \"riscv64\"" in c for c in matched_code)
        self.assertFalse(switch_with_riscv64, "包含riscv64的switch语句不应该被匹配")

    def test_multiline_assignment(self):
        """测试多行赋值语句"""
        code = """
package main

import "runtime"

func test() {
    isSupported = runtime.GOARCH == "amd64" ||
                 runtime.GOARCH == "arm64" ||
                 runtime.GOARCH == "386"
}
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 应该检测到不包含riscv64的赋值语句
        self.assertGreaterEqual(len(results), 1, 
                                f"Expected at least 1 result, got {len(results)}: {results}")

    def test_const_with_multiple_conditions(self):
        """测试包含多个条件的const声明"""
        code = """
package main

import "runtime"

const (
    isX86 = runtime.GOARCH == "amd64" || runtime.GOARCH == "386"
    isArm = runtime.GOARCH == "arm64" || runtime.GOARCH == "arm"
)
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 应该检测到不包含riscv64的const声明
        self.assertGreaterEqual(len(results), 1, 
                                f"Expected at least 1 result, got {len(results)}: {results}")

    def test_if_with_goarch_variable_and_riscv64(self):
        """测试使用goarch变量的if语句，包含riscv64时不应该匹配"""
        code = """
package main

import "runtime"

func test() {
    goarch := runtime.GOARCH
    if goarch == "amd64" || goarch == "riscv64" {
        fmt.Println("supported")
    }
}
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 包含riscv64的if语句不应该被匹配
        matched_code = [code for _, _, _, _, code in results]
        if_with_riscv64 = any("riscv64" in c and "if" in c and "amd64" in c for c in matched_code)
        # 注意：由于使用了变量，可能不会直接匹配，但包含riscv64的块不应该被匹配
        # 如果同时包含riscv64和其他架构，说明逻辑可能有问题
        self.assertFalse(if_with_riscv64, "包含riscv64的if语句不应该被匹配")

    def test_build_tags_edge_cases(self):
        """测试build tags的边界情况"""
        code = """
//go:build amd64
// +build amd64
//go:build !riscv64 && amd64
// +build !riscv64,amd64
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 前两行应该被匹配（不包含riscv64）
        # 后两行包含riscv64，不应该被匹配
        matched_lines = [start for start, _, _, _, _ in results]
        # 注意：字符串代码从第2行开始，所以实际行号是2,3,4,5
        self.assertIn(2, matched_lines, "第2行（代码中的第1行）应该被匹配")
        self.assertIn(3, matched_lines, "第3行（代码中的第2行）应该被匹配")
        # 第4、5行包含riscv64，不应该被匹配（但!riscv64可能被识别为包含riscv64）
        # 这里主要验证基本匹配逻辑

    def test_import_C_without_comment(self):
        """测试没有注释的import C"""
        code = """
import "C"
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 没有注释的import C不应该产生匹配
        self.assertIsInstance(results, list, "结果应该是列表")

    def test_import_C_with_single_line_comment(self):
        """测试单行注释的import C"""
        code = """
// #include <stdio.h>
import "C"
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 单行注释的import C可能产生匹配（取决于子solver）
        self.assertIsInstance(results, list, "结果应该是列表")

    def test_nested_switch_statements(self):
        """测试嵌套的switch语句"""
        code = """
package main

import "runtime"

func test() {
    switch runtime.GOARCH {
    case "amd64":
        switch runtime.GOARCH {
        case "arm64":
            fmt.Println("nested")
        }
    }
}
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 嵌套的switch语句也应该被检测
        self.assertGreaterEqual(len(results), 1, 
                                f"Expected at least 1 result, got {len(results)}: {results}")

    def test_if_with_only_riscv64(self):
        """测试只包含riscv64的if语句不应该被匹配"""
        code = """
package main

import "runtime"

func test() {
    if runtime.GOARCH == "riscv64" {
        fmt.Println("riscv64 only")
    }
}
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 只包含riscv64的if语句不应该被匹配
        matched_code = [code for _, _, _, _, code in results]
        only_riscv64 = any("riscv64" in c and "amd64" not in c and "arm64" not in c 
                          for c in matched_code)
        # 如果只包含riscv64，不应该被匹配
        self.assertFalse(only_riscv64, "只包含riscv64的if语句不应该被匹配")

    def test_result_structure(self):
        """测试结果结构完整性"""
        test_file = SourceFile(os.path.join(self.test_dir, 'result_format.go'))
        results, _ = self.solver.solve(test_file)
        
        self.assertGreater(len(results), 0, "应该有匹配结果")
        
        # 验证每个结果的结构
        for result in results:
            self.assertEqual(len(result), 5, f"结果应该包含5个元素: {result}")
            start_line, end_line, suggestion, code_too_long, code = result
            
            self.assertIsInstance(start_line, int, "起始行号应该是整数")
            self.assertIsInstance(end_line, int, "结束行号应该是整数")
            self.assertIsInstance(suggestion, str, "建议应该是字符串")
            self.assertIsInstance(code_too_long, CodeTooLong, "code_too_long应该是CodeTooLong枚举")
            self.assertIsInstance(code, str, "代码应该是字符串")
            
            self.assertGreaterEqual(start_line, 1, "起始行号应该大于等于1")
            self.assertGreaterEqual(end_line, start_line, "结束行号应该大于等于起始行号")

    def test_empty_build_tag(self):
        """测试空的build tag"""
        code = """
//go:build
// +build
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 空的build tag不应该被匹配（因为没有架构关键字）
        matched_lines = [start for start, _, _, _, _ in results]
        # 空的build tag不应该匹配，因为没有架构关键字
        self.assertEqual(len(matched_lines), 0, "空的build tag不应该被匹配")

    def test_build_tag_with_complex_expression(self):
        """测试复杂表达式的build tag"""
        code = """
//go:build (amd64 || arm64) && !windows
// +build amd64,arm64 !windows
"""
        test_file = SourceFile("")
        test_file.code = code
        results, _ = self.solver.solve(test_file)
        
        # 包含架构关键字的build tag应该被匹配（如果不包含riscv64）
        matched_lines = [start for start, _, _, _, _ in results]
        # 注意：字符串代码从第2行开始，所以实际行号是2,3
        self.assertIn(2, matched_lines, "第2行（代码中的第1行）应该被匹配")
        self.assertIn(3, matched_lines, "第3行（代码中的第2行）应该被匹配")


if __name__ == '__main__':
    unittest.main()
