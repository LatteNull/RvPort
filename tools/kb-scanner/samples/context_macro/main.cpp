#ifdef USE_FAST_PATH
#include <immintrin.h>
#endif

#define VEC_ADD(a, b) _mm256_add_ps(a, b)

void demo() {
  VEC_ADD(x, y);
}

void cpu_probe() {
  int out[4];
  __cpuid(out, 0);
  auto ticks = __rdtsc();
}
