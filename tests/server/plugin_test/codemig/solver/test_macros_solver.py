from plugin.codemig.codemig_common.codemig_common_utils import ChangeType
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong
from plugin.codemig.main.source_file import SourceFile
from plugin.codemig.solver.macros_solver import MacrosSolver

import os
import unittest

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__)))
TEST_FILE_PATH = os.path.join(MODULE_PATH, 'test_files', 'macros_solver')

Expect_inner = [
    [9, 12,
     ' #elif defined(__riscv) && __riscv_xlen == 64\n     // Suggestion: Add macros for the RISC-V architecture.\n',
     CodeTooLong.HAS_SOURCE_CODE,
     '	#if defined(__x86_64)\n\n		#define PMEM_PAGESIZE 4096\n	#endif'],
    [20, 29,
     '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
     CodeTooLong.HAS_SOURCE_CODE,
     '#if HAS_LONG\n	#if defined(__x86_64)\n\n		#define PMEM_PAGESIZE 4096\n	#endif\n#elif __aarch64__\n\n	#error not support\n\n#endif']
]

Expect_long = [
    [8, 13,
     '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
     CodeTooLong.HAS_SOURCE_CODE,
     '#if HAS_LONG || \\\n	defined(__x86_64)\n\n#define PMEM_PAGESIZE 4096\n\n#endif'],
    [16, 34,
     '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
     CodeTooLong.HAS_SOURCE_CODE,
     '#if defined(__x86_64) || \\\n	defined(_M_X64) || \\\n	defined(__aarch64__)\n\n#define PMEM_PAGESIZE 4096\n\n#elif defined(__PPC64__)\n\n#define PMEM_PAGESIZE 65536\n\n#elif defined(__loongarch64)\n\n#define PMEM_PAGESIZE 16384\n\n#else\n\n#error unable to recognize ISA at compile time\n\n#endif']
]

Expect_multiarch = [
    [1, 7,
     '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
     CodeTooLong.HAS_SOURCE_CODE,
     '#if (VSAN_ARCH == x86_64)\nstatic inline unsigned long dp_bit_ffz(unsigned long long_word)\n{\n\n'
     '        return long_word;\n}\n#endif'],
    [9, 15,
     '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
     CodeTooLong.HAS_SOURCE_CODE,
     '#if (VSAN_ARCH == aarch64)\nstatic inline unsigned long dp__ffs(unsigned long word)\n{\n'
     '    return __builtin_ctzl(word);\n}\n#define dp_bit_ffz(x)  dp__ffs(~(x))\n#endif']
]
Expect_macro = [[
    1, 11,
    '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
    CodeTooLong.HAS_SOURCE_CODE,
    '#if (__i386 || __amd64 || __powerpc__) && __GNUC__\n  #define GNUC_VERSION (__GNUC__ * 10000 + __GNUC_MINOR__ * 100 + __GNUC_PATCHLEVEL__)\n  #if defined(__clang__)\n    #define HAVE_ATOMIC\n  #endif\n  #if (defined(__GLIBC__) && defined(__GLIBC_PREREQ))\n    #if (GNUC_VERSION >= 40100 && __GLIBC_PREREQ(2, 6))\n      #define HAVE_ATOMIC\n    #endif\n  #endif\n#endif'
],
    [
        12, 22,
        '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
        CodeTooLong.HAS_SOURCE_CODE,
        '#if (__i386 || __amd64 || __powerpc__) && __GNUC__\n  #define GNUC_VERSION (__GNUC__ * 10000 + __GNUC_MINOR__ * 100 + __GNUC_PATCHLEVEL__)\n  #if defined(__clang__)\n    #define HAVE_ATOMIC\n  #endif\n  #if (defined(__GLIBC__) && defined(__GLIBC_PREREQ))\n    #if (GNUC_VERSION >= 40100 && __GLIBC_PREREQ(2, 6))\n      #define HAVE_ATOMIC\n    #endif\n  #endif\n#endif'
    ],
    [
        24, 34,
        '  #elif defined(__riscv) && __riscv_xlen == 64\n      // Suggestion: Add macros for the RISC-V architecture.\n',
        CodeTooLong.HAS_SOURCE_CODE,
        '  #if (__i386 || __amd64 || __powerpc__) && __GNUC__\n    #define GNUC_VERSION (__GNUC__ * 10000 + __GNUC_MINOR__ * 100 + __GNUC_PATCHLEVEL__)\n    #if defined(__clang__)\n      #define HAVE_ATOMIC\n    #endif\n    #if (defined(__GLIBC__) && defined(__GLIBC_PREREQ))\n      #if (GNUC_VERSION >= 40100 && __GLIBC_PREREQ(2, 6))\n        #define HAVE_ATOMIC\n      #endif\n    #endif\n  #endif'
    ],
    [
        36, 48,
        '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
        CodeTooLong.HAS_SOURCE_CODE,
        '#if __GNUC__\n  #define HAVE_ATOMIC\n#elif (__i386 || __amd64 || __powerpc__) && __GNUC__\n  #define GNUC_VERSION (__GNUC__ * 10000 + __GNUC_MINOR__ * 100 + __GNUC_PATCHLEVEL__)\n  #if defined(__clang__)\n    #define HAVE_ATOMIC\n  #endif\n  #if (defined(__GLIBC__) && defined(__GLIBC_PREREQ))\n    #if (GNUC_VERSION >= 40100 && __GLIBC_PREREQ(2, 6))\n      #define HAVE_ATOMIC\n    #endif\n  #endif\n#endif'
    ]]
Expect_macro2 = [[
    1, 2,
    '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
    CodeTooLong.HAS_SOURCE_CODE,
    '#if (__i386 || __amd64 || __powerpc__) && __GNUC__\n#endif'
]]
Expect_macro5 = [[
    1, 14,
    '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
    CodeTooLong.HAS_SOURCE_CODE,
    '#if (__i386 || __amd64 || __powerpc__) && __GNUC__\n  #define GNUC_VERSION (__GNUC__ * 10000 + __GNUC_MINOR__ * 100 + __GNUC_PATCHLEVEL__)\n  #if defined(__clang__)\n    #define HAVE_ATOMIC\n  #endif\n  #if (defined(__GLIBC__) && defined(__GLIBC_PREREQ))\n    #if (GNUC_VERSION >= 40100 && __GLIBC_PREREQ(2, 6))\n      #define HAVE_ATOMIC\n      #if (__i386 || __amd64 || __powerpc__) && __GNUC__\n        #define HAVE_ATOMIC\n      #endif\n    #endif\n  #endif\n#endif'
],
    [
        15, 25,
        '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
        CodeTooLong.HAS_SOURCE_CODE,
        '#if (__i386 || __amd64 || __powerpc__) && __GNUC__\n  #define GNUC_VERSION (__GNUC__ * 10000 + __GNUC_MINOR__ * 100 + __GNUC_PATCHLEVEL__)\n  #if defined(__clang__)\n    #define HAVE_ATOMIC\n  #endif\n  #if (defined(__GLIBC__) && defined(__GLIBC_PREREQ))\n    #if (GNUC_VERSION >= 40100 && __GLIBC_PREREQ(2, 6))\n      #define HAVE_ATOMIC\n    #endif\n  #endif\n#endif'
    ]]
Expect_macro7 = [[
    22, 35,
    '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
    CodeTooLong.HAS_SOURCE_CODE,
    '#if (__i386 || __amd64 || __powerpc__) && __GNUC__\n  #define GNUC_VERSION (__GNUC__ * 10000 + __GNUC_MINOR__ * 100 + __GNUC_PATCHLEVEL__)\n  #if defined(__clang__)\n    #define HAVE_ATOMIC\n  #endif\n  #if (defined(__GLIBC__) && defined(__GLIBC_PREREQ))\n    #if (GNUC_VERSION >= 40100 && __GLIBC_PREREQ(2, 6))\n      #define HAVE_ATOMIC\n      #if (__i386 || __amd64 || __powerpc__) && __GNUC__\n        #define HAVE_ATOMIC\n      #endif\n    #endif\n  #endif\n#endif'
]]
Expect_macro8 = [[
    1, 3,
    '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
    CodeTooLong.HAS_SOURCE_CODE,
    '#if defined(__x86_64__)\n  #define HAVE_ATOMIC\n#endif'],
    [5, 7,
     '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
     CodeTooLong.HAS_SOURCE_CODE,
     '#if defined(__X86_64__)\n  #define HAVE_ATOMIC\n#endif']]
Expect_macro9 = [[
    4, 14,
    '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
    CodeTooLong.HAS_SOURCE_CODE,
    '#if (__i386 || __amd64 || __powerpc__) && __GNUC__\n  #define GNUC_VERSION (__GNUC__ * 10000 + __GNUC_MINOR__ * 100 + __GNUC_PATCHLEVEL__)\n  #if defined(__clang__)\n    #define HAVE_ATOMIC\n  #endif\n  #if (defined(__GLIBC__) && defined(__GLIBC_PREREQ))\n    #if (GNUC_VERSION >= 40100 && __GLIBC_PREREQ(2, 6))\n      #define HAVE_ATOMIC\n    #endif\n  #endif\n#endif'
]]
Expect_macro10 = [[
    1, 3,
    '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
    CodeTooLong.HAS_SOURCE_CODE,
    '#ifdef __x86_64__\n  #define HAVE_ATOMIC\n#endif'
]]
Expect_macro11 = [[
    1, 2,
    '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
    CodeTooLong.HAS_SOURCE_CODE,
    '# if (__i386 || __amd64 || __powerpc__) && __GNUC__\n# endif'
]]
Expect_macro12 = [[
    28, 46,
    '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
    CodeTooLong.HAS_SOURCE_CODE,
    '#if defined(__x86_64) || \\\n\tdefined(_M_X64) || \\\n\tdefined(__aarch64__)\n\n#define PMEM_PAGESIZE 4096\n\n#elif defined(__PPC64__)\n\n#define PMEM_PAGESIZE 65536\n\n#elif defined(__loongarch64)\n\n#define PMEM_PAGESIZE 16384\n\n#else\n\n#error unable to recognize ISA at compile time\n\n#endif'
]]

Expect_macro14 = [[
    1, 3,
    '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
    CodeTooLong.HAS_SOURCE_CODE,
    '#if defined(SIMDE_X86_AES_NATIVE)\n  #include <wmmintrin.h>\n#endif'
], [
    9, 13,
    '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
    CodeTooLong.HAS_SOURCE_CODE,
    '#if !defined(SIMDE_ARM_NEON_A64V8_NATIVE) && !defined(SIMDE_ARM_NEON_A64V8_NO_NATIVE) && !defined(SIMDE_NO_NATIVE)\n'
    '  #if defined(SIMDE_ARCH_ARM_NEON) && defined(SIMDE_ARCH_AARCH64) && SIMDE_ARCH_ARM_CHECK(8,0)\n    #define SIMDE_ARM_NEON_A64V8_NATIVE\n'
    '  #endif\n#endif'],
    [14, 16,
     '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
     CodeTooLong.HAS_SOURCE_CODE,
     '#if defined(SIMDE_ARM_NEON_A64V8_NATIVE) && !defined(SIMDE_ARM_NEON_A32V8_NATIVE)\n'
     '  #define SIMDE_ARM_NEON_A32V8_NATIVE\n#endif'],
    [18, 22,
     '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
     CodeTooLong.HAS_SOURCE_CODE,
     '#if !defined(SIMDE_ARM_NEON_A32V8_NATIVE) && !defined(SIMDE_ARM_NEON_A32V8_NO_NATIVE) && !defined(SIMDE_NO_NATIVE)\n'
     '  #if defined(SIMDE_ARCH_ARM_NEON) && SIMDE_ARCH_ARM_CHECK(8,0) && (__ARM_NEON_FP & 0x02)\n    #define SIMDE_ARM_NEON_A32V8_NATIVE\n'
     '  #endif\n#endif'],
    [23, 25,
     '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
     CodeTooLong.HAS_SOURCE_CODE, '#if defined(__ARM_ACLE)\n  #include <arm_acle.h>\n#endif'],
    [26, 28,
     '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
     CodeTooLong.HAS_SOURCE_CODE,
     '#if defined(SIMDE_ARM_NEON_A32V8_NATIVE) && !defined(SIMDE_ARM_NEON_A32V7_NATIVE)\n  #define SIMDE_ARM_NEON_A32V7_NATIVE\n#endif'
     ]]

Expect_macro15 = [[
    1, 3,
    '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
    CodeTooLong.HAS_SOURCE_CODE,
    '#if defined(SIMDE_X86_AES_NATIVE)\n  #include <wmmintrin.h>\n#endif'
], [
    8, 12,
    '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
    CodeTooLong.HAS_SOURCE_CODE,
    '#if !defined(SIMDE_ARM_NEON_A64V8_NATIVE) && !defined(SIMDE_ARM_NEON_A64V8_NO_NATIVE) && !defined(SIMDE_NO_NATIVE)\n'
    '  #if defined(SIMDE_ARCH_ARM_NEON) && defined(SIMDE_ARCH_AARCH64) && SIMDE_ARCH_ARM_CHECK(8,0)\n    #define SIMDE_ARM_NEON_A64V8_NATIVE\n'
    '  #endif\n#endif'],
    [13, 15,
     '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
     CodeTooLong.HAS_SOURCE_CODE,
     '#if defined(SIMDE_ARM_NEON_A64V8_NATIVE) && !defined(SIMDE_ARM_NEON_A32V8_NATIVE)\n'
     '  #define SIMDE_ARM_NEON_A32V8_NATIVE\n#endif'],
    [17, 19,
     '#elif defined(__riscv) && __riscv_xlen == 64\n    // Suggestion: Add macros for the RISC-V architecture.\n',
     CodeTooLong.HAS_SOURCE_CODE,
     '#if defined(__ARM_ACLE)\n  #include <arm_acle.h>\n#endif'
     ]]
TEST_CASE = {
    'inner_macro.c': ('内部宏定义才和架构相关', Expect_inner),
    # 'long_macro.c': ('带换行的宏定义', Expect_long),
    # 'multiarch_macro.c': ("多架构处理", Expect_multiarch),
    # 'macros.c': ("", Expect_macro),
    # 'macros2.c': ("", Expect_macro2),
    # 'macros3.c': ("", []),
    # 'macros4.c': ("", []),
    # 'macros5.c': ("", Expect_macro5),
    # 'macros6.c': ("", []),
    # 'macros7.c': ("", Expect_macro7),
    # 'macros8.c': ("", Expect_macro8),
    # 'macros9.c': ("", Expect_macro9),
    # 'macros10.c': ("", Expect_macro10),
    # 'macros11.c': ("", Expect_macro11),
    # 'macros12.c': ("", Expect_macro12),
    # 'macros13.c': ("复杂多级宏定义", []),
    # 'macro14.c': ("复杂多级宏定义", Expect_macro14),
    # 'macro15.c': ("复杂多级宏定义", Expect_macro15)
}


# TEST_CASE={
#            'macro15.c': ("复杂多级宏定义", Expect_macro15)
# }
class TestMacrosSolver(unittest.TestCase):

    def test_matches_file(self):
        self.assertTrue(MacrosSolver.matches_file("abc.h"))
        self.assertTrue(MacrosSolver.matches_file("some/dir/aaa.c"))
        self.assertTrue(MacrosSolver.matches_file("abc.cc"))
        self.assertTrue(MacrosSolver.matches_file("abc.cpp"))

    def test_not_matches_file(self):
        self.assertFalse(MacrosSolver.matches_file("README.md"))
        self.assertFalse(MacrosSolver.matches_file("make_file.f"))
        self.assertFalse(MacrosSolver.matches_file("make_file.cp"))

    def test_append_or_replace(self):
        self.assertEqual(MacrosSolver.append_or_replace(), ChangeType.APPEND.value)

    def test_case(self):
        for file, data in TEST_CASE.items():
            msg, expect = data
            actual, _ = MacrosSolver.solve(SourceFile(os.path.join(TEST_FILE_PATH, file)))
            self.assertEqual(actual, expect, msg)


if __name__ == "__main__":
    unittest.main()
