#include "shared.h"
int payload;
atomic_int flag;
void *producer(void *arg) { (void)arg; payload = 42; atomic_store_explicit(&flag, 1, memory_order_relaxed); return 0; }
