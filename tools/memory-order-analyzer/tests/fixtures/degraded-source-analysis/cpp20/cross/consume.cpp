#include "shared.hpp"
void consume() { if (state.ready.load(std::memory_order_acquire)) (void)state.payload; }
