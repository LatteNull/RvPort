#include <assert.h>
#include <immintrin.h>
int main(void) {
    assert(_mm_cvtsi128_si32(_mm_setzero_si128()) == 0);
    return 0;
}
