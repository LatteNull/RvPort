#include <threads.h>
typedef int (*entry_fn)(void *);
int start_thread(thrd_t *handle, entry_fn callback, void *argument);
int worker(void *argument);
