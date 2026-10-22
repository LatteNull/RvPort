double scalar(double left, double right) {
  double sum = left + right;
  return sum == left ? (float)sum : sum / right;
}
