## Why

新 staged scanner 在 AVX 人工基线范围内已完整识别 x86 header、向量类型、intrinsic、宏替换和构建参数，但兼容投影丢失了部分已存在的证据细节，构建目标到源码的可达性闭包也不足，导致 `symbol` 为空、宏定义位置难以追溯、诊断重复、明显 AVX-only 项目的分类与摘要过于保守。现在需要修复这些表达和分析缺口，使现有 schema 1.0 报告既保持兼容，又能准确呈现 scanner 已经掌握的事实和有证据支持的项目结论。

## What Changes

- 保持 `scan-result.json` 的 `schemaVersion: "1.0"`、既有顶层字段、Finding 核心字段、summary 计数口径以及 JSON/HTML/log 三个 artifact，不引入第二套主结果或 breaking schema。
- 完善 Finding 投影：从 Evidence/Relation 恢复可用 `symbol`，在 `trace` 中闭合宏调用到宏定义和终端 intrinsic 的证据引用，并以可选字段保留完整 source span。
- 为合并后的构建参数 Finding 在 `trace` 中保留 occurrence count 和逐次出现的位置/选择状态，同时保持现有 Finding 聚合和顶层位置语义。
- 聚合重复的 unresolved/ambiguous relation diagnostics，保留稳定计数、代表位置和可追溯引用，避免同类诊断淹没有效结论。
- 补齐 build target → source → x86 dependency 的静态可达性分析，并对重复宏定义按实际可见性、配置和位置消歧；无法证明时继续保持 unknown，不通过猜测升级。
- 修正项目分类和 summary 映射，使已证明的 x86 依赖、缺少 RISC-V/generic alternative 与 portability gap 能一致表达，同时不把纯静态结论表述成真实编译或测试结果。
- 修正 AVX 人工基线中 3 个错误列号，将已实现的 24 个构建参数 occurrence 从 deferred 基线迁入正式回归，并增加字段级人工对照断言。
- 为每个新增或实质修改的投影、诊断、图分析、分类和评估业务模块同步补齐隔离单元测试及机器可读映射，在独立 `kb-scanner-test` 容器中执行至少 90% line / 80% branch 门禁和完整回归；不在宿主机安装依赖。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `kb-scanner-compatible-projection-and-cutover`: 完善兼容 Finding/trace、完整 span、聚合 occurrence、diagnostic 去重以及 schema 1.0 投影约束。
- `kb-scanner-evidence-graph`: 补齐投影所需的引用闭包，并改进重复宏定义的有证据消歧和关系诊断聚合输入。
- `kb-scanner-build-selection-analysis`: 建立 build target 到 source 和 x86 dependency 的可追溯可达性闭包，并保留每次构建参数 occurrence。
- `kb-scanner-classification-and-assessment`: 使 source/build reachability、alternative 缺失、portability gap、blocking/actionable 和项目 readiness 的表达一致且保守。

## Impact

- 主要影响 `kb_scanner/graph`、`kb_scanner/analyzers`、`kb_scanner/classifiers`、`kb_scanner/assessors`、`kb_scanner/projection` 与相关兼容策略/renderer。
- 更新 AVX 人工基线、build-selection 基线、compatible cutover fixtures、测试 inventory 和容器测试门禁。
- 不修改两份 compiler-derived facts（`clang-x86-entries.json`、`gcc-x86-entries.json`）及其摘要，不恢复 Legacy/YAML 生产路径，不执行真实编译、链接、测试或项目命令。
- 范围仅限 C/C++、汇编、构建/打包和测试选择的静态迁移分析，继续排除 OS、内核、系统调用、驱动与板级迁移。
