__attribute__((target("avx2")))
static int optimized(int value) {
    return value + 1;
}

typedef int vector4 __attribute__((vector_size(16)));

int use_attribute(int value) {
    return optimized(value);
}
