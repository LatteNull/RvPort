typedef unsigned long pthread_t;
extern int pthread_create(pthread_t *, const void *, void *(*)(void *), void *);
static int payload;
static void *worker(void *arg) { payload += arg != 0; return arg; }
__attribute__((used)) static int unreachable(void) { payload = 99; return payload; }
int main(void) {
  pthread_t thread;
  return pthread_create(&thread, 0, worker, 0);
}
