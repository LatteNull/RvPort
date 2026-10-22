#include "portable.h"
#define APPLY(value) transform(value)

template <typename T>
T transform(T value) {
    if constexpr (sizeof(T) == 8) {
        return value;
    }
    return T{};
}

int run_cpp(int value) {
    return APPLY(value);
}
