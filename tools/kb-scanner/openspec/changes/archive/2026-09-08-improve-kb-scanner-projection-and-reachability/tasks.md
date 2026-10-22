## 1. 冻结修正范围与单元测试映射

- [x] 1.1 修正 AVX 人工 baseline 中 `set.c:56`、`setr.c:56` 和 `permute2f128.c:19` 的真实 token 起始列，并记录这是 baseline correction 而非 scanner 行为变更。
- [x] 1.2 将 AVX build baseline 的 24 个 x86 flag occurrence 从 deferred 迁入正式 path/span/flag/configuration/selection-status 断言，确认无 missing/extra。
- [x] 1.3 创建本 change 的机器可读 unit-test inventory，逐项映射 reference closure、macro resolver、relation diagnostic producer、target/source resolver、reachability analyzer、occurrence collector、proof builder、Finding/summary mapper、Diagnostic aggregator、renderer、classification policy 和 assessment reducer。
- [x] 1.4 固化 schema 1.0 必需字段、旧消费者、三个 artifact、Finding/summary 既有计数以及 Clang/GCC 两份事实文件 bytes/SHA-256 基线。

## 2. Evidence 引用闭包与宏定义消歧

- [x] 2.1 扩展 graph/reference index，使 Relation/ProofPath 的 source、target 和中间 Evidence/Entity 可确定性闭合，并对悬空、冲突和预算截断引用产生稳定 completeness/reason。
- [x] 2.2 为 reference closure 增加隔离单元测试，使用内存 snapshot/store 覆盖完整链、悬空 ID、类型冲突、循环、预算和输入乱序，并达到模块 90% line / 80% branch。
- [x] 2.3 实现基于 translation unit/include 可见性、configuration、定义位置和结构化 macro identity 的宏定义消歧，唯一或等价候选形成 complete proof，非等价候选保持 ambiguous。
- [x] 2.4 为 macro resolver 增加隔离单元测试，使用合成 Evidence/Relation 覆盖唯一、等价重复、非等价重复、配置冲突、include 顺序和乱序确定性，并达到模块覆盖门槛。
- [x] 2.5 将 relation diagnostic producer 改为输出可聚合的稳定 code/reason/kind/stage/severity/位置/引用数据，不在 graph 阶段重复生成用户文案。
- [x] 2.6 为 relation diagnostic producer 增加隔离单元测试，覆盖 unresolved/ambiguous、不同严重性、重复引用和 partial/failed 传播，并达到模块覆盖门槛。

## 3. Build target 到 source dependency 的静态可达性

- [x] 3.1 审计现有 build entities/relations，补齐 target/source membership 与 configuration identity 的稳定连接，且不读取或执行项目命令。
- [x] 3.2 实现 selector/configuration → target → source → knowledge-backed x86 dependency 的有界 Relation/ProofPath，只有全部关系 complete 且配置一致时标为 selected/reachable。
- [x] 3.3 为 target/source resolver、reachability analyzer 和 proof builder 分别增加隔离单元测试，使用 fake workspace/snapshot/budget 覆盖 selected、inactive、partial、dynamic、conflict、budget 和顺序扰动，每个模块达到 90% line / 80% branch。
- [x] 3.4 确保每个构建参数位置在聚合前保留独立 Evidence、完整 span、configuration 和 selection status，并用稳定根因关系关联。
- [x] 3.5 为 occurrence collector 增加隔离单元测试，覆盖同 flag 多位置、多配置状态、缺失 end span、去重与稳定排序，并达到模块覆盖门槛。

## 4. schema 1.0 Finding、trace 与 diagnostics 投影

- [x] 4.1 扩展 projection reference index，使 Finding mapper 能取得完整 Evidence closure，同时验证断裂引用而不重新读取源码、构建文件或 snippet。
- [x] 4.2 实现结构化 symbol 选择策略，按主 Evidence value、KnowledgeEntry symbol、终端 Relation target 的固定优先级填充 intrinsic、macro replacement 和 vector type Finding。
- [x] 4.3 在既有对象型 `trace` 中增加兼容的完整 primary span、occurrenceCount/occurrences 和闭合 evidence 引用，同时保持顶层 location、Finding identity、聚合数量和 summary 计数。
- [x] 4.4 为 reference index、symbol resolver 和 Finding mapper 分别增加隔离单元测试，覆盖宏调用/定义/终端链、vector/intrinsic、完整/断裂 span、24-to-4 occurrence 聚合、未知字段和输入乱序，每个模块达到覆盖门槛。
- [x] 4.5 实现 Diagnostic aggregator，按 code/reason/relation kind/stage/severity 确定分组，保留 count、代表位置、全部稳定引用和最严重状态。
- [x] 4.6 更新 JSON/HTML/log renderer 对聚合诊断及新增可选 trace 字段的处理，并保持 schema 1.0 和三个 artifact 行为。
- [x] 4.7 为 Diagnostic aggregator 和受影响 renderer 分别增加隔离单元测试，覆盖同组聚合、跨组隔离、failed/partial、转义、确定字节输出和旧消费者忽略可选字段，每个模块达到覆盖门槛。

## 5. Classification、portability gap 与 Assessment 一致性

- [x] 5.1 更新 classification decision table，使 selected source/build x86 dependency 使用闭合 proof 形成 blocking/actionable，inactive proof 形成 guarded/non-actionable，partial/冲突继续 unknown。
- [x] 5.2 实现显式 alternative completeness 与 portability-gap policy：只有范围完整且无 RISC-V/generic/portable alternative 时产生 gap，不完整时保持 unknown 而非误导性零值。
- [x] 5.3 为 classification policy 和 portability-gap policy 分别增加隔离单元测试，使用合成 Observation/Proof 覆盖 selected、inactive、alternative present/absent、unknown、冲突和顺序扰动，每个模块达到覆盖门槛。
- [x] 5.4 更新 assessment dimension reducer 和 summary mapper，使 target reachability、x86 dependency、alternative、portability gap 与 readiness 使用同一 proof 状态，且不从 Finding 数量推断项目结论。
- [x] 5.5 为 assessment reducer 和 summary mapper 分别增加隔离单元测试，覆盖证据完整的 x86-only、partial/provisional、无命中但输入不完整、冲突配置和静态范围标志，每个模块达到覆盖门槛。

## 6. AVX 字段级回归与兼容验证

- [x] 6.1 扩展 AVX evidence-graph 回归，逐项验证 39 个 header、362 个 vector type、360 个 intrinsic、45 个 comment hint、12 个宏定义、18 个 replacement 终端引用及其闭合 relation/span/symbol。
- [x] 6.2 扩展 AVX build-selection 回归，验证 24 个 occurrence 在 4 个兼容 Finding 的 trace 中全部可还原，且 path/span/flag/configuration/selection status 无 missing/extra。
- [x] 6.3 增加 AVX classification/assessment 人工对照，验证 source/build reachability、宏调用 actionable 状态、portability gap、blocking dimensions、项目 state 和静态范围声明一致。
- [x] 6.4 增加 diagnostics 回归，确认 74 个同类 unresolved-include 不再重复输出，同时聚合 count 和引用仍覆盖全部原始问题，其他 reason/severity 不被错误合并。
- [x] 6.5 运行 schema 1.0 contract、旧消费者、artifact lifecycle、default CLI、no-side-effect 和 deterministic output 回归，登记并解释所有预期修正。

## 7. 独立容器验收与 OpenSpec 完成

- [x] 7.1 在唯一 `kb-scanner-test` 容器中校验 unit-test inventory 完整性，确认每个新增/修改业务模块都有独立 suite 且未用 integration/component 测试代替。
- [x] 7.2 在独立测试容器中逐模块运行 unit suites 和 line/branch gate，确认每个模块至少 90% line / 80% branch。
- [x] 7.3 在独立测试容器中运行 AVX 字段级、build selection、projection、classification/assessment、schema consumer、artifact 和无副作用 component/contract tests。
- [x] 7.4 在独立测试容器中运行完整回归，确认没有执行 compiler/build/test/project command 或网络访问，并清理测试容器资源。
- [x] 7.5 复核两份 compiler facts、生产镜像、根 Compose、Legacy/YAML 生产边界和非 KB Scanner 用户修改均未变化。
- [x] 7.6 更新 README/基线说明，记录 schema 1.0 可选 trace 增强、诊断聚合、静态 proof 范围与 AVX approved corrections。
- [x] 7.7 运行 `openspec validate improve-kb-scanner-projection-and-reachability --strict`，修复 proposal/design/spec/tasks 一致性问题并确认 apply-ready。
