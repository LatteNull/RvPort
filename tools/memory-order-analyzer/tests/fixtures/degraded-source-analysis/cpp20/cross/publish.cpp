#include "shared.hpp"
void publish() { state.payload = 42; state.ready.store(1, std::memory_order_release); }
