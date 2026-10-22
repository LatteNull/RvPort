extern double sqrt(double);

double call_math(double value) {
  return __builtin_fma(value, 2.0, sqrt(value));
}
