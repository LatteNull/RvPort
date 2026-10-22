#include "c17-cross.h"
int cross_consume(void) {
  int value = atomic_load_explicit(&cross_flag, memory_order_relaxed);
  atomic_thread_fence(memory_order_acquire);
  return value ? cross_payload : 0;
}
