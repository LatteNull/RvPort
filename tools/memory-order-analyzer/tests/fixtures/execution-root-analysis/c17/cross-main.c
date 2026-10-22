#include <pthread.h>
extern void *cross_worker(void *);
int main(void) {
    pthread_t thread;
    return pthread_create(&thread, 0, cross_worker, 0) || pthread_join(thread, 0);
}
