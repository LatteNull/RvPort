#include <pthread.h>
#include "shared.h"
int main(void) { pthread_t a, b; pthread_create(&a, 0, producer, 0); pthread_create(&b, 0, consumer, 0); pthread_join(a, 0); pthread_join(b, 0); return 0; }
