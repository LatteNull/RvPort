#include <stdio.h>

int main() {
    register int a = 1;
    register int b = 2;
    register int result;

    asm("some text with a quote: \" inside");

    printf("result = %d\n", result);
    return 0;
}
