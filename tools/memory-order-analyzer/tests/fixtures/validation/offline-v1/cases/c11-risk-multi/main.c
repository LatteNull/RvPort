#include <pthread.h>
#include "shared.h"
int main(void) { pthread_t p, c; pthread_create(&p, 0, producer, 0); pthread_create(&c, 0, consumer, 0); pthread_join(p, 0); pthread_join(c, 0); }
