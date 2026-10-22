enum class Backend { scalar, avx2 = 2, riscv, portable };

float avx2_sum(float *data);
float scalar_sum(float *data);

float select_runtime(Backend backend, float *data) {
  if (backend == Backend::avx2) {
    return _mm256_cvtss_f32(_mm256_add_ps(*(__m256 *)data, *(__m256 *)data));
  }
  return scalar_sum(data);
}

template <Backend B>
float select_template(float *data) {
  if constexpr (B == Backend::avx2) {
    return avx2_sum(data);
  }
  return scalar_sum(data);
}

float select_switch(Backend backend, float *data) {
  switch (backend) {
    case Backend::avx2: return avx2_sum(data);
    case Backend::riscv: return scalar_sum(data);
    case Backend::portable: return scalar_sum(data);
    default: return scalar_sum(data);
  }
}

enum LegacyBackend { BACKEND_SCALAR, BACKEND_AVX2 };
int select_unqualified(LegacyBackend backend) {
  switch (backend) {
    case BACKEND_AVX2: return 1;
    default: return 0;
  }
}
