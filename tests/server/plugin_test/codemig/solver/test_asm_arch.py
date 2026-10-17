import pytest
from plugin.codemig.solver.asm_arch import AsmArch

# 测试数据
asm_code_samples = {
    AsmArch.UNKNOWN: [
        """
        asm volatile (
            "movl %[count], %%ecx\n\t"
            "xorl %%eax, %%eax\n\t"
            "xorl %%ebx, %%ebx\n\t"
            "loop_start:\n\t"
            "addl %%ebx, %%eax\n\t"
            "incl %%ebx\n\t"
            "loop loop_start\n\t"
            "movl %%eax, %[result]\n\t"
            : [result] "=r" (sum)
            : [count] "r" (i)
            : "eax", "ebx", "ecx"
        );
        """,
        """
        asm volatile ("cpuid\n"
            : "=a"(*a), "=b"(*b), "=c"(*c), "=d"(*d)
            : "0"(*a), "2"(*c));
        """,
        """
        asm volatile ( "rdtsc" : "=a"(rax), "=d"(rdx) );
        """,
        """
        asm volatile ( "rdtscp" : "=a"(rax), "=d"(rdx) : : "rcx" );
        """,
        """
        asm volatile ( "pause\n" );
        """,
        """
        asm volatile (
            "mov x1, %[cnt]\n\t"
            "mov x2, #0\n\t"
            "mov x3, #0\n\t"
            "loop_start:\n\t"
            "add x3, x3, x2\n\t"
            "add x2, x2, #1\n\t"
            "subs x1, x1, #1\n\t"
            "bne loop_start\n\t"
            "str w3, %[res]\n\t"
            : [res] "=m" (sum)
            : [cnt] "r" (count)
            : "x1", "x2", "x3", "memory"
        );
        """,
        """
        asm volatile (
            "add %0, %1, %2\n\t"
            : "=r" (result)
            : "r" (a), "r" (b)
            :
        );
        """
    ],
    AsmArch.RISCV: [
        """
        asm volatile (
            "mv t0, %[cnt]\n\t"
            "li t1, 0\n\t"
            "li t2, 0\n\t"
            "loop_start:\n\t"
            "add t2, t2, t1\n\t"
            "addi t1, t1, 1\n\t"
            "addi t0, t0, -1\n\t"
            "bnez t0, loop_start\n\t"
            "sw t2, %[res]\n\t"
            : [res] "=m" (sum)
            : [cnt] "r" (count)
            : "t0", "t1", "t2", "memory"
        );
        """
    ],
}


# 参数化测试
@pytest.mark.parametrize("arch, samples", asm_code_samples.items())
def test_detect_arch(arch, samples):
    """测试不同架构的汇编代码检测"""
    for sample in samples:
        assert AsmArch.detect_asm_arch(sample) == arch