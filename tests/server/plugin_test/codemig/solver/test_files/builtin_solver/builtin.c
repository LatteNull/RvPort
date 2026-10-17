#include <math.h>

int main() {
  double result1 = __builtin_copysignq(1.0, -2.0);  // __builtin_cpu_init
  // double result2 = __builtin_copysignq(1.0, -2.0);
  double result3 = __builtin_copysignq(1.0, -2.0);
  __builtin_cpu_init(); double result5 = __builtin_copysignq(1.0, -2.0);
  /* double result6 = __builtin_copysignq(1.0, -2.0); */
  return 0;
}
