#pragma GCC target("sse2,avx2")
static void gcc_target(void) {}

#pragma clang attribute push(__attribute__((target("aes,avx,pclmul"))), apply_to = function)
static void clang_target(void) {}
#pragma clang attribute pop

__attribute__((target_clones("default,avx2")))
int cloned(int x) { return x; }
