enum class Mode { fast, avx2_counted, arm_neon };
int avx2_counted = 0;
const char *text = "Backend::avx2";
// Backend::avx2 and X86_AESNI are comments only.
int ordinary_identifier(int backend_avx2_counter) {
  return backend_avx2_counter + avx2_counted;
}
