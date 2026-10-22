cmake_minimum_required(VERSION 3.28)
project(fp_ir_worker LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(FP_SCANNER_BUILD_TESTS "Build C++ unit tests" ON)
option(FP_SCANNER_COVERAGE "Enable source-based coverage" OFF)

find_package(LLVM 21.1.8 EXACT REQUIRED CONFIG)
list(APPEND CMAKE_MODULE_PATH "${LLVM_CMAKE_DIR}")
include(HandleLLVMOptions)
include_directories(SYSTEM ${LLVM_INCLUDE_DIRS})
add_definitions(${LLVM_DEFINITIONS})

llvm_map_components_to_libnames(FP_LLVM_LIBS AsmParser Core IRReader BitReader Support)

add_library(fp_ir_facts STATIC src/cpp/ir_facts.cpp)
target_include_directories(fp_ir_facts PUBLIC src/cpp)
target_link_libraries(fp_ir_facts PUBLIC ${FP_LLVM_LIBS})

add_executable(fp-ir-worker src/cpp/ir_worker.cpp)
target_link_libraries(fp-ir-worker PRIVATE fp_ir_facts)

if(FP_SCANNER_COVERAGE)
  foreach(target fp_ir_facts fp-ir-worker)
    target_compile_options(${target} PRIVATE -fprofile-instr-generate -fcoverage-mapping)
    target_link_options(${target} PRIVATE -fprofile-instr-generate -fcoverage-mapping)
  endforeach()
endif()

if(FP_SCANNER_BUILD_TESTS)
  enable_testing()
  find_package(GTest REQUIRED)
  add_executable(fp-ir-worker-tests tests/cpp/test_ir_facts.cpp)
  target_link_libraries(fp-ir-worker-tests PRIVATE fp_ir_facts GTest::gtest_main)
  if(FP_SCANNER_COVERAGE)
    target_compile_options(fp-ir-worker-tests PRIVATE -fprofile-instr-generate -fcoverage-mapping)
    target_link_options(fp-ir-worker-tests PRIVATE -fprofile-instr-generate -fcoverage-mapping)
  endif()
  include(GoogleTest)
  gtest_discover_tests(fp-ir-worker-tests)
  add_test(NAME fp-ir-worker-version COMMAND fp-ir-worker --version-json)
  add_test(NAME fp-ir-worker-invalid-arguments COMMAND fp-ir-worker)
  set_tests_properties(fp-ir-worker-invalid-arguments PROPERTIES WILL_FAIL TRUE)
  add_test(NAME fp-ir-worker-invalid-single-argument COMMAND fp-ir-worker --bad)
  set_tests_properties(fp-ir-worker-invalid-single-argument PROPERTIES WILL_FAIL TRUE)
  add_test(NAME fp-ir-worker-even-arguments COMMAND fp-ir-worker --input x extra)
  set_tests_properties(fp-ir-worker-even-arguments PROPERTIES WILL_FAIL TRUE)
  add_test(NAME fp-ir-worker-missing-argument COMMAND fp-ir-worker --input missing.bc)
  set_tests_properties(fp-ir-worker-missing-argument PROPERTIES WILL_FAIL TRUE)
  set(FP_WORKER_COMMON
      --input ${CMAKE_SOURCE_DIR}/tests/fixtures/bitcode/scalar.bc
      --artifact-set-id aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
      --artifact-key bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
      --physical-tu-id cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      --context-id dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
      --profile source-preserving
      --protocol-version 1.1
      --sha256 eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
      --max-summary-depth 3
      --max-summary-call-edges 1000)
  add_test(NAME fp-ir-worker-success COMMAND fp-ir-worker ${FP_WORKER_COMMON} --max-facts 100 --max-use-edges 1000)
  add_test(NAME fp-ir-worker-invalid-budget COMMAND fp-ir-worker ${FP_WORKER_COMMON} --max-facts bad --max-use-edges 1000)
  set_tests_properties(fp-ir-worker-invalid-budget PROPERTIES WILL_FAIL TRUE)
  add_test(NAME fp-ir-worker-invalid-bitcode COMMAND fp-ir-worker
      --input ${CMAKE_SOURCE_DIR}/tests/fixtures/bitcode/invalid.bc.txt
      --artifact-set-id aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
      --artifact-key bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
      --physical-tu-id cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      --context-id dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
      --profile source-preserving
      --protocol-version 1.1
      --sha256 eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
      --max-facts 100
      --max-use-edges 1000
      --max-summary-depth 3
      --max-summary-call-edges 1000)
  set_tests_properties(fp-ir-worker-invalid-bitcode PROPERTIES WILL_FAIL TRUE)
endif()
