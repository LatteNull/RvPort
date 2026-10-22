#include <atomic>

std::atomic<int> cpp17_flag{0};
int cpp17_payload = 0;

void cpp17_release_then_relaxed() {
  cpp17_payload = 1;
  cpp17_flag.store(1, std::memory_order_release);
  cpp17_flag.store(2, std::memory_order_relaxed);
}

int cpp17_rmw() {
  return cpp17_flag.fetch_or(4, std::memory_order_relaxed);
}

bool cpp17_cas() {
  int expected = 2;
  return cpp17_flag.compare_exchange_strong(
      expected, 3, std::memory_order_release, std::memory_order_relaxed);
}

int cpp17_consume() {
  return cpp17_flag.load(std::memory_order_acquire) == 2 ? cpp17_payload : 0;
}
