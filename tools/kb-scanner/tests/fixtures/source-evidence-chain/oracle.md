# Human source-chain oracle

This fixture is read-only input; never run Make or a compiler.

The macro definition originates at Makefile:1 (`-DUSE_AVX2=1`).
Makefile:2 references BASE_FLAGS; Makefile:6 actually consumes CPPFLAGS
in a C++ compile recipe for main.cpp, whose membership is declared at line 5.
main.cpp:4 tests definition existence, guarding WRAP_OUTER at line 5.
wrapper.h:2 defines WRAP_OUTER and expands WRAP_INNER; wrapper.h:1
defines WRAP_INNER and contains the exact intrinsic `_mm256_setzero_si256`.
main.cpp:1 establishes local include visibility. Both wrapper layers must survive.
Knowledge matching is a side branch of the actual intrinsic, not a causal code step.

Negative variants are constructed independently in tests: unused CPPFLAGS,
recipe for another source, unresolved variable, duplicate target configuration,
`-D USE_AVX2=0` (defined true but numeric false), later `-UUSE_AVX2`,
source `#undef`/`#define`, and missing local include. None may invent a
selected build-to-condition relationship from a matching macro name alone.
