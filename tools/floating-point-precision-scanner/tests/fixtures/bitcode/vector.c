typedef float float4 __attribute__((ext_vector_type(4)));

float4 vector_add(float4 left, float4 right) {
  return left + right;
}
