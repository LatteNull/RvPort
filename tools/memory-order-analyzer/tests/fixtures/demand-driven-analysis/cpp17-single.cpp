extern "C" int pthread_create(unsigned long *, const void *, void *(*)(void *), void *);
static int payload;
static void *worker(void *arg) { payload = arg ? 2 : 1; return arg; }
__attribute__((used)) static int unreachable() { return payload + 99; }
int main() {
  unsigned long thread;
  return pthread_create(&thread, nullptr, worker, nullptr);
}
