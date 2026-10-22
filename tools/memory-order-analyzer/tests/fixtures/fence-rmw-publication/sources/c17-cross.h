#include <stdatomic.h>
extern _Atomic int cross_flag;
extern int cross_payload;
void cross_publish(void);
int cross_consume(void);
