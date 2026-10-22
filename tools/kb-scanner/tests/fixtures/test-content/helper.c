#include <immintrin.h>
static int unused(void) {
    return _mm_cvtsi128_si32(_mm_setzero_si128());
}
int main(void) { return 0; }
