#include "shared.h"
void *consumer(void *unused) { (void)unused; if (atomic_load(&state.ready)) (void)state.payload; return 0; }
