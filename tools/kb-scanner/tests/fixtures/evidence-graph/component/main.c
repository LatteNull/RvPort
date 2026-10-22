#include "support.h"

#if defined(__AVX__)
int implementation(void) { return FAST(1, 2); }
#elif defined(__riscv)
int implementation(void) { return 1 + 2; }
#else
int implementation(void) { return portable_add(1, 2); }
#endif

int nested(void) { return WRAP(1, 2); }
int cycle(void) { return LOOP_A(1); }
