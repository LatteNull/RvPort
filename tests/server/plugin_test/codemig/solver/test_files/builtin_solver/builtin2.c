#include <math.h>

int main() {
  double result1 = __builtin_aarch64_get_fpcr(1.0, -2.0);
  return 0;
}
