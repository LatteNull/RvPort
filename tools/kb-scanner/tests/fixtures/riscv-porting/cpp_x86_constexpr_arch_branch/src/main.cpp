enum class Backend {
  scalar,
  avx2,
};

template <Backend B>
float sum(float *data) {
  if constexpr (B == Backend::avx2) {
    return avx2_sum(data);
  }
  return scalar_sum(data);
}

