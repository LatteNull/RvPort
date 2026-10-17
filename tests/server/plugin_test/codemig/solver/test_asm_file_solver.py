import unittest
import os
from plugin.codemig.codemig_common.codemig_common_utils import CodeTooLong
from plugin.codemig.solver.asm_file_solver import AsmFileSolver
from plugin.codemig.codemig_common.codemig_common_utils import ChangeType
from plugin.codemig.main.source_file import SourceFile
from plugin.codemig.codemig_common.codemig_common_utils import NUMBER_LINES_TOO_LONG

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__)))


class TestAsmFileSolver(unittest.TestCase):
    test_file1 = SourceFile(MODULE_PATH +
                            "/test_files/asm_file_solver/hello_x86_64.s")
    test_file2 = SourceFile(MODULE_PATH +
                            "/test_files/asm_file_solver/hello_aarch64.s")
    test_file3 = SourceFile(MODULE_PATH +
                            "/test_files/asm_file_solver/hello_riscv64.s")
    test_file4 = SourceFile(MODULE_PATH + "/test_files/asm_file_solver/empty.s")

    def test_matches_file(self):
        self.assertTrue(AsmFileSolver.matches_file("test.s"))
        self.assertTrue(AsmFileSolver.matches_file("test.S"))
        self.assertTrue(AsmFileSolver.matches_file("test.asm"))
        self.assertFalse(AsmFileSolver.matches_file("test.h"))
        self.assertFalse(AsmFileSolver.matches_file("test.c"))

    def test_solve(self):
        self.assertEqual(AsmFileSolver.solve(self.test_file1), ([[
            1, 17, '此处汇编与架构相关，请转换为适用于 RISC-V 架构的实现。',
            CodeTooLong.HAS_SOURCE_CODE,
            '.section .data\nmsg:    .ascii  "Hello from x86_64!\\n"\nlen = . - msg\n\n.section .text\n.global _start\n\n_start:\n    mov     $1, %rax        # syscall: write\n    mov     $1, %rdi        # fd: stdout\n    mov     $msg, %rsi      # buffer\n    mov     $len, %rdx      # length\n    syscall\n\n    mov     $60, %rax       # syscall: exit\n    xor     %rdi, %rdi      # status 0\n    syscall'
        ]], []))
        self.assertEqual(AsmFileSolver.solve(self.test_file2), ([[
            1, 17, '此处汇编与架构相关，请转换为适用于 RISC-V 架构的实现。',
            CodeTooLong.HAS_SOURCE_CODE,
            '.section .data\nmsg:    .ascii "Hello from AArch64!\\n"\nlen = . - msg\n\n.section .text\n.global _start\n\n_start:\n    mov     x8, #64         // syscall: write\n    mov     x0, #1          // fd: stdout\n    ldr     x1, =msg        // buffer\n    mov     x2, #len        // length\n    svc     #0\n\n    mov     x8, #93         // syscall: exit\n    mov     x0, #0          // status 0\n    svc     #0'
        ]], []))
        self.assertEqual(AsmFileSolver.solve(self.test_file3), ([], []))
        self.assertEqual(AsmFileSolver.solve(self.test_file4), ([], []))

    def test_append_or_replace(self):
        self.assertEqual(AsmFileSolver.append_or_replace(),
                         ChangeType.OTHER.value)

    def test_extract_code(self):
        code_too_long, code = AsmFileSolver.extract_code(            "deadbeaf", 1, NUMBER_LINES_TOO_LONG )
        self.assertEqual(code_too_long, CodeTooLong.HAS_SOURCE_CODE)
        self.assertEqual(code, "deadbeaf")
        code_too_long, code = AsmFileSolver.extract_code(            "deadbeaf", 1, NUMBER_LINES_TOO_LONG + 1)
        self.assertEqual(code_too_long, CodeTooLong.CODE_TOO_LONG)
        self.assertEqual(code, None)


if __name__ == "__main__":
    unittest.main()
