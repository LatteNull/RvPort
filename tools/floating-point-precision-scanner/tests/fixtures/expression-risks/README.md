# 表达式风险 truth fixture

`expression.c` 由锁定的 Clang 21.1.8 在 Linux/amd64 容器中生成真实 AST；
`expected.json` 固定 canonical facts 1.3、LLVM facts/evidence 1.1 对应的规则结论。该 fixture
覆盖隐式 double→float 转换、计算值精确比较、循环累加和标准数学调用。因为最小 build
context 不固定应用 libm，数学库规则的 truth 结论必须是 `unknown`，不能借用容器宿主库。

固定 BC 及其源码 oracle 位于 `tests/fixtures/bitcode`；AST↔IR exact/strong/ambiguous truth
由 `tests/unit/test_ir_worker_evidence.py` 的固定 bundle/sidecar 数据覆盖。二进制 BC 不计入
C++ 源码覆盖率分母。
