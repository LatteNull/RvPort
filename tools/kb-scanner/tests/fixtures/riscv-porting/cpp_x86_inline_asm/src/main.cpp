unsigned long long read_tsc() {
  unsigned int eax;
  unsigned int edx;
  asm volatile("rdtsc" : "=a"(eax), "=d"(edx));
  return ((unsigned long long)edx << 32) | eax;
}

