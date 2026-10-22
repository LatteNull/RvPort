# LLVM BC 固定语料

这些二进制 fixture 只用于锁定 LLVM 21.1.8 的本地集成测试，不进入 C++ 覆盖率源码分母。
更新时必须在 `linux/amd64` 的 `Dockerfile.dev` 环境内，从工具根目录 `/workspace` 执行以下命令，保持源码相对路径与审核基线一致：

```sh
clang-21 -g -emit-llvm -c tests/fixtures/bitcode/scalar.c -o tests/fixtures/bitcode/scalar.bc
clang-21 -g -emit-llvm -c tests/fixtures/bitcode/calls.c -o tests/fixtures/bitcode/calls.bc
clang-21 -g -emit-llvm -c tests/fixtures/bitcode/vector.c -o tests/fixtures/bitcode/vector.bc
clang-21 -g -ffp-model=strict -emit-llvm -c tests/fixtures/bitcode/constrained.c -o tests/fixtures/bitcode/constrained.bc
sha256sum tests/fixtures/bitcode/*.bc
```

审核基线：

| 文件 | 场景 | 字节 | SHA-256 |
|---|---|---:|---|
| `scalar.bc` | 标量算术、比较、窄化/扩展 | 2968 | `551268ef934ba501798329fbf15ababb2195979b20ec5909e80f54eeb67c031e` |
| `calls.bc` | libm 与 FMA call/intrinsic | 3176 | `e95d49a73c73d9c9f1d252fbdd58b280d9a452da6af23520a82914222d57469c` |
| `vector.bc` | 向量浮点算术 | 2876 | `8cfd0f66ad6f77fd76c96d8e1126a730cc436a779ab73cfbe430dafbe852db28` |
| `constrained.bc` | constrained FP 与 fenv | 2972 | `950ef2a289fb06d530de92c2bd44aa0b893b4353346f6f3394a3149bd94f6ad8` |

`invalid.bc.txt` 是确定性非法输入。空文件、截断、错误摘要、错误 target/data layout、无 debug、
未知 intrinsic 与预算超限由单元测试在临时目录中从上述固定字节派生，避免提交重复或平台相关
二进制。fixture 更新必须同时更新本表、真实 worker oracle 与验证报告，并由另一名维护者审核。
