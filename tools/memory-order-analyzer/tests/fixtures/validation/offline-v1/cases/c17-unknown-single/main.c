#include <pthread.h>
#include <stdatomic.h>
static int payload;
static atomic_int flag;
static void *producer(void *arg) { (void)arg; payload = 42; atomic_thread_fence(memory_order_release); atomic_store_explicit(&flag, 1, memory_order_relaxed); return 0; }
static void *consumer(void *arg) { (void)arg; if (atomic_load_explicit(&flag, memory_order_relaxed)) { atomic_thread_fence(memory_order_acquire); return (void *)(long)payload; } return 0; }
int main(void) { pthread_t p, c; pthread_create(&p, 0, producer, 0); pthread_create(&c, 0, consumer, 0); pthread_join(p, 0); pthread_join(c, 0); }
