#include <stdio.h>

// 单行注释
char* message = "This is a /* string  with fake comments";
#ifdef __x86
#endif
char ch = '"'; // 另一个注释

/* 这是一个
   多行注释 */

/* 第二个注释*/
int main() {
    printf("Hello /* not a comment */ World\n");
    /* 另一个注释 */
    return 0;
}
/* 第三个注释*/
int test() {
    printf("Hello not a comment */ World\n");
    /* 另一个注释 */
    return 0;
}
/* 最后一个注释 */