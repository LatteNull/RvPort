#include <stdatomic.h>
union payload_value { int value; unsigned bits; };
extern _Atomic int ready;
extern union payload_value payload;
void publish(void);
void consume(void);
