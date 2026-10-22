#include <pthread.h>

int shared_value;
pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
void *worker(void *) { pthread_mutex_lock(&mutex); shared_value++; pthread_mutex_unlock(&mutex); return nullptr; }
int main() { pthread_t first, second; pthread_create(&first, nullptr, worker, nullptr); pthread_create(&second, nullptr, worker, nullptr); pthread_join(first, nullptr); pthread_join(second, nullptr); return shared_value; }
