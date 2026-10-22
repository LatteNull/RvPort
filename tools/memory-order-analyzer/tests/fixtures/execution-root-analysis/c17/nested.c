#include <pthread.h>

static void *leaf(void *argument) {
  return argument;
}

static void *parent(void *argument) {
  pthread_t child;
  if (pthread_create(&child, 0, leaf, argument) != 0)
    return argument;
  pthread_join(child, 0);
  return argument;
}

int main(void) {
  pthread_t thread;
  if (pthread_create(&thread, 0, parent, 0) != 0)
    return 1;
  return pthread_join(thread, 0);
}
