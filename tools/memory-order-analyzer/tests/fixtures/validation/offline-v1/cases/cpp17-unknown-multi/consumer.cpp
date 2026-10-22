#include "shared.hpp"
void *consumer(void *) { if (flag.load(std::memory_order_acquire)) return reinterpret_cast<void *>(static_cast<long>(payload)); return nullptr; }
