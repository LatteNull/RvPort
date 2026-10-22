#include "shared.h"
#define PUBLISH(v) atomic_store_explicit(&state.ready, (v), memory_order_release)
void *producer(void *unused) { (void)unused; state.payload = 42; PUBLISH(1); return 0; }
