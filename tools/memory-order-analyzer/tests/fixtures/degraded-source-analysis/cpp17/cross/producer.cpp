#include "shared.hpp"
void *producer(void *) { payload = 42; ready.store(1, std::memory_order_release); return nullptr; }
