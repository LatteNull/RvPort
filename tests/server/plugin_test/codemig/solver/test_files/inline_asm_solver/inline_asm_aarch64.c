#include <stdio.h>

int main() {
    int sum = 0;
    int count = 10;

    asm volatile (
        "mov x1, %[cnt]\n\t"       // x1 = count
        "mov x2, #0\n\t"           // x2 = i
        "mov x3, #0\n\t"           // x3 = sum
        "loop_start:\n\t"
        "add x3, x3, x2\n\t"       // sum += i
        "add x2, x2, #1\n\t"       // i++
        "subs x1, x1, #1\n\t"      // count--
        "bne loop_start\n\t"       // if count != 0, jump
        "str w3, %[res]\n\t"       // store result
        : [res] "=m" (sum)
        : [cnt] "r" (count)
        : "x1", "x2", "x3", "memory"
    );

    printf("aarch64 sum = %d\n", sum);
    return 0;
}
