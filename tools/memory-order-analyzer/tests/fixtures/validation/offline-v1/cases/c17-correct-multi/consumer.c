#include "shared.h"
void *consumer(void *arg) { (void)arg; if (atomic_load_explicit(&flag, memory_order_acquire)) return (void *)(long)payload; return 0; }
