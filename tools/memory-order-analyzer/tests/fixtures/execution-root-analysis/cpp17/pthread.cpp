#include <pthread.h>
static void *worker(void *arg) { return arg; }
int main() {
    pthread_t thread;
    return pthread_create(&thread, nullptr, worker, nullptr) || pthread_join(thread, nullptr);
}
