#include <pthread.h>
#include "shared.hpp"
int main() { pthread_t p, c; pthread_create(&p, nullptr, producer, nullptr); pthread_create(&c, nullptr, consumer, nullptr); pthread_join(p, nullptr); pthread_join(c, nullptr); }
