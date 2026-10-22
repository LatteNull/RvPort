#include "shared.h"
int start_thread(thrd_t *handle, entry_fn callback, void *argument) {
  return thrd_create(handle, callback, argument);
}
