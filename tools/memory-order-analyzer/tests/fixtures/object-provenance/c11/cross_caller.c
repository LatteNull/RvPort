#include "cross.h"
struct Shared c11_shared;
int c11_read(void) { return *c11_field(&c11_shared); }
