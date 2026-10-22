#include "wrapper.h"

int main() {
#if defined(USE_AVX2)
    WRAP_OUTER();
#endif
}
