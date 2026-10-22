#include <pthread.h>
static void *worker(void *argument) { return argument; }
int main(void) {
  pthread_t thread;
  return pthread_create(&thread, 0, worker, 0);
}
