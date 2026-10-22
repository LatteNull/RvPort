#include <atomic>

std::atomic<int> cpp20_flag{0};
int cpp20_payload = 0;

void cpp20_release_then_relaxed() {
  cpp20_payload = 1;
  cpp20_flag.store(1, std::memory_order_release);
  cpp20_flag.store(2, std::memory_order_relaxed);
}

int cpp20_rmw() {
  return cpp20_flag.fetch_xor(4, std::memory_order_relaxed);
}

bool cpp20_cas() {
  int expected = 2;
  return cpp20_flag.compare_exchange_weak(
      expected, 3, std::memory_order_acq_rel, std::memory_order_acquire);
}

int cpp20_consume() {
  return cpp20_flag.load(std::memory_order_acquire) == 2 ? cpp20_payload : 0;
}
