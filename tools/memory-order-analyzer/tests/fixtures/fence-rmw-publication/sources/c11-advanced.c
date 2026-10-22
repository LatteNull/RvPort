#include <stdatomic.h>

_Atomic int c11_flag = 0;
int c11_payload = 0;

void c11_fence_publish(void) {
  c11_payload = 1;
  atomic_thread_fence(memory_order_release);
  atomic_store_explicit(&c11_flag, 1, memory_order_relaxed);
}

int c11_fence_consume(void) {
  int seen = atomic_load_explicit(&c11_flag, memory_order_relaxed);
  atomic_thread_fence(memory_order_acquire);
  return seen ? c11_payload : 0;
}

int c11_rmw(void) {
  return atomic_fetch_add_explicit(&c11_flag, 1, memory_order_relaxed);
}

int c11_cas(void) {
  int expected = 1;
  return atomic_compare_exchange_weak_explicit(
      &c11_flag, &expected, 2, memory_order_acq_rel, memory_order_acquire);
}

void c11_signal_only(void) {
  atomic_signal_fence(memory_order_release);
}
