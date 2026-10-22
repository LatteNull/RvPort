# Fixed LLVM bitcode corpus

English | [简体中文](README.md)

These binary fixtures are used only by local integration tests pinned to LLVM 21.1.8. They are excluded from the C++ source-coverage denominator.

To update them, run the following commands inside the `linux/amd64` `Dockerfile.dev` environment from the tool root `/workspace`. Preserve relative source paths and the reviewed baseline:

```sh
clang-21 -g -emit-llvm -c tests/fixtures/bitcode/scalar.c -o tests/fixtures/bitcode/scalar.bc
clang-21 -g -emit-llvm -c tests/fixtures/bitcode/calls.c -o tests/fixtures/bitcode/calls.bc
clang-21 -g -emit-llvm -c tests/fixtures/bitcode/vector.c -o tests/fixtures/bitcode/vector.bc
clang-21 -g -ffp-model=strict -emit-llvm -c tests/fixtures/bitcode/constrained.c -o tests/fixtures/bitcode/constrained.bc
sha256sum tests/fixtures/bitcode/*.bc
```

Reviewed baseline:

| File | Scenario | Bytes | SHA-256 |
|---|---|---:|---|
| `scalar.bc` | Scalar arithmetic, comparisons, narrowing/widening | 2968 | `551268ef934ba501798329fbf15ababb2195979b20ec5909e80f54eeb67c031e` |
| `calls.bc` | libm and FMA calls/intrinsics | 3176 | `e95d49a73c73d9c9f1d252fbdd58b280d9a452da6af23520a82914222d57469c` |
| `vector.bc` | Vector floating-point arithmetic | 2876 | `8cfd0f66ad6f77fd76c96d8e1126a730cc436a779ab73cfbe430dafbe852db28` |
| `constrained.bc` | Constrained FP and fenv | 2972 | `950ef2a289fb06d530de92c2bd44aa0b893b4353346f6f3394a3149bd94f6ad8` |

`invalid.bc.txt` is deterministic invalid input. Unit tests derive empty, truncated, incorrect-hash, incorrect-target/data-layout, no-debug, unknown-intrinsic, and budget-exceeded cases from these fixed bytes in temporary directories, avoiding duplicate or platform-dependent binaries in the repository. Fixture updates must update this table, real-worker oracles, and validation reports together, and be reviewed by another maintainer.
