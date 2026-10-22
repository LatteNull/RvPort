#include <pthread.h>
#include "shared.h"
int main(void) { pthread_t thread; pthread_create(&thread, 0, write_payload, 0); int value = shared_payload; pthread_join(thread, 0); return value; }
