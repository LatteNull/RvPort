## ADDED Requirements

### Requirement: Unit test every R2 owned executable module at ninety percent coverage
所有新增、修改或复用的 R2 schema/引用校验、effect projection、execution-instance binding、MHP normalization、object/range comparison、bucket/pair builder、protection overlay、frontier/completeness、budget、cache、CLI、报告、acceptance及 C++ worker逻辑 SHALL 有正常、边界、异常和 unknown/partial 路径的有效单元测试。项目整体、Python、C++及每个受影响自有模块的行覆盖率和工具支持的分支覆盖率 MUST 均至少 90%；未加载源码、子目录和可执行头文件 MUST 纳入分母，集成 truth、编译冒烟、归档样例或历史覆盖率不得替代单元覆盖。

#### Scenario: Overall coverage passes but one pairing module fails
- **WHEN** 项目整体和实现语言覆盖率达标而任一受影响 R2 模块的行或分支覆盖率低于 90%
- **THEN** required quality gate非零退出，任务保持未完成且不得提示同步或归档

#### Scenario: Unknown and budget branches lack assertions
- **WHEN** 正常候选路径被覆盖但对象 unknown、MHP unknown、cache损坏或预算耗尽分支没有有效单元断言
- **THEN** R2质量任务不得以集成 fixture通过为由完成

### Requirement: Validate R2 semantics offline for all four language profiles
项目 SHALL 在本项目内维护可编译、人工标注且离线的 C11、C17、C++17、C++20 R2 truth，分别报告 planned、completed、failed、expected/actual candidate pairs、protected、excluded、frontier、TP、FP、FN和abstention。truth MUST 覆盖单 TU、跨 TU、no-debug、AST+IR、IR-only、AST-only、字段/指针、同名字段不同对象、mutex内外、single/merged/repeated、开放 scope、预算和缓存；C profile不得依赖 C++模型。测试运行时 MUST NOT 读取兄弟归档目录、访问网络/SSH、运行专有工具或执行被分析程序。

#### Scenario: Four language matrices are reported separately
- **WHEN** required semantic gate完成
- **THEN** C11、C17、C++17、C++20 各自有独立分母和结果，任一语言的 FN、FP或abstention不得被合并统计掩盖

#### Scenario: An archived sample is reused
- **WHEN** 从 `memory-model-ir-checker/samples` 选择样例进入 R2 truth
- **THEN** 样例必须最小化复制到本项目、记录原路径/摘要/改写原因并人工重标 candidate/protected/excluded/frontier，旧 safe/unsafe 标签不得直接作为 oracle

### Requirement: Publish repeatable R2 quality acceptance before synchronization
交付前 SHALL 在锁定的独立开发容器和全新输出目录实际运行全量单元测试、整体/语言/逐模块覆盖率门禁、四语言 truth、既有 P1–P4/A1–A5/R1/R1.1 回归、cold/warm cache、预算/性能/内存及文档/OpenSpec严格校验。acceptance MUST 记录精确命令、环境/版本/hash、测试数、覆盖 hit/total、truth分母、TP/FP/FN/abstention、资源指标、缓存一致性和报告路径；任一 required gate失败时不得把 change声明为实现完成、可同步或可归档。

#### Scenario: A required truth or coverage gate fails
- **WHEN** 任一单元测试、90%行/分支门槛、四语言 truth、确定性缓存、旧协议回归或文档校验失败
- **THEN** acceptance记录失败和差距，相关任务保持未完成且下一阶段命令只能是继续 apply/修复验证

#### Scenario: All required offline gates pass
- **WHEN** 全部 required gate在记录环境中通过且 artifact/文档一致
- **THEN** acceptance可标记 R2实施完成并具备后续同步条件，但不得把覆盖率、exact match或零候选描述为安全证明
