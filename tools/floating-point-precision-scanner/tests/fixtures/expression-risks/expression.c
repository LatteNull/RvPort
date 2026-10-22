#include <math.h>

float narrow(double value) { return value; }

int compare(double left, double right) { return left == right; }

double sum(const double *values, int count) {
  double total = 0.0;
  for (int index = 0; index < count; ++index) total += values[index];
  return total;
}

double trig(double value) { return sin(value); }
