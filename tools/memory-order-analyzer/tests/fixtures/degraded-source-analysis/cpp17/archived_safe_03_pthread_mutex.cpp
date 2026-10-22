// Minimized local regression derived from archived sample SHA-256
// f37e516834a9511b5591deb6a2b83ea31332a6923d2d6b932d93f217b9d89eae.
#include <mutex>
#include <pthread.h>
int payload;
bool ready;
std::mutex mutex;
void *producer(void *) { std::lock_guard<std::mutex> guard(mutex); payload = 42; ready = true; return nullptr; }
void *consumer(void *) { std::lock_guard<std::mutex> guard(mutex); if (ready) (void)payload; return nullptr; }
int main() { pthread_t a, b; pthread_create(&a, nullptr, producer, nullptr); pthread_create(&b, nullptr, consumer, nullptr); }
