#if (__i386 || __amd64 || __powerpc__) && __GNUC__
#elif defined(__riscv) && __riscv_xlen == 64
    // Suggestion: Add macros for the RISC-V architecture.
#endif
