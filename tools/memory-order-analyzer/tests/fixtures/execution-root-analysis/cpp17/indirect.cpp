#include <pthread.h>
static void *worker(void *arg) { return arg; }
int launch(void *(*callback)(void *)) {
    pthread_t thread;
    return pthread_create(&thread, nullptr, callback, nullptr);
}
int main() { return launch(worker); }
