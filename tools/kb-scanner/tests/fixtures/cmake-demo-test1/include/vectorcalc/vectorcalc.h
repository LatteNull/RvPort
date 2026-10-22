#pragma once

#include <cstddef>

namespace vectorcalc {

void add_vectors(
    const float* left,
    const float* right,
    float* output,
    std::size_t count);

float dot_product(
    const float* left,
    const float* right,
    std::size_t count);

const char* implementation_name();

}  // namespace vectorcalc
