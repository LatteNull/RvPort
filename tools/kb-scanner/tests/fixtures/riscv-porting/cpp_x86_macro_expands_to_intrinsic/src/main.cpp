#define VEC_ADD(a, b) _mm256_add_ps(a, b)

void add_vector() {
  VEC_ADD(x, y);
}

