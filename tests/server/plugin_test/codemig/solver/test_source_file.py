import unittest
import os
from plugin.codemig.main.source_file import SourceFile

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__)))
TEST_FILE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__),"test_files", "source_file"))
TEST_CASE={'multiline_comments.c': '字符串中包含/**/',
               'half_comments.c':'字符串中包含一半的/**/'}
class TestSolver(unittest.TestCase):

    def setUp(self):
        self.file = MODULE_PATH + "/test_files/builtin_solver/builtin.c"
        self.file2 = MODULE_PATH + "/test_files/macros_solver/macros6.c"
        self.file3 = MODULE_PATH + "/test_files/makefile_solver/Makefile3"

    def test_get_code(self):
        source_file = SourceFile(self.file2)
        self.assertEqual(
            source_file.get_code(),
            '#if defined(__clang__)\n  #define HAVE_ATOMIC\n#endif\n')

    def test_remove_c_comments(self):
        source_file = SourceFile(self.file)
        self.assertEqual(
            source_file.remove_c_comments(), '#include <math.h>\n'
            '\n'
            'int main() {\n'
            '  double result1 = __builtin_copysignq(1.0, -2.0);  \n'
            '  \n'
            '  double result3 = __builtin_copysignq(1.0, -2.0);\n'
            '  __builtin_cpu_init(); double result5 = __builtin_copysignq(1.0, -2.0);\n'
            '  \n'
            '  return 0;\n'
            '}\n')

    def test_remove_c_comments_lines(self):
        source_file = SourceFile(self.file)
        self.assertEqual(source_file.remove_c_comments_lines(), [
            '#include <math.h>', '', 'int main() {',
            '  double result1 = __builtin_copysignq(1.0, -2.0);  ', '  ',
            '  double result3 = __builtin_copysignq(1.0, -2.0);',
            '  __builtin_cpu_init(); double result5 = __builtin_copysignq(1.0, -2.0);',
            '  ', '  return 0;', '}'
        ])
    def test_multi_line_comments(self):
        file_name = 'multiline_comments.c'
        source_file = SourceFile(os.path.join(TEST_FILE_PATH, file_name))
        self.assertEqual(
            source_file.remove_c_comments(), '#include <stdio.h>\n'
                                             '\n'
                                             '\n'
                                             'char* message = "This is a /* string */ with fake comments";\n'
                                             'char ch = \'"\'; \n'
                                             '\n'
                                             '\n'
                                             '\n'
                                             '\n'
                                             'int main() {\n'
                                             '    printf("Hello /* not a comment */ World\\n");\n'
                                             '    \n'
                                             '    return 0;\n'
                                             '}\n'
                                             '\n',
            TEST_CASE.get(file_name)
        )

    def test_half_comments(self):
        file_name='half_comments.c'
        source_file = SourceFile(os.path.join(TEST_FILE_PATH, file_name))
        self.assertEqual(
            source_file.remove_c_comments(), '#include <stdio.h>\n'
            '\n'
            '\n'
            'char* message = "This is a /* string  with fake comments";\n'
            '#ifdef __x86\n'
            '#endif\n'                                 
            'char ch = \'"\'; \n'
            '\n'
            '\n'
            '\n'
            '\n'
            '\n'                                 
            'int main() {\n'
            '    printf("Hello /* not a comment */ World\\n");\n'
            '    \n'
            '    return 0;\n'
            '}\n'
            '\n'
            'int test() {\n'
            '    printf("Hello not a comment */ World\\n");\n'
            '    \n'
            '    return 0;\n'
            '}\n',
            TEST_CASE.get(file_name)
        )





    def test_remove_makefile_comments(self):
        source_file = SourceFile(self.file3)
        self.assertEqual(source_file.remove_makefile_comments(),
                         ['MY4 = -fsigned-char ', '', 'GLIBS = -aaa -lm'])


if __name__ == "__main__":
    unittest.main()
