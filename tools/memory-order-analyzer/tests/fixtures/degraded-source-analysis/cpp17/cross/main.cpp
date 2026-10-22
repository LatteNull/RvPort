#include <pthread.h>
#include "shared.hpp"
int main() { pthread_t a, b; pthread_create(&a, nullptr, producer, nullptr); pthread_create(&b, nullptr, consumer, nullptr); pthread_join(a, nullptr); pthread_join(b, nullptr); }
