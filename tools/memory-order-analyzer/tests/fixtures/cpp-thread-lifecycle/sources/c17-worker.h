#include <pthread.h>
extern pthread_t shared_thread;
void *cross_tu_worker(void *arg);
