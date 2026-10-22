#include <threads.h>

struct box { int *pointer; } shared_box;
static int payload;

static int worker(void *unused) {
    (void)unused;
    *shared_box.pointer = 1;
    return 0;
}

int main(void) {
    thrd_t thread;
    shared_box.pointer = &payload;
    thrd_create(&thread, worker, 0);
    int value = *shared_box.pointer;
    thrd_join(thread, 0);
    return value;
}
