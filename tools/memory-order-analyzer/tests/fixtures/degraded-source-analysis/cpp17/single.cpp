#include <atomic>
#include <pthread.h>
std::atomic<int> ready{0};
int payload;
void *producer(void *) { payload = 42; ready.store(1, std::memory_order_release); return nullptr; }
void *consumer(void *) { if (ready.load(std::memory_order_acquire)) (void)payload; return nullptr; }
int main() { pthread_t a, b; pthread_create(&a, nullptr, producer, nullptr); pthread_create(&b, nullptr, consumer, nullptr); pthread_join(a, nullptr); pthread_join(b, nullptr); }
