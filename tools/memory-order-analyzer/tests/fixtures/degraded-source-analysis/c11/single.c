#include <pthread.h>
#include <stdatomic.h>

struct shared_state { _Atomic int ready; int payload; } state = {0, 0};
union observed_value { int signed_value; unsigned raw; } observed;

static void *producer(void *unused) {
    (void)unused;
    state.payload = 42;
    atomic_store_explicit(&state.ready, 1, memory_order_release);
    return 0;
}

static void *consumer(void *unused) {
    (void)unused;
    if (atomic_load_explicit(&state.ready, memory_order_acquire))
        observed.signed_value = state.payload;
    return 0;
}

int main(void) {
    pthread_t first, second;
    pthread_create(&first, 0, producer, 0);
    pthread_create(&second, 0, consumer, 0);
    pthread_join(first, 0);
    pthread_join(second, 0);
    return observed.raw == 42u ? 0 : 0;
}
