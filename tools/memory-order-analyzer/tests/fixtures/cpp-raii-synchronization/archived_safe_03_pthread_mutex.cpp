#include <pthread.h>
#include <mutex>

int payload = 0;
bool ready = false;
std::mutex mutex;
void *producer(void *) { std::lock_guard<std::mutex> guard(mutex); payload = 42; ready = true; return nullptr; }
void *consumer(void *) { std::lock_guard<std::mutex> guard(mutex); if (ready) (void)payload; return nullptr; }
int main() { pthread_t a, b; pthread_create(&a, nullptr, producer, nullptr); pthread_create(&b, nullptr, consumer, nullptr); pthread_join(a, nullptr); pthread_join(b, nullptr); }
