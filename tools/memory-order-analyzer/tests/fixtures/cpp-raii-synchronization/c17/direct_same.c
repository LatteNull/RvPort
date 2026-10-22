#include <pthread.h>

int payload;
pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
void write_payload(void) { pthread_mutex_lock(&mutex); payload = 1; pthread_mutex_unlock(&mutex); }
int read_payload(void) { int value; pthread_mutex_lock(&mutex); value = payload; pthread_mutex_unlock(&mutex); return value; }
