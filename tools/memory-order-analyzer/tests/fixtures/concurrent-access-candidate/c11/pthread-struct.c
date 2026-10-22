#include <pthread.h>

struct shared_state { int payload; pthread_mutex_t mutex; } state = {0, PTHREAD_MUTEX_INITIALIZER};

static void *writer(void *unused) {
    (void)unused;
    pthread_mutex_lock(&state.mutex);
    state.payload = 1;
    pthread_mutex_unlock(&state.mutex);
    return 0;
}

int main(void) {
    pthread_t thread;
    pthread_create(&thread, 0, writer, 0);
    pthread_mutex_lock(&state.mutex);
    int value = state.payload;
    pthread_mutex_unlock(&state.mutex);
    pthread_join(thread, 0);
    return value;
}
