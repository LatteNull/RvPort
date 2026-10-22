add_library(api INTERFACE)
target_compile_definitions(api INTERFACE USE_AVX2=1)
add_library(kernel kernel.cpp)
target_link_libraries(kernel PRIVATE api)
