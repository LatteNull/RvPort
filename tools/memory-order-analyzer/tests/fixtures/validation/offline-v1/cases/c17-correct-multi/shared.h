#include <stdatomic.h>
extern int payload;
extern atomic_int flag;
void *producer(void *arg);
void *consumer(void *arg);
