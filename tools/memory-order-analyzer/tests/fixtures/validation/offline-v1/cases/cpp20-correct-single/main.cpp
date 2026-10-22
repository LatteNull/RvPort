#include <atomic>
#include <pthread.h>
static int payload;
static std::atomic<int> flag{0};
static void *producer(void *) { payload = 42; flag.store(1, std::memory_order_release); return nullptr; }
static void *consumer(void *) { if (flag.load(std::memory_order_acquire)) return reinterpret_cast<void *>(static_cast<long>(payload)); return nullptr; }
int main() { pthread_t p, c; pthread_create(&p, nullptr, producer, nullptr); pthread_create(&c, nullptr, consumer, nullptr); pthread_join(p, nullptr); pthread_join(c, nullptr); }
