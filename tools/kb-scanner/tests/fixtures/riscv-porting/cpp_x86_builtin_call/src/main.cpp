int has_avx2() {
  return __builtin_cpu_supports("avx2");
}

int builtin_ia32() {
  return __builtin_ia32_rdtsc();
}

