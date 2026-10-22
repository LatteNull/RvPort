## ADDED Requirements

### Requirement: Unit test every A3 owned executable module at ninety percent coverage

A3 新增、修改或复用的 C++/Python worker、schema/引用验证、library profile、callable/binding、对象状态机、lifecycle graph、P3/A2 adapter、cache、CLI、报告、双语诊断和质量逻辑 SHALL 有正常、边界、异常及 unknown/partial 的有效单元测试。项目整体、C++、Python及每个受影响自有模块的行覆盖率和分支覆盖率 MUST 均至少 90%；未加载源码、子目录和可执行头文件必须进入分母，集成 profile 不得补入单元覆盖率。

#### Scenario: Overall coverage passes but the ownership state machine does not
- **WHEN** 项目和语言覆盖率达标而对象状态机任一行或分支指标低于 90%
- **THEN** 质量入口非零退出，任务不得完成、同步或归档

#### Scenario: Integration exercises an untested ABI rejection branch
- **WHEN** profile mismatch 集成用例通过但对应自有拒绝逻辑没有单元断言
- **THEN** 不得用集成命中补足单元门槛或排除该模块

### Requirement: Exercise A3 semantics and regressions entirely offline

独立集成 SHALL 在锁定开发容器离线运行 C11/C17 pthread 回归、C++17/C++20 生命周期 truth、至少一个 libstdc++ 与一个 libc++ 实测 profile、单/跨 TU、无 debug、开放 scope、异常、预算、缓存损坏、CLI 退出码和中英文字段；测试 MUST NOT 访问网络/SSH、运行目标程序、用户 CMake、ARM DevKit 或外部后端。

#### Scenario: A required standard-library profile cannot be validated
- **WHEN** libstdc++ 或 libc++ 任一 required profile 没有实际编译、提取和 truth 断言
- **THEN** A3 语义验收保持未完成，不以合成 schema fixture 或另一 vendor 替代

### Requirement: Publish repeatable A3 quality acceptance

交付前 SHALL 在全新输出目录实际运行 OpenSpec/schema、全量单元、整体/语言/逐受影响模块行分支覆盖率、四语言语义矩阵、旧 P1–A2/P4 回归、profile fingerprint、cold/warm 确定性、性能/预算和文档门禁，并记录命令、版本/hash、测试数、hit/total、truth 指标、缓存、排除理由和报告位置。任一 required gate 失败时任务 MUST 保持未完成。

#### Scenario: Lifecycle truth has one false relation
- **WHEN** 覆盖率全部达标但人工 truth 出现一个错误 callback、实例或 join/detach relation
- **THEN** 验收失败并增加针对性单元/集成回归，不能以 90% 覆盖率或零风险 finding 替代修复
