#include "wrapper.h"
#define ENABLE USE_AVX2
#if defined(USE_AVX2) && ENABLE
int kernel(int x, int y) { return OUTER(_mm256_add_epi32, x, y); }
#endif
