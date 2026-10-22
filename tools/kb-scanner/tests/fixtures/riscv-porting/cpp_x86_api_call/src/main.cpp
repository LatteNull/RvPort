void cpu_feature_probe() {
  int out[4];
  __cpuid(out, 0);
  auto ticks = __rdtsc();
}

