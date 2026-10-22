#include "vectorcalc/vectorcalc.h"

#include <array>
#include <iostream>
#include <numeric>

int main() {
    const std::array<float, 8> left{1, 2, 3, 4, 5, 6, 7, 8};
    const std::array<float, 8> right{8, 7, 6, 5, 4, 3, 2, 1};
    std::array<float, 8> output{};

    vectorcalc::add_vectors(left.data(), right.data(), output.data(), output.size());
    const float sum = std::accumulate(output.begin(), output.end(), 0.0F);
    const float dot = vectorcalc::dot_product(left.data(), right.data(), left.size());

    std::cout << "implementation=" << vectorcalc::implementation_name()
              << " sum=" << sum
              << " dot=" << dot << '\n';
    return 0;
}
