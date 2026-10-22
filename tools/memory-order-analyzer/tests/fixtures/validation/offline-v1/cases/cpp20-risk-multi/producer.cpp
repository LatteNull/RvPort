#include "shared.hpp"
int payload;
std::atomic<int> flag{0};
void *producer(void *) { flag.store(1, std::memory_order_release); payload = 42; return nullptr; }
