## ADDED Requirements

### Requirement: Unit test every A4 owned executable module at ninety percent coverage

A4 新增、修改或复用的 C++/Python worker、schema/引用验证、profile、binding、mutex/owner 状态机、wrapper 摘要、图组合、P3/A3/A2/P4 adapter、cache、CLI、报告、双语诊断和质量逻辑 SHALL 有正常、边界、异常及 unknown/partial 的有效单元测试。项目整体、C++、Python 和每个受影响自有模块的行覆盖率与分支覆盖率 MUST 均至少 90%；未加载源码、子目录和可执行头文件必须进入分母，集成覆盖不得补入单元覆盖率。

#### Scenario: Overall coverage passes but the owner state machine does not
- **WHEN** 项目和语言覆盖率达标而任一 A4 状态机模块行或分支低于 90%
- **THEN** 质量入口非零退出，任务不得完成、同步或归档

#### Scenario: Integration executes an untested exception branch
- **WHEN** RAII 异常清理集成用例通过但对应自有错误/cleanup 分支没有单元断言
- **THEN** 不得用集成命中补足单元门槛或排除该模块

### Requirement: Exercise A4 semantics and regressions entirely offline

独立集成 SHALL 在锁定开发容器离线运行 C11/C17 pthread mutex 回归、C++17/C++20 RAII truth、至少一个实际 libstdc++ 和一个实际 libc++ profile、单/跨 TU、全局/字段对象、move、异常、无 debug、开放 scope、profile/ABI 失配、预算、缓存损坏、CLI 退出码和中英文字段；测试 MUST NOT 访问网络/SSH、运行目标程序、用户 CMake、ARM DevKit 或外部后端。

#### Scenario: Archived safe sample still remains unknown with complete evidence
- **WHEN** `safe/03_pthread_mutex.cpp` 已满足声明的 A4 profile、对象、路径和线程证据而最终仍返回 unknown 或 risk
- **THEN** 语义验收失败并增加针对性单元/集成回归，不能以其他 truth 或覆盖率通过替代

#### Scenario: Unsupported mutex is accidentally discharged
- **WHEN** try/timed/recursive/robust 或未知自定义 mutex 用例产生正式互斥 proof/discharged
- **THEN** 语义验收失败，即使没有 FP 风险 finding 也不得归档

### Requirement: Publish repeatable A4 quality acceptance

交付前 SHALL 在全新输出目录实际运行 OpenSpec/schema、全量单元、项目整体/语言/逐受影响模块行分支覆盖率、四语言语义矩阵、P1–A3/P4 回归、profile probe、cold/warm 确定性、性能/内存/预算和文档门禁，并记录精确命令、版本/hash、测试数、hit/total、truth 指标、缓存、排除理由和报告位置。任一 required gate 失败时任务 MUST 保持未完成。

#### Scenario: A required gate is unavailable
- **WHEN** 任一实际 vendor profile、单元测试、覆盖率、语义 truth 或文档校验未执行、失败或环境阻塞
- **THEN** 验收记录真实状态且相关任务不勾选，不使用历史 A3 数据、DevKit 零建议或合成结果宣称完成
