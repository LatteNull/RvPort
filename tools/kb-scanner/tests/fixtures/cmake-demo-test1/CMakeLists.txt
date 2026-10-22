cmake_minimum_required(VERSION 3.20)

project(VectorCalcBefore LANGUAGES CXX)

option(VECTORCALC_ENABLE_COVERAGE "Enable source-based coverage instrumentation" OFF)

if(NOT CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|AMD64|amd64)$")
    message(FATAL_ERROR "The before version intentionally supports x86_64 only")
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(VECTORCALC_ENABLE_COVERAGE)
    if(CMAKE_CXX_COMPILER_ID MATCHES "Clang")
        add_compile_options(-O0 -g -fprofile-instr-generate -fcoverage-mapping)
        add_link_options(-fprofile-instr-generate -fcoverage-mapping)
    elseif(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
        add_compile_options(-O0 -g --coverage)
        add_link_options(--coverage)
    else()
        message(FATAL_ERROR "Coverage is supported with Clang or GCC")
    endif()
endif()

add_library(vectorcalc
    src/vectorcalc.cpp
)

target_include_directories(vectorcalc
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_compile_options(vectorcalc
    PRIVATE
        -mavx2
        -msse4.2
)

add_executable(vectorcalc_demo app/main.cpp)
target_link_libraries(vectorcalc_demo PRIVATE vectorcalc)

enable_testing()

add_executable(vectorcalc_tests tests/vectorcalc_tests.cpp)
target_link_libraries(vectorcalc_tests PRIVATE vectorcalc)

add_test(NAME vectorcalc_unit_tests COMMAND vectorcalc_tests)
add_test(NAME vectorcalc_demo_smoke COMMAND vectorcalc_demo)
set_tests_properties(vectorcalc_demo_smoke PROPERTIES
    PASS_REGULAR_EXPRESSION "implementation=x86-avx2 sum=72 dot=120"
)
