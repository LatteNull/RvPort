#include <atomic>
#include <pthread.h>
struct shared_state { std::atomic<int> ready{0}; int payload{}; } state;
void *producer(void *) { state.payload = 42; state.ready.store(1, std::memory_order_relaxed); return nullptr; }
void *consumer(void *) { if (state.ready.load(std::memory_order_relaxed)) (void)state.payload; return nullptr; }
int main() { pthread_t a, b; pthread_create(&a, nullptr, producer, nullptr); pthread_create(&b, nullptr, consumer, nullptr); pthread_join(a, nullptr); pthread_join(b, nullptr); }
