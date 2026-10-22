#include <immintrin.h>

typedef float v4f __attribute__((vector_size(16)));

#define add_vector(a, b) _Generic((a), __m128: _mm_add_ps, v4f: generic_add)(a, b)

