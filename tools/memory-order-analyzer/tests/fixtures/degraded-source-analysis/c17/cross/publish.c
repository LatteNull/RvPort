#include "shared.h"
#define SET_READY() atomic_store_explicit(&ready, 1, memory_order_relaxed)
void publish(void) { payload.value = 42; SET_READY(); }
