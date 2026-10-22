#include "c17-cross.h"
_Atomic int cross_flag = 0;
int cross_payload = 0;
void cross_publish(void) {
  cross_payload = 1;
  atomic_thread_fence(memory_order_release);
  atomic_store_explicit(&cross_flag, 1, memory_order_relaxed);
}
