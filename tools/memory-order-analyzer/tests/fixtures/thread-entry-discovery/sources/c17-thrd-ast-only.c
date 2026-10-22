#include <threads.h>
static int worker(void *argument) { return argument != 0; }
int main(void) {
  thrd_t thread;
  return thrd_create(&thread, worker, 0);
}
