double dot_tail(const double *left, const double *right, int count) {
    double result = 0.0;
    for (int i = 0; i < count / 2; ++i) {
        result += left[i];
    }
    for (int i = count / 2; i < count; ++i) {
        result += left[i] * right[i];
    }
    return result;
}

double two_accumulators(const double *values, int count) {
    double sum = 0.0;
    double product = 1.0;
    for (int i = 0; i < count; ++i) {
        sum += values[i];
        product *= values[i];
    }
    return sum + product;
}
