#include "shared.h"
void *consumer(void *arg) { (void)arg; while (!atomic_load_explicit(&flag, memory_order_relaxed)) {} return (void *)(long)payload; }
