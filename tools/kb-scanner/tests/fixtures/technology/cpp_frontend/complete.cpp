#define X86_ADD(v) _mm_add_epi32((v), (v))

#if defined(__x86_64__)
#include <immintrin.h>
static int x86_path(int value) {
  asm volatile(
      "movl %1, %0\n\t"
      : "=r"(value)
      : "r"(value));
  return value;
}
#endif

template <typename T>
constexpr T choose_value(T value) {
  if constexpr (sizeof(T) == 8) {
    return value;
  }
  return T{};
}
