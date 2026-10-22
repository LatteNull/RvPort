#include <atomic>
extern int payload;
extern std::atomic<int> flag;
void *producer(void *);
void *consumer(void *);
