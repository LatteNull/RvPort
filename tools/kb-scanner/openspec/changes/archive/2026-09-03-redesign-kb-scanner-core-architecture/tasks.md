## 1. 总体设计评审

- [x] 1.1 评审并确认 C/C++ x86→RISC-V 的模块范围，以及操作系统、内核、系统调用、硬件适配和 RVWMO 实现的排除边界。
- [x] 1.2 逐项核对交叉验证结论，确认 `clang-x86-entries.json`、`gcc-x86-entries.json` 及现有高价值 x86 检测资产都有明确保留路径。
- [x] 1.3 评审“Workspace Intake → Frontends → Evidence Graph → Detectors/Analyzers → Classification → Assessment → Compatible Report Projection”的职责边界。
- [x] 1.4 固化 Fact/Evidence、Relation、Observation、Finding、Assessment 的术语、生命周期和禁止混用规则。

## 2. 现有结果兼容契约

- [x] 2.1 以当前 `report.py` 和后端 `KbScannerResult` 为基线，整理 `scan-result.json` 顶层字段、Finding 字段、字段类型和现有语义清单。
- [x] 2.2 为 Relation、Observation、Assessment 定义到现有 `findings[].trace`、`summary.readiness`、`project` 和 diagnostics 的兼容投影矩阵。
- [x] 2.3 确认 `schemaVersion` 保持 `1.0`，且新设计不新增主结果文件、不修改 artifact 文件名和类型。
- [x] 2.4 定义兼容性验收标准：既有 scanner fixture 不退化，当前后端 parser 无需修改即可导入，原 summary/finding 行为保持稳定。
- [x] 2.5 决定 `summary.readiness` 的最小可选字段集合，并确认旧消费者忽略该字段时不受影响。

## 3. 关键分析模型评审

- [x] 3.1 评审架构 ontology，覆盖 family、alias、feature、implementation role，以及注释 hint 与模糊代码标识符的边界。
- [x] 3.2 评审统一构建选择关系，确保能够用 Makefile、Autoconf、RPM 和 compile_commands 静态推导目标为 RISC-V 时的源码、参数和依赖选择链路，并排除交叉编译误选假设。
- [x] 3.3 评审测试角色与静态覆盖关系，确认 `x86_test_guarded`、`riscv_test_blocker`、`riscv_test_coverage_gap` 的证据门槛，不引入实际测试执行结果。
- [x] 3.4 评审项目级 readiness 状态及维度，明确缺失证据必须产生 unknown，不能等价为 ready。
- [x] 3.5 评审 memory-model IR checker 的外部结果关联边界，确认 KB Scanner 不重复实现 RVWMO 分析。

## 4. 后续 change 拆分

- [x] 4.1 为“事实/关系模型与结果兼容投影”拟定独立实现 change 的范围和验收条件。
- [x] 4.2 为“现有前端、Clang/GCC 事实数据和规则资产接入新分析层”拟定独立实现 change，要求 `generatedSet`、现有 fixture 和降噪能力不退化。
- [x] 4.3 为“Makefile/Autoconf 构建选择关系”拟定独立实现 change。
- [x] 4.4 为“架构感知测试分析”拟定独立实现 change。
- [x] 4.5 为“宏传播、RPM 深层关系和项目 readiness”分别确定后续 change 边界，避免一次重写全部能力。

## 5. 设计收口

- [x] 5.1 对实现语言、C/C++ 前端和 Makefile 部分求值边界等开放问题给出 spike 计划，不在本 change 内预设技术答案。
- [x] 5.2 运行 `openspec validate redesign-kb-scanner-core-architecture --strict` 并修复所有规格格式或一致性问题。
- [x] 5.3 完成设计评审后记录已接受的决策和仍需后续 change 解决的问题；本 change 不修改运行时代码。
