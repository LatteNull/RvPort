import os
import unittest
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong, ChangeType
from plugin.codemig.codemig_common.migration_class import MigrationClass
from plugin.codemig.main.source_file import SourceFile
from plugin.codemig.solver.java_source_code_solver import JavaSourceCodeSolver


class TestJavaSourceCodeSolver(unittest.TestCase):
    """JavaSourceCodeSolver 测试类"""

    def setUp(self):
        """测试前准备"""
        self.solver = JavaSourceCodeSolver()
        self.test_dir = os.path.join(os.path.dirname(__file__), 'test_files', 'test_java_files')

    def tearDown(self):
        """测试后清理"""
        pass

    def test_matches_file(self):
        """测试文件类型识别"""
        self.assertTrue(self.solver.matches_file("Test.java"))
        self.assertTrue(self.solver.matches_file("/path/to/SomeClass.java"))
        self.assertFalse(self.solver.matches_file("script.py"))
        self.assertFalse(self.solver.matches_file("README.txt"))

    def test_empty_file(self):
        """测试空文件处理"""
        test_file = SourceFile(os.path.join(self.test_dir, 'empty_file.java'))
        results, _ = self.solver.solve(test_file)
        self.assertEqual(len(results), 0)

    def test_append_or_replace(self):
        """测试append_or_replace函数"""
        value = self.solver.append_or_replace()
        self.assertEqual(value, ChangeType.OTHER.value)

    def test_migration_class(self):
        """测试migration_class函数"""
        value = self.solver.migration_class()
        self.assertEqual(value, MigrationClass.TEXT)

    def test_jni_standard_load(self):
        """测试标准JNI加载模式"""
        test_file = SourceFile(
            os.path.join(self.test_dir, 'jni_standard_load.java'))
        results, _ = self.solver.solve(test_file)

        # jni_standard_load.java 包含：
        # 第1行: System.loadLibrary("mylib") - 匹配 jni_standard_load
        # 第2行: System. load ("/path/lib.so") - 匹配 jni_standard_load (System.load)
        # 第3行: Native.loadLibrary("jni", MyClass.class) - 匹配 jni_standard_load
        # 第4行: loader.loadLibrary("x") - 不匹配（不是 System 或 Native）
        # 预期：3个匹配项
        self.assertEqual(len(results), 3, f"Expected 3 results, got {len(results)}: {results}")

        # 检查每个结果是否符合预期
        for start_line, end_line, suggestion, _, _ in results:
            self.assertIn(self.solver.migration_advice.get('jni_standard_load'),
                          suggestion)
            # 验证行号范围
            self.assertGreaterEqual(start_line, 1)
            self.assertLessEqual(start_line, 4)
            self.assertEqual(start_line, end_line)

    def test_runtime_load(self):
        """测试Runtime加载模式"""
        test_file = SourceFile(os.path.join(self.test_dir, 'runtime_load.java'))
        results, _ = self.solver.solve(test_file)

        # runtime_load.java 包含：
        # 第1行: Runtime.getRuntime().load("lib.so") - 匹配 runtime_load
        # 第2行: Runtime. getRuntime (). loadLibrary ("mylib") - 匹配 runtime_load
        # 第3行: runtime.load() - 不匹配（没有对应的 Runtime.getRuntime() 变量定义）
        # 注意：runtime_getruntime_variable 模式需要先有变量定义，但当前实现中 tmpclass 每行重置
        # 预期：2个匹配项
        self.assertEqual(len(results), 2, f"Expected 2 results, got {len(results)}: {results}")

        # 检查每个结果是否符合预期
        for start_line, end_line, suggestion, _, _ in results:
            self.assertIn(self.solver.migration_advice.get('runtime_load'),
                          suggestion)
            # 验证行号范围
            self.assertGreaterEqual(start_line, 1)
            self.assertLessEqual(start_line, 3)
            self.assertEqual(start_line, end_line)

    def test_result_format(self):
        """测试返回结果格式"""
        test_file = SourceFile(os.path.join(self.test_dir,
                                            'result_format.java'))
        results, _ = self.solver.solve(test_file)

        # result_format.java 包含：
        # 第2行: System.loadLibrary("valid"); - 匹配 jni_standard_load
        # 第4行: Runtime.getRuntime().load("test.so"); - 匹配 runtime_load
        # 第6行: System.load("/path/to/lib.so"); - 匹配 jni_standard_load
        # 第10行: Native.loadLibrary("jnalib", MyClass.class); - 匹配 jni_standard_load
        # 预期：4个匹配项
        self.assertEqual(len(results), 4, f"Expected 4 results, got {len(results)}: {results}")

        # 检查第一个匹配项
        start_line, end_line, suggestion, code_too_long, code = results[0]
        self.assertEqual(start_line, 2)
        self.assertEqual(end_line, 2)
        self.assertIn("System.loadLibrary", suggestion)
        self.assertIn(self.solver.migration_advice.get('jni_standard_load'),
                      suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code, 'System.loadLibrary("valid");')

        # 检查第二个匹配项
        start_line, end_line, suggestion, code_too_long, code = results[1]
        self.assertEqual(start_line, 4)
        self.assertEqual(end_line, 4)
        self.assertIn("Runtime.getRuntime().load", suggestion)
        self.assertIn(self.solver.migration_advice.get('runtime_load'),
                      suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code, 'Runtime.getRuntime().load("test.so");')

        # 检查第三个匹配项
        start_line, end_line, suggestion, code_too_long, code = results[2]
        self.assertEqual(start_line, 6)
        self.assertEqual(end_line, 6)
        self.assertIn("System.load", suggestion)
        self.assertIn(self.solver.migration_advice.get('jni_standard_load'),
                      suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code, 'System.load("/path/to/lib.so");')

        # 检查第四个匹配项
        start_line, end_line, suggestion, code_too_long, code = results[3]
        self.assertEqual(start_line, 10)
        self.assertEqual(end_line, 10)
        self.assertIn("Native.loadLibrary", suggestion)
        self.assertIn(self.solver.migration_advice.get('jni_standard_load'),
                      suggestion)
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code, 'Native.loadLibrary("jnalib", MyClass.class);')

    def test_runtime_variable(self):
        """测试Runtime变量模式（先定义变量，后使用）"""
        test_file = SourceFile(os.path.join(self.test_dir, 'runtime_variable.java'))
        results, _ = self.solver.solve(test_file)
        
        # runtime_variable.java 包含：
        # 第3行: Runtime runtime = Runtime.getRuntime(); - 匹配 runtime_getruntime_variable_class（记录变量名 "runtime"），continue，不产生结果
        # 第4行: runtime.load("test.so"); - 匹配 runtime_getruntime_variable（使用变量 "runtime"），产生结果
        # 第5行: runtime.loadLibrary("mylib"); - 匹配 runtime_getruntime_variable（使用变量 "runtime"），产生结果
        # 第7行: Runtime rt = Runtime.getRuntime(); - 匹配 runtime_getruntime_variable_class（记录变量名 "rt"），continue，不产生结果
        # 第8行: rt.load("another.so"); - 匹配 runtime_getruntime_variable（使用变量 "rt"），产生结果
        # 第14行: java.lang.System.loadLibrary("fullname_lib"); - 匹配 jni_standard_load
        # 第16行: java.lang.Runtime rt2 = java.lang.Runtime.getRuntime(); - 匹配 runtime_getruntime_variable_class（记录变量名 "rt2"），continue，不产生结果
        # 第17行: rt2.load("/full/path/lib.so"); - 匹配 runtime_getruntime_variable（使用变量 "rt2"），产生结果
        # 预期：5个匹配项（第4、5、8、14、17行）
        self.assertEqual(len(results), 5, f"Expected 5 results, got {len(results)}: {results}")
        
        # 按行号排序结果以便检查
        results_sorted = sorted(results, key=lambda x: x[0])
        
        # 检查第4行：runtime.load("test.so")
        start_line, end_line, suggestion, code_too_long, code = results_sorted[0]
        self.assertEqual(start_line, 4)
        self.assertEqual(end_line, 4)
        self.assertIn(
            self.solver.migration_advice.get('runtime_getruntime_variable'),
            suggestion,
            f"Suggestion should contain runtime_getruntime_variable advice: {suggestion}"
        )
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code.strip(), 'runtime.load("test.so");')
        
        # 检查第5行：runtime.loadLibrary("mylib")
        start_line, end_line, suggestion, code_too_long, code = results_sorted[1]
        self.assertEqual(start_line, 5)
        self.assertEqual(end_line, 5)
        self.assertIn(
            self.solver.migration_advice.get('runtime_getruntime_variable'),
            suggestion,
            f"Suggestion should contain runtime_getruntime_variable advice: {suggestion}"
        )
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code.strip(), 'runtime.loadLibrary("mylib");')
        
        # 检查第8行：rt.load("another.so")
        start_line, end_line, suggestion, code_too_long, code = results_sorted[2]
        self.assertEqual(start_line, 8)
        self.assertEqual(end_line, 8)
        self.assertIn(
            self.solver.migration_advice.get('runtime_getruntime_variable'),
            suggestion,
            f"Suggestion should contain runtime_getruntime_variable advice: {suggestion}"
        )
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code.strip(), 'rt.load("another.so");')
        
        # 检查第14行：java.lang.System.loadLibrary("fullname_lib")
        start_line, end_line, suggestion, code_too_long, code = results_sorted[3]
        self.assertEqual(start_line, 14)
        self.assertEqual(end_line, 14)
        self.assertIn(
            self.solver.migration_advice.get('jni_standard_load'),
            suggestion,
            f"Suggestion should contain jni_standard_load advice: {suggestion}"
        )
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertIn("java.lang.System.loadLibrary", code)
        
        # 检查第17行：rt2.load("/full/path/lib.so")
        start_line, end_line, suggestion, code_too_long, code = results_sorted[4]
        self.assertEqual(start_line, 17)
        self.assertEqual(end_line, 17)
        self.assertIn(
            self.solver.migration_advice.get('runtime_getruntime_variable'),
            suggestion,
            f"Suggestion should contain runtime_getruntime_variable advice: {suggestion}"
        )
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code.strip(), 'rt2.load("/full/path/lib.so");')

    def test_comment_lines(self):
        """测试注释行被正确跳过"""
        test_code = """
// System.loadLibrary("commented");
/* System.load("commented.so"); */
System.loadLibrary("valid");
"""
        test_file = SourceFile("")
        test_file.code = test_code
        results, _ = self.solver.solve(test_file)
        # 应该只匹配第5行的 System.loadLibrary
        self.assertEqual(len(results), 1, f"Expected 1 result, got {len(results)}: {results}")
        start_line, end_line, suggestion, _, code = results[0]
        self.assertIn("System.loadLibrary", suggestion)
        self.assertIn("valid", code)

    def test_multiline_comment(self):
        """测试跨行多行注释被正确跳过"""
        test_code = """
/* 
 * System.loadLibrary("commented1");
 * Runtime.getRuntime().load("commented2.so");
 */
System.loadLibrary("valid1");
/*
Runtime.getRuntime().loadLibrary("commented3");
*/
System.load("valid2.so");
"""
        test_file = SourceFile("")
        test_file.code = test_code
        results, _ = self.solver.solve(test_file)
        # 应该只匹配第6行和第10行的有效代码
        self.assertEqual(len(results), 2, f"Expected 2 results, got {len(results)}: {results}")
        # 验证结果行号
        result_lines = [r[0] for r in results]
        self.assertIn(6, result_lines)
        self.assertIn(10, result_lines)

    def test_empty_lines(self):
        """测试空行被正确跳过"""
        test_code = """

System.loadLibrary("test");

"""
        test_file = SourceFile("")
        test_file.code = test_code
        results, _ = self.solver.solve(test_file)
        # 应该只匹配第3行的 System.loadLibrary
        self.assertEqual(len(results), 1, f"Expected 1 result, got {len(results)}: {results}")
        start_line, end_line, suggestion, _, _ = results[0]
        self.assertEqual(start_line, 3)
        self.assertEqual(end_line, 3)

    def test_multiple_patterns_same_line(self):
        """测试同一行多个模式只匹配一次"""
        test_code = 'System.loadLibrary("lib1"); System.load("lib2.so");'
        test_file = SourceFile("")
        test_file.code = test_code
        results, _ = self.solver.solve(test_file)
        # 由于 break 语句，同一行应该只匹配第一个模式
        self.assertEqual(len(results), 1, f"Expected 1 result, got {len(results)}: {results}")

    def test_case_insensitive(self):
        """测试大小写不敏感匹配"""
        test_code = """
SYSTEM.LOADLIBRARY("test");
system.load("test.so");
Runtime.GETRuntime().load("test.so");
"""
        test_file = SourceFile("")
        test_file.code = test_code
        results, _ = self.solver.solve(test_file)
        # 所有模式都应该匹配（因为使用了 re.IGNORECASE）
        self.assertGreaterEqual(len(results), 2, f"Expected at least 2 results, got {len(results)}: {results}")

    def test_fully_qualified_runtime_variable(self):
        """测试完全限定名的Runtime变量定义和使用"""
        test_code = """
java.lang.Runtime runtime = java.lang.Runtime.getRuntime();
runtime.load("test.so");
runtime.loadLibrary("mylib");
"""
        test_file = SourceFile("")
        test_file.code = test_code
        results, _ = self.solver.solve(test_file)
        # 应该匹配第3行和第4行的变量使用
        self.assertEqual(len(results), 2, f"Expected 2 results, got {len(results)}: {results}")
        # 验证结果
        for start_line, end_line, suggestion, code_too_long, code in results:
            self.assertIn(
                self.solver.migration_advice.get('runtime_getruntime_variable'),
                suggestion,
                f"Suggestion should contain runtime_getruntime_variable advice: {suggestion}"
            )
            self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
            self.assertIn(start_line, [3, 4])


if __name__ == '__main__':
    unittest.main()
