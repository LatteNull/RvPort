#include <pthread.h>
static void *worker(void *arg) { return arg; }
int main(void) {
    pthread_t thread;
    if (pthread_create(&thread, 0, worker, 0) != 0) return 1;
    return pthread_join(thread, 0);
}
