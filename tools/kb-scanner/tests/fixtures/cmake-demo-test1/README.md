# VectorCalc 修复前版本

该版本故意绑定 x86_64 和 AVX2，用于演示 RvPort 如何发现架构迁移风险。

## 构建

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j2
ctest --test-dir build --output-on-failure
```

在非 x86_64 环境中，CMake 配置阶段会主动失败。即使移除该检查，源码中的 AVX2 intrinsic、x86 内联汇编和编译参数也需要迁移处理。
