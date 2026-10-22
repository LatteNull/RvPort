#include <stdatomic.h>
struct shared_state { _Atomic int ready; int payload; };
extern struct shared_state state;
void *producer(void *);
void *consumer(void *);
