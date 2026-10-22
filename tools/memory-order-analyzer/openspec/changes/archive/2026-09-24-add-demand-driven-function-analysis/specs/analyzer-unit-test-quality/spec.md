## ADDED Requirements

### Requirement: Unit test every R3 owned executable module at ninety percent coverage
所有新增、修改或复用的 R3 schema/引用校验、lazy module index、function-local identity、semantic/effect/thread shard、demand graph/worklist、SCC/递归、scheduler/batch、worker manifest、只读适配、失败/frontier、预算、缓存、CLI、报告、acceptance 及 C++ worker 逻辑 SHALL 有正常、边界、异常和 unknown/partial 路径的有效单元测试。项目整体、Python、C++及每个受影响自有模块的行覆盖率和工具支持的分支覆盖率 MUST 均至少 90%；未加载源码、子目录和可执行头文件 MUST 纳入分母，集成等价、编译冒烟、性能结果或历史覆盖率不得替代单元覆盖。

#### Scenario: Overall coverage passes but a scheduler module fails
- **WHEN** 项目整体和实现语言覆盖率达标，而任一受影响 R3 模块的行或分支覆盖率低于 90%
- **THEN** required quality gate 非零退出，任务保持未完成且不得提示同步或归档

#### Scenario: Failure paths lack effective assertions
- **WHEN** 正常 lazy 路径已覆盖，但 worker crash、timeout、损坏缓存、递归预算或 AST-only frontier 没有有效单元断言
- **THEN** R3 质量任务不得以集成 fixture 或 eager/lazy happy-path 通过为由完成

### Requirement: Validate R3 semantics and scale offline for all four language profiles
项目 SHALL 在本项目内维护可编译、人工标注且离线的 C11、C17、C++17、C++20 R3 fixtures，并分别报告 planned、completed、failed、eager/lazy exact、identity/effect/thread/R2 mismatch、frontier 和 abstention。验收 MUST 覆盖单 TU、跨 TU、no-debug、AST+IR、IR-only、AST-only、不可达函数、精确 demand 扩展、递归、失败隔离、cold/warm cache、固定稀疏可达规模和 TinyCThread；C profile不得依赖 C++模型。测试运行时 MUST NOT 读取兄弟归档目录、访问网络/SSH、运行专有工具、执行 configure/build/link 或被分析程序。

#### Scenario: Four language matrices are reported separately
- **WHEN** required semantic gate 完成
- **THEN** C11、C17、C++17、C++20 各自有独立分母、eager/lazy 等价结果、R2 truth 回归和 frontier 统计，任一语言缺口不得被合并统计掩盖

#### Scenario: Sparse scale metrics are collected
- **WHEN** 固定稀疏可达规模 fixture 运行 cold 和 warm R3 分析
- **THEN** acceptance 记录 indexed、demanded、scheduled、materialized、completed、partial、failed、cache-hit、module parse、CPU、wall、RSS 和输出大小，并区分确定性语义门禁与环境敏感性能观测

### Requirement: Publish repeatable R3 quality acceptance before synchronization
交付前 SHALL 在锁定的独立开发容器和全新输出目录实际运行全量单元测试、整体/语言/逐模块覆盖率门禁、eager/lazy 规范化等价、R2 四语言 truth、TinyCThread、不可达不物化、cold/warm cache、递归/失败/预算、稀疏规模以及文档/OpenSpec 严格校验。acceptance MUST 记录精确命令、环境/版本/hash、测试数、覆盖 hit/total、各语言分母、mismatch/frontier、资源指标、缓存一致性和报告路径；任一 required gate 失败时不得把 change 声明为实现完成、可同步或可归档。

#### Scenario: A required equivalence or coverage gate fails
- **WHEN** 任一单元测试、90% 行/分支门槛、eager/lazy 等价、R2/TinyCThread 回归、缓存确定性、不可达不物化或文档校验失败
- **THEN** acceptance 记录失败和差距，相关任务保持未完成且下一阶段命令只能是继续 apply/修复验证

#### Scenario: All required offline gates pass
- **WHEN** 全部 required gate 在记录环境中通过且 artifact、报告和文档一致
- **THEN** acceptance 可标记 R3 实施完成并具备后续同步条件，但不得把覆盖率、等价、资源下降、零 frontier 或零 finding 描述为并发安全证明
