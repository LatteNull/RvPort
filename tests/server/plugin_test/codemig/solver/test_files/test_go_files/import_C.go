"""
// #include <x86intrin.h>
// #include <x86intrin.h>
// #include <immintrin.h>
// #include <stdio.h>
// #include <stdlib.h>
import "C"
"""
"""
/*
int main() {
    int a = __builtin_foo(1, 2);
    float b = __builtin_bar(3.0);
    __builtin_baz();
}
*/
import "C"
"""
"""
/*
#include <stdio.h>
*/
// #include <stdlib.h>

import "C"
"""
"""
/*
#include <stdio.h>
#if defined(__x86_64__) || defined(__AVX2__)
  #define FOO 1
#elif defined(__aarch64__)
  #define FOO 2
#endif
*/
import "C"
"""
"""
/*
#include <stdio.h>

#include <stdlib.h>
void foo() {
    __asm__ volatile (
        "movl $1, %%eax\n"
        "int $0x80"
    );
}

void foo() {
    __asm__ volatile (
        "movl $1, %%eax\n"
        "int $0x80"
    );
}
*/
import "C"
"""
"""
/*
#include <stdio.h>

#include <stdlib.h>
void hello() {
    printf("Hello from C\n");
}
*/
import AB
import "C"
"""
"""
/*
#include <stdio.h>
#include <stdlib.h>
void hello() {
    printf("Hello from C\n");
}
*/

import "C"
"""
"""
import "C"
"""
"""
/*
#include <stdio.h>
#include <stdlib.h>
void hello() {
    printf("Hello from C\n");
}
*/
"""