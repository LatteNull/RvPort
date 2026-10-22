#define INNER(fn, a, b) fn(a, b)
#define OUTER(fn, a, b) INNER(fn, a, b)
