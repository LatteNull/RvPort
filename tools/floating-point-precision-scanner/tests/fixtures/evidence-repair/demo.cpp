#include "project.hpp"

#include <array>
#include <cmath>
#include <cstddef>

using real64 = double;

float convert(real64 value) {
    auto narrowed = RVPORT_TO_FLOAT(value);
    float *pointer = &narrowed;
    float (*function_pointer)(real64) = &convert;
    std::array<float, 2> values{1, 2};
    (void)pointer;
    (void)function_pointer;
    return narrowed + values[0];
}

float reduce(const float *values, std::size_t size) {
    float result = 0.0F;
    for (std::size_t index = 0; index < size; ++index) {
        result += values[index];
    }
    return result;
}
