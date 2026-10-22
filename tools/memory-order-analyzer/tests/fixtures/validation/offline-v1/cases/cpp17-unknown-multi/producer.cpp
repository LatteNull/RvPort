#include "shared.hpp"
int payload;
std::atomic<int> flag{0};
void *producer(void *) { payload = 42; int expected = 0; flag.compare_exchange_strong(expected, 1, std::memory_order_release, std::memory_order_relaxed); return nullptr; }
