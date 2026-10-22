#include "shared.h"
void consume(void) { if (atomic_load_explicit(&ready, memory_order_relaxed)) (void)payload.bits; }
