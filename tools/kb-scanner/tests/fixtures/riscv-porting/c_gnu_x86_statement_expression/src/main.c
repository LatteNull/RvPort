#include <immintrin.h>

#define LOAD4(ptr) ({ __m128 v = _mm_loadu_ps(ptr); v; })

