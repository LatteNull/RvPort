#include "portable.h"
#define DOUBLE(value) ((value) + (value))

#if defined(__x86_64__)
static int selected(int value) { return DOUBLE(value); }
#else
static int selected(int value) { return value; }
#endif

typedef unsigned long word_t;

int run_c(word_t value) {
    __asm__("pause");
    return selected((int)value);
}
