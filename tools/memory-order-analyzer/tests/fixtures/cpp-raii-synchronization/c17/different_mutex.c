#include <pthread.h>

int payload;
pthread_mutex_t left = PTHREAD_MUTEX_INITIALIZER;
pthread_mutex_t right = PTHREAD_MUTEX_INITIALIZER;
void write_payload(void) { pthread_mutex_lock(&left); payload = 1; pthread_mutex_unlock(&left); }
int read_payload(void) { int value; pthread_mutex_lock(&right); value = payload; pthread_mutex_unlock(&right); return value; }
