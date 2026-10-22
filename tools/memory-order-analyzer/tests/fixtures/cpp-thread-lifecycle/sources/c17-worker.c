#include "c17-worker.h"
pthread_t shared_thread;
void *cross_tu_worker(void *arg) { return arg; }
