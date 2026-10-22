## ADDED Requirements

### Requirement: Unit test all degraded analysis owned code at ninety percent coverage

新增、修改或复用的编排、schema/引用验证、failure taxonomy、evidence availability、SourceCandidate、dependency slice、SynchronizationGap、P3/P4 adapter、cache、CLI、报告、双语诊断和质量逻辑 SHALL 有正常、边界、异常及 unknown/partial 的有效单元测试。项目整体、C++、Python和每个受影响自有模块的行覆盖率与分支覆盖率 MUST 均至少 90%，未加载源码、子目录和可执行头文件必须进入分母。

#### Scenario: Overall coverage passes but failure classification is untested

- **WHEN** 项目整体和语言覆盖达标，但任一 failure/cache/slice 模块行或分支低于 90%
- **THEN** 质量入口非零退出，相关任务不得完成或提示归档

#### Scenario: Integration fixtures cover an untested branch

- **WHEN** 四语言集成矩阵命中某错误路径但单元 profile 没有有效断言
- **THEN** 不得把集成覆盖合入单元门槛或排除该自有代码

### Requirement: Exercise C and C++ degradation semantics offline

单元及独立集成 SHALL 离线覆盖 C11、C17、C++17、C++20 的四种模式、失败分类、错误恢复 AST、source candidate 证明边界、candidate-relevant gap、无关 TU、预算、cache corruption、CLI 退出码和中英文字段。C fixture SHALL 独立覆盖 pthread、C linkage、struct/union、宏和 C atomic；测试不得访问网络/SSH、运行目标程序、DevKit 或外部后端。

#### Scenario: C tests are absent while C++ tests pass

- **WHEN** C++17/C++20 矩阵通过但 C11 或 C17 任一必需 profile 没有计划/完成 fixture 和断言
- **THEN** 语义验收失败，不能用 C++ 或合并覆盖率替代 C 结果

### Requirement: Publish repeatable degraded analysis acceptance

交付前 SHALL 在锁定开发容器和全新输出目录实际运行 OpenSpec/schema、全量单元、整体/语言/逐模块行分支覆盖率、四语言 truth、旧协议回归、mutex conservatism、归档样例筛选、cold/warm 确定性和文档门禁，并记录命令、版本/hash、测试数、hit/total、TP/FP/FN/abstention、性能、cache、排除理由及报告位置。任一必需门禁失败时任务 MUST 保持未完成。

#### Scenario: Unknown RAII remains a risk finding

- **WHEN** 最终回归仍将未建模 `std::lock_guard` 相关访问报告为确定 potential-data-race
- **THEN** 语义验收失败，即使单元覆盖率和其他 truth 指标达到门槛也不得归档
