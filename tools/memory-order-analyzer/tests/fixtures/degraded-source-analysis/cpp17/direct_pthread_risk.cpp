#include <pthread.h>
int payload;
bool ready;
void *producer(void *) { payload = 42; ready = true; return nullptr; }
void *consumer(void *) { if (ready) (void)payload; return nullptr; }
int main() { pthread_t a, b; pthread_create(&a, nullptr, producer, nullptr); pthread_create(&b, nullptr, consumer, nullptr); pthread_join(a, nullptr); pthread_join(b, nullptr); }
