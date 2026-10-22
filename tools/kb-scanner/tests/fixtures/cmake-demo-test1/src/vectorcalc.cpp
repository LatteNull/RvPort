#include "vectorcalc/vectorcalc.h"

#include <immintrin.h>

#include <cstdint>
#include <stdexcept>

#ifndef __AVX2__
#error "The before version requires AVX2 compiler support"
#endif

namespace vectorcalc {
namespace {

void validate_inputs(
    const float* left,
    const float* right,
    const float* output,
    const std::size_t count) {
    if (count == 0) {
        return;
    }
    if (left == nullptr) {
        throw std::invalid_argument("left input must not be null");
    }
    if (right == nullptr) {
        throw std::invalid_argument("right input must not be null");
    }
    if (output == nullptr) {
        throw std::invalid_argument("output must not be null");
    }
}

void validate_dot_inputs(
    const float* left,
    const float* right,
    const std::size_t count) {
    if (count == 0) {
        return;
    }
    if (left == nullptr) {
        throw std::invalid_argument("left input must not be null");
    }
    if (right == nullptr) {
        throw std::invalid_argument("right input must not be null");
    }
}

std::uint32_t maximum_cpuid_leaf() {
    std::uint32_t eax = 0;
    std::uint32_t ebx = 0;
    std::uint32_t ecx = 0;
    std::uint32_t edx = 0;
    __asm__ volatile(
        "cpuid"
        : "+a"(eax), "=b"(ebx), "=c"(ecx), "=d"(edx));
    return eax;
}

}  // namespace

void add_vectors(
    const float* left,
    const float* right,
    float* output,
    const std::size_t count) {
    validate_inputs(left, right, output, count);

    std::size_t index = 0;
    for (; index + 8 <= count; index += 8) {
        const __m256 left_values = _mm256_loadu_ps(left + index);
        const __m256 right_values = _mm256_loadu_ps(right + index);
        const __m256 result = _mm256_add_ps(left_values, right_values);
        _mm256_storeu_ps(output + index, result);
    }
    for (; index < count; ++index) {
        output[index] = left[index] + right[index];
    }
}

float dot_product(
    const float* left,
    const float* right,
    const std::size_t count) {
    validate_dot_inputs(left, right, count);

    __m256 accumulator = _mm256_setzero_ps();
    std::size_t index = 0;
    for (; index + 8 <= count; index += 8) {
        const __m256 left_values = _mm256_loadu_ps(left + index);
        const __m256 right_values = _mm256_loadu_ps(right + index);
        accumulator = _mm256_add_ps(
            accumulator,
            _mm256_mul_ps(left_values, right_values));
    }

    alignas(32) float lanes[8] = {};
    _mm256_store_ps(lanes, accumulator);
    float result = 0.0F;
    for (const float lane : lanes) {
        result += lane;
    }
    for (; index < count; ++index) {
        result += left[index] * right[index];
    }
    return result;
}

const char* implementation_name() {
    return maximum_cpuid_leaf() > 0 ? "x86-avx2" : "x86-unknown";
}

}  // namespace vectorcalc
