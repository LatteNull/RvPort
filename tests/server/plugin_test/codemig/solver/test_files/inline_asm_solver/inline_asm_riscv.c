#include <stdio.h>

int main() {
    int sum = 0;
    int count = 10;

    asm volatile (
        "mv t0, %[cnt]\n\t"       // t0 = count
        "li t1, 0\n\t"            // t1 = i
        "li t2, 0\n\t"            // t2 = sum
        "loop_start:\n\t"
        "add t2, t2, t1\n\t"      // sum += i
        "addi t1, t1, 1\n\t"      // i++
        "addi t0, t0, -1\n\t"     // count--
        "bnez t0, loop_start\n\t" // if count != 0, loop
        "sw t2, %[res]\n\t"       // store result
        : [res] "=m" (sum)
        : [cnt] "r" (count)
        : "t0", "t1", "t2", "memory"
    );

    printf("riscv sum = %d\n", sum);
    return 0;
}
