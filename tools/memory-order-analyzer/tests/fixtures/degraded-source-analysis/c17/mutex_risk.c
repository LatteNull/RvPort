#include <pthread.h>
int ready;
int payload;
static void *producer(void *p) { (void)p; payload = 42; ready = 1; return 0; }
static void *consumer(void *p) { (void)p; if (ready) (void)payload; return 0; }
int main(void) { pthread_t a, b; pthread_create(&a, 0, producer, 0); pthread_create(&b, 0, consumer, 0); pthread_join(a, 0); pthread_join(b, 0); return 0; }
