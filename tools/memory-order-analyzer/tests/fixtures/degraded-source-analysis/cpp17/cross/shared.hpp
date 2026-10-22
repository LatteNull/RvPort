#include <atomic>
extern std::atomic<int> ready;
extern int payload;
void *producer(void *);
void *consumer(void *);
