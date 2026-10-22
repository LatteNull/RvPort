#ifndef SUPPORT_H
#define SUPPORT_H

#define FAST(x, y) _mm_add_ps((x), (y))
#define WRAP(x, y) FAST((x), (y))
#define LOOP_A(x) LOOP_B(x)
#define LOOP_B(x) LOOP_A(x)

#endif
