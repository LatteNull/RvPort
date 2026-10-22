template <typename Backend>
struct Kernel;

struct avx2_tag {};

template <>
struct Kernel<avx2_tag> {
  static float run(float *data);
};

