#include <stdatomic.h>

_Atomic unsigned c17_flag = 0;
int c17_payload = 0;

void c17_release_then_relaxed(void) {
  c17_payload = 1;
  atomic_store_explicit(&c17_flag, 1, memory_order_release);
  atomic_store_explicit(&c17_flag, 2, memory_order_relaxed);
}

unsigned c17_exchange(void) {
  return atomic_exchange_explicit(&c17_flag, 3, memory_order_acq_rel);
}

int c17_consume(void) {
  return atomic_load_explicit(&c17_flag, memory_order_acquire) == 2 ? c17_payload : 0;
}
