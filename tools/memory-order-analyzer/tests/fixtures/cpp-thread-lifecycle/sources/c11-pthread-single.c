#include <pthread.h>
static void *worker(void *arg) { return arg; }
int main(void) { pthread_t thread; return pthread_create(&thread, 0, worker, 0) || pthread_join(thread, 0); }
