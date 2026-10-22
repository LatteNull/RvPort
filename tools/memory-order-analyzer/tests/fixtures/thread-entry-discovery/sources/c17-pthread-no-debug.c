#include <pthread.h>
static void *worker(void *argument) { return argument; }
#define START(handle, callback) pthread_create((handle), 0, (callback), 0)
int main(void) {
  pthread_t thread;
  return START(&thread, worker);
}
