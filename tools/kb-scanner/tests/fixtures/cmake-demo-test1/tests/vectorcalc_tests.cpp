#include "vectorcalc/vectorcalc.h"

#include <array>
#include <cmath>
#include <exception>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

int failures = 0;

void expect_true(const bool condition, const std::string& message) {
    if (!condition) {
        std::cerr << "FAIL: " << message << '\n';
        ++failures;
    }
}

void expect_close(const float actual, const float expected, const std::string& message) {
    expect_true(std::fabs(actual - expected) < 0.0001F, message);
}

template <typename Action>
void expect_invalid_argument(Action action, const std::string& message) {
    try {
        action();
        expect_true(false, message);
    } catch (const std::invalid_argument&) {
        expect_true(true, message);
    } catch (const std::exception&) {
        expect_true(false, message + " threw the wrong exception");
    }
}

void test_full_vector_and_tail() {
    const std::array<float, 10> left{1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
    const std::array<float, 10> right{10, 9, 8, 7, 6, 5, 4, 3, 2, 1};
    std::array<float, 10> output{};

    vectorcalc::add_vectors(left.data(), right.data(), output.data(), output.size());
    for (const float value : output) {
        expect_close(value, 11.0F, "vector addition should cover SIMD and tail elements");
    }
    expect_close(
        vectorcalc::dot_product(left.data(), right.data(), left.size()),
        220.0F,
        "dot product should cover SIMD and tail elements");
}

void test_multiple_vector_chunks() {
    std::array<float, 16> left{};
    std::array<float, 16> right{};
    std::array<float, 16> output{};
    left.fill(1.5F);
    right.fill(2.5F);

    vectorcalc::add_vectors(left.data(), right.data(), output.data(), output.size());
    for (const float value : output) {
        expect_close(value, 4.0F, "vector addition should cover multiple SIMD chunks");
    }
    expect_close(
        vectorcalc::dot_product(left.data(), right.data(), left.size()),
        60.0F,
        "dot product should cover multiple SIMD chunks");
}

void test_empty_input() {
    vectorcalc::add_vectors(nullptr, nullptr, nullptr, 0);
    expect_close(vectorcalc::dot_product(nullptr, nullptr, 0), 0.0F, "empty dot product is zero");
}

void test_invalid_inputs() {
    float value = 1.0F;
    expect_invalid_argument(
        [&] { vectorcalc::add_vectors(nullptr, &value, &value, 1); },
        "add_vectors should reject a null left input");
    expect_invalid_argument(
        [&] { vectorcalc::add_vectors(&value, nullptr, &value, 1); },
        "add_vectors should reject a null right input");
    expect_invalid_argument(
        [&] { vectorcalc::add_vectors(&value, &value, nullptr, 1); },
        "add_vectors should reject a null output");
    expect_invalid_argument(
        [&] { vectorcalc::dot_product(nullptr, &value, 1); },
        "dot_product should reject a null left input");
    expect_invalid_argument(
        [&] { vectorcalc::dot_product(&value, nullptr, 1); },
        "dot_product should reject a null right input");
}

void test_implementation_name() {
    expect_true(
        std::string(vectorcalc::implementation_name()) == "x86-avx2",
        "before version should report the AVX2 implementation");
}

}  // namespace

int main() {
    test_full_vector_and_tail();
    test_multiple_vector_chunks();
    test_empty_input();
    test_invalid_inputs();
    test_implementation_name();

    if (failures != 0) {
        std::cerr << failures << " assertion(s) failed\n";
        return 1;
    }
    std::cout << "all vectorcalc tests passed\n";
    return 0;
}
