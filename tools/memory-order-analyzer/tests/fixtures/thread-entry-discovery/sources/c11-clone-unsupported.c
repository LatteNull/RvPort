int clone(int (*callback)(void *), void *stack, int flags, void *argument);
static int worker(void *argument) { return argument != 0; }
int main(void) { return clone(worker, 0, 0, 0); }
