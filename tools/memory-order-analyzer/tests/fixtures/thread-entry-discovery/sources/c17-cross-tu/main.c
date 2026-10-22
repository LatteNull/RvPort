#include "shared.h"
int main(void) {
  thrd_t thread;
  return start_thread(&thread, worker, 0);
}
