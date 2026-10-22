#include "shared.hpp"
void *consumer(void *) { if (ready.load(std::memory_order_acquire)) (void)payload; return nullptr; }
