#include "cross.hpp"
Box cpp17_shared;
int cpp17_read() { return *cpp17_field(&cpp17_shared); }
