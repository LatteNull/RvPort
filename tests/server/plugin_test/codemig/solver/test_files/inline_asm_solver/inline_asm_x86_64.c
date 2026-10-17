#include <stdio.h>

int main() {
    int sum = 0;
    int i = 10;

    asm volatile (
        "movl %[count], %%ecx\n\t"   // 将计数值放入 ECX
        "xorl %%eax, %%eax\n\t"      // EAX 清零（用于累加）
        "xorl %%ebx, %%ebx\n\t"      // EBX 清零（用于迭代器）
        "loop_start:\n\t"
        "addl %%ebx, %%eax\n\t"      // 将 EBX 加到 EAX 上
        "incl %%ebx\n\t"             // EBX++
        "loop loop_start\n\t"        // 循环
        "movl %%eax, %[result]\n\t"  // 把结果写入 C 变量
        : [result] "=r" (sum)        // 输出
        : [count] "r" (i)            // 输入
        : "eax", "ebx", "ecx"        // 被修改的寄存器
    );

    printf("x86_64 sum = %d\n", sum);
    return 0;
}
