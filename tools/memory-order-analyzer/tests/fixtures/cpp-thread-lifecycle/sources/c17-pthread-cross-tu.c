#include "c17-worker.h"
int main(void) { return pthread_create(&shared_thread, 0, cross_tu_worker, 0) || pthread_join(shared_thread, 0); }
