#include <pthread.h>
pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
struct shared_state { int ready; int payload; } state;
static void *producer(void *p) { (void)p; pthread_mutex_lock(&mutex); state.payload = 42; state.ready = 1; pthread_mutex_unlock(&mutex); return 0; }
static void *consumer(void *p) { (void)p; pthread_mutex_lock(&mutex); if (state.ready) (void)state.payload; pthread_mutex_unlock(&mutex); return 0; }
int main(void) { pthread_t a, b; pthread_create(&a, 0, producer, 0); pthread_create(&b, 0, consumer, 0); pthread_join(a, 0); pthread_join(b, 0); return 0; }
