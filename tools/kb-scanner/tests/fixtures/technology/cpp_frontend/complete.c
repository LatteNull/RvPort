#define ARCH_VALUE 7
#if defined(__x86_64__)
static int x86_value(int value) {
  __asm__ volatile("movl %1, %0" : "=r"(value) : "r"(value));
  return value;
}
#else
static int portable_value(int value) {
  return value + ARCH_VALUE;
}
#endif
