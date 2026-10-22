#include <cpuid.h>
#include <immintrin.h>

typedef int v4si __attribute__((vector_size (16)));

__attribute__((target("avx2"))) int x86_sample(void) {
    unsigned int a, b, c, d;
    __cpuid(0, a, b, c, d);
    __asm__("pause %%rax");
    return cpuinfo_x86();
}

// AVX path; comments remain hints only.
