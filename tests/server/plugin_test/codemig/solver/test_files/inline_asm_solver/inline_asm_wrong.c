#include <stdio.h>

int main() {
    register int a = 1;
    register int b = 2;
    register int result;

    asm volatile (
        "add %0, %1, %2\n\t"
        : "=r" (result)      // 输出
        : "r" (a), "r" (b)    // 输入
        :

    printf("result = %d\n", result);
    return 0;
}
